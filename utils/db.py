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
        if self.ssl_ca_content:
            if os.path.isfile(self.ssl_ca_content):
                self.ssl_ca_path = self.ssl_ca_content
            else:
                cert_content = self.ssl_ca_content.replace("\\n", "\n")
                fd, self.ssl_ca_path = tempfile.mkstemp(suffix=".pem")
                with os.fdopen(fd, 'w') as f:
                    f.write(cert_content)

    def _get_connection(self):
        if self.conn is None or not self.conn.open:
            ssl_config = None
            if self.ssl_ca_path:
                ssl_config = {"ca": self.ssl_ca_path}
            self.conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                ssl=ssl_config,
                cursorclass=DictCursor,
                autocommit=True
            )
        return self.conn

    def _execute(self, query: str, params: tuple = None, fetch: bool = False):
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()

    def _sanitize_name(self, name: str) -> str:
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', str(name))
        if sanitized[0].isdigit():
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
            max_len = max((len(str(v)) for v in sample_values if v is not None), default=255)
            if max_len > 65535:
                return 'LONGTEXT'
            elif max_len > 255:
                return 'TEXT'
            return f'VARCHAR({min(max_len * 2, 500)})'

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        dot = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot / (norm1 * norm2))

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

    def ingest_structured_data(self, df: pd.DataFrame, filename: str) -> Dict[str, Any]:
        base_name = re.sub(r'[^a-zA-Z0-9]', '_', os.path.splitext(filename)[0])
        table_name = f"data_{base_name}".lower()[:64]
        
        columns = []
        col_mapping = {}
        for col in df.columns:
            safe_col = self._sanitize_name(col)
            col_mapping[col] = safe_col
            sample = df[col].dropna().head(100).tolist()
            col_type = self._get_mysql_type(df[col].dtype, sample)
            columns.append(f"`{safe_col}` {col_type}")
        
        schema_info = ", ".join([f"{col_mapping[c]} ({str(df[c].dtype)})" for c in df.columns])
        
        try:
            self._execute(f"DROP TABLE IF EXISTS `{table_name}`")
        except:
            pass
        
        create_sql = f"CREATE TABLE `{table_name}` (id INT AUTO_INCREMENT PRIMARY KEY, {', '.join(columns)})"
        self._execute(create_sql)
        
        df_renamed = df.rename(columns=col_mapping)
        
        if len(df_renamed) > 0:
            cols = [f"`{c}`" for c in df_renamed.columns]
            placeholders = ", ".join(["%s"] * len(cols))
            insert_sql = f"INSERT INTO `{table_name}` ({', '.join(cols)}) VALUES ({placeholders})"
            
            conn = self._get_connection()
            with conn.cursor() as cursor:
                for _, row in df_renamed.iterrows():
                    values = tuple(None if pd.isna(v) else v for v in row.values)
                    try:
                        cursor.execute(insert_sql, values)
                    except:
                        pass
            conn.commit()
        
        summary_text = f"Structured table '{table_name}' with {len(df)} rows. Schema: {schema_info}. Sample columns: {', '.join(list(df.columns)[:5])}"
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
        if not chunks:
            return {"doc_name": filename, "chunks": 0}
        
        full_text = " ".join([c.get("text", "")[:500] for c in chunks[:10]])
        summary_text, _ = self.llm.summarize(full_text, filename)
        summary_embedding = self.embedding_gen.generate_embedding(summary_text)
        summary_blob = pickle.dumps(summary_embedding)
        
        self._execute("""
            INSERT INTO docs_summary (doc_name, doc_type, is_structured, summary_text, summary_embedding)
            VALUES (%s, %s, %s, %s, %s)
        """, (filename, "UNSTRUCTURED", False, summary_text, summary_blob))
        
        doc_id_result = self._execute("SELECT LAST_INSERT_ID() as doc_id", fetch=True)
        doc_id = doc_id_result[0]["doc_id"] if doc_id_result else 0
        
        texts = [c.get("text", "") for c in chunks]
        embeddings = self.embedding_gen.generate_embeddings(texts)
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            embedding_blob = pickle.dumps(embedding)
            self._execute("""
                INSERT INTO unstructured_docs (doc_id, doc_name, chunk_text, chunk_embedding, page_no, chunk_index)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                doc_id,
                filename,
                chunk.get("text", ""),
                embedding_blob,
                chunk.get("page_num", 1),
                i
            ))
        
        return {
            "doc_name": filename,
            "doc_id": doc_id,
            "chunks": len(chunks)
        }

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

    def validate_sql(self, sql: str) -> Tuple[bool, str]:
        sql_upper = sql.strip().upper()
        
        if not sql_upper.startswith("SELECT"):
            return False, "Only SELECT queries are allowed"
        
        dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"]
        for keyword in dangerous:
            if keyword in sql_upper:
                return False, f"Dangerous keyword '{keyword}' detected"
        
        return True, "Valid"

    def generate_sql_with_llm(self, question: str, tables_info: str) -> str:
        system_prompt = """You are an expert MySQL query generator. Given a user question and table schema, generate a valid MySQL SELECT query.

RULES:
1. Generate ONLY the SQL query, no explanation
2. Use only SELECT statements
3. Use proper MySQL syntax
4. Use backticks for table and column names
5. Handle NULL values appropriately
6. Use LIMIT for large result sets"""

        user_prompt = f"""Tables available:
{tables_info}

User question: {question}

Generate the SQL query:"""

        response, _ = self.llm._call_llm(system_prompt, user_prompt)
        
        sql = response.strip()
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql_lines = []
            in_code = False
            for line in lines:
                if line.startswith("```"):
                    in_code = not in_code
                    continue
                if in_code or not line.startswith("```"):
                    sql_lines.append(line)
            sql = "\n".join(sql_lines)
        
        sql = sql.strip()
        if sql.lower().startswith("sql"):
            sql = sql[3:].strip()
        
        sql = sql.rstrip(";") + ";"
        
        return sql

    def execute_structured_query(self, query: str, relevant_docs: List[Dict[str, Any]], 
                                  chat_context: str = "") -> Dict[str, Any]:
        structured_docs = [d for d in relevant_docs if d["is_structured"]]
        
        if not structured_docs:
            return {"answer": "No structured data found.", "sql": "", "data": []}
        
        tables_info = "\n".join([
            f"Table `{d['table_name']}`: {d['schema_info']}" 
            for d in structured_docs
        ])
        
        sql = self.generate_sql_with_llm(query, tables_info)
        
        if not sql or sql == ";":
            return {"answer": "Could not generate SQL query.", "sql": "", "data": []}
        
        is_valid, validation_msg = self.validate_sql(sql)
        if not is_valid:
            return {"answer": f"Query rejected: {validation_msg}", "sql": sql, "data": []}
        
        try:
            rows = self._execute(sql, fetch=True)
            rows = list(rows) if rows else []
            
            context = f"Previous conversation:\n{chat_context}\n\n" if chat_context else ""
            
            answer, _ = self.llm.structured_db_retrieval(
                query, 
                rows[:50], 
                f"{context}Tables: {tables_info}"
            )
            
            return {"answer": answer, "sql": sql, "data": rows[:50]}
            
        except Exception as e:
            return {"answer": f"Query execution error: {str(e)}", "sql": sql, "data": []}

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
        chat_context = self.get_chat_context(session_id, limit=5)
        
        relevant_docs = self.select_relevant_documents(query, top_k=3)
        
        if not relevant_docs:
            answer = "No documents found in the knowledge base. Please upload documents first."
            self.save_chat(session_id, query, answer, "none", "")
            return {"answer": answer, "source": "none", "docs": []}
        
        query_type = self.route_query(query, relevant_docs)
        
        if query_type == "structured":
            result = self.execute_structured_query(query, relevant_docs, chat_context)
            doc_names = ", ".join([d["doc_name"] for d in relevant_docs if d["is_structured"]])
            self.save_chat(session_id, query, result["answer"], "structured", doc_names)
            return {
                "answer": result["answer"],
                "source": "structured",
                "sql": result.get("sql", ""),
                "data": result.get("data", []),
                "docs": relevant_docs
            }
        
        elif query_type == "unstructured":
            result = self.execute_unstructured_query(query, relevant_docs, chat_context)
            doc_names = ", ".join([d["doc_name"] for d in relevant_docs if not d["is_structured"]])
            self.save_chat(session_id, query, result["answer"], "unstructured", doc_names)
            return {
                "answer": result["answer"],
                "source": "unstructured",
                "chunks": result.get("chunks", []),
                "docs": relevant_docs
            }
        
        else:
            answer = "I couldn't determine the type of your query. Please try rephrasing."
            self.save_chat(session_id, query, answer, "unknown", "")
            return {"answer": answer, "source": "none", "docs": relevant_docs}

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

    def delete_all_data(self):
        self._execute("DELETE FROM chat_history")
        self._execute("DELETE FROM unstructured_docs")
        self._execute("DELETE FROM docs_summary")
        
        tables = self._execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = %s AND table_name LIKE 'data_%'
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
