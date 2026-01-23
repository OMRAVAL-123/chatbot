# Implementation Guide

Complete step-by-step guide for the Hybrid Document Chatbot.

## System Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER QUERY                                │
│                    "Total sales last month"                      │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│              STEP 1: Load Chat Memory                            │
│         Fetch last 5 chats from chat_history                     │
│         Provides context for follow-up questions                 │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│              STEP 2: Document Selection                          │
│         Generate query embedding                                 │
│         Compare with docs_summary.summary_embedding              │
│         Select top-k relevant documents                          │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│              STEP 3: Route Query                                 │
│         Check document types (structured vs unstructured)        │
│         Analyze SQL keywords in query                            │
│         Decide processing path                                   │
└─────────────────────────────┬────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│    STRUCTURED PATH      │     │   UNSTRUCTURED PATH     │
│                         │     │                         │
│  1. LLM generates SQL   │     │  1. Vector search on    │
│  2. Validate SELECT     │     │     chunk_embedding     │
│  3. Execute on Aiven    │     │  2. Get top-k chunks    │
│  4. LLM explains result │     │  3. LLM generates answer│
└─────────────────────────┘     └─────────────────────────┘
```

## Step 1: Aiven MySQL Setup

1. Go to https://aiven.io
2. Create a MySQL service
3. Wait for service to be running
4. Note connection details:
   - Host
   - Port
   - User
   - Password
   - Database name
5. Download CA certificate (ca.pem)

## Step 2: Groq API Setup

1. Go to https://console.groq.com
2. Create account
3. Generate API key

## Step 3: Environment Variables

Create `.env` file:

```
GROQ_API_KEY=your_groq_key
AIVEN_MYSQL_HOST=mysql-xxx.aivencloud.com
AIVEN_MYSQL_PORT=3306
AIVEN_MYSQL_USER=avnadmin
AIVEN_MYSQL_PASSWORD=your_password
AIVEN_MYSQL_DATABASE=defaultdb
AIVEN_MYSQL_SSL_CA=/path/to/ca.pem
```

## Step 4: Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Step 5: Docker Deployment

```bash
docker build -t chatbot .
docker run -p 7860:7860 --env-file .env chatbot
```

## Step 6: HuggingFace Spaces

1. Create Docker Space
2. Upload all files
3. Add secrets in Settings:
   - GROQ_API_KEY
   - AIVEN_MYSQL_HOST
   - AIVEN_MYSQL_PORT
   - AIVEN_MYSQL_USER
   - AIVEN_MYSQL_PASSWORD
   - AIVEN_MYSQL_DATABASE

## Database Tables

### docs_summary
```sql
CREATE TABLE docs_summary (
    doc_id INT AUTO_INCREMENT PRIMARY KEY,
    doc_name VARCHAR(500),
    doc_type VARCHAR(50),
    is_structured BOOLEAN,
    table_name VARCHAR(255),
    schema_info TEXT,
    summary_text TEXT,
    summary_embedding LONGBLOB
);
```

### unstructured_docs
```sql
CREATE TABLE unstructured_docs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doc_id INT,
    doc_name VARCHAR(500),
    chunk_text TEXT,
    chunk_embedding LONGBLOB,
    page_no INT,
    chunk_index INT
);
```

### chat_history
```sql
CREATE TABLE chat_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100),
    user_query TEXT,
    final_answer TEXT,
    query_type VARCHAR(50),
    doc_used VARCHAR(500)
);
```

### data_[filename] (Dynamic)
Created from CSV/XLSX with actual columns.

## Text-to-SQL with LLM

The system uses Groq LLM (Llama 3.1-8b-instant) for SQL generation:

1. User asks structured data question
2. System identifies relevant tables from docs_summary
3. LLM receives:
   - Table schemas
   - User question
4. LLM generates MySQL SELECT query
5. Query validated (SELECT only, no dangerous keywords)
6. Executed on Aiven MySQL
7. Results explained by LLM

## Why This Architecture Works

| Principle | Implementation |
|-----------|----------------|
| Document selection before LLM | docs_summary embeddings filter irrelevant docs |
| Structured/Unstructured separation | Different processing pipelines |
| SQL safety | SELECT-only validation |
| Chat memory | Last 5 messages as context |
| Embeddings in DB | No external vector store needed |
| Single source of truth | All data in Aiven MySQL |
| LLM for SQL | Groq generates queries from natural language |

## Troubleshooting

**Database connection fails**
- Verify host, port, user, password
- Check SSL CA path
- Ensure Aiven service is running

**SQL query fails**
- Check table exists
- Verify column names in schema_info
- Review LLM-generated query

**Document not selected**
- Check if summary_embedding was generated
- Verify embedding similarity threshold

**Chat context missing**
- Ensure session_id is consistent
- Check chat_history table has data
