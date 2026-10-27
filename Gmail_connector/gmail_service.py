
import asyncio
import random
import time

from dataclasses import dataclass
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from sqlalchemy import select

from DataBase_M.database import SessionLocal
from DataBase_M.tables import (
    GmailConnection,
    GmailSyncState,
    GmailNotification,
)

from RAG.notification_ingestion import (
    index_notification,
    make_storage_id,
)

from .gmail_auth import get_gmail_credentials

from Reminders.notification_generation import (
    generate_gmail_notifications,
)


# CONFIGURATION

@dataclass
class GmailSyncConfig:
    initial_query: str = "newer_than:90d"
    batch_size: int = 10
    max_concurrent_batches: int = 1
    max_retries: int = 5
    include_spam_trash: bool = False
    max_results: int = 500
    wait_seconds: int = 20


# GENERAL HELPERS

def utc_now():
    return datetime.now(timezone.utc)


def backoff_delay(attempt):
    base_delay = min(2 ** attempt, 60)
    return base_delay + random.uniform(0, 1)


# GOOGLE API HELPERS

def build_gmail_service(credentials):
    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )


def is_retryable_error(error):

    if not isinstance(error, HttpError):
        return False

    status = error.resp.status

    if status == 429 or status in (500, 502, 503, 504):
        return True

    if status == 403:

        try:
            content = error.content.decode("utf-8").lower()
        except Exception:
            content = str(error).lower()

        return (
            "ratelimitexceeded" in content
            or "userratelimitexceeded" in content
        )

    return False


def execute_with_retry(request, config):

    for attempt in range(config.max_retries + 1):

        try:
            return request.execute()

        except HttpError as error:

            if not is_retryable_error(error):
                raise

            if attempt >= config.max_retries:
                raise

            delay = backoff_delay(attempt)

            print(
                f"Gmail API rate/server limit. "
                f"Retrying in {delay:.1f} seconds..."
            )

            time.sleep(delay)


def get_gmail_profile(service, config):

    request = service.users().getProfile(userId="me")

    return execute_with_retry(request, config)


# FETCH MESSAGE IDS

def fetch_message_ids(service, config):

    message_ids = []
    page_token = None

    while True:

        kwargs = {
            "userId": "me",
            "maxResults": config.max_results,
            "includeSpamTrash": config.include_spam_trash,
        }

        if config.initial_query:
            kwargs["q"] = config.initial_query

        if page_token:
            kwargs["pageToken"] = page_token

        request = service.users().messages().list(**kwargs)

        response = execute_with_retry(request, config)

        message_ids.extend(
            item["id"]
            for item in response.get("messages", [])
            if item.get("id")
        )

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return list(dict.fromkeys(message_ids))


# EXTRACT EMAIL DATA

def extract_headers(message):

    headers = message.get("payload", {}).get("headers", [])

    return {
        header["name"].lower(): header["value"]
        for header in headers
        if header.get("name")
    }


def extract_message_data(message):

    headers = extract_headers(message)

    return {
        "gmail_message_id": message["id"],
        "thread_id": message.get("threadId"),
        "sender": headers.get("from"),
        "recipient": headers.get("to"),
        "cc": headers.get("cc"),
        "subject": headers.get("subject"),
        "date": headers.get("date"),
        "snippet": message.get("snippet"),
        "internal_date": message.get("internalDate"),
        "history_id": message.get("historyId"),
    }


# BATCH FETCHING


def fetch_message_batch_sync(
    credentials,
    message_ids,
    config,
):
    """
    Fetch Gmail messages using Gmail HTTP batching.

    Original messages are held temporarily in memory.
    They are never persisted by this function.
    """

    pending_ids = list(dict.fromkeys(message_ids))

    successful = {}
    deleted_ids = set()

    retry_counts = {
        message_id: 0
        for message_id in pending_ids
    }

    service = build_gmail_service(credentials)

    while pending_ids:

        batch_ids = pending_ids[:config.batch_size]
        pending_ids = pending_ids[config.batch_size:]

        results = {}
        failures = {}

        def callback(request_id, response, exception):

            if exception is not None:
                failures[request_id] = exception
            else:
                results[request_id] = response

        batch_executed = False

        for attempt in range(config.max_retries + 1):

            results.clear()
            failures.clear()

            batch = service.new_batch_http_request(
                callback=callback
            )

            for message_id in batch_ids:

                request = (
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=message_id,
                        format="full",
                    )
                )

                batch.add(
                    request,
                    request_id=message_id,
                )

            try:
                batch.execute()
                batch_executed = True
                break

            except HttpError as error:

                if not is_retryable_error(error):
                    raise

                if attempt >= config.max_retries:
                    raise

                delay = backoff_delay(attempt)

                print(
                    f"Batch request failed. "
                    f"Retrying in {delay:.1f} seconds..."
                )

                time.sleep(delay)

        if not batch_executed:
            raise RuntimeError("Gmail batch request failed.")

        # Keep successful responses temporarily in memory.
        for message_id, message in results.items():

            successful[message_id] = extract_message_data(
                message
            )

        # Handle failed individual requests.
        retry_ids = []

        for message_id, error in failures.items():

            if isinstance(error, HttpError):

                status = error.resp.status

                if status in (404, 410):
                    deleted_ids.add(message_id)
                    continue

                if is_retryable_error(error):

                    retry_counts[message_id] += 1

                    if retry_counts[message_id] > config.max_retries:
                        raise error

                    retry_ids.append(message_id)
                    continue

            raise error

        pending_ids.extend(retry_ids)

    return successful, deleted_ids


