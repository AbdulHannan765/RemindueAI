\# RemindueAI — Privacy-Aware Intelligent Reminder & Conversational Memory Assistant\
\
\> \*\*Never miss an important commitment hidden in your emails or conversations.\*\*\
\
RemindueAI is an AI-powered personal assistant that automatically processes connected Gmail emails and Telegram conversations, identifies important tasks and commitments, and generates actionable reminders without requiring users to create them manually.\
\
Instead of relying on users to remember every message, RemindueAI turns everyday communication into structured, searchable reminders. Its key differentiator is a \*\*JEV-powered intelligent classification pipeline\*\* that understands the intent and context of messages before deciding whether they deserve a LLM call for creating notification (JEV is used for cost cutting by reducing llm calls upto 90 percent).\
\
The system also provides a Retrieval-Augmented Generation (RAG) pipeline, allowing users to ask natural-language questions about their reminders and retrieve relevant information from their communication history.\
\
Privacy is integrated into the processing workflow through PII detection and anonymization, encrypted credentials and selected stored data, protected embeddings, and user-scoped data access.\
\
\---\
\
\##  Why RemindueAI?\
\
Important information is scattered across emails and conversations:\
\
\- A manager assigns a task with a deadline in Telegram.\
\- An email contains an interview invitation or submission deadline.\
\- Someone asks you to return money on a particular date.\
\- You promise to send a document but forget about it.\
\- An important meeting date gets buried in an inbox.\
\
Traditional reminder applications require users to manually identify these tasks and create reminders.\
\
\*\*RemindueAI automates this process.\*\*\
\
After users connect their accounts and initiate synchronization, RemindueAI fetches available messages, analyzes their meaning, identifies actionable information, and automatically creates reminder notifications.\
\
Users can also ask questions about their saved reminders through a conversational AI interface.\
\
\---\
\
\## 🚀 Core Features\
\
\### 1. Automatic Email & Conversation Processing\
\
Connect communication accounts and let RemindueAI process available messages.\
\
\- \*\*Gmail:\*\* Google OAuth 2.0 authentication and Gmail API integration.\
\- \*\*Telegram:\*\* Personal Telegram account integration using Telethon.\
\- Incremental synchronization to fetch newly available messages.\
\- Per-chat Telegram synchronization checkpoints.\
\- Gmail history-based synchronization checkpoints.\
\- Message normalization and conversation-aware chunking.\
\
Users initiate synchronization through the application; the backend then performs the fetching and processing workflow.\
\
\### 2. JEV-Powered Intelligent Classification — Core Differentiator\
\
The most important component of RemindueAI is its \*\*JEV-based semantic classification system\*\*, implemented using TypeSafe.\
\
Rather than relying on simple keyword matching, JEV evaluates the meaning and intention of each message chunk and assigns a category.\
\
\| Category   | Purpose                                                           |\
\| ---------- | ----------------------------------------------------------------- |\
\| WORK       | Tasks, assignments and work responsibilities                      |\
\| DEADLINE   | Tasks with an explicit or clearly implied deadline                |\
\| COMMITMENT | Promises, agreements and obligations                              |\
\| EVENT      | Meetings, interviews, appointments and important events           |\
\| NORMAL     | Casual conversations, advertisements, spam and irrelevant content |\
\
Only relevant categories proceed to reminder generation. NORMAL chunks are filtered out.\
\
This reduces unnecessary notifications and focuses the system on information that requires attention.\
\
\### 3. Automatic AI Reminder Generation\
\
After JEV identifies relevant chunks, RemindueAI uses LangChain and Groq to generate concise, actionable reminder notifications.\
\
The generation pipeline considers:\
\
\- The actual conversation context.\
\- Who requested the task and who made the commitment.\
\- Email sender, recipient and subject information where available.\
\- Dates and deadlines.\
\- Current date and time in Indian Standard Time.\
\- Whether a deadline is upcoming, due today or overdue.\
\
The generated reminders are plain-language notifications, not generic summaries.\
\
Examples:\
\
\- Prepare the investor-meeting presentation before 28 October.\
\- Submit the DSA assignment by Friday.\
\- Follow up with Zain about the promised payment.\
\- Confirm whether the overdue project submission has been completed.\
\
Generated notifications are stored with relevant metadata, including source, date, category and completion status.\
\
\### 4. Conversational Memory & RAG\
\
RemindueAI also provides a conversational interface for retrieving information from previously generated reminders.\
\
Users can ask questions such as:\
\
\- What tasks do I need to complete this week?\
\- When is my next interview?\
\- What commitments did I make?\
\- What am I waiting for someone to send me?\
\- Show all my pending reminders.\
\
The RAG pipeline uses JEV to understand the type of user query and choose an appropriate retrieval strategy:\
\
1\. Retrieve relevant notifications using semantic search.\
2\. Retrieve all reminders when a complete overview is requested.\
3\. Handle normal questions that do not require stored reminder context.\
\
Relevant context is passed to Groq through a privacy-aware generation pipeline.\
\
\---\
\
\##  System Architecture & Workflow\
\
RemindueAI follows a two-branch architecture after message processing: an automatic notification-generation pipeline and a conversational memory/RAG pipeline.\
\
                        ┌───────────────────────────────┐
                         │          RemindueAI            │
                         │  Intelligent Reminder System  │
                         └───────────────┬───────────────┘
                                         │
                         ┌───────────────▼───────────────┐
                         │       1. DATA SOURCES         │
                         └───────────────┬───────────────┘
                                         │
                 ┌───────────────────────┼
                 │                       │                       
          ┌──────▼──────┐        ┌───────▼──────┐        
          │   Telegram  │        │    Gmail     │       
          │  Telethon   │        │  Gmail API   │       
          │User Account │        │ Google OAuth │       
          └──────┬──────┘        └───────┬──────┘        
                 │                       │
                 └───────────┬───────────┘
                             │
                ┌────────────▼────────────┐
                │ 2. CONNECTOR AUTH &     │
                │       MESSAGE FETCH     │
                └────────────┬────────────┘
                             │
             ┌───────────────┼────────────────┐
             │               │                │
       ┌─────▼─────┐   ┌─────▼─────┐   ┌──────▼──────┐
       │  OAuth /  │   │ Incremental│   │ Credential  │
       │  Session  │   │    Sync    │   │ Encryption  │
       │   Auth    │   │ Checkpoints│   │   Fernet    │
       └─────┬─────┘   └─────┬─────┘   └─────────────┘
             │               │
             └───────┬───────┘
                     │
          ┌──────────▼──────────┐
          │ 3. CHUNKING &       │
          │    NORMALIZATION   │
          └──────────┬──────────┘
                     │
          ┌──────────┼───────────┐
          │          │           │
     ┌────▼────┐ ┌───▼────┐ ┌────▼────────┐
     │Telegram │ │ Gmail │ │   Metadata  │
     │Max 10   │ │1 Email│ │Source, Date,│
     │Messages │ │1 Chunk│ │Chat, Msg ID │
     │+ 2 Overlap│ └───────┘ └─────────────┘
     └────┬────┘
          │
          └────────────┬──────────────┘
                       │
            ┌──────────▼──────────┐
            │ 4. PRIVACY LAYER    │
            │ Microsoft Presidio  │
            │      + spaCy        │
            └──────────┬──────────┘
                       │
              ┌────────▼────────┐
              │   PII DETECTION │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │ PII ANONYMIZATION│
              │ [PERSON_1]       │
              │ [EMAIL_ADDRESS_1]│
              └────────┬────────┘
                       │
             ┌─────────▼──────────┐
             │ SANITIZED CHUNKS   │
             │ Ready for AI       │
             │ Processing         │
             └─────────┬──────────┘
                       │
          ┌────────────▼────────────┐
          │ 5. PER-USER ACCESS      │
          │       CONTROL           │
          │                         │
          │ JWT Authentication      │
          │ Authenticated user_id   │
          │ User Data Isolation     │
          └────────────┬────────────┘
                       │
          ┌────────────▼────────────┐
          │ 6. PARALLEL AI PIPELINES│
          └────────────┬────────────┘
                       │
          ┌────────────┴─────────────┐
          │                          │
          ▼                          ▼

