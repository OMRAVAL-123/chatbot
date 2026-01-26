---
title: Chatbot
emoji: 🏆
colorFrom: pink
colorTo: green
sdk: docker
pinned: false
---

# Hybrid Document Chatbot

A production-grade conversational AI system combining **structured SQL queries** and **unstructured RAG retrieval** with intelligent routing, multi-modal input support, web search fallback, and advanced anti-hallucination mechanisms.

## 🎯 Core Capabilities

**Multi-Source Intelligence**
- 📊 **Structured Data**: CSV/XLSX → SQL queries with statistical awareness
- 📄 **Unstructured Data**: PDF/DOCX/TXT/MD → RAG with semantic chunking
- 🌐 **Web Search**: Real-time information when documents don't contain answers
- 🎙️ **Multi-Modal Input**: Text typing, live microphone recording

**Anti-Hallucination Design**
- Column-level statistics prevent fabricated data
- Complete transparency with full query results
- Clear source attribution (documents vs web)
- Download capability for user verification

**Intelligent Query Processing**
- Automatic document selection via embedding similarity
- Smart routing between SQL, RAG, and web search
- Context-aware chat memory (last 5 turns)
- SQL injection prevention (SELECT-only)

---

## 🏗️ System Architecture

### Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│  💬 Text Input         🎤 Live Microphone Recording             │
│                                  ▼                               │
│                   Google Speech Recognition API                  │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA PREPARATION LAYER                        │
├──────────────────────────┬──────────────────────────────────────┤
│   STRUCTURED PATH        │        UNSTRUCTURED PATH             │
│   (CSV, XLSX)           │    (PDF, DOCX, TXT, MD, PPTX)        │
│         ▼               │              ▼                        │
│   Parse Schema          │      Text Extraction + OCR            │
│         ▼               │              ▼                        │
│   Create MySQL Table    │      Semantic Chunking                │
│         ▼               │              ▼                        │
│   📊 Column Statistics: │      Generate Embeddings              │
│   • Numerical: μ,σ,min  │      (intfloat/e5-base-v2)           │
│   • Categorical: all    │              ▼                        │
│   • Text: samples       │      Store in unstructured_docs       │
│         ▼               │              ▼                        │
│   Generate Summary      │      Generate Summary                 │
│   + Embedding           │      + Embedding                      │
│         └───────────────┴──────► docs_summary (Router)          │
└─────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    QUERY PROCESSING LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│  1. Receive Query (Text/Audio)                                  │
│  2. Load Chat History (last 5 messages)                         │
│  3. Embed Query & Select Relevant Documents                     │
│  4. Calculate Similarity Scores                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
              ┌────────────┴──────────────┐
              ▼                           ▼
    Score >= 0.3 (Relevant)      Score < 0.3 (Not Relevant)
              │                           │
    ┌─────────┴─────────┐                ▼
    ▼                   ▼      ┌──────────────────────┐
┌──────────┐  ┌──────────────┐│   WEB SEARCH PATH    │
│STRUCTURED│  │ UNSTRUCTURED ││                      │
│   PATH   │  │     PATH     ││  DuckDuckGo Search   │
│          │  │              ││         ▼            │
│ Stats to │  │ Embed Query  ││  Scrape Top Results  │
│   LLM    │  │      ▼       ││         ▼            │
│    ▼     │  │  Cosine Sim  ││  LLM Summarization   │
│Generate  │  │      ▼       ││         ▼            │
│  SQL     │  │  Top-5 Chunks││  Answer + References │
│    ▼     │  │      ▼       │└──────────────────────┘
│Validate  │  │ RAG Context  │          │
│(SELECT)  │  │      ▼       │          │
│    ▼     │  │ LLM Answer   │          │
│Execute   │  │              │          │
│Query     │  │              │          │
│    ▼     │  │      ▼       │          │
│Full Data │  │   Response   │          │
│+ Analysis│  │              │          │
└──────────┘  └──────────────┘          │
      │              │                  │
      └──────────────┴──────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RESPONSE LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│  • Save to chat_history (context for future queries)            │