# FETCH FULL MESSAGES

async def fetch_full_messages(
    credentials,
    message_ids,
    config,
    save_progress,
):
    """
    Fetch Gmail messages in batches.

    Messages are passed directly to save_progress().
    Only generated notifications are persisted.
    """

    remaining_ids = list(dict.fromkeys(message_ids))

    print("Total IDs:", len(message_ids))
    print("Messages to fetch:", len(remaining_ids))

    batches = [
        remaining_ids[i:i + config.batch_size]
        for i in range(0, len(remaining_ids), config.batch_size)
    ]

    all_results = {}
    completed = 0

    semaphore = asyncio.Semaphore(
        config.max_concurrent_batches
    )

    async def process_batch(batch_ids):

        async with semaphore:

            return await asyncio.to_thread(
                fetch_message_batch_sync,
                credentials,
                batch_ids,
                config,
            )

    for start in range(
        0,
        len(batches),
        config.max_concurrent_batches,
    ):

        current_batches = batches[
            start:start + config.max_concurrent_batches
        ]

        batch_results = await asyncio.gather(
            *[
                process_batch(batch_ids)
                for batch_ids in current_batches
            ]
        )

        newly_fetched = []

        for results, deleted_ids in batch_results:

            all_results.update(results)

            newly_fetched.extend(results.values())

            completed += len(results) + len(deleted_ids)

        print(
            f"Processed {completed}/{len(remaining_ids)} "
            "Gmail messages"
        )

        # Generate and save reminders directly.
        if newly_fetched:

            await save_progress(newly_fetched)

            # Wait between batches, but not after the final batch.
            if start + config.max_concurrent_batches < len(batches):

                print(
                    f"Waiting {config.wait_seconds} seconds..."
                )

                await asyncio.sleep(config.wait_seconds)

    return list(all_results.values())


# POSTGRESQL: SAVE GENERATED GMAIL NOTIFICATIONS ONLY

async def save_gmail_notifications_postgres(
    user_id,
    notifications,
):

    if not notifications:
        print("No Gmail notifications generated.")
        return 0

    records_to_index = []

    async with SessionLocal() as db:

        async with db.begin():

            for notification in notifications:

                reminder_text = notification["text"]

                source = notification["source"].lower()

                origin = notification["senders_email_id"]

                storage_id = make_storage_id(
                    user_id=user_id,
                    source=source,
                    date=notification["date"],
                    origin=origin,
                    reminder_text=reminder_text,
                )

                existing = await db.scalar(
                    select(GmailNotification).where(
                        GmailNotification.storage_id == storage_id
                    )
                )

                if existing:

                    row = existing

                else:

                    row = GmailNotification(
                        storage_id=storage_id,
                        user_id=user_id,
                        source=source,
                        my_email_id=notification["my_email_id"],
                        senders_email_id=notification["senders_email_id"],
                        date=notification["date"],
                        category=notification["category"],
                        status=notification.get(
                            "status",
                            "not_completed",
                        ),
                        text=reminder_text,
                    )

                    db.add(row)

                    await db.flush()

                records_to_index.append({
                    "storage_id": row.storage_id,
                    "user_id": row.user_id,
                    "reminder_text": row.text,
                    "source": row.source,
                    "date": row.date,
                    "category": row.category,
                    "status": row.status,
                    "origin": row.senders_email_id,
                })

    # Index reminders only after PostgreSQL commits.

    for item in records_to_index:

        await index_notification(
            storage_id=item["storage_id"],
            user_id=item["user_id"],
            reminder_text=item["reminder_text"],
            source=item["source"],
            date=item["date"],
            category=item["category"],
            status=item["status"],
            origin=item["origin"],
        )

    print(
        f"Gmail notifications processed: "
        f"{len(records_to_index)}"
    )

    return len(records_to_index)


# DATABASE CHECKPOINT

