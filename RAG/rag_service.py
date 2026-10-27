
import asyncio
import logging
import time

from qdrant_client import models

from typesafe_sdk import TypeSafeClient, Choice
from security_and_privacy import decrypt_payload

from vector_database.qdrant_db import (
    qdrant_client,
    QDRANT_COLLECTION,
)

from .qdrant_retriever import retrieve_notifications
from RAG.llm import generate_rag_answer


logger = logging.getLogger(__name__)



jev_client = TypeSafeClient()


def categorize_user_query(user_query: str):

    response = jev_client.system_one(
        state=user_query,
        questions={
            "query_type": Choice(
                instructions=(
                    "Analyze the user's query and decide "
                    "which retrieval strategy is required."
                ),
                criteria={

                    "retrieve_all_reminders": (
                        """
                        Choose this when the user needs all
                        their reminders instead of only a few
                        semantically relevant reminders.

                        Examples:
                        - Create a summary of all my tasks.
                        - Create a schedule for all my pending tasks.
                        - Organize my tasks by priority.
                        - Show all my reminders.
                        - List all my completed tasks.
                        - How many pending tasks do I have?
                        - Give me an overview of my reminders.
                        """
                    ),

                    "retrieve_notifications": (
                        """
                        Choose this when the user needs specific
                        reminder information that can be found
                        through semantic search.

                        Examples:
                        - When do I have an investor meeting?
                        - Did I receive an email from my manager
                          about work?
                        - When do I have to submit my DSA assignment?
                        - What was the task related to my project?
                        """
                    ),

                    "Normal_question": (
                        """
                        Choose this when the question does not
                        require the user's stored reminders.

                        Examples:
                        - Hi.
                        - What is 2 + 2?
                        - Give me steps to create a PPT.
                        - Explain what machine learning is.
                        """
                    ),
                },
            )
        },
    )

    return response.answers["query_type"].choice



async def retrieve_all_reminders(user_id: str) -> str:

    if not user_id:
        raise ValueError("user_id is required")

    user_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(
                    value=str(user_id)
                ),
            )
        ]
    )

    all_reminders = []

    offset = None
    page_size = 256
    reminder_count = 0

    while True:

        response, next_offset = await qdrant_client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=user_filter,
            limit=page_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in response:

            payload = point.payload or {}

            encrypted_reminder_text = payload.get(
                "reminder_text"
            )

            if not encrypted_reminder_text:
                continue

            try:

                # Decrypt sensitive fields.
                reminder_text = decrypt_payload(
                    encrypted_reminder_text
                )

                chat_name = decrypt_payload(
                    payload.get("chat_name")
                )

                origin = decrypt_payload(
                    payload.get("origin")
                )

            except ValueError:

                logger.exception(
                    "Could not decrypt notification %s",
                    payload.get("notification_id"),
                )

                continue

            if not reminder_text:
                continue

            reminder_count += 1

            reminder_details = f"""
            reminder no: {reminder_count}
            reminder text: {reminder_text}
            source: {payload.get("source")}
            date: {payload.get("date")}
            chat name: {chat_name}
            origin: {origin}
            category: {payload.get("category")}
            status: {payload.get("status")}
            """.strip()

            all_reminders.append(reminder_details)

        if next_offset is None:
            break

        offset = next_offset

    reminders_text = "\n\n".join(all_reminders)

    logger.info(
        "Retrieved %s reminders for user %s",
        reminder_count,
        user_id,
    )

    if not reminders_text:
        return "No reminders were found for this user."

    return reminders_text




async def retrieve_all_reminders(user_id: str) -> str:

    if not user_id:
        raise ValueError("user_id is required")

    user_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(
                    value=str(user_id)
                ),
            )
        ]
    )

    all_reminders = []

    offset = None
    page_size = 256

    reminder_count = 0

    while True:

        response, next_offset = await qdrant_client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=user_filter,
            limit=page_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in response:

            payload = point.payload or {}

            reminder_text = payload.get("reminder_text")

            if not reminder_text:
                continue

            reminder_count += 1

            reminder_details = f"""
reminder no : {reminder_count}
reminder text: {reminder_text}
source : {payload.get("source")}
date : {payload.get("date")}
origin : {payload.get("origin")}
category : {payload.get("category")}
status : {payload.get("status")}
""".strip()

            all_reminders.append(reminder_details)

        if next_offset is None:
            break

        offset = next_offset

    # Separate every reminder with one blank line
    reminders_text = "\n\n".join(all_reminders)

    logger.info(
        "Retrieved %s reminders for user %s",
        reminder_count,
        user_id,
    )

    if not reminders_text:
        return "No reminders were found for this user."

    return reminders_text