│  • Return formatted answer to UI                                │
│  • Attach metadata:                                             │
│    - SQL: Full data table + Download CSV                        │
│    - RAG: Retrieved chunks with similarity scores               │
│    - Web: Source links with snippets                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Schema

### **docs_summary** (Document Router & Index)
Routes queries to appropriate documents and processing paths.

| Column | Type | Purpose |
|--------|------|---------|
| `doc_id` | INT (PK) | Unique document identifier |
| `doc_name` | VARCHAR(500) | Original filename |
| `doc_type` | VARCHAR(50) | STRUCTURED / UNSTRUCTURED |
| `is_structured` | BOOLEAN | Quick filter for routing |
| `table_name` | VARCHAR(255) | MySQL table name (structured only) |
| `schema_info` | TEXT | Column names and types |
| `summary_text` | TEXT | **Includes detailed column statistics** |
| `summary_embedding` | LONGBLOB | For document similarity search |
| `created_at` | TIMESTAMP | Upload timestamp |

### **unstructured_docs** (RAG Vector Store)
Stores semantic chunks from unstructured documents.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INT (PK) | Chunk identifier |
| `doc_id` | INT (FK) | Links to docs_summary |
| `doc_name` | VARCHAR(500) | Source document |
| `chunk_text` | TEXT | Semantic chunk content |
| `chunk_embedding` | LONGBLOB | E5-base-v2 embedding (768d) |
| `page_no` | INT | Source page reference |
| `chunk_index` | INT | Chunk sequence number |
| `created_at` | TIMESTAMP | Ingestion timestamp |

### **data_[filename]** (Dynamic Tables)
Auto-created from CSV/XLSX uploads. Each table has:
- Auto-incremented `id` primary key
- User data columns (sanitized names)
- Original data types preserved

### **chat_history** (Conversation Memory)
Maintains conversation context across sessions.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INT (PK) | Message identifier |
| `session_id` | VARCHAR(100) | Conversation group |
| `user_query` | TEXT | User question (text or transcribed) |
| `final_answer` | TEXT | Complete assistant response |
| `query_type` | VARCHAR(50) | structured / unstructured / web_search |
| `doc_used` | VARCHAR(500) | Referenced documents |
| `created_at` | TIMESTAMP | Query timestamp |

---

## 🎯 Anti-Hallucination Architecture

### 1. **Statistical Column Profiling**
During structured data ingestion, the system generates comprehensive statistics:

**Numerical Columns**
```python
Column 'price' (NUMERICAL): mean=45.67, median=42.00, mode=39.99,
  std_dev=12.34, min=10.00, max=99.99
```
- Prevents LLM from inventing fake prices
- Enables data-grounded SQL generation

**Categorical Columns**
```python
Column 'category' (CATEGORICAL): unique_values=[Shoes, Boots,
  Sandals, Sneakers, Formal Shoes, Loafers, Slippers]
```
- LLM knows exact categories that exist
- Prevents fabricated category names

**Text Columns**
```python
Column 'description' (TEXT): 234 unique values,
  samples=[Premium leather shoes, Comfortable daily..., ...]
```
- Provides context without overwhelming token limits
- Shows data format and content style

### 2. **Complete Data Transparency**
Every structured query response includes:
- ✅ **Generated SQL query** (syntax highlighted)
- ✅ **Full result set** (all rows, all columns)
- ✅ **CSV download** (independent verification)
- ✅ **LLM analysis** (insights based on visible data)

Users can verify every claim against raw data.

### 3. **Smart Routing with Confidence Thresholds**

| Score | Action | Reasoning |
|-------|--------|-----------|
| ≥ 0.3 | Use documents | High confidence in relevance |
| < 0.3 | Web search | Document knowledge insufficient |
| Clear indication | 🌐 "Source: Web Search" | No confusion about data origin |