async def get_connection_state(
    user_id,
    connection_id,
):

    async with SessionLocal() as db:

        connection = await db.scalar(
            select(GmailConnection).where(
                GmailConnection.id == connection_id,
                GmailConnection.user_id == user_id,
                GmailConnection.is_active.is_(True),
            )
        )

        if not connection:
            raise ValueError("Gmail connection not found.")

        sync_state = await db.scalar(
            select(GmailSyncState).where(
                GmailSyncState.connection_id == connection_id
            )
        )

        if not sync_state or not sync_state.history_id:
            return None

        return str(sync_state.history_id)


async def update_history_checkpoint(
    connection_id,
    history_id,
):

    if not history_id:
        raise ValueError(
            "Cannot save an empty history checkpoint."
        )

    async with SessionLocal() as db:

        async with db.begin():

            sync_state = await db.scalar(
                select(GmailSyncState)
                .where(
                    GmailSyncState.connection_id == connection_id
                )
                .with_for_update()
            )

            if not sync_state:

                sync_state = GmailSyncState(
                    connection_id=connection_id,
                    history_id=str(history_id),
                    last_synced_at=utc_now(),
                )

                db.add(sync_state)

            else:

                sync_state.history_id = str(history_id)
                sync_state.last_synced_at = utc_now()


# GMAIL HISTORY

def fetch_history(
    service,
    start_history_id,
    config,
):

    message_ids = set()
    page_token = None
    latest_history_id = None

    while True:

        kwargs = {
            "userId": "me",
            "startHistoryId": str(start_history_id),
            "historyTypes": ["messageAdded"],
        }

        if page_token:
            kwargs["pageToken"] = page_token

        request = service.users().history().list(**kwargs)

        response = execute_with_retry(request, config)

        if response.get("historyId"):
            latest_history_id = str(response["historyId"])

        for record in response.get("history", []):

            for added in record.get("messagesAdded", []):

                message_id = (
                    added.get("message", {}).get("id")
                )

                if message_id:
                    message_ids.add(message_id)

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return list(message_ids), latest_history_id


# INITIAL GMAIL SYNC

async def initial_gmail_sync(
    credentials,
    save_progress,
    config,
):
    """
    Initial sync:

    1. Capture history baseline.
    2. List emails matching initial_query.
    3. Fetch messages added during listing.
    4. Generate and save reminders.
    5. Return the new history checkpoint.

    Original emails are never persisted.
    """

    service = await asyncio.to_thread(
        build_gmail_service,
        credentials,
    )

    latest_history_id = None
    baseline = None
    message_ids = []

    for attempt in range(2):

        profile = await asyncio.to_thread(
            get_gmail_profile,
            service,
            config,
        )

        baseline = str(profile["historyId"])

        print("Initial history baseline:", baseline)
        print("Initial query:", config.initial_query)

        message_ids = await asyncio.to_thread(
            fetch_message_ids,
            service,
            config,
        )

        print("Message IDs found:", len(message_ids))

        try:

            arrived_ids, latest_history_id = (
                await asyncio.to_thread(
                    fetch_history,
                    service,
                    baseline,
                    config,
                )
            )

            message_ids = list(
                dict.fromkeys(message_ids + arrived_ids)
            )

            print(
                "Messages arriving during listing:",
                len(arrived_ids),
            )

            break

        except HttpError as error:

            if error.resp.status != 404 or attempt == 1:
                raise

            print(
                "History baseline expired. "
                "Retrying initial sync."
            )

    messages = await fetch_full_messages(
        credentials=credentials,
        message_ids=message_ids,
        config=config,
        save_progress=save_progress,
    )

    checkpoint = str(latest_history_id or baseline)

    return {
        "messages": messages,
        "history_id": checkpoint,
        "sync_type": "initial",
        "total_ids": len(message_ids),
    }


# INCREMENTAL GMAIL SYNC

async def incremental_gmail_sync(
    credentials,
    last_history_id,
    save_progress,
    config,
):
    """
    Incremental sync:

    1. Use the previous history checkpoint.
    2. Fetch newly added message IDs.
    3. Generate and save reminders.
    4. Return the new history checkpoint.

    Original emails are never persisted.
    """

    if not last_history_id:

        return await initial_gmail_sync(
            credentials=credentials,
            save_progress=save_progress,
            config=config,
        )

    service = await asyncio.to_thread(
        build_gmail_service,
        credentials,
    )

    try:

        message_ids, new_history_id = await asyncio.to_thread(
            fetch_history,
            service,
            last_history_id,
            config,
        )

    except HttpError as error:

        if error.resp.status != 404:
            raise

        print(
            "History checkpoint expired. "
            "Starting a new initial sync."
        )

        return await initial_gmail_sync(
            credentials=credentials,
            save_progress=save_progress,
            config=config,
        )

    if not new_history_id:

        profile = await asyncio.to_thread(
            get_gmail_profile,
            service,
            config,
        )

        new_history_id = str(profile["historyId"])

    print("New message IDs:", len(message_ids))

    messages = await fetch_full_messages(
        credentials=credentials,
        message_ids=message_ids,
        config=config,
        save_progress=save_progress,
    )

    return {
        "messages": messages,
        "history_id": str(new_history_id),
        "sync_type": "incremental",
        "total_ids": len(message_ids),
    }


