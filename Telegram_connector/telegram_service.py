
import asyncio
import json
import os
import tempfile

from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

from sqlalchemy import select

from Reminders.notification_generation import generate_telegram_notifications
from DataBase_M.config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    decrypt_session,

)

from chunking.chunks_creation import Telegram_chunking

from DataBase_M.database import SessionLocal
from Telegram_connector.telegram_notification_storage import save_telegram_notifications
from DataBase_M.tables import (
    TelegramConnection,
    TelegramChatSync,

)
from RAG.notification_ingestion import (
    index_notification,
    make_storage_id,
)
from chunking.text_format_chunking import convert_telegram_chunks_to_text





def utc_now():
    return datetime.now(timezone.utc)








async def create_telegram_client(connection):


    # Step 1: Decrypt the encrypted session
    decrypted_session = decrypt_session(
        connection.session_encrypted
    )

    # Step 2: Convert bytes into string
    session_string = decrypted_session.decode("utf-8")

    # Step 3: Validate the session
    if not session_string:
        raise ValueError("Decrypted Telegram session is empty.")

    # Step 4: Create Telethon client
    client = TelegramClient(
        StringSession(session_string),
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
    )

    # Step 5: Connect
    await client.connect()

    # Step 6: Verify authentication
    if not await client.is_user_authorized():
        await client.disconnect()

        raise ValueError(
            f"Telegram session expired for {connection.phone_number}. "
            "Please reconnect the account."
        )

    return client



# FOR  CHAT CHECKPOINTS


async def get_chat_checkpoints(connection_id):
    """
    Returns the last synced message ID for every chat
    belonging to this Telegram connection.

    Result:
    {
        chat_id: last_message_id
    }
    """

    async with SessionLocal() as db:

        result = await db.execute(
            select(
                TelegramChatSync.chat_id,
                TelegramChatSync.last_message_id,
            ).where(
                TelegramChatSync.connection_id == connection_id
            )
        )

        return {
            int(chat_id): int(last_message_id or 0)
            for chat_id, last_message_id in result.all()
        }


# UPDATE CHAT CHECKPOINT

async def update_chat_checkpoint(
    connection_id,
    chat_id,
    last_message_id,
):
    """
    Creates or updates the checkpoint for one chat.
    """

    async with SessionLocal() as db:

        result = await db.scalar(
            select(TelegramChatSync).where(
                TelegramChatSync.connection_id == connection_id,
                TelegramChatSync.chat_id == chat_id,
            )
        )

        if result:

            result.last_message_id = last_message_id
            result.last_synced_at = utc_now()

        else:

            result = TelegramChatSync(
                connection_id=connection_id,
                chat_id=chat_id,
                last_message_id=last_message_id,
                last_synced_at=utc_now(),
            )

            db.add(result)

        await db.commit()


# EXTRACT MESSAGE DATA

def extract_message_data(message, chat_id, chat_title):
    """
    Converts a Telethon message into a JSON-serializable dictionary.
    """

    return {
        "chat_id": int(chat_id),
        "chat_title": chat_title,
        "message_id": int(message.id),
        "sender_id": (
            int(message.sender_id)
            if message.sender_id is not None
            else None
        ),
        "text": message.message or "",
        "date": (
            message.date.isoformat()
            if message.date
            else None
        ),
        "reply_to_message_id": (
            message.reply_to.reply_to_msg_id
            if message.reply_to
            else None
        ),
        "has_media": message.media is not None,
        "views": message.views,
        "forwards": message.forwards,
    }


# FETCH CHATS

async def fetch_telegram_chats(client):
    """
    Fetches all accessible Telegram dialogs.

    Returns a list of chat dictionaries.
    """

    chats = []

    async for dialog in client.iter_dialogs():

        entity = dialog.entity

        if not hasattr(entity, "id"):
            continue

        chats.append({
            "chat_id": int(entity.id),
            "chat_title": dialog.name or "Unknown",
            "entity": entity,
        })

    return chats


# FETCH MESSAGES FROM ONE CHAT

async def fetch_chat_messages(
    client,
    chat,
    INITIAL_MESSAGES_PER_CHAT,
    last_message_id=0,
    initial_sync=False,
    

    
):
    
    


    messages = []

    if initial_sync:

        message_iterator = client.iter_messages(
            chat["entity"],
            limit=INITIAL_MESSAGES_PER_CHAT,
        )

    else:

        message_iterator = client.iter_messages(
            chat["entity"],
            min_id=last_message_id,
            reverse=True,
        )

    async for message in message_iterator:

        if message.id is None:
            continue

        messages.append(
            extract_message_data(
                message=message,
                chat_id=chat["chat_id"],
                chat_title=chat["chat_title"],
            )
        )

    return messages


# json storage is only for testing

# def load_telegram_json(json_path):
#     """
#     Loads previously synced messages from JSON.
#     """

#     json_path = Path(json_path)

#     if not json_path.exists():
#         return []

#     with open(json_path, "r", encoding="utf-8") as file:
#         data = json.load(file)