### 4. **Source Attribution**
Every response clearly indicates:
- **Documents**: Shows exact document names + page numbers
- **Web**: Shows search result links + publication dates
- **SQL**: Shows complete executed query

---

## 📦 Utility Modules

### 🎙️ `audio_handler.py`
Live speech input via Google Speech Recognition.

```python
AudioInputHandler()
  ├─ transcribe_from_microphone()          # 🎤 Primary: Live recording
  │    ├─ Capture from system microphone
  │    ├─ Adjust for ambient noise (1 second)
  │    ├─ Listen with timeout (10s) and phrase limit (30s)
  │    ├─ Call Google Speech API
  │    └─ Return {"success": True, "text": "...", "error": None}
  │
  └─ transcribe_audio_file(audio_file)     # Optional: File upload
       ├─ Save to temp WAV file
       ├─ Adjust for ambient noise (0.5s)
       ├─ Call Google Speech API
       └─ Return transcription

process_text_input(text)                    # Validate and clean text
```

### 🌐 `web_scraper.py`
Fallback knowledge source for out-of-scope queries.

```python
WebScraper()
  ├─ is_current_event_query(query)         # Detect time-sensitive queries
  │    └─ Keywords: today, now, current, latest, live, update
  │
  ├─ search_news(query)                    # DuckDuckGo News
  │    └─ Returns: title, url, snippet, date
  │
  ├─ search_text(query)                    # DuckDuckGo General
  │    └─ Timelimit: last week
  │
  ├─ search(query)                         # Auto-route news vs text
  │
  └─ get_page_content(url)                 # BeautifulSoup4 scraping
       ├─ Remove scripts, styles, nav
       ├─ Extract main content
       └─ Return clean paragraphs

scrape_web_content(query)                   # High-level wrapper
  └─ Search → Scrape top 2 → Combine
```

### 📄 `docsreciever.py`
Universal document processor with OCR support.

```python
DocumentProcessor()
  ├─ process_pdf(path)        # pdfplumber + Tesseract OCR
  ├─ process_docx(path)       # python-docx + image OCR
  ├─ process_image(path)      # Tesseract direct
  ├─ process_txt(path)        # UTF-8 with error handling
  ├─ process_md(path)         # Markdown
  ├─ process_csv(path)        # Pandas → returns DataFrame
  ├─ process_xlsx(path)       # Multi-sheet support
  ├─ process_pptx(path)       # python-pptx + slide images
  └─ process_zip(path)        # Recursive processing

Returns: [{"page_num": 1, "text": "...", "source": "...", 
           "is_structured": False, "dataframe": None}]
```

### 🧩 `rag.py`
Semantic chunking and embedding generation.

```python
SemanticChunker(min_chunk_size=100, max_chunk_size=500)
  └─ chunk_text(text, source, page_num)
       ├─ Split into sentences
       ├─ Generate embeddings per sentence
       ├─ Calculate inter-sentence similarity
       ├─ Merge similar sentences into chunks
       └─ Split on semantic boundaries (similarity < 0.5)

EmbeddingGenerator()
  ├─ generate_embedding(text)              # Single passage
  ├─ generate_embeddings(texts)            # Batch processing
  ├─ generate_query_embedding(query)       # Query-optimized
  ├─ embedding_to_blob(embedding)          # Pickle for MySQL
  └─ blob_to_embedding(blob)               # Unpickle from MySQL

Model: intfloat/e5-base-v2 (768 dimensions)
Prefix: "passage: " for documents, "query: " for questions
```

### 🗄️ `db.py`
Core database operations with intelligent query routing.

