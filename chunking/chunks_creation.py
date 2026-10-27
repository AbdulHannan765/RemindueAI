from collections import defaultdict


def Telegram_chunking(messages, chunk_size=10, overlap_size=2):

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if overlap_size < 0 or overlap_size >= chunk_size:
        raise ValueError("overlap_size must be between 0 and chunk_size - 1")

    chunks = defaultdict(list)

    for message in messages:

        chat_title = message.get("chat_title")

        if not chat_title:
            continue

        chat_chunks = chunks[chat_title]

        if not chat_chunks:
            chat_chunks.append([])

        elif len(chat_chunks[-1]) >= chunk_size:

   
            previous_messages = chat_chunks[-1][-overlap_size:] if overlap_size else []

            chat_chunks.append(previous_messages)

        chat_chunks[-1].append(message)

    return [
        {
            "chat_title": chat_title,
            "messages": chunk
        }
        for chat_title, chat_chunks in chunks.items()
        for chunk in chat_chunks
    ]