┌──────────────────────────┐  ┌────────────────────────────┐
│  A. REMINDER GENERATION  │  │ B. VECTOR DB & RAG PIPELINE│
└────────────┬─────────────┘  └──────────────┬─────────────┘
             │                               │
      ┌──────▼──────┐                 ┌──────▼────────┐
      │ Sanitized   │                 │ Generate      │
      │ Message     │                 │ Embeddings    │
      │ Chunks      │                 │ FastEmbed     │
      └──────┬──────┘                 │ BGE-small     │
             │                        └──────┬────────┘
      ┌──────▼──────┐                        │
      │ JEV         │                 ┌──────▼────────┐
      │Classification│                │ Embedding     │
      │ TypeSafe    │                 │ Protection    │
      └──────┬──────┘                 │ Orthogonal    │
             │                        │ Transformation│
      ┌──────▼──────┐                 └──────┬────────┘
      │ Category    │                        │
      │ Detection   │                 ┌──────▼────────┐
      └──────┬──────┘                 │ Qdrant Vector │
             │                        │ Database      │
      ┌──────▼──────┐                 │               │
      │ WORK        │                 │ Encrypted     │
      │ DEADLINE    │                 │ Payloads      │
      │ COMMITMENT  │                 │ user_id Filter│
      │ EVENT       │                 └──────┬────────┘
      │ NORMAL      │                        │
      └──────┬──────┘                 ┌──────▼────────┐
             │                        │ User Query    │
      ┌──────▼──────┐                 └──────┬────────┘
      │ Filter      │                        │
      │ Relevant    │                 ┌──────▼────────┐
      │ Categories  │                 │ JEV Query     │
      └──────┬──────┘                 │ Intent        │
             │                        │ Classification│
      ┌──────▼──────┐                 └──────┬────────┘
      │ Groq +      │                        │
      │ LangChain   │                 ┌──────▼────────┐
      │ Reminder    │                 │ Retrieve      │
      │ Generation  │                 │ Context       │
      └──────┬──────┘                 │               │
             │                        │ Semantic Search│
      ┌──────▼──────┐                 │ All Reminders │
      │ Validate &  │                 │ User Filtering│
      │ Format      │                 └──────┬────────┘
      │ Reminders   │                        │
      └──────┬──────┘                 ┌──────▼────────┐
             │                        │ Decrypt       │
      ┌──────▼──────┐                 │ Retrieved     │
      │ PostgreSQL  │                 │ Payloads      │
      │             │                 └──────┬────────┘
      │ Notifications│                       │
      │ Metadata    │                 ┌──────▼────────┐
      │ user_id     │                 │ Presidio PII  │
      │ Encryption  │                 │ Anonymization │
      └──────┬──────┘                 └──────┬────────┘
             │                               │
             │                        ┌──────▼────────┐
             │                        │ Groq RAG      │
             │                        │ Answer        │
             │                        │ Generation    │
             │                        └──────┬────────┘
             │                               │
             └──────────────┬────────────────┘
                            │
                  ┌─────────▼─────────┐
                  │ 7. DASHBOARD /    │
                  │    API RESPONSE   │
                  └─────────┬─────────┘
                            │
               ┌────────────┼─────────────┐
               │            │             │
          ┌────▼────┐ ┌─────▼─────┐ ┌────▼─────────┐
          │Reminder │ │Conversational│ │ User-Scoped │
          │Dashboard│ │ AI Interface │ │ API Results │
          └────┬────┘ └─────┬─────┘ └──────────────┘
               │            │
          ┌────▼────┐ ┌─────▼──────┐
          │Complete │ │Contextual  │
          │Pending  │ │AI Answers  │
          │Reminders│ │            │
          └─────────┘ └────────────┘


     ┌──────────────────────────────────────────────┐
     │         SHARED SECURITY CONTROLS             │
     │                                              │
     │  • JWT Authentication                        │
     │  • Per-user Data Isolation                   │
     │  • Presidio PII Detection & Anonymization    │
     │  • Fernet Encryption                         │
     │  • Qdrant user_id Filtering                  │
     │  • Environment-based Secret Management       │
     └──────────────────────────────────────────────┘
