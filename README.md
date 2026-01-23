---
title: Chatbot
emoji: 🏆
colorFrom: pink
colorTo: green
sdk: docker
pinned: false
---

# Hybrid Document Chatbot

A production-grade conversational AI system with dual processing pipelines for structured and unstructured data.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA PREPARATION LAYER                        │
├─────────────────────────────┬───────────────────────────────────┤
│      STRUCTURED PATH        │        UNSTRUCTURED PATH          │
│      (CSV, XLSX)            │    (PDF, DOCX, TXT, MD, PPTX)     │
│            │                │              │                    │
│            ▼                │              ▼                    │
│    Create MySQL Table       │      Text Extraction + OCR        │
│            │                │              │                    │
│            ▼                │              ▼                    │
│    Store in Aiven           │      Semantic Chunking            │
│            │                │              │                    │
│            ▼                │              ▼                    │
│    Generate Summary         │      Generate Embeddings          │
│    + Embedding              │              │                    │
│            │                │              ▼                    │
│            └────────────────┴──────► docs_summary               │
│                                      (Routing Table)            │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    QUERY PROCESSING LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│  1. User Query                                                   │
│  2. Load Chat History (last 5)                                  │
│  3. Select Relevant Documents (via docs_summary embeddings)     │
│  4. Route Query (structured vs unstructured)                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│    STRUCTURED PATH      │     │   UNSTRUCTURED PATH     │
│                         │     │                         │
│  LLM: NL → SQL          │     │   Vector Search         │
│          │              │     │   (Cosine Similarity)   │
│          ▼              │     │          │              │
│  SQL Validation         │     │          ▼              │
│  (SELECT only)          │     │   Top-K Chunks          │
│          │              │     │          │              │
│          ▼              │     │          ▼              │
│  Execute on Aiven       │     │   Build Context         │
│          │              │     │          │              │
│          ▼              │     │          ▼              │
│  LLM Explanation        │     │   LLM Answer            │
└─────────────────────────┘     └─────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FINALIZATION LAYER                            │
├─────────────────────────────────────────────────────────────────┤
│  1. Save to chat_history                                        │
│  2. Return Answer to UI                                         │
│  3. Show SQL/Chunks (transparency)                              │
└─────────────────────────────────────────────────────────────────┘
```

## Database Schema

### docs_summary (Document Router)
| Column | Type | Purpose |
|--------|------|---------|
| doc_id | INT | Primary key |
| doc_name | VARCHAR | Original filename |
| doc_type | VARCHAR | STRUCTURED / UNSTRUCTURED |
| is_structured | BOOLEAN | Quick filter |
| table_name | VARCHAR | MySQL table (structured only) |
| schema_info | TEXT | Column info (structured only) |
| summary_text | TEXT | Document summary |
| summary_embedding | LONGBLOB | For document selection |

### unstructured_docs (RAG Store)
| Column | Type | Purpose |
|--------|------|---------|
| id | INT | Primary key |
| doc_id | INT | Link to docs_summary |
| doc_name | VARCHAR | Source document |
| chunk_text | TEXT | Chunk content |
| chunk_embedding | LONGBLOB | For vector search |
| page_no | INT | Source page |

### data_[filename] (Dynamic Tables)
Created from CSV/XLSX with actual data columns.

### chat_history (Memory)
| Column | Type | Purpose |
|--------|------|---------|
| session_id | VARCHAR | Conversation ID |
| user_query | TEXT | User question |
| final_answer | TEXT | Assistant response |
| query_type | VARCHAR | structured/unstructured |
| doc_used | VARCHAR | Documents referenced |

## Key Features

| Feature | Implementation |
|---------|----------------|
| Document Routing | Embedding similarity on docs_summary |
| Query Classification | Keyword + score analysis |
| Text-to-SQL | Groq LLM generates SQL |
| SQL Safety | SELECT-only validation |
| Chat Memory | Last 5 messages as context |
| Transparency | Show SQL queries and retrieved chunks |

## Environment Variables

```
GROQ_API_KEY=...
AIVEN_MYSQL_HOST=...
AIVEN_MYSQL_PORT=3306
AIVEN_MYSQL_USER=...
AIVEN_MYSQL_PASSWORD=...
AIVEN_MYSQL_DATABASE=...
AIVEN_MYSQL_SSL_CA=...
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | Streamlit |
| LLM | Groq Llama 3.1-8b-instant |
| Text-to-SQL | Groq LLM |
| Embeddings | intfloat/e5-base-v2 |
| Database | Aiven MySQL |
| OCR | Tesseract |
