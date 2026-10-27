
import os
import re
import logging

from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from .JEV_chunk_classification import categorize
from chunking.text_format_chunking import convert_gmail_emails_to_text
from security_and_privacy.pii_middleware import PIISanitizer


logger = logging.getLogger(__name__)

load_dotenv(override=True)



GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is missing. Check your .env file."
    )

GROQ_API_KEY = GROQ_API_KEY.strip()

MODEL_NAME = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)






def llm_invoke(batch, current_datetime):
    llm = ChatGroq(
        model=MODEL_NAME,
        groq_api_key=GROQ_API_KEY,
        temperature=0,
        max_tokens=4096,
    )

    """
    Receives a batch of conversation texts.

    Sanitizes PII before sending conversations to Groq.

    Extracts actionable reminders using LangChain + Groq.

    Restores original PII in generated reminders.

    Returns:
    [
        {
            "chunk_index": 1,
            "reminder": "Reminder text"
        }
    ]
    """

    if not batch:
        return []

    # STEP 1: INITIALIZING PII MIDDLEWARE

    pii = PIISanitizer()

    # Sanitizing every conversation chunk.
    safe_batch = [
        pii.sanitize(text)
        for text in batch
    ]

    logger.info(
        "PII sanitization completed for %s chunks",
        len(safe_batch)
    )

    # STEP 2: PREPARE SANITIZED CHUNK INPUT

    batch_text = "\n\n".join(
        f"[CHUNK {index}]\n{text}"
        for index, text in enumerate(safe_batch, start=1)
    )

    # STEP 3: SYSTEM PROMPT

    system_prompt = f"""
You are an intelligent reminder extraction assistant.

Your responsibility is to extract actionable reminders
from conversations and understand their date and time context.

CURRENT DATE AND TIME:
{current_datetime}

TIMEZONE:
Asia/Kolkata (Indian Standard Time).

--------------------------------------------------
PII PLACEHOLDER RULES
--------------------------------------------------

The input may contain anonymized placeholders such as:

[PERSON_1]
[EMAIL_ADDRESS_1]
[PHONE_NUMBER_1]
[LOCATION_1]

These placeholders represent original personal information.

1. Preserve every placeholder exactly as provided.
2. Never modify, remove, rename or invent placeholders.
3. Use placeholders naturally when generating reminders.
4. Do not attempt to guess the original personal information.

--------------------------------------------------
REMINDER EXTRACTION RULES
--------------------------------------------------

1. Identify actual actionable tasks, deadlines,
   commitments and events.

2. Extract only meaningful reminders.

3. Do not create reminders from ordinary conversations,
   greetings, jokes, general information or casual discussions.

4. Ignore login codes, OTPs, advertisements, promotional
   messages, spam and irrelevant messages.

5. Avoid duplicate reminders within the same chunk.

6. A single chunk can contain multiple reminders.
   Extract each meaningful reminder separately.

7. IMPORTANT NOTE: If a chunk does not contain enough
   information, like any of this: who, where, what,
   to create a meaningful reminder, skip it.

   Example:
   Internshala indicated that applications close tomorrow
   (18 October 2026); please confirm whether you completed
   the required application.

   Here it is not mentioned which application.
   This information is not enough. Analyze every chunk
   and decide whether the given information is sufficient
   for a reminder. If not, skip it.

8. For emails, consider the sender, recipient, subject
   and actual email content when extracting reminders.

--------------------------------------------------
DATE AND TIME REASONING
--------------------------------------------------

1. Use dates and time references available in the conversation.

2. Compare clearly identifiable deadlines with the current
   date and time provided above when appropriate.

3. If a deadline is in the future, clearly mention
   the deadline in the reminder.

4. If a deadline is today, clearly indicate that
   the task is due today.

5. If a deadline has already passed, clearly explain
   that the deadline has passed and ask the user whether
   they completed the task.

6. Never assume that an overdue task was completed
   or missed.

7. Do not calculate relative dates such as "tomorrow"
   or "next Friday" using the current date if the original
   message date is not available in the conversation.
   Preserve the original wording in that situation.

8. If a deadline is ambiguous, do not invent a specific date.

9. If an event has already happened, do not treat it
   as an upcoming event. Create a follow-up only when
   there is an actionable task or unresolved commitment.

--------------------------------------------------
CONVERSATION CONTEXT
--------------------------------------------------

1. Include relevant information about who said something
   and to whom the task or commitment was directed.

2. If someone asked the user to complete a task,
   mention who requested it.

3. If the user committed to doing something for another
   person, mention that the user made the commitment
   and identify the person.

4. For email conversations, include available information
   about the sender, recipient and subject when relevant.

5. Never invent names, recipients, email addresses
   or other missing information.

--------------------------------------------------
OUTPUT RULES
--------------------------------------------------

1. Return plain text only. Do not return JSON.

2. Each reminder must be on a separate line.

3. Every reminder MUST start with its corresponding
   chunk number in this exact format:

   [1] Reminder text

4. Use the chunk number provided in the input.
   Never change or invent chunk numbers.

5. If a chunk contains multiple reminders, repeat
   its chunk number for every reminder.

Example:

[1] Zain asked you to send the backend file before 28 October.
[1] You committed to preparing the project presentation.
[2] You need to attend the technical meeting on Friday.

6. Do not use headings, explanations, introductions
   or additional commentary.

7. Do not use bullet points.

8. Each reminder should be concise but informative.

9. If no actionable reminders exist in any chunk,
   return exactly:
   NONE

10. Never generate metadata fields. The application
    handles those fields.

11. Never invent dates, times, people or missing information.

12. Every reminder must be a complete sentence on a single line.

13. Never return incomplete chunk markers.

14. Before finishing, verify that every output line follows
    the required [chunk_number] Reminder text format.
"""

    # STEP 4: LANGCHAIN PROMPT TEMPLATE

    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        ("human", "{user_prompt}"),
    ])

    # STEP 5: CREATE LANGCHAIN CHAIN

    reminder_chain = prompt | llm

    # STEP 6: INVOKE GROQ

    response = reminder_chain.invoke({

        "system_prompt": system_prompt,

        "user_prompt": (
            "Extract actionable reminders from "
            "the following conversation chunks.\n\n"
            + batch_text
        )
    })

    # STEP 7: VALIDATE LLM RESPONSE

    content = response.content

    if not content:
        raise ValueError(
            "Groq returned an empty response."
        )

    if not isinstance(content, str):
        raise ValueError(
            "Unexpected response format from Groq."
        )

    content = content.strip()

    print("\nLLM response:")
    print(content)

    # STEP 8: PARSE REMINDERS

    parsed_reminders = []

    if content.upper() == "NONE":
        return parsed_reminders

    lines = content.splitlines()

    for line_number, line in enumerate(lines):

        line = line.strip()

        if not line:
            continue

        # Expected format: [1] Reminder text
        match = re.match(
            r"^\[(\d+)\]\s+(.+)$",
            line
        )

        if not match:

            remaining_lines = [
                item.strip()
                for item in lines[line_number + 1:]
                if item.strip()
            ]

            if line == "[" and not remaining_lines:

                logger.warning(
                    "Ignoring incomplete trailing LLM output."
                )

                break

            raise ValueError(
                f"Invalid LLM output format: {line}"
            )

        chunk_index = int(match.group(1))

        reminder_text = match.group(2).strip()

        # STEP 9: VALIDATE CHUNK INDEX

        if not (1 <= chunk_index <= len(batch)):

            raise ValueError(
                f"Invalid chunk number returned by LLM: "
                f"{chunk_index}"
            )

        if not reminder_text:
            continue

        # STEP 10: RESTORE ORIGINAL PII

        reminder_text = pii.restore(reminder_text)

        # STEP 11: STORE PARSED REMINDER

        parsed_reminders.append({

            "chunk_index": chunk_index,

            "reminder": reminder_text
        })

    logger.info(
        "Successfully extracted %s reminders",
        len(parsed_reminders)
    )

    return parsed_reminders