\### Workflow Breakdown\
\
\*\*Stage 1 — Connectors and data ingestion\*\*\
\
\- Users authenticate with Gmail using Google OAuth 2.0.\
\- Users connect their personal Telegram account.\
\- The backend fetches available emails and chat messages.\
\- Incremental synchronization avoids repeatedly processing previously synchronized messages.\
\
\*\*Stage 2 — Chunking and normalization\*\*\
\
\- Telegram messages are grouped by chat.\
\- Telegram chunks use a configurable maximum of 10 messages with a 2-message overlap in the configured sync workflow.\
\- Gmail processes one email as one chunk.\
\- Metadata such as source, date, chat name and message identifiers is preserved.\
\
\*\*Stage 3 — Privacy protection before LLM processing\*\*\
\
Microsoft Presidio and spaCy detect personally identifiable information (PII).\
\
Examples include:\
\
\- Names\
\- Email addresses\
\- Phone numbers\
\- Locations\
\
Sensitive values are replaced with placeholders such as \`[PERSON_1]\` and \`[EMAIL_ADDRESS_1]\` before the notification-generation LLM receives the content.\
\
The same privacy principle is applied to the RAG question and retrieved notification context before generating conversational answers.\
\
\*\*Stage 4 — JEV classification (major processing stage)\*\*\
\
TypeSafe JEV analyzes each message chunk and identifies its semantic category.\
\
\- WORK\
\- DEADLINE\
\- COMMITMENT\
\- EVENT\
\- NORMAL\
\
Irrelevant messages are filtered out. Relevant chunks continue to the reminder-generation stage.\
\
\*\*Stage 5 — Automatic reminder generation\*\*\
\
LangChain orchestrates the Groq LLM to extract actionable reminders from relevant chunks.\
\
The system performs date and time reasoning, preserves relevant conversation context, validates the generated output, and associates each reminder with its original source metadata.\
\
\*\*Stage 6 — Structured notification storage\*\*\
\
Generated reminders are saved in PostgreSQL with user-specific ownership and metadata.\
\
Users can view notifications and update their status between \`not_completed\` and \`completed\`.\
\
\*\*Stage 7 — Vector indexing and conversational memory\*\*\
\
Generated reminders are converted into embeddings using \`BAAI/bge-small-en-v1.5\`.\
\
The embedding protection layer applies a random orthogonal transformation before vectors are stored in Qdrant.\
\
Selected sensitive Qdrant payload fields, including reminder text, chat names and origins, are encrypted before storage.\
\
\*\*Stage 8 — Privacy-aware RAG retrieval\*\*\
\
When a user asks a question:\
\
1\. JEV classifies the query intent.\
2\. The application retrieves relevant reminders or all reminders as appropriate.\
3\. Qdrant applies a \`user_id\` filter to isolate the user's data.\
4\. Retrieved sensitive content is decrypted inside the application.\
5\. Presidio anonymizes PII before the RAG LLM call.\
6\. Groq generates a context-aware answer.\
7\. The response is returned to the authenticated user.\
\
\---\
\
\## Privacy & Security Architecture\
\
Privacy is not treated as a separate feature. It is integrated into the data ingestion, AI processing, storage and retrieval stages.\
\
\| Security layer            | Implementation                                             | Where it applies                      |\
\| ------------------------- | ---------------------------------------------------------- | ------------------------------------- |\
\| Authentication            | JWT-based authentication                                   | API access                            |\
\| Password security         | Argon2 password hashing                                    | User registration and login           |\
\| Gmail authorization       | Google OAuth 2.0                                           | Gmail connection                      |\
\| Telegram session security | Fernet encryption                                          | Telegram session storage              |\
\| PII detection             | Microsoft Presidio + spaCy                                 | Before notification and RAG LLM calls |\
\| PII anonymization         | Reversible placeholder mapping within a sanitizer instance | AI processing                         |\
\| Database isolation        | Authenticated \`user_id\` filtering                          | Notification access and updates       |\
\| Payload encryption        | Fernet-based encryption                                    | Selected Qdrant payload fields        |\
\| Embedding protection      | Random orthogonal transformation                           | Before vector storage                 |\
\| Vector access isolation   | Qdrant metadata filters                                    | Semantic retrieval                    |\
\| Secret management         | Environment variables                                      | Deployment configuration              |\
\
\### Privacy-first AI processing\
\
Sensitive personal information is anonymized before conversations and retrieved context are sent to Groq.\
\
The application preserves placeholder consistency during generation and restores original values within the application where the corresponding sanitizer mapping is available.\
\
\### Multi-user data isolation\
\
Each authenticated request obtains the current user identity from the JWT.\
\
The application uses that identity when:\
\
\- Fetching connected accounts.\
\- Synchronizing messages.\
\- Saving notifications.\
\- Listing and updating reminders.\
\- Retrieving vectors from Qdrant.\
\
This is designed to prevent one user's reminders from being returned to another user.\
\
\### Encrypted storage\
\
\- Telegram session strings are encrypted using Fernet before PostgreSQL storage.\
\- Sensitive Qdrant payload fields are encrypted before indexing.\
\- Encryption keys and API credentials are configured through environment variables rather than hardcoded in application logic.\
\
\---\
\
\##  Technology Stack\
\
\| Technology             | Purpose                                                     |\
\| ---------------------- | ----------------------------------------------------------- |\
\| Python                 | Core application                                            |\
\| FastAPI                | Backend APIs and application services                       |\
\| PostgreSQL             | Users, connections, synchronization state and notifications |\
\| SQLAlchemy + asyncpg   | Asynchronous database operations                            |\
\| Telethon               | Telegram MTProto integration                                |\
\| Gmail API              | Email retrieval                                             |\
\| Google OAuth 2.0       | Gmail authentication                                        |\
\| TypeSafe / JEV         | Semantic message and query classification                   |\
\| LangChain              | LLM orchestration                                           |\
\| Groq                   | Reminder and RAG answer generation                          |\
\| Microsoft Presidio     | PII detection and anonymization                             |\
\| spaCy                  | NLP engine for PII analysis                                 |\
\| FastEmbed              | Text embedding generation                                   |\
\| BAAI/bge-small-en-v1.5 | Embedding model                                             |\
\| Qdrant                 | Vector database and semantic retrieval                      |\
\| Cryptography / Fernet  | Encryption of credentials and selected stored content       |\
\| JWT                    | Authentication and authorization                            |\
\| Docker                 | Containerization                                            |\
\| Render                 | Application deployment                                      |\
\
\---\
\
\##  Project Structure\
\`\`\`arduino\
RemindueAI/\
│\
├── DataBase_M/\
│   ├── database.py\
│   ├── tables.py\
│   ├── auth.py\
│   └── config.py\
│\
├── Gmail_connector/\
│   ├── gmail_auth.py\
│   └── gmail_service.py\
│\
├── Telegram_connector/\
│   ├── telegram_auth.py\
│   ├── telegram_service.py\
│   └── telegram_notification_storage.py\
│\
├── chunking/\
│   ├── chunks_creation.py\
│   └── text_format_chunking.py\
│\
├── Reminders/\
│   ├── JEV_chunk_classification.py\
│   └── notification_generation.py\
│\
├── security_and_privacy/\
│   └── pii_middleware.py\
│\
├── RAG/\
│   ├── embeddings.py\
│   ├── llm.py\
│   ├── rag_service.py\
│   ├── qdrant_retriever.py\
│   ├── notification_ingestion.py\
│   └── prompt.py\
│\
├── vector_database/\
│   └── qdrant_db.py\
│\
├── static/\
│   ├── login_signup.html\
│   ├── connectors.html\
│   └── dashboard.html\
│\
├── main.py\
├── requirements.txt\
├── Dockerfile\
├── render.yaml\
└── README.md\
\`\`\`\
\
\---\
\
\## ⚙️ Setup & Installation\
\
\### Prerequisites\
\
\- Python 3.13\
\- PostgreSQL database\
\- Qdrant instance\
\- Google Cloud project with Gmail API enabled\
\- Telegram API credentials\
\- Groq API key\
\- TypeSafe API key\
\
\### 1. Clone the repository\
\`\`\`bash\
git clone https\://github.com/AbdulHannan765/RemindueAI.git\
\
cd RemindueAI\
\`\`\`\
\
\### 2. Create a virtual environment\
\
Using \`uv\`:\
\`\`\`\
uv venv .remindue_env\
\`\`\`\
\
Activate on Windows:\
\`\`\`\
.remindue_env\Scripts\activate\
\`\`\`\
\
\### 3. Install dependencies\
\`\`\`\
uv sync\
\`\`\`\
\
Or:\
\`\`\`\
pip install -r requirements.txt\
\`\`\`\
\
\### 4. Configure environment variables\
\
Create a \`.env\` file in the project root.\
\`\`\`ini\
\# Application\
SECRET_KEY=your_application_secret\
\
\# PostgreSQL\
DATABASE_URL=postgresql+asyncpg://username:password@host:5432/database\
\
\# Telegram\
TELEGRAM_API_ID=your_telegram_api_id\
TELEGRAM_API_HASH=your_telegram_api_hash\
\
\# Gmail OAuth\
GOOGLE_CLIENT_ID=your_google_client_id\
GOOGLE_CLIENT_SECRET=your_google_client_secret\
GMAIL_REDIRECT_URI=http\://localhost:8000/api/gmail/callback\
\
\# Encryption\
SESSION_ENCRYPTION_KEY=your_fernet_key\
\
\# AI services\
TYPESAFE_API_KEY=your_typesafe_api_key\
GROQ_API_KEY=your_groq_api_key\
GROQ_MODEL=openai/gpt-oss-120b\
\
\# Qdrant\
QDRANT_URL=your_qdrant_url\
QDRANT_API_KEY=your_qdrant_api_key\
QDRANT_COLLECTION=remindue_notifications\
\
\# Embeddings\
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5\
\`\`\`\
\
Add any additional encryption and privacy keys required by your configuration.\
\
Never commit \`.env\` files or production credentials to GitHub.\
\
\### 5. Initialize the database\
\
Run the database initialization or table-creation procedure configured in the project.\
\
\### 6. Start the application\
\`\`\`\
uvicorn main:app --reload\
\`\`\`\
\
Open:\
\`\`\`\
http\://localhost:8000\
\`\`\`\
\
\---\
\
\##  Application Usage\
\
1\. Register a RemindueAI account.\
2\. Log in to the dashboard.\
3\. Connect Gmail using Google OAuth.\
4\. Connect Telegram using the authentication flow.\
5\. Initiate synchronization for the connected sources.\
6\. RemindueAI fetches messages and processes them through the chunking and privacy pipeline.\
7\. JEV classifies message chunks and filters irrelevant information.\
8\. Groq generates actionable reminders automatically.\
9\. View generated notifications on the dashboard.\
10\. Ask questions through the conversational RAG interface.\
\
\---\
\
\##  What Makes RemindueAI Different?\
\
\| Traditional reminder applications                | RemindueAI                                                    |\
\| ------------------------------------------------ | ------------------------------------------------------------- |\
\| Require manual reminder creation                 | Automatically extracts reminders from connected communication |\
\| Depend on users remembering important messages   | Identifies actionable information from emails and chats       |\
\| Often rely on simple keyword matching            | Uses JEV to understand message intent and context             |\
\| Generate generic reminders                       | Generates contextual, actionable reminder sentences           |\
\| Store reminders without conversational retrieval | Combines reminders with vector search and RAG                 |\
\| Privacy often handled separately                 | Integrates PII anonymization and encryption into processing   |\
\
\### The Core Innovation\
\
\*\*RemindueAI is more than a reminder application. It is an intelligent, privacy-aware memory system that converts everyday communication into actionable reminders automatically.\*\*\
\
Its JEV-powered classification stage is central to this approach: it distinguishes genuine tasks, deadlines, commitments and events from ordinary conversations before the system generates notifications.\
\
\---\
\
\## Current Scope\
\
\- Gmail integration.\
\- Telegram integration.\
\- Automatic reminder generation following synchronization.\
\- JEV-powered message classification.\
\- Privacy-aware LLM processing.\
\- PostgreSQL notification management.\
\- Qdrant-based semantic retrieval.\
\- Conversational RAG.\
\- User-scoped data access.\
\- Docker-based deployment.\

\---\
\