```python
DatabaseManager()
  ├─ initialize_tables()
  │    └─ Create: docs_summary, unstructured_docs, chat_history
  │
  ├─ _generate_column_statistics(df)       # 🔑 Anti-hallucination
  │    ├─ Numerical: mean, median, mode, std, min, max
  │    ├─ Categorical: all unique values (limit 50)
  │    └─ Text: sample values + count
  │
  ├─ ingest_structured_data(df, filename)
  │    ├─ Create sanitized MySQL table
  │    ├─ Batch insert with transactions
  │    ├─ Generate column statistics
  │    └─ Store summary + embedding
  │
  ├─ ingest_unstructured_data(chunks, filename)
  │    ├─ LLM summarization of content
  │    ├─ Store summary + embedding
  │    └─ Store all chunks + embeddings
  │
  ├─ select_relevant_documents(query, top_k=3)
  │    ├─ Embed query
  │    ├─ Calculate cosine similarity with all doc summaries
  │    └─ Return top-K documents with scores
  │
  ├─ route_query(query, relevant_docs)
  │    ├─ Calculate structured vs unstructured scores
  │    ├─ Keyword boosting for SQL queries
  │    └─ Return: "structured" / "unstructured" / "none"
  │
  ├─ generate_sql_with_llm(question, tables_info, chat_context)
  │    ├─ Include column statistics in prompt
  │    ├─ Include sample rows
  │    └─ Generate SELECT query
  │
  ├─ validate_sql(sql)
  │    ├─ Must start with SELECT
  │    └─ Block: INSERT, UPDATE, DELETE, DROP, etc.
  │
  ├─ execute_structured_query(query, docs, context)
  │    ├─ Generate SQL with statistics
  │    ├─ Validate safety
  │    ├─ Execute query
  │    ├─ Build formatted data table
  │    ├─ LLM analysis
  │    └─ Return: answer, sql, data, full_data
  │
  ├─ execute_unstructured_query(query, docs, context, top_k=5)
  │    ├─ Load chunks from relevant docs
  │    ├─ Vector search for top-K chunks
  │    ├─ LLM RAG answer
  │    └─ Return: answer, chunks (with scores)
  │
  ├─ process_user_query(session_id, query)   # 🎯 Main entry point
  │    ├─ Load chat context (last 5 messages)
  │    ├─ Select relevant documents
  │    ├─ Check relevance score
  │    │
  │    ├─ IF score >= 0.3:
  │    │    ├─ Route to structured/unstructured
  │    │    └─ Execute appropriate pipeline
  │    │
  │    └─ IF score < 0.3:  # 🌐 Web fallback
  │         ├─ DuckDuckGo search
  │         ├─ Scrape top results
  │         ├─ LLM answer from web content
  │         └─ Return with "Source: Web Search" label
  │
  ├─ get_chat_context(session_id, limit=5)
  ├─ save_chat(session_id, query, answer, type, docs)
  ├─ get_all_documents()
  ├─ get_chat_history(session_id)
  ├─ get_all_sessions()
  ├─ delete_chat_session(session_id)
  └─ delete_all_data()
```

### 🤖 `llm.py`
LLM interaction layer with specialized prompts.

```python
LLMHandler(model="llama-3.1-8b-instant")
  ├─ _call_llm(system_prompt, user_prompt)
  │    └─ Groq API with error handling
  │
  ├─ summarize(text, filename)
  │    └─ Generate document summary for embedding
  │
  ├─ rag_retrieval(query, chunks, chat_history)
  │    ├─ System: "ONLY use provided context"
  │    ├─ User: Query + chunks + scores
  │    └─ Anti-hallucination rules enforced
  │
  ├─ structured_db_retrieval(query, rows, schema, chat_history)
  │    ├─ System: "Analyze data, don't repeat table"
  │    ├─ User: Query + results + column stats
  │    └─ Return insights and patterns
  │
  └─ web_retrieval(query, web_content)  # 🌐 Web search answers
       ├─ System: "State this is from web search"
       ├─ User: Query + scraped content
       └─ Include source citations
```

---

## 🎨 Frontend (Streamlit UI)

### **Three-Tab Interface**