#     if not isinstance(data, list):
#         raise ValueError(
#             f"Expected a JSON list in {json_path}"
#         )

#     return data


# def save_telegram_json(json_path, messages,overlap_size,chunk_size):
#     """
#     Merges messages using (chat_id, message_id) as the unique key.
#     Writes atomically to avoid leaving a partially written file.
#     """

#     json_path = Path(json_path)
#     json_path.parent.mkdir(parents=True, exist_ok=True)

#     existing_messages = load_telegram_json(json_path)

#     merged = {
#         (int(message["chat_id"]), int(message["message_id"])): message
#         for message in existing_messages
#     }

#     for message in messages:

#         key = (
#             int(message["chat_id"]),
#             int(message["message_id"]),
#         )

#         merged[key] = message

#     final_messages = sorted(
#         merged.values(),
#         key=lambda item: (
#             int(item["chat_id"]),
#             int(item["message_id"]),
#         ),
#     )

#     temp_path = None
#     final_chunks=Telegram_chunking(final_messages,overlap_size=overlap_size,chunk_size=chunk_size)
#     final_text_chunks=convert_telegram_chunks_to_text(final_chunks)
#     final_reminders=generate_telegram_notifications(final_text_chunks)

#     try:

#         with tempfile.NamedTemporaryFile(
#             mode="w",
#             encoding="utf-8",
#             suffix=".tmp",
#             dir=json_path.parent,
#             delete=False,
#         ) as file:

#             temp_path = file.name

#             json.dump(
#                 final_reminders,
#                 file,
#                 indent=4,
#                 ensure_ascii=False,
#             )

#         os.replace(temp_path, json_path)

#     finally:

#         if temp_path and os.path.exists(temp_path):
#             os.remove(temp_path)

#     return len(final_messages)




async def process_telegram_messages(
    messages,
    user_id,
    connection_id,
    overlap_size,
    chunk_size,
    noti_batch_size
):
    """
    1. Creates chunks from fetched Telegram messages.
    2. Converts chunks into text format.
    3. Generates notifications using the LLM.
    4. Stores notifications in PostgreSQL.
    """

    if not messages:
        print("No new Telegram messages to process.")
        return 0

    # STEP 1: CREATE CHUNKS

    chunks = Telegram_chunking(
        messages,
        overlap_size=overlap_size,
        chunk_size=chunk_size
    )

    text_chunks = convert_telegram_chunks_to_text(chunks)

    # STEP 2: GENERATE NOTIFICATIONS

    notifications = generate_telegram_notifications(text_chunks,noti_batch_size=noti_batch_size)

    # STEP 3: STORE IN POSTGRESQL

    saved_count = await save_telegram_notifications(
        user_id=user_id,
        notifications=notifications
    )

    return saved_count

#only for testing
# async def json_sync_telegram(
#     user_id,
#     connection_id,
#     json_path,
#     INITIAL_MESSAGES_PER_CHAT,
#     overlap_size,
#     chunk_size,
  
# ):
#     """
#     Synchronizes all chats for one Telegram connection.

#     Initial sync:
#         Fetches latest 100 messages per chat.

#     Incremental sync:
#         Fetches messages newer than each chat's checkpoint.

#     Messages are saved in JSON.
#     Checkpoints are stored in PostgreSQL.

#     Checkpoints are updated only after JSON storage succeeds.
#     """

#     async with SessionLocal() as db:

#         connection = await db.scalar(
#             select(TelegramConnection).where(
#                 TelegramConnection.id == connection_id,
#                 TelegramConnection.user_id == user_id,
#                 TelegramConnection.is_active.is_(True),
#             )
#         )

#     if not connection:
#         raise ValueError(
#             "Active Telegram connection not found for this user."
#         )

#     client = await create_telegram_client(connection)

#     try:

#         chats = await fetch_telegram_chats(client)

#         checkpoints = await get_chat_checkpoints(
#             connection_id
#         )

#         all_new_messages = []
#         checkpoint_updates = []

#         initial_chat_count = 0
#         incremental_chat_count = 0

#         for chat in chats:

#             chat_id = chat["chat_id"]

#             is_initial_sync = chat_id not in checkpoints

#             last_message_id = checkpoints.get(
#                 chat_id,
#                 0,
#             )

#             if is_initial_sync:
#                 initial_chat_count += 1
#             else:
#                 incremental_chat_count += 1
            


#             new_messages = await fetch_chat_messages(
#                 INITIAL_MESSAGES_PER_CHAT=INITIAL_MESSAGES_PER_CHAT,
#                 client=client,
#                 chat=chat,
#                 last_message_id=last_message_id,
#                 initial_sync=is_initial_sync,
#             )

#             if not new_messages:
#                 continue

#             all_new_messages.extend(new_messages)

#             highest_message_id = max(
#                 message["message_id"]
#                 for message in new_messages
#             )

#             checkpoint_updates.append({
#                 "chat_id": chat_id,
#                 "last_message_id": highest_message_id,
#             })

