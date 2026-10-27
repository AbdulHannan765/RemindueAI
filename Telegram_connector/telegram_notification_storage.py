import uuid
import logging

from sqlalchemy import select

from DataBase_M.database import SessionLocal
from DataBase_M.tables import TelegramNotification

from RAG.notification_ingestion import index_notification

logger = logging.getLogger(__name__)


def make_storage_id(
    user_id,
    source,
    date,
    origin,
    reminder_text,
):
    """
    Produce a deterministic UUID.

    If the same notification is processed again during
    a retry, it receives the same Qdrant point ID.
    """

    identity = "|".join([
        str(user_id),
        source.lower(),
        str(date),
        str(origin or ""),
        reminder_text.strip(),
    ])

    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        identity,
    )


async def save_telegram_notifications(
    notifications,
    user_id,
):

    if not notifications:
        print("No Telegram notifications to save.")
        return 0

    records_to_index = []

    async with SessionLocal() as db:

        async with db.begin():

            for notification in notifications:

                reminder_text = notification["reminder"]

                source = notification["source"].lower()

                chat_name = notification["chat_name"]

                storage_id = make_storage_id(
                    user_id=user_id,
                    source=source,
                    date=notification["date"],
                    origin=chat_name,
                    reminder_text=reminder_text,
                )

                existing = await db.scalar(
                    select(TelegramNotification).where(
                        TelegramNotification.storage_id == storage_id
                    )
                )

                if existing:

                    row = existing

                else:

                    row = TelegramNotification(
                        storage_id=storage_id,
                        user_id=user_id,
                        source=source,
                        date=notification["date"],
                        chat_name=chat_name,
                        category=notification["category"],
                        status=notification.get(
                            "status",
                            "not_completed",
                        ),
                        reminder=reminder_text,
                    )

                    db.add(row)

                    await db.flush()

                records_to_index.append({
                    "storage_id": row.storage_id,
                    "user_id": row.user_id,
                    "reminder_text": row.reminder,
                    "source": row.source,
                    "date": row.date,
                    "chat_name": row.chat_name,
                    "category": row.category,
                    "status": row.status,
                })

    # PostgreSQL transaction has committed here.
    # Only index records that have successfully been saved.

    for item in records_to_index:

        await index_notification(
            storage_id=item["storage_id"],
            user_id=item["user_id"],
            reminder_text=item["reminder_text"],
            source=item["source"],
            date=item["date"],
            category=item["category"],
            status=item["status"],
            chat_name=item["chat_name"],
        )

    print(
        f"Telegram notifications processed: "
        f"{len(records_to_index)}"
    )

    return len(records_to_index)