# PARENT FUNCTION - COMPLETE GMAIL SYNC

async def sync_gmail(
    user_id,
    connection_id,
    initial_query="newer_than:90d",
    batch_size=10,
    max_concurrent_batches=1,
    max_retries=5,
    include_spam_trash=False,
    max_results=500,
    wait_seconds=20,
):
    """
    Main Gmail sync function.

    Original Gmail messages:
        Temporary memory only.

    Generated notifications:
        PostgreSQL (gmail_notifications).

    Sync checkpoint:
        PostgreSQL (gmail_sync_states).
    """

    # STEP 1: CREATE CONFIGURATION

    config = GmailSyncConfig(
        initial_query=initial_query,
        batch_size=batch_size,
        max_concurrent_batches=max_concurrent_batches,
        max_retries=max_retries,
        include_spam_trash=include_spam_trash,
        max_results=max_results,
        wait_seconds=wait_seconds,
    )

    # STEP 2: VALIDATE CONFIGURATION

    if (
        not isinstance(config.batch_size, int)
        or not 1 <= config.batch_size <= 100
    ):
        raise ValueError(
            "batch_size must be between 1 and 100"
        )

    if (
        not isinstance(config.max_concurrent_batches, int)
        or config.max_concurrent_batches < 1
    ):
        raise ValueError(
            "max_concurrent_batches must be at least 1"
        )

    if (
        not isinstance(config.max_retries, int)
        or config.max_retries < 0
    ):
        raise ValueError(
            "max_retries cannot be negative"
        )

    if (
        not isinstance(config.max_results, int)
        or not 1 <= config.max_results <= 500
    ):
        raise ValueError(
            "max_results must be between 1 and 500"
        )

    if config.wait_seconds < 0:
        raise ValueError(
            "wait_seconds cannot be negative"
        )

    # STEP 3: GET CREDENTIALS AND VALIDATE CONNECTION

    credentials = await get_gmail_credentials(
        user_id,
        connection_id,
    )

    last_history_id = await get_connection_state(
        user_id,
        connection_id,
    )

    print("\n========== GMAIL SYNC ==========")
    print("Storage: notifications only")
    print("Batch size:", config.batch_size)
    print("Concurrent batches:", config.max_concurrent_batches)
    print("Max retries:", config.max_retries)
    print("Initial query:", config.initial_query)

    # STEP 4: DEFINE SAVE PROGRESS CALLBACK

    async def save_progress(messages):

        # Original messages exist only in memory.
        # Generate reminders directly from fetched messages.

        notifications = await asyncio.to_thread(
            generate_gmail_notifications,
            messages,
        )

        print(
            f"Generated {len(notifications)} Gmail notifications."
        )

        # Persist only generated reminders.
        await save_gmail_notifications_postgres(
            user_id=user_id,
            notifications=notifications,
        )

        print("Gmail reminders saved in PostgreSQL.")

    # STEP 5: RUN INITIAL OR INCREMENTAL SYNC

    if last_history_id:

        print("Sync mode: INCREMENTAL")

        result = await incremental_gmail_sync(
            credentials=credentials,
            last_history_id=last_history_id,
            save_progress=save_progress,
            config=config,
        )

    else:

        print("Sync mode: INITIAL")

        result = await initial_gmail_sync(
            credentials=credentials,
            save_progress=save_progress,
            config=config,
        )

    # STEP 6: UPDATE CHECKPOINT AFTER PROCESSING

    await update_history_checkpoint(
        connection_id=connection_id,
        history_id=result["history_id"],
    )

    # STEP 7: RETURN SUMMARY

    summary = {
        "status": "success",
        "sync_type": result["sync_type"],
        "storage": "notifications_only",
        "new_messages_fetched": len(result["messages"]),
        "total_ids_found": result["total_ids"],
        "total_notifications_saved": None,
        "history_id": result["history_id"],
    }

    print("\n========== SYNC COMPLETED ==========")
    print("Sync type:", summary["sync_type"])
    print(
        "New messages fetched:",
        summary["new_messages_fetched"],
    )
    print(
        "Total IDs found:",
        summary["total_ids_found"],
    )

    return summary