def get_current_ist_datetime():

    IST = timezone(timedelta(hours=5, minutes=30))

    return datetime.now(IST).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def validate_batch_size(noti_batch_size):

    if (
        not isinstance(noti_batch_size, int)
        or isinstance(noti_batch_size, bool)
        or noti_batch_size <= 0
    ):
        raise ValueError(
            "noti_batch_size must be a positive integer."
        )


# TELEGRAM NOTIFICATION GENERATOR

def generate_telegram_notifications(
    chunks,
    noti_batch_size=5
):

    notification_list = []

    validate_batch_size(noti_batch_size)

    current_datetime = get_current_ist_datetime()

    print(
        f"\nCurrent date and time: {current_datetime}"
    )

    # STEP 1: CATEGORIZE TELEGRAM CHUNKS

    relevant_chunks = []

    for chunk in chunks:

        category = categorize(chunk["text"])

        if category == "NORMAL":
            continue

        relevant_chunks.append({

            "source": chunk["source"],

            "date": chunk["date"],

            "chat_name": chunk["chat_name"],

            "category": category,

            "text": chunk["text"]
        })

    if not relevant_chunks:

        print("No relevant Telegram chunks found.")

        return notification_list

    print(
        f"Relevant Telegram chunks found: "
        f"{len(relevant_chunks)}"
    )

    # STEP 2: PROCESS IN BATCHES

    total_chunks = len(relevant_chunks)

    total_batches = (
        total_chunks + noti_batch_size - 1
    ) // noti_batch_size

    for batch_start in range(
        0,
        total_chunks,
        noti_batch_size
    ):

        batch = relevant_chunks[
            batch_start:batch_start + noti_batch_size
        ]

        batch_number = (
            batch_start // noti_batch_size
        ) + 1

        print(
            f"\nProcessing Telegram batch "
            f"{batch_number}/{total_batches}"
        )

        try:

            batch_texts = [
                chunk["text"]
                for chunk in batch
            ]

            parsed_reminders = llm_invoke(
                batch=batch_texts,
                current_datetime=current_datetime
            )

            # STEP 3: BUILD TELEGRAM NOTIFICATIONS

            batch_notifications = []

            for item in parsed_reminders:

                original_chunk = batch[
                    item["chunk_index"] - 1
                ]

                notification = {

                    "source": original_chunk["source"],

                    "date": original_chunk["date"],

                    "chat_name": original_chunk["chat_name"],

                    "category": original_chunk["category"],

                    "status": "not_completed",

                    "reminder": item["reminder"]
                }

                batch_notifications.append(notification)

            notification_list.extend(batch_notifications)

            print(
                f"Telegram batch {batch_number}: "
                f"{len(batch_notifications)} notifications created"
            )

        except Exception as e:

            print(
                f"\nError processing Telegram batch "
                f"{batch_number}: {type(e).__name__}: {e}"
            )

            raise RuntimeError(
                f"Telegram notification generation failed "
                f"for batch {batch_number}/{total_batches}"
            ) from e

    print(
        f"\nTotal Telegram notifications generated: "
        f"{len(notification_list)}"
    )

    return notification_list