#         # Save all fetched messages before advancing checkpoints.
#         total_messages_saved = save_telegram_json(
#             json_path=json_path,
#             messages=all_new_messages,
#             overlap_size=overlap_size,
#             chunk_size=chunk_size,
#         )

#         # Only advance checkpoints after successful JSON persistence.
#         for update in checkpoint_updates:

#             await update_chat_checkpoint(
#                 connection_id=connection_id,
#                 chat_id=update["chat_id"],
#                 last_message_id=update["last_message_id"],
#             )

#         return {
#             "status": "success",
#             "connection_id": str(connection_id),
#             "phone_number": connection.phone_number,
#             "total_chats_found": len(chats),
#             "initial_chats": initial_chat_count,
#             "incremental_chats": incremental_chat_count,
#             "new_messages_fetched": len(all_new_messages),
#             "total_messages_saved": total_messages_saved,
#             "json_path": str(json_path),
#         }

#     finally:

#         await client.disconnect()



async def sync_telegram(
    user_id,
    connection_id,
    INITIAL_MESSAGES_PER_CHAT,
    overlap_size,
    chunk_size,
    noti_batch_size,
):
    """
    Synchronizes all chats for one Telegram connection.

    Initial sync:
        Fetches the latest messages per chat.

    Incremental sync:
        Fetches messages newer than each chat's checkpoint.

    Notifications:
        Generated and stored directly in PostgreSQL.

    Checkpoints:
        Updated only after notification storage succeeds.
    """

    # STEP 1: VALIDATE TELEGRAM CONNECTION

    async with SessionLocal() as db:

        connection = await db.scalar(
            select(TelegramConnection).where(
                TelegramConnection.id == connection_id,
                TelegramConnection.user_id == user_id,
                TelegramConnection.is_active.is_(True),
            )
        )

    if not connection:
        raise ValueError(
            "Active Telegram connection not found for this user."
        )

    client = await create_telegram_client(connection)

    try:

        # STEP 2: FETCH TELEGRAM CHATS

        chats = await fetch_telegram_chats(client)

        checkpoints = await get_chat_checkpoints(
            connection_id
        )

        all_new_messages = []
        checkpoint_updates = []

        initial_chat_count = 0
        incremental_chat_count = 0

        # STEP 3: FETCH NEW MESSAGES

        for chat in chats:

            chat_id = chat["chat_id"]

            is_initial_sync = chat_id not in checkpoints

            last_message_id = checkpoints.get(
                chat_id,
                0,
            )

            if is_initial_sync:
                initial_chat_count += 1
            else:
                incremental_chat_count += 1

            new_messages = await fetch_chat_messages(
                INITIAL_MESSAGES_PER_CHAT=INITIAL_MESSAGES_PER_CHAT,
                client=client,
                chat=chat,
                last_message_id=last_message_id,
                initial_sync=is_initial_sync,
            )

            if not new_messages:
                continue

            all_new_messages.extend(new_messages)

            highest_message_id = max(
                message["message_id"]
                for message in new_messages
            )

            checkpoint_updates.append({
                "chat_id": chat_id,
                "last_message_id": highest_message_id,
            })

        print(
            f"\nTotal new Telegram messages fetched: "
            f"{len(all_new_messages)}"
        )

        # STEP 4: PROCESS AND STORE NOTIFICATIONS

        if all_new_messages:

            saved_notifications = await process_telegram_messages(
                messages=all_new_messages,
                user_id=user_id,
                connection_id=connection_id,
                overlap_size=overlap_size,
                chunk_size=chunk_size,
                noti_batch_size=noti_batch_size
            )

            # Verify successful database storage.
            if saved_notifications is None or saved_notifications <= 0:

                raise RuntimeError(
                    "Telegram notifications were not saved successfully. "
                    "Checkpoints will not be updated."
                )

            print(
                f"\nSuccessfully saved "
                f"{saved_notifications} Telegram notifications."
            )

        else:

            saved_notifications = 0

            print(
                "\nNo new Telegram messages found. "
                "No notification processing required."
            )

        # STEP 5: UPDATE CHECKPOINTS

        if all_new_messages:

            for update in checkpoint_updates:

                await update_chat_checkpoint(
                    connection_id=connection_id,
                    chat_id=update["chat_id"],
                    last_message_id=update["last_message_id"],
                )

            print(
                "\nTelegram checkpoints updated successfully."
            )

        # STEP 6: RETURN SYNC SUMMARY

        return {
            "status": "success",
            "connection_id": str(connection_id),
            "phone_number": connection.phone_number,
            "total_chats_found": len(chats),
            "initial_chats": initial_chat_count,
            "incremental_chats": incremental_chat_count,
            "new_messages_fetched": len(all_new_messages),
            "notifications_saved": saved_notifications,
            "checkpoints_updated": len(checkpoint_updates),
        }

    except Exception as error:

        print(
            "\nTelegram synchronization failed: "
            f"{type(error).__name__}: {error}"
        )

        raise

    finally:

        await client.disconnect()
