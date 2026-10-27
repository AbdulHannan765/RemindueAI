def convert_telegram_chunks_to_text(chunks):

    converted_chunks = []

    for chunk in chunks:

        chat_title = chunk["chat_title"]
        messages = chunk["messages"]

        chunk_date = messages[0].get("date", "") if messages else ""

        formatted_text = f"Telegram chat name = {chat_title}\n"

        for message in messages:

            sender_id = message.get("sender_id")
            chat_id = message.get("chat_id")

            if sender_id == chat_id:
                sender_name = chat_title
            else:
                sender_name = "Me"

            message_text = message.get("text", "")
            message_date = message.get("date", "")

            formatted_text += (
                f"{sender_name}: {message_text} "
                f"[messaged on {message_date}]\n"
            )

        converted_chunks.append({
            "source": "Telegram",
            "date": chunk_date,
            "chat_name": chat_title,
            "text": formatted_text.strip()
        })

    return converted_chunks

import re


def convert_gmail_emails_to_text(emails):

    converted_emails = []

    for email in emails:

        sender = email.get("sender", "")

        sender_match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', sender)

        sender_email = (
            sender_match.group(0)
            if sender_match
            else sender
        )

        recipient = email.get("recipient", "")

        recipient_match = re.search(
            r'[\w.+-]+@[\w.-]+\.\w+',
            recipient
        )

        recipient_email = (
            recipient_match.group(0)
            if recipient_match
            else recipient
        )

        date = email.get("date", "")
        subject = email.get("subject", "")
        actual_email = email.get("snippet", "")

        text = f"""
sender = {email.get("sender", "")}
my email id = {recipient_email}
date = {date}
subject = {subject}

actual email = {actual_email}
""".strip()

        converted_emails.append({

            "source": "GMAIL",

            "my_email_id": recipient_email,

            "senders_email_id": sender_email,

            "date": date,

            "text": text
        })

    return converted_emails