# GMAIL NOTIFICATION GENERATOR

def generate_gmail_notifications(
    emails,
    noti_batch_size=5
):

    notification_list = []

    validate_batch_size(noti_batch_size)

    current_datetime = get_current_ist_datetime()

    print(
        f"\nCurrent date and time: {current_datetime}"
    )

    # STEP 1: CONVERT EMAILS TO TEXT

    converted_emails = convert_gmail_emails_to_text(
        emails
    )

    # STEP 2: CATEGORIZE EMAILS

    relevant_emails = []

    for email in converted_emails:

        category = categorize(email["text"])

        if category == "NORMAL":
            continue

        relevant_emails.append({

            "source": email["source"],

            "my_email_id": email["my_email_id"],

            "senders_email_id": email["senders_email_id"],

            "date": email["date"],

            "category": category,

            "text": email["text"]
        })

    if not relevant_emails:

        print("No relevant Gmail emails found.")

        return notification_list

    print(
        f"Relevant Gmail emails found: "
        f"{len(relevant_emails)}"
    )

    # STEP 3: PROCESS EMAILS IN BATCHES

    total_emails = len(relevant_emails)

    total_batches = (
        total_emails + noti_batch_size - 1
    ) // noti_batch_size

    for batch_start in range(
        0,
        total_emails,
        noti_batch_size
    ):

        batch = relevant_emails[
            batch_start:batch_start + noti_batch_size
        ]

        batch_number = (
            batch_start // noti_batch_size
        ) + 1

        print(
            f"\nProcessing Gmail batch "
            f"{batch_number}/{total_batches}"
        )

        try:

            batch_texts = [
                email["text"]
                for email in batch
            ]

            parsed_reminders = llm_invoke(
                batch=batch_texts,
                current_datetime=current_datetime
            )

            # STEP 4: BUILD GMAIL NOTIFICATIONS

            batch_notifications = []

            for item in parsed_reminders:

                original_email = batch[
                    item["chunk_index"] - 1
                ]

                notification = {

                    "source": original_email["source"],

                    "my_email_id": original_email["my_email_id"],

                    "senders_email_id": original_email[
                        "senders_email_id"
                    ],

                    "date": original_email["date"],

                    "text": item["reminder"],

                    "category": original_email["category"],

                    "status": "not_completed"
                }

                batch_notifications.append(notification)

            notification_list.extend(batch_notifications)

            print(
                f"Gmail batch {batch_number}: "
                f"{len(batch_notifications)} notifications created"
            )

        except Exception as e:

            print(
                f"\nError processing Gmail batch "
                f"{batch_number}: {type(e).__name__}: {e}"
            )

            raise RuntimeError(
                f"Gmail notification generation failed "
                f"for batch {batch_number}/{total_batches}"
            ) from e

    # --------------------------------------------------
    # STEP 5: RETURN GMAIL NOTIFICATIONS
    # --------------------------------------------------

    print(
        f"\nTotal Gmail notifications generated: "
        f"{len(notification_list)}"
    )

    return notification_list
