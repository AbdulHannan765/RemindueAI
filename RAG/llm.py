import os
import logging

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from .prompt import build_rag_prompt
from security_and_privacy.pii_middleware import PIISanitizer

logger = logging.getLogger(__name__)

llm = ChatGroq(
    model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    groq_api_key=os.environ["GROQ_API_KEY"],
    temperature=0.2,
    max_tokens=700,
)





async def generate_rag_answer(
    question: str,
    retrieved_notifications: list[dict],
) -> str:

    try:
        #independent for all users
        pii = PIISanitizer()
        # 1. Sanitize user's question
        safe_question = pii.sanitize(question)

        # 2. Sanitize retrieved notifications

        safe_notifications = []

        for notification in retrieved_notifications:

            safe_notification = notification.copy()

            # Sanitize all text fields that may contain PII
            for field in [
                "text",
                "reminder_text",
                "reminder",
                "chat_name",
                "subject",
                "email",
            ]:
                value = safe_notification.get(field)

                if isinstance(value, str) and value:
                    safe_notification[field] = pii.sanitize(value)

            safe_notifications.append(safe_notification)

        # 3. Build prompt using sanitized data

        messages = build_rag_prompt(
            question=safe_question,
            retrieved_notifications=safe_notifications,
        )

        # 4. Convert messages to LangChain

        langchain_messages = []

        for message in messages:

            content = message["content"]

            # Tell the LLM to preserve PII placeholders
            content += (
                "\n\nPrivacy instruction: Text may contain placeholders "
                "such as [PERSON_1], [EMAIL_ADDRESS_1], or [PHONE_NUMBER_1]. "
                "Treat them as original information, preserve them exactly "
                "when needed, and never invent or modify placeholder values."
            )

            if message["role"] == "system":
                langchain_messages.append(
                    SystemMessage(content=content)
                )

            elif message["role"] == "user":
                langchain_messages.append(
                    HumanMessage(content=content)
                )

        # 5. Send sanitized data to Groq

        response = await llm.ainvoke(langchain_messages)

        answer = response.content

        if not answer:
            raise RuntimeError("Groq returned an empty response")

        # 6. Restore PII in the answer

        restored_answer = pii.restore(answer)

        logger.info(
            "RAG answer generated using LangChain + Groq with PII sanitization"
        )

        return restored_answer.strip()

    except Exception:
        logger.exception("Failed to generate RAG answer")
        raise