async def ask_remindue(
    user_id: str,
    question: str,
    top_k: int = 6,
    source: str | None = None,
    category: str | None = None,
):

    if not user_id:
        raise ValueError("user_id is required")

    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    question = question.strip()

    start_time = time.perf_counter()

    # STEP 1: CLASSIFY USER QUERY

    question_type = await asyncio.to_thread(
        categorize_user_query,
        question,
    )

    logger.info(
        "User query classified as: %s",
        question_type,
    )

    retrieval_time = 0.0
    generation_time = 0.0

    retrieved = []
    all_reminders_text = ""

    # CASE 1: SEMANTIC SEARCH / RAG

    if question_type == "retrieve_notifications":

        # RETRIEVE RELEVANT NOTIFICATIONS

        retrieval_start = time.perf_counter()

        retrieved = await retrieve_notifications(
            user_id=user_id,
            query=question,
            top_k=top_k,
            source=source,
            category=category,
        )

        retrieval_time = (
            time.perf_counter() - retrieval_start
        )

        # GENERATE ANSWER

        answer_start = time.perf_counter()

        answer = await generate_rag_answer(
            question=question,
            retrieved_notifications=retrieved,
        )

        generation_time = (
            time.perf_counter() - answer_start
        )

        # BUILD SOURCES

        sources = []

        for index, item in enumerate(
            retrieved,
            start=1,
        ):

            sources.append({

                "reference": f"Source {index}",

                "text": item["text"],

                "source": item["source"],

                "date": item["date"],

                "origin": item["origin"],

                "category": item["category"],

                "status": item["status"],

                "similarity": round(
                    item["score"], 4
                ),
            })

        retrieved_count = len(retrieved)

    # CASE 2: RETRIEVE ALL REMINDERS

    elif question_type == "retrieve_all_reminders":

        # RETRIEVE EVERY NOTIFICATION

        retrieval_start = time.perf_counter()

        all_reminders_text = await retrieve_all_reminders(
            user_id=user_id,
        )

        retrieval_time = (
            time.perf_counter() - retrieval_start
        )

        # PASS COMPLETE CONTEXT TO LANGCHAIN + GROQ

        answer_start = time.perf_counter()

        all_reminders_context = [
            {
                "text": all_reminders_text,
                "source": None,
                "date": None,
                "origin": None,
                "category": None,
                "status": None,
            }
        ]

        answer = await generate_rag_answer(
            question=question,
            retrieved_notifications=all_reminders_context,
        )

        generation_time = (
            time.perf_counter() - answer_start
        )

        # BUILD SOURCES

        sources = [
            {
                "reference": "All reminders",
                "text": all_reminders_text,
            }
        ]

        retrieved_count = all_reminders_text.count(
            "reminder no :"
        )

    # CASE 3: NORMAL QUESTION

    elif question_type == "Normal_question":

        # NO QDRANT RETRIEVAL

        logger.info(
            "Normal question detected. Skipping Qdrant retrieval."
        )

        # GENERATE ANSWER USING LLM ONLY

        answer_start = time.perf_counter()

        answer = await generate_rag_answer(
            question=question,
            retrieved_notifications=[],
        )

        generation_time = (
            time.perf_counter() - answer_start
        )

        sources = []

        retrieved_count = 0

    # INVALID CLASSIFICATION

    else:

        raise ValueError(
            f"Unknown query classification: {question_type}"
        )

    # STEP 4: CALCULATE METRICS

    total_time = time.perf_counter() - start_time

    logger.info(
        "Remindue timings | "
        "query_type=%s | "
        "retrieval=%.3fs | "
        "generation=%.3fs | "
        "total=%.3fs",
        question_type,
        retrieval_time,
        generation_time,
        total_time,
    )

    # STEP 5: RETURN RESPONSE

    return {

        "answer": answer,

        "question_type": question_type,

        "sources": sources,

        "metrics": {

            "retrieval_seconds": round(
                retrieval_time, 3
            ),

            "generation_seconds": round(
                generation_time, 3
            ),

            "total_seconds": round(
                total_time, 3
            ),

            "retrieved_count": retrieved_count,
        },
    }
