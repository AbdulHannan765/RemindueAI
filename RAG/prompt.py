def build_rag_prompt(
    question: str,
    retrieved_notifications: list[dict],
) -> list[dict]:

    if not retrieved_notifications:
        context = "No relevant notifications were retrieved."

    else:
        context_parts = []

        for index, item in enumerate(
            retrieved_notifications,
            start=1,
        ):

            context_parts.append(
                f"""
[Source {index}]
Reminder: {item.get("text")}
Source type: {item.get("source")}
Date: {item.get("date")}
Origin: {item.get("origin")}
Category: {item.get("category")}
Status: {item.get("status")}
""".strip()
            )

        context = "\n\n".join(context_parts)

    system_prompt = """
You are RemindueAI, a personal reminder assistant.

Answer the user's question using the retrieved notification
records provided in the context.

Rules:

1. Use the retrieved context as your evidence.
2. Never invent a reminder, deadline, date, person, or event.
3. If the context does not contain the answer, clearly say 
   something like: i dont have enough information to answer this question.
4. If the user asks about upcoming work, deadlines, or tasks,
   organize the relevant reminders clearly.
5. Distinguish Telegram, Gmail, and WhatsApp sources.
6. Use dates from the context. Do not guess missing dates.
7. If multiple reminders are related, combine them sensibly.
8. Cite supporting records using [Source 1], [Source 2], etc.
9. Keep the answer direct, useful, and concise.
10. Do not expose internal database IDs or implementation details.
"""

    user_prompt = f"""
Retrieved notification context:

{context}

User question:

{question}

Write the answer with source references where appropriate.
"""

    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]