**1. 📤 Upload Tab**
- Multi-file upload (drag & drop)
- Supported formats: PDF, DOCX, TXT, MD, CSV, XLSX, PPTX, ZIP, Images
- Real-time processing with progress bar
- Document library with type badges

**2. 💬 Chat Tab**
- Text input field
- 🎤 Record button for live microphone input
- Send button
- Message history (user/assistant)
- Metadata expandable sections:
  - 📊 SQL Query & Full Data (with CSV download)
  - 📄 Retrieved Chunks (with similarity scores)
  - 🌐 Web Sources (with clickable links)
- Session management sidebar

**3. ⚙️ Settings Tab**
- Database statistics (docs, chats, messages)
- Password-protected data deletion
- Session list with delete options

---

## 🚀 Getting Started

### Prerequisites
```bash
# Python 3.8+
python --version

# Tesseract OCR (for image text extraction)
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt-get install tesseract-ocr
# Mac: brew install tesseract
```

### Installation

1. **Clone and navigate**
   ```bash
   cd chatbot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   Create `.env` file:
   ```bash
   # LLM API Key
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx

   # MySQL Database (Aiven or any MySQL 8.0+)
   AIVEN_MYSQL_HOST=your-mysql-host.aivencloud.com
   AIVEN_MYSQL_PORT=3306
   AIVEN_MYSQL_USER=avnadmin
   AIVEN_MYSQL_PASSWORD=your_password
   AIVEN_MYSQL_DATABASE=defaultdb
   AIVEN_MYSQL_SSL_CA=-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----
   ```

4. **Run application**
   ```bash
   streamlit run app.py
   ```

5. **Access UI**
   ```
   http://localhost:8501
   ```

---

## 📊 Usage Examples

### Example 1: **Structured Query with Anti-Hallucination**

**Scenario**: User uploads `products.csv` with columns: `id, name, category, price, stock`

**User Query**: *"Show me shoes under $50"*

**System Flow**:
1. ✅ Document selection: `products.csv` (score: 0.89)
2. ✅ Route: **STRUCTURED**
3. ✅ Column stats provided to LLM:
   ```
   price (NUMERICAL): mean=62.45, median=55.00, min=19.99, max=149.99
   category (CATEGORICAL): unique_values=[Shoes, Boots, Sandals, Sneakers, 
                                          Formal Shoes, Loafers, Slippers]
   ```
4. ✅ Generated SQL:
   ```sql
   SELECT * FROM data_products 
   WHERE category LIKE '%Shoes%' AND price < 50
   ORDER BY price ASC;
   ```
5. ✅ Results: 47 rows displayed in full table
6. ✅ CSV download available
7. ✅ LLM analysis: "Found 47 shoe products under $50, ranging from $19.99 to $49.99. Most popular category: Sneakers (28 items)."

**Why no hallucination?**
- LLM knows exact categories from statistics
- LLM sees actual price range
- User verifies against full data table

---

### Example 2: **Unstructured RAG Query**

**Scenario**: User uploads `company_policy.pdf` (50 pages)

**User Query**: *"What is the remote work policy?"*

**System Flow**:
1. ✅ Document selection: `company_policy.pdf` (score: 0.76)
2. ✅ Route: **UNSTRUCTURED**
3. ✅ Vector search: Top 5 chunks retrieved
   ```
   Chunk 1 (Page 12, Score: 0.91): "Remote work is permitted up to 3 days/week..."
   Chunk 2 (Page 13, Score: 0.87): "Employees must notify manager 24h in advance..."
   Chunk 3 (Page 13, Score: 0.82): "Required equipment: laptop, VPN access..."
   ```
4. ✅ LLM answer: Built from chunks only
5. ✅ User can expand "Retrieved Chunks" to verify sources

---

### Example 3: **Web Search Fallback**

**Scenario**: User has uploaded financial reports (nothing about weather)

**User Query**: *"What's the weather in Mumbai today?"*

**System Flow**:
1. ❌ Document selection: No relevant docs (max score: 0.12)
2. 🌐 **Web search triggered** (score < 0.3)
3. ✅ DuckDuckGo search: "weather Mumbai today"
4. ✅ Scrape top 2 results
5. ✅ LLM answer with clear label:
   ```
   🌐 Source: Web Search (No relevant documents found in knowledge base)
   
   Current weather in Mumbai: 28°C, partly cloudy...
   
   References:
   - [Weather.com - Mumbai Weather](https://weather.com/...)
   - [AccuWeather - Mumbai Forecast](https://accuweather.com/...)
   ```

**Why transparent?**
- Clear "Source: Web Search" badge
- Clickable reference links
- User knows this isn't from uploaded docs

---

### Example 4: **Live Microphone Input**

**User Action**: Clicks 🎤 Record button and speaks: *"What are our top selling products?"*

**System Flow**:
1. 🎤 Listening indicator: *"🎤 Listening... Speak now!"*
2. User speaks within 10 seconds
3. Speech recognition: ✅ "What are our top selling products?"
4. Display transcription: *"✅ Transcribed: What are our top selling products?"*
5. Transcription auto-fills text input
6. User clicks Send
7. Process as normal text query
8. Route to appropriate path (structured, in this case)
9. Return results with full data

**Note**: Requires microphone permissions in browser/system settings.

---

## 🔒 Security & Safety

| Feature | Implementation | Protection |
|---------|----------------|------------|
| **SQL Injection** | SELECT-only validation | Blocks INSERT/UPDATE/DELETE/DROP |
| **Data Isolation** | Session-based chat history | Users don't see others' sessions |
| **SSL/TLS** | Required for MySQL connections | Encrypted data transfer |
| **Password Protection** | Delete operations require password | Prevents accidental data loss |
| **No Code Execution** | LLM output is text only | No `eval()` or `exec()` |

**Delete Password**: `Jaymahadev@789`

---

## 📊 Technology Stack

### Core Components

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Streamlit 1.28+ | Interactive UI with real-time updates |
| **LLM** | Groq (Llama 3.1-8b-instant) | Fast inference for SQL, RAG, summaries |
| **Embeddings** | intfloat/e5-base-v2 | 768-dim multilingual embeddings |
| **Database** | Aiven MySQL 8.0+ | Relational storage + vector blobs |
| **OCR** | Tesseract 0.3.10+ | Extract text from images/PDFs |
| **Speech** | Google Speech Recognition 3.10+ | Audio transcription |
| **Web Search** | DuckDuckGo Search 3.9+ | Zero-API-key web search |
| **Scraping** | BeautifulSoup4 4.12+ | HTML parsing and cleaning |

### Python Libraries
```txt
streamlit>=1.28.0          # UI framework
pdfplumber>=0.10.0         # PDF text extraction
python-docx>=1.0.0         # DOCX processing
openpyxl>=3.1.0            # Excel file support
pandas>=2.0.0              # Data manipulation
python-pptx>=0.6.21        # PowerPoint processing
Pillow>=10.0.0             # Image handling
pytesseract>=0.3.10        # OCR wrapper
pymysql>=1.1.0             # MySQL connector
groq>=0.4.0                # Groq API client
sentence-transformers>=2.2.0  # Embedding models
torch>=2.0.0               # PyTorch (model backend)
numpy>=1.24.0              # Numerical operations
scikit-learn>=1.3.0        # Cosine similarity
python-dotenv>=1.0.0       # Environment variables
SpeechRecognition>=3.10.0  # Audio transcription
beautifulsoup4>=4.12.0     # HTML parsing
requests>=2.31.0           # HTTP client
duckduckgo-search>=3.9.0   # Web search
```

---

## 🔄 Development Workflow

### Adding New Document Types
1. Add processor method in `docsreciever.py`
2. Register file extension in `process_file()`
3. Test with sample file
4. Update UI file uploader types in `app.py`

### Customizing LLM Behavior
- Edit system prompts in `llm.py`
- Adjust temperature (default: 0.7)
- Increase max_tokens for longer responses
- Switch model in `LLMHandler.__init__()`

### Tuning Similarity Thresholds
- **Document selection**: Adjust `top_k` in `select_relevant_documents()`
- **Web fallback**: Change `0.3` threshold in `process_user_query()`
- **Chunk retrieval**: Modify `top_k` in `execute_unstructured_query()`

---

## 📝 Configuration Reference

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `GROQ_API_KEY` | ✅ Yes | Groq API key | `gsk_abc123...` |
| `AIVEN_MYSQL_HOST` | ✅ Yes | MySQL hostname | `mysql-xxx.aivencloud.com` |
| `AIVEN_MYSQL_PORT` | ✅ Yes | MySQL port | `3306` |
| `AIVEN_MYSQL_USER` | ✅ Yes | Database username | `avnadmin` |
| `AIVEN_MYSQL_PASSWORD` | ✅ Yes | Database password | `secretpass123` |
| `AIVEN_MYSQL_DATABASE` | ✅ Yes | Database name | `defaultdb` |
| `AIVEN_MYSQL_SSL_CA` | ⚠️ Recommended | SSL certificate (use `\n` for newlines) | `-----BEGIN CERTIFICATE-----\n...` |

### Chunking Parameters
```python
SemanticChunker(
    min_chunk_size=100,  # Minimum characters per chunk
    max_chunk_size=500   # Maximum characters per chunk
)
```

### Query Parameters
```python
# Document selection
top_k = 3  # Number of documents to consider

# Chunk retrieval (unstructured)
top_k = 5  # Number of chunks to pass to LLM

# Chat context
limit = 5  # Number of previous messages to include
```

---

## 🐛 Troubleshooting

### Common Issues

**SSL Certificate Error**
```
Error: SSL connection error
Solution: Escape newlines in .env file: AIVEN_MYSQL_SSL_CA="-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"
```

**Tesseract Not Found**
```
Error: pytesseract.pytesseract.TesseractNotFoundError
Solution: Install Tesseract OCR system package (see Prerequisites)
```

**Microphone Access Issues**
```
Error: "Microphone error: ..." or no recording starts
Solutions:
  - Grant microphone permissions in browser settings
  - Windows: Settings → Privacy → Microphone → Allow apps
  - Chrome: Site settings → Microphone → Allow
  - Check if another app is using the microphone
  - Verify microphone is connected and working (test in system settings)
  - Use headset microphone for better noise cancellation
```

**Speech Recognition Fails**
```
Error: "Could not understand the audio"
Solutions:
  - Speak clearly and at moderate pace
  - Ensure quiet environment (minimize background noise)
  - Wait for "Listening..." indicator before speaking
  - Speak within 30-second phrase limit
  - Check internet connection (Google Speech API required)
  - Try speaking louder if too quiet
```

**Web Search Returns No Results**
```
Error: "No results found"
Solutions:
  - Check internet connectivity
  - Try rephrasing query
  - DuckDuckGo may rate-limit excessive requests
```

---

## 🚢 Deployment

### Docker (Hugging Face Spaces)

**Dockerfile** (included):
```dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y tesseract-ocr

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
```

**Deploy to Hugging Face**:
1. Create new Space
2. Select "Docker" SDK
3. Upload all files
4. Add secrets in Space settings (env vars)
5. Space auto-builds and deploys

---

## 📄 License

This project is configured for deployment on Hugging Face Spaces with Docker.
Open-source dependencies retain their original licenses.

---

## 🙏 Acknowledgments

- **Groq**: Fast LLM inference
- **Aiven**: Managed MySQL database
- **Hugging Face**: Model hosting and deployment
- **OpenAI**: Inspiration for RAG architecture
- **DuckDuckGo**: Privacy-focused search
