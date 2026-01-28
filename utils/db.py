import os
import json
import pickle
import re
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import pymysql
from pymysql.cursors import DictCursor
import numpy as np
import pandas as pd

from utils.llm import LLMHandler
from utils.rag import EmbeddingGenerator


class DatabaseManager:
    def __init__(self):
        self.host = os.getenv("AIVEN_MYSQL_HOST", "")
        self.port = int(os.getenv("AIVEN_MYSQL_PORT", "3306"))
        self.user = os.getenv("AIVEN_MYSQL_USER", "")
        self.password = os.getenv("AIVEN_MYSQL_PASSWORD", "")
        self.database = os.getenv("AIVEN_MYSQL_DATABASE", "")
        self.ssl_ca_content = os.getenv("AIVEN_MYSQL_SSL_CA", "")
        self.ssl_ca_path = None
        self.llm = LLMHandler()
        self.embedding_gen = EmbeddingGenerator()
        self.conn = None
        self._setup_ssl_cert()

    def _setup_ssl_cert(self):
        if not self.ssl_ca_content:
            return

        # Check if ssl_ca_content is a file path or actual certificate content
        if os.path.exists(self.ssl_ca_content):
            # It's a file path - use it directly
            self.ssl_ca_path = self.ssl_ca_content
            print(f"✅ Using SSL certificate from: {self.ssl_ca_path}")
        else:
            # It's certificate content - write to temp file
            cert_content = self.ssl_ca_content.replace("\\n", "\n")
            
            # Use platform-appropriate temp directory
            if os.name == 'nt':  # Windows
                temp_dir = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), 'chatbot')
                os.makedirs(temp_dir, exist_ok=True)
                self.ssl_ca_path = os.path.join(temp_dir, "aiven_ca.pem")
            else:  # Linux/Docker
                self.ssl_ca_path = "/tmp/aiven_ca.pem"

            with open(self.ssl_ca_path, "w") as f:
                f.write(cert_content)

            if not os.path.exists(self.ssl_ca_path):
                raise RuntimeError("SSL CA certificate file was not created")
            
            print(f"✅ SSL certificate written to: {self.ssl_ca_path}")

    def _get_connection(self):
        if self.conn is None or not self.conn.open:
            ssl_config = None
            if self.ssl_ca_path:
                ssl_config = {
                    "ca": self.ssl_ca_path,
                    "check_hostname": True
                }
            self.conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                ssl=ssl_config,
                cursorclass=DictCursor,
                autocommit=False
            )
        return self.conn

    def _execute(self, query: str, params: tuple = None, fetch: bool = False):
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()
            else:
                conn.commit()

    def _sanitize_name(self, name: str) -> str:
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', str(name))
        if not sanitized:
            sanitized = 'col_unnamed'
        elif sanitized[0].isdigit():
            sanitized = 'col_' + sanitized
        return sanitized[:64]

    def _get_mysql_type(self, dtype: str, sample_values: list) -> str:
        dtype_str = str(dtype).lower()
        if 'int' in dtype_str:
            return 'BIGINT'
        elif 'float' in dtype_str or 'double' in dtype_str:
            return 'DOUBLE'
        elif 'bool' in dtype_str:
            return 'BOOLEAN'
        elif 'datetime' in dtype_str:
            return 'DATETIME'
        elif 'date' in dtype_str:
            return 'DATE'
        else:
            valid_lengths = [len(str(v)) for v in sample_values if v is not None and str(v).strip()]
            max_len = max(valid_lengths, default=255) if valid_lengths else 255
            if max_len > 65535:
                return 'LONGTEXT'
            elif max_len > 255:
                return 'TEXT'
            return f'VARCHAR({min(max(max_len * 2, 50), 500)})'

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        dot = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot / (norm1 * norm2))

    def _build_data_table(self, rows: List[Dict[str, Any]], max_rows: int = 15) -> str:
        if not rows:
            return "## 📊 Data Retrieved (0 rows)\n\n**No matching data found in the database.**"
        
        all_cols = list(rows[0].keys())
        display_cols = all_cols[:10]
        
        header = "| " + " | ".join(display_cols) + " |"
        separator = "| " + " | ".join(["---"] * len(display_cols)) + " |"
        
        table_rows = []
        for row in rows[:max_rows]:
            values = []
            for col in display_cols:
                val = row.get(col, "")
                if isinstance(val, float):
                    val = f"{val:.2f}"
                elif isinstance(val, str) and len(val) > 35:
                    val = val[:32] + "..."
                values.append(str(val))
            table_rows.append("| " + " | ".join(values) + " |")
        
        table = "\n".join([header, separator] + table_rows)
        
        remaining = len(rows) - max_rows
        note = f"\n\n*Showing {min(len(rows), max_rows)} of {len(rows)} rows*" if remaining > 0 else ""
        
        extra_cols = ""
        if len(all_cols) > 10:
            extra_cols = f"\n\n*Additional columns not shown: {', '.join(all_cols[10:])}*"
        
        return f"## 📊 Data Retrieved ({len(rows)} rows)\n\n{table}{note}{extra_cols}"


    def initialize_tables(self):
        self._execute("""
            CREATE TABLE IF NOT EXISTS docs_summary (
                doc_id INT AUTO_INCREMENT PRIMARY KEY,
                doc_name VARCHAR(500) NOT NULL,
                doc_type VARCHAR(50),
                is_structured BOOLEAN DEFAULT FALSE,
                table_name VARCHAR(255),
                schema_info TEXT,
                summary_text TEXT,
                summary_embedding LONGBLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self._execute("""
            CREATE TABLE IF NOT EXISTS unstructured_docs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                doc_id INT NOT NULL,
                doc_name VARCHAR(500) NOT NULL,
                chunk_text TEXT,
                chunk_embedding LONGBLOB,
                page_no INT,
                chunk_index INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self._execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id VARCHAR(100) NOT NULL,
                user_query TEXT,
                final_answer TEXT,
                query_type VARCHAR(50),
                doc_used VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _generate_column_statistics(self, df: pd.DataFrame) -> str:
        stats_parts = []
        
        for col in df.columns:
            col_data = df[col].dropna()
            if len(col_data) == 0:
                continue
            
            dtype_str = str(df[col].dtype).lower()
            
            if 'int' in dtype_str or 'float' in dtype_str or 'double' in dtype_str:
                try:
                    mean_val = col_data.mean()
                    median_val = col_data.median()
                    mode_series = col_data.mode()
                    mode_val = mode_series.iloc[0] if len(mode_series) > 0 else None
                    std_val = col_data.std()
                    min_val = col_data.min()
                    max_val = col_data.max()
                    
                    stats_parts.append(
                        f"Column '{col}' (NUMERICAL): mean={mean_val:.2f}, median={median_val:.2f}, "
                        f"mode={mode_val}, std_dev={std_val:.2f}, min={min_val}, max={max_val}"
                    )
                except Exception:
                    stats_parts.append(f"Column '{col}' (NUMERICAL): statistics unavailable")
            else:
                unique_vals = col_data.unique()
                if len(unique_vals) <= 50:
                    unique_str = ", ".join([str(v)[:50] for v in unique_vals[:50]])
                    stats_parts.append(f"Column '{col}' (CATEGORICAL): unique_values=[{unique_str}]")
                else:
                    sample_vals = ", ".join([str(v)[:50] for v in unique_vals[:10]])
                    stats_parts.append(
                        f"Column '{col}' (TEXT/CATEGORICAL): {len(unique_vals)} unique values, "
                        f"samples=[{sample_vals}...]"
                    )
        
        return "\n".join(stats_parts)

    def ingest_structured_data(self, df: pd.DataFrame, filename: str) -> Dict[str, Any]:
        base_name = re.sub(r'[^a-zA-Z0-9]', '_', os.path.splitext(filename)[0])
        table_name = f"data_{base_name}".lower()[:64]
        
        columns = []
        col_mapping = {}
        has_id_column = False
        
        for col in df.columns:
            safe_col = self._sanitize_name(col)
            col_mapping[col] = safe_col
            
            if safe_col.lower() == 'id':
                has_id_column = True
            
            sample = df[col].dropna().head(100).tolist()
            col_type = self._get_mysql_type(df[col].dtype, sample)
            columns.append(f"`{safe_col}` {col_type}")
        
        schema_info = ", ".join([f"{col_mapping[c]} ({str(df[c].dtype)})" for c in df.columns])
        
        column_statistics = self._generate_column_statistics(df)
        
        try:
            self._execute(f"DROP TABLE IF EXISTS `{table_name}`")
        except:
            pass
        
        if has_id_column:
            create_sql = f"CREATE TABLE `{table_name}` (auto_id INT AUTO_INCREMENT PRIMARY KEY, {', '.join(columns)})"
        else:
            create_sql = f"CREATE TABLE `{table_name}` (id INT AUTO_INCREMENT PRIMARY KEY, {', '.join(columns)})"
        
        self._execute(create_sql)
        
        df_renamed = df.rename(columns=col_mapping)
        
        if len(df_renamed) > 0:
            cols = [f"`{c}`" for c in df_renamed.columns]
            placeholders = ", ".join(["%s"] * len(cols))
            insert_sql = f"INSERT INTO `{table_name}` ({', '.join(cols)}) VALUES ({placeholders})"
            
            conn = self._get_connection()
            batch_size = 1000
            total_rows = len(df_renamed)
            inserted_count = 0
            
            all_values = []
            for idx, row in df_renamed.iterrows():
                values = tuple(None if pd.isna(v) else v for v in row.values)
                all_values.append(values)
            
            conn.begin()
            try:
                with conn.cursor() as cursor:
                    for i in range(0, len(all_values), batch_size):
                        batch = all_values[i:i + batch_size]
                        cursor.executemany(insert_sql, batch)
                        inserted_count += len(batch)
                        print(f"📦 Inserted batch {i//batch_size + 1}: {inserted_count}/{total_rows} rows")
                conn.commit()
                print(f"✅ Inserted {inserted_count} rows into {table_name}")
            except Exception as e:
                conn.rollback()
                print(f"❌ Transaction failed, rolled back: {str(e)}")
                raise
        
        summary_text = f"Table '{table_name}' with {len(df)} rows.\n\nColumn Statistics:\n{column_statistics}\n\nSchema: {schema_info}"
        summary_embedding = self.embedding_gen.generate_embedding(summary_text)
        summary_blob = pickle.dumps(summary_embedding)
        
        self._execute("""
            INSERT INTO docs_summary (doc_name, doc_type, is_structured, table_name, schema_info, summary_text, summary_embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (filename, "STRUCTURED", True, table_name, schema_info, summary_text, summary_blob))
        
        return {
            "doc_name": filename,
            "table_name": table_name,
            "row_count": len(df),
            "schema": schema_info
        }

    def ingest_unstructured_data(self, chunks: List[Dict[str, Any]], filename: str) -> Dict[str, Any]:
        """Ingest unstructured document chunks with robust error handling"""
        if not chunks:
            return {"doc_name": filename, "chunks": 0}
        
        try:
            print(f"📝 Ingesting {len(chunks)} chunks for {filename}")
            
            # Generate summary from all chunks
            all_texts = [c.get("text", "") for c in chunks if c.get("text", "").strip()]
            if all_texts:
                full_text = " ".join([t[:300] for t in all_texts[:20]])
            else:
                full_text = filename
            
            summary_text, _ = self.llm.summarize(full_text, filename)
            summary_embedding = self.embedding_gen.generate_embedding(summary_text)
            summary_blob = pickle.dumps(summary_embedding)
            
            self._execute("""
                INSERT INTO docs_summary (doc_name, doc_type, is_structured, summary_text, summary_embedding)
                VALUES (%s, %s, %s, %s, %s)
            """, (filename, "UNSTRUCTURED", False, summary_text, summary_blob))
            
            # Get the inserted doc_id
            doc_id_result = self._execute("SELECT LAST_INSERT_ID() as doc_id", fetch=True)
            doc_id = doc_id_result[0]["doc_id"] if doc_id_result else None
            
            if not doc_id:
                # Fallback: query the database
                recent = self._execute("SELECT doc_id FROM docs_summary WHERE doc_name = %s ORDER BY created_at DESC LIMIT 1", 
                                      (filename,), fetch=True)
                doc_id = recent[0]["doc_id"] if recent else 0
            
            print(f"📌 Document ID: {doc_id}")
            
            # Generate embeddings for all chunks
            texts = [c.get("text", "") for c in chunks]
            embeddings = self.embedding_gen.generate_embeddings(texts)
            
            # Ensure we have embeddings for all chunks
            if len(embeddings) != len(chunks):
                print(f"⚠️  Generated {len(embeddings)} embeddings for {len(chunks)} chunks")
                while len(embeddings) < len(chunks):
                    embeddings.append(np.zeros(768))
            
            # Batch insert chunks
            inserted_count = 0
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                try:
                    if embedding is None or (isinstance(embedding, np.ndarray) and embedding.size == 0):
                        embedding = np.zeros(768)
                    embedding_blob = pickle.dumps(embedding)
                    self._execute("""
                        INSERT INTO unstructured_docs (doc_id, doc_name, chunk_text, chunk_embedding, page_no, chunk_index)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        doc_id,
                        filename,
                        chunk.get("text", "")[:5000],
                        embedding_blob,
                        chunk.get("page_num", 1),
                        i
                    ))
                    inserted_count += 1
                except Exception as e:
                    print(f"❌ Error inserting chunk {i}: {str(e)}")
                    continue
            
            print(f"✅ Inserted {inserted_count}/{len(chunks)} chunks")
            return {
                "doc_name": filename,
                "doc_id": doc_id,
                "chunks": inserted_count
            }
        except Exception as e:
            print(f"❌ Error in ingest_unstructured_data: {str(e)}")
            raise

    def select_relevant_documents(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        query_embedding = self.embedding_gen.generate_query_embedding(query)
        
        rows = self._execute("""
            SELECT doc_id, doc_name, doc_type, is_structured, table_name, schema_info, summary_text, summary_embedding
            FROM docs_summary
        """, fetch=True)
        
        if not rows:
            return []
        
        scored_docs = []
        for row in rows:
            if row["summary_embedding"]:
                doc_embedding = pickle.loads(bytes(row["summary_embedding"]))
                score = self._cosine_similarity(query_embedding, doc_embedding)
                scored_docs.append({
                    "doc_id": row["doc_id"],
                    "doc_name": row["doc_name"],
                    "doc_type": row["doc_type"],
                    "is_structured": row["is_structured"],
                    "table_name": row["table_name"],
                    "schema_info": row["schema_info"],
                    "summary": row["summary_text"],
                    "score": score
                })
        
        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        return scored_docs[:top_k]

    def route_query(self, query: str, relevant_docs: List[Dict[str, Any]]) -> str:
        if not relevant_docs:
            return "none"
        
        structured_score = 0
        unstructured_score = 0
        
        for doc in relevant_docs:
            if doc["is_structured"]:
                structured_score += doc["score"]
            else:
                unstructured_score += doc["score"]
        
        sql_keywords = ["count", "sum", "average", "total", "how many", "list all", "show all", "maximum", "minimum", "group by", "top", "highest", "lowest"]
        query_lower = query.lower()
        
        for kw in sql_keywords:
            if kw in query_lower:
                structured_score += 0.3
        
        if structured_score > unstructured_score and structured_score > 0.3:
            return "structured"
        elif unstructured_score > 0.2:
            return "unstructured"
        elif structured_score > 0:
            return "structured"
        else:
            return "none"
    
    def is_time_sensitive_query(self, query: str) -> bool:
        """Check if query requires live/external data and should skip database"""
        time_sensitive_keywords = [
            "cricket", "match", "live", "current", "today", "score", "now",
            "latest news", "trending", "viral", "breaking", "update",
            "weather", "stock", "price today", "current price",
            "happening now", "right now", "this moment", "real-time",
            "ongoing", "in progress", "at the moment"
        ]
        
        query_lower = query.lower()
        
        for keyword in time_sensitive_keywords:
            if keyword in query_lower:
                print(f"🌐 Time-sensitive keyword detected: '{keyword}' - Routing to web")
                return True
        
        return False
    
    def check_intent_mismatch(self, query: str, rows: List[Dict[str, Any]]) -> bool:
        """Check if returned data domain mismatches the question intent"""
        if not rows or len(rows) == 0:
            return False  # No data to check
        
        # Extract key domain terms from query
        query_lower = query.lower()
        
        # Domain-specific keywords that indicate specific intent
        domain_indicators = {
            "cricket": ["cricket", "bat", "ball", "wicket", "run", "over", "innings"],
            "football": ["football", "soccer", "goal", "penalty", "striker"],
            "weather": ["weather", "temperature", "rain", "forecast", "climate"],
            "stock": ["stock", "share", "market", "trading", "nasdaq", "dow"],
            "news": ["news", "article", "headline", "report", "journalist"],
            "product": ["product", "item", "price", "buy", "sell", "inventory"],
        }
        
        # Check if query has strong domain intent
        detected_domain = None
        for domain, keywords in domain_indicators.items():
            if any(kw in query_lower for kw in keywords):
                detected_domain = domain
                break
        
        if not detected_domain:
            return False  # No strong domain detected, accept results
        
        # Check if any row data contains domain-related terms
        row_text = " ".join([str(v).lower() for row in rows[:5] for v in row.values()])
        
        domain_match = any(kw in row_text for kw in domain_indicators[detected_domain])
        
        if not domain_match:
            print(f"⚠️  Intent mismatch: Query about '{detected_domain}' but data doesn't match")
            return True  # Mismatch detected
        
        return False  # Data matches intent

    def validate_sql(self, sql: str) -> Tuple[bool, str]:
        """Validate and sanitize SQL - extract pure SQL from LLM response"""
        if not sql or not sql.strip():
            return False, "Empty SQL query"
        
        sql = sql.strip()
        
        # Extract SQL from code blocks if present
        if "```" in sql:
            lines = sql.split("\n")
            sql_lines = []
            in_code = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_code = not in_code
                    continue
                if in_code:
                    sql_lines.append(line)
            sql = "\n".join(sql_lines).strip()
        
        # Remove "sql" prefix if present
        if sql.lower().startswith("sql"):
            sql = sql[3:].strip()
        
        # Extract only the SQL statement - stop at first semicolon
        if ";" in sql:
            sql = sql.split(";")[0].strip() + ";"
        
        # Check if it contains natural language (multiple sentences or explanations)
        # SQL should be a single statement, not paragraphs
        lines = [l.strip() for l in sql.split("\n") if l.strip()]
        
        # If more than 5 lines or contains explanation keywords, it's likely contaminated
        explanation_keywords = ["this query", "the above", "note that", "explanation", "because", "in order to", "we use", "i have", "here is"]
        for line in lines:
            line_lower = line.lower()
            for kw in explanation_keywords:
                if kw in line_lower and not line_lower.startswith("select"):
                    return False, "SQL contains natural language explanation - regeneration needed"
        
        sql_upper = sql.strip().upper()
        
        # Must start with SELECT
        if not sql_upper.startswith("SELECT"):
            return False, "Only SELECT queries are allowed"
        
        # Check for dangerous keywords
        dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE"]
        for keyword in dangerous:
            if keyword in sql_upper:
                return False, f"Dangerous keyword '{keyword}' detected"
        
        # Check for multiple queries (UNION, multiple SELECT, OR between queries)
        if "UNION" in sql_upper:
            return False, "UNION queries are not allowed"
        
        # Check for OR followed by SELECT (invalid pattern)
        if re.search(r'\bOR\s+SELECT\b', sql_upper):
            return False, "Multiple queries with OR are not allowed - use single query with AND/OR in WHERE clause"
        
        # Count SELECT statements - should only be 1
        select_count = sql_upper.count("SELECT")
        if select_count > 1:
            return False, f"Multiple SELECT statements detected ({select_count}) - only one query allowed"
        
        return True, "Valid"

    def generate_sql_with_llm(self, question: str, tables_info: str, chat_context: str = "") -> str:
        system_prompt = """You are a professional MySQL query generator. Output ONLY the SQL query.

====================
OUTPUT FORMAT (CRITICAL!)
====================
Your response MUST be the raw SQL query only. Nothing else.

WRONG outputs (DO NOT do this):
- ```sql SELECT ... ```
- Here is the query: SELECT ...
- To answer this, I will: SELECT ...

CORRECT output:
SELECT * FROM `table_name` WHERE condition LIMIT 100;

====================
ABSOLUTE CONSTRAINTS
====================
1. ALWAYS use SELECT * FROM pattern - retrieve ALL columns
2. Output must start with SELECT and contain only ONE SQL SELECT statement
3. Do not include explanations, comments, markdown, or extra text
4. Use only the tables and columns explicitly listed in the schema
5. Do not invent column names, table names, or enum values
6. Use proper MySQL syntax with backticks for table and column names
7. Always add LIMIT clause (default LIMIT 100)
8. NO UNION or multiple SELECT statements

====================
SEMANTIC INTERPRETATION (CRITICAL!)
====================
IMPORTANT: The 'gender' column typically contains: [Men, Women, Unisex]
   - There is usually NO 'Kids' or 'Children' gender value!
   - NEVER use WHERE gender = 'Kids' unless you see it in the sample data!

When interpreting natural language:
1. "kids" / "children" / "youth" → Use SIZE filter for smaller sizes (e.g., size <= 7)
2. "adults" → Use SIZE filter for larger sizes (e.g., size >= 9)
3. "formal" → Look for 'Formal' in category-related columns
4. "casual" → Look for 'Casual' in category-related columns
5. "top rated" / "best" → ORDER BY rating column DESC
6. "expensive" / "costliest" → ORDER BY price DESC
7. "cheap" / "affordable" → ORDER BY price ASC
8. "latest" / "new" → ORDER BY launch_year/created_at DESC

====================
SELF-CHECK BEFORE OUTPUT
====================
Before producing the final SQL, verify:
- Every column used exists in the schema
- Every literal value used is valid for that column (check sample data!)
- If using 'gender' column, value MUST be in the sample data
- The query answers the question directly
- No explanatory text is included"""

        context_section = ""
        if chat_context:
            context_section = f"""Previous conversation context:
{chat_context}

"""

        user_prompt = f"""{context_section}====================
DATABASE SCHEMA & SAMPLE DATA
====================
{tables_info}

====================
USER QUESTION
====================
{question}

Generate the SQL query (raw SQL only, no explanations):"""

        response, _ = self.llm._call_llm(system_prompt, user_prompt)
        
        sql = response.strip()
        
        # Clean up markdown code blocks
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql_lines = []
            in_code = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_code = not in_code
                    continue
                if in_code:
                    sql_lines.append(line)
            sql = "\n".join(sql_lines).strip()
        
        # Remove "sql" prefix if present
        if sql.lower().startswith("sql"):
            sql = sql[3:].strip()
        
        # Extract only the SELECT statement - take first line or up to semicolon
        if "SELECT" in sql.upper():
            # Find where SELECT starts
            select_pos = sql.upper().find("SELECT")
            sql = sql[select_pos:]
        
        # Take only first statement (up to first semicolon)
        if ";" in sql:
            sql = sql.split(";")[0].strip()
        
        # Ensure it ends with semicolon
        sql = sql.rstrip(";") + ";"
        
        return sql

    def execute_structured_query(self, query: str, relevant_docs: List[Dict[str, Any]], 
                                  chat_context: str = "") -> Dict[str, Any]:
        structured_docs = [d for d in relevant_docs if d["is_structured"]]
        
        if not structured_docs:
            return {"answer": "No structured data found.", "sql": "", "data": [], "full_data": [], "retry_attempted": False}
        
        tables_info_parts = []
        for d in structured_docs:
            table_name = d['table_name']
            summary = d.get('summary', '')
            try:
                sample_rows = self._execute(f"SELECT * FROM `{table_name}` LIMIT 5", fetch=True)
                sample_str = ""
                if sample_rows:
                    sample_str = "\nTop 5 Sample Rows:\n" + "\n".join([str(row) for row in sample_rows])
            except:
                sample_str = ""
            
            tables_info_parts.append(f"Table `{table_name}`:\n{summary}{sample_str}")
        
        tables_info = "\n\n".join(tables_info_parts)
        
        # PASS 1: Normal SQL generation
        sql = self.generate_sql_with_llm(query, tables_info, chat_context)
        
        if not sql or sql == ";":
            return {"answer": "Could not generate SQL query.", "sql": "", "data": [], "full_data": [], "retry_attempted": False}
        
        # GUARD 2: SQL Sanitization - validate and regenerate if needed
        is_valid, validation_msg = self.validate_sql(sql)
        if not is_valid:
            if "natural language" in validation_msg.lower() or "explanation" in validation_msg.lower():
                print(f"⚠️  SQL contains natural language. Regenerating...")
                # Try one more time with stricter prompt
                sql = self.generate_sql_with_llm(query, tables_info, chat_context)
                is_valid, validation_msg = self.validate_sql(sql)
                if not is_valid:
                    return {"answer": f"Query rejected after retry: {validation_msg}", "sql": sql, "data": [], "full_data": [], "retry_attempted": False}
            else:
                return {"answer": f"Query rejected: {validation_msg}", "sql": sql, "data": [], "full_data": [], "retry_attempted": False}
        
        try:
            rows = self._execute(sql, fetch=True)
            rows = list(rows) if rows else []
            
            # PASS 2: If 0 rows, retry with smarter reinterpretation
            if len(rows) == 0:
                print(f"⚠️  Pass-1 returned 0 rows. Attempting smart reinterpretation...")
                
                retry_sql = self._generate_retry_sql(query, tables_info, sql, chat_context)
                
                if retry_sql and retry_sql != sql:
                    is_valid_retry, _ = self.validate_sql(retry_sql)
                    if is_valid_retry:
                        try:
                            rows = self._execute(retry_sql, fetch=True)
                            rows = list(rows) if rows else []
                            if len(rows) > 0:
                                print(f"✅ Pass-2 successful! Found {len(rows)} rows")
                                sql = retry_sql  # Use the retry SQL
                            else:
                                print(f"❌ Pass-2 also returned 0 rows")
                        except:
                            print(f"❌ Pass-2 SQL execution failed")
            
            # If still 0 rows after 2 passes, return indication for web scraping
            if len(rows) == 0:
                return {
                    "answer": "", 
                    "sql": sql, 
                    "data": [], 
                    "full_data": [], 
                    "retry_attempted": True,
                    "needs_web_fallback": True
                }
            
            # INTENT MISMATCH CHECK: Verify data domain matches query intent
            if self.check_intent_mismatch(query, rows):
                print(f"🌐 Data domain doesn't match query intent - routing to web")
                return {
                    "answer": "",
                    "sql": sql,
                    "data": [],
                    "full_data": [],
                    "retry_attempted": True,
                    "needs_web_fallback": True
                }
            
            data_section = self._build_data_table(rows)
            
            chat_history = []
            if chat_context:
                lines = chat_context.strip().split('\n')
                for line in lines:
                    if line.startswith('User: '):
                        chat_history.append({"role": "user", "content": line[6:]})
                    elif line.startswith('Assistant: '):
                        chat_history.append({"role": "assistant", "content": line[11:]})
            
            llm_analysis, _ = self.llm.structured_db_retrieval(
                query, 
                rows, 
                f"Tables: {tables_info}",
                chat_history
            )
            
            full_answer = f"{data_section}\n\n{llm_analysis}"
            
            return {"answer": full_answer, "sql": sql, "data": rows[:50], "full_data": rows, "retry_attempted": len(rows) > 0}
            
        except Exception as e:
            return {"answer": f"Query execution error: {str(e)}", "sql": sql, "data": [], "full_data": [], "retry_attempted": False}

    def _generate_retry_sql(self, question: str, tables_info: str, failed_sql: str, chat_context: str = "") -> str:
        """Generate a smarter SQL query when first attempt returns 0 rows"""
        system_prompt = """You are an expert at reinterpreting failed SQL queries.
The previous query returned 0 rows. Generate a NEW query with relaxed constraints.

OUTPUT FORMAT: Raw SQL query ONLY. No explanations, no markdown, no comments.

COMMON FAILURES TO FIX:
1. Used gender = 'Kids' → FIX: Use size <= 7 instead (gender only has Men/Women/Unisex)
2. Used non-existent category → FIX: Use LIKE '%keyword%' on description/name
3. Too restrictive WHERE → FIX: Remove some conditions
4. Wrong column name → FIX: Check schema for correct name

REINTERPRETATION RULES:
- "kids"/"children" → WHERE size <= 7 (NOT gender = 'Kids')
- "adult" → WHERE size >= 9
- "top rated"/"best" → ORDER BY rating DESC
- "expensive" → ORDER BY price DESC
- "cheap" → ORDER BY price ASC
- Exact match failed → Use LIKE '%value%'

CONSTRAINTS:
- ALWAYS use SELECT * FROM pattern
- Only ONE SQL query
- No UNION, no multiple SELECTs
- Add LIMIT 100"""

        context_section = ""
        if chat_context:
            context_section = f"""Previous conversation:
{chat_context}

"""

        user_prompt = f"""{context_section}Schema:
{tables_info}

Original question: {question}

Failed SQL: {failed_sql}

Generate improved SQL (raw query only):"""

        response, _ = self.llm._call_llm(system_prompt, user_prompt)
        
        sql = response.strip()
        
        # Clean up markdown
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql_lines = []
            in_code = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_code = not in_code
                    continue
                if in_code:
                    sql_lines.append(line)
            sql = "\n".join(sql_lines).strip()
        
        if sql.lower().startswith("sql"):
            sql = sql[3:].strip()
        
        # Extract SELECT statement
        if "SELECT" in sql.upper():
            select_pos = sql.upper().find("SELECT")
            sql = sql[select_pos:]
        
        if ";" in sql:
            sql = sql.split(";")[0].strip()
        
        sql = sql.rstrip(";") + ";"
        
        return sql

    def execute_unstructured_query(self, query: str, relevant_docs: List[Dict[str, Any]], 
                                    chat_context: str = "", top_k: int = 5) -> Dict[str, Any]:
        unstructured_docs = [d for d in relevant_docs if not d["is_structured"]]
        
        if not unstructured_docs:
            return {"answer": "No unstructured documents found.", "chunks": []}
        
        doc_ids = [d["doc_id"] for d in unstructured_docs]
        placeholders = ",".join(["%s"] * len(doc_ids))
        
        rows = self._execute(f"""
            SELECT doc_id, doc_name, chunk_text, chunk_embedding, page_no
            FROM unstructured_docs
            WHERE doc_id IN ({placeholders})
        """, tuple(doc_ids), fetch=True)
        
        if not rows:
            return {"answer": "No content found in documents.", "chunks": []}
        
        query_embedding = self.embedding_gen.generate_query_embedding(query)
        
        scored_chunks = []
        for row in rows:
            if row["chunk_embedding"]:
                chunk_embedding = pickle.loads(bytes(row["chunk_embedding"]))
                score = self._cosine_similarity(query_embedding, chunk_embedding)
                scored_chunks.append({
                    "text": row["chunk_text"],
                    "source": row["doc_name"],
                    "page_num": row["page_no"],
                    "score": score
                })
        
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        top_chunks = scored_chunks[:top_k]
        
        if not top_chunks:
            return {"answer": "No relevant content found.", "chunks": []}
        
        chat_history = []
        if chat_context:
            chat_history = [{"role": "system", "content": chat_context}]
        
        answer, _ = self.llm.rag_retrieval(query, top_chunks, chat_history)
        
        return {"answer": answer, "chunks": top_chunks}

    def get_chat_context(self, session_id: str, limit: int = 5) -> str:
        rows = self._execute("""
            SELECT user_query, final_answer 
            FROM chat_history 
            WHERE session_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (session_id, limit), fetch=True)
        
        if not rows:
            return ""
        
        rows = list(reversed(rows))
        context_parts = []
        for row in rows:
            context_parts.append(f"User: {row['user_query'][:200]}")
            context_parts.append(f"Assistant: {row['final_answer'][:300]}")
        
        return "\n".join(context_parts)

    def save_chat(self, session_id: str, user_query: str, final_answer: str, 
                  query_type: str = "", doc_used: str = ""):
        self._execute("""
            INSERT INTO chat_history (session_id, user_query, final_answer, query_type, doc_used)
            VALUES (%s, %s, %s, %s, %s)
        """, (session_id, user_query, final_answer, query_type, doc_used))

    def process_user_query(self, session_id: str, query: str) -> Dict[str, Any]:
        """Main entry point for processing user queries with multi-question support"""
        from utils.web_scraper import scrape_web_content
        
        # Split into multiple questions if needed
        questions = self.llm.split_questions(query)
        
        if len(questions) > 1:
            print(f"📝 Detected {len(questions)} questions")
            # Process each question independently
            all_answers = []
            combined_result = {
                "answer": "",
                "source": "multiple",
                "docs": [],
                "sql": None,
                "data": [],
                "full_data": [],
                "chunks": [],
                "web_sources": []
            }
            
            for i, q in enumerate(questions):
                print(f"Processing question {i+1}/{len(questions)}: {q[:50]}...")
                result = self._process_single_question(session_id, q, scrape_web_content)
                all_answers.append(f"**Q{i+1}:** {q}\n\n{result['answer']}")
                
                # Aggregate results
                if result.get("docs"):
                    combined_result["docs"].extend(result["docs"])
                if result.get("sql"):
                    combined_result["sql"] = result["sql"]  # Keep last SQL
                if result.get("full_data"):
                    combined_result["full_data"].extend(result["full_data"])
                if result.get("chunks"):
                    combined_result["chunks"].extend(result["chunks"])
                if result.get("web_sources"):
                    combined_result["web_sources"].extend(result["web_sources"])
            
            # Combine all answers
            combined_result["answer"] = "\n\n---\n\n".join(all_answers)
            
            # Save combined result
            self.save_chat(session_id, query, combined_result["answer"], "multiple", "Multiple sources")
            
            return combined_result
        else:
            # Single question - process normally
            return self._process_single_question(session_id, query, scrape_web_content)
    
    def _process_single_question(self, session_id: str, query: str, scrape_web_content) -> Dict[str, Any]:
        """Process a single question through the pipeline"""
        
        chat_context = self.get_chat_context(session_id, limit=5)
        
        relevant_docs = self.select_relevant_documents(query, top_k=3)
        
        # Check if documents are relevant enough
        if not relevant_docs or (relevant_docs and max([d.get("score", 0) for d in relevant_docs]) < 0.3):
            # No relevant docs - go straight to web
            return self._web_search_fallback(session_id, query, scrape_web_content, "No relevant documents found")
        
        # GUARD 1: LLM-based intelligent routing decision
        # Build schema summary for LLM
        schema_summary = ""
        if relevant_docs:
            schema_parts = []
            for doc in relevant_docs[:3]:
                if doc.get("is_structured") and doc.get("table_name"):
                    try:
                        # Get column info
                        table_name = doc["table_name"]
                        sample = self._execute(f"SELECT * FROM `{table_name}` LIMIT 1", fetch=True)
                        if sample:
                            columns = list(sample[0].keys())
                            schema_parts.append(f"Table: {table_name}\nColumns: {', '.join(columns)}")
                    except:
                        pass
                else:
                    schema_parts.append(f"Document: {doc.get('doc_name', 'Unknown')}\nType: Unstructured text")
            
            schema_summary = "\n\n".join(schema_parts) if schema_parts else "No structured schema available"
        
        # Ask LLM if web scraping is needed
        needs_web, reason = self.llm.should_use_web_scraping(query, schema_summary)
        
        if needs_web:
            print(f"🌐 LLM Decision: WEB - {reason}")
            return self._web_search_fallback(session_id, query, scrape_web_content, f"LLM routing: {reason}")
        else:
            print(f"💾 LLM Decision: DATABASE - {reason}")
        
        query_type = self.route_query(query, relevant_docs)
        
        if query_type == "structured":
            result = self.execute_structured_query(query, relevant_docs, chat_context)
            
            # Check if we need web fallback (0 rows after 2 passes)
            if result.get("needs_web_fallback"):
                print(f"🌐 Both SQL attempts failed. Falling back to web search...")
                return self._web_search_fallback(session_id, query, scrape_web_content, "Database query returned no results")
            
            doc_names = ", ".join([d["doc_name"] for d in relevant_docs if d["is_structured"]])
            self.save_chat(session_id, query, result["answer"], "structured", doc_names)
            return {
                "answer": result["answer"],
                "source": "structured",
                "sql": result.get("sql", ""),
                "data": result.get("data", []),
                "full_data": result.get("full_data", []),
                "docs": relevant_docs
            }
        
        elif query_type == "unstructured":
            result = self.execute_unstructured_query(query, relevant_docs, chat_context)
            
            # If no relevant chunks found, try web
            if not result.get("chunks") or len(result.get("chunks", [])) == 0:
                print(f"🌐 No relevant chunks found. Falling back to web search...")
                return self._web_search_fallback(session_id, query, scrape_web_content, "No relevant content in documents")
            
            doc_names = ", ".join([d["doc_name"] for d in relevant_docs if not d["is_structured"]])
            self.save_chat(session_id, query, result["answer"], "unstructured", doc_names)
            return {
                "answer": result["answer"],
                "source": "unstructured",
                "chunks": result.get("chunks", []),
                "docs": relevant_docs
            }
        
        else:
            # Unknown query type - try web
            return self._web_search_fallback(session_id, query, scrape_web_content, "Could not determine query type")
    
    def _web_search_fallback(self, session_id: str, query: str, scrape_web_content, reason: str) -> Dict[str, Any]:
        """Fallback to web search when other methods fail"""
        try:
            print(f"🌐 Attempting web search for: {query}")
            web_result = scrape_web_content(query, llm=self.llm)
            
            print(f"🔍 Web result success: {web_result.get('success', False)}")
            print(f"🔍 Search results count: {len(web_result.get('search_results', []))}")
            print(f"🔍 Detailed content length: {len(web_result.get('detailed_content', ''))}")
            
            if web_result.get("error"):
                print(f"❌ Web scraping error: {web_result['error']}")
            
            if web_result.get("success"):
                web_context = ""
                if web_result.get("detailed_content"):
                    web_context = web_result["detailed_content"]
                    print(f"✅ Using detailed content ({len(web_context)} chars)")
                elif web_result.get("search_results"):
                    web_context = "\n\n".join([
                        f"- {r.get('title', 'No title')}: {r.get('snippet', 'No snippet')}" 
                        for r in web_result["search_results"][:3]
                    ])
                    print(f"✅ Using search snippets ({len(web_context)} chars)")
                
                if web_context and len(web_context.strip()) > 10:
                    print(f"🤖 Generating answer from web content...")
                    answer_text, _ = self.llm.web_retrieval(query, web_context)
                    final_answer = f"🌐 **Source: Web Search** ({reason})\n\n{answer_text}"
                    
                    if web_result.get("search_results"):
                        sources = "\n\n**References:**\n" + "\n".join([
                            f"- [{r.get('title', 'Source')}]({r.get('link', '#')})" 
                            for r in web_result["search_results"][:3]
                        ])
                        final_answer += sources
                    
                    self.save_chat(session_id, query, final_answer, "web_search", "Web")
                    print(f"✅ Web search successful!")
                    return {
                        "answer": final_answer, 
                        "source": "web", 
                        "docs": [],
                        "web_sources": web_result.get("search_results", [])[:3]
                    }
                else:
                    print(f"⚠️ Web context is empty or too short")
            else:
                print(f"❌ Web search returned success=False")
                
        except Exception as e:
            print(f"❌ Web scraping exception: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # If web also fails
        answer = f"🔍 **{reason}**\n\nI attempted to search the web for this information, but encountered an issue. This could be due to:\n- Network connectivity\n- Rate limiting from search services\n- No relevant results found\n\nPlease try:\n1. Rephrasing your question\n2. Being more specific\n3. Trying again in a moment"
        self.save_chat(session_id, query, answer, "none", "")
        return {"answer": answer, "source": "none", "docs": []}

    def get_all_documents(self) -> List[Dict[str, Any]]:
        rows = self._execute("""
            SELECT doc_id, doc_name, doc_type, is_structured, table_name, summary_text, created_at
            FROM docs_summary
            ORDER BY created_at DESC
        """, fetch=True)
        return list(rows) if rows else []

    def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self._execute("""
            SELECT user_query, final_answer, query_type, created_at
            FROM chat_history
            WHERE session_id = %s
            ORDER BY created_at ASC
        """, (session_id,), fetch=True)
        return list(rows) if rows else []

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        rows = self._execute("""
            SELECT session_id, 
                   MIN(created_at) as started_at,
                   MAX(created_at) as last_activity,
                   COUNT(*) as message_count
            FROM chat_history
            GROUP BY session_id
            ORDER BY last_activity DESC
        """, fetch=True)
        return list(rows) if rows else []

    def delete_chat_session(self, session_id: str):
        self._execute("""
            DELETE FROM chat_history WHERE session_id = %s
        """, (session_id,))

    def delete_all_data(self):
        self._execute("DELETE FROM chat_history")
        self._execute("DELETE FROM unstructured_docs")
        self._execute("DELETE FROM docs_summary")
        
        tables = self._execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = %s AND table_name LIKE 'data_%%'
        """, (self.database,), fetch=True)
        
        if tables:
            for t in tables:
                try:
                    self._execute(f"DROP TABLE IF EXISTS `{t['table_name']}`")
                except:
                    pass

    def close(self):
        if self.conn and self.conn.open:
            self.conn.close()
