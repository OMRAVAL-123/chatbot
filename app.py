import os
import uuid
import tempfile
import streamlit as st
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

from utils.docsreciever import DocumentProcessor
from utils.db import DatabaseManager
from utils.rag import SemanticChunker

st.set_page_config(
    page_title="Document Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        animation: fadeIn 0.3s ease;
    }
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: 20%;
    }
    .assistant-message {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        color: #333;
        margin-right: 20%;
    }
    .sidebar-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #667eea;
        padding: 0.5rem 0;
        border-bottom: 2px solid #667eea;
        margin-bottom: 1rem;
    }
    .doc-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .structured-badge {
        background: #10b981;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .unstructured-badge {
        background: #f59e0b;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .routing-info {
        background: #1e1e2e;
        color: #cdd6f4;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-size: 0.85rem;
        margin: 0.5rem 0;
    }
    .sql-box {
        background: #1e1e1e;
        color: #d4d4d4;
        padding: 1rem;
        border-radius: 8px;
        font-family: monospace;
        overflow-x: auto;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 5px 15px rgba(102,126,234,0.4);
    }
</style>
""", unsafe_allow_html=True)

if "db" not in st.session_state:
    st.session_state.db = DatabaseManager()
    try:
        st.session_state.db.initialize_tables()
    except Exception as e:
        st.error(f"Database connection failed: {e}")

if "processor" not in st.session_state:
    st.session_state.processor = DocumentProcessor()

if "chunker" not in st.session_state:
    st.session_state.chunker = SemanticChunker()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

if "messages" not in st.session_state:
    st.session_state.messages = []

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "upload"


def process_uploaded_files(files):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, file in enumerate(files):
        status_text.text(f"Processing: {file.name}...")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as tmp:
            tmp.write(file.read())
            tmp_path = tmp.name
        
        try:
            result = st.session_state.processor.process_and_save(tmp_path)
            
            if result["is_structured"]:
                for doc in result["documents"]:
                    if "dataframe" in doc:
                        db_result = st.session_state.db.ingest_structured_data(
                            doc["dataframe"], 
                            file.name
                        )
                        results.append({
                            "name": file.name,
                            "status": "success",
                            "type": "structured",
                            "info": f"Table: {db_result['table_name']} ({db_result['row_count']} rows)"
                        })
            else:
                all_chunks = []
                for doc in result["documents"]:
                    chunks = st.session_state.chunker.chunk_text(
                        doc.get("text", ""),
                        doc.get("source", file.name),
                        doc.get("page_num", 1)
                    )
                    all_chunks.extend(chunks)
                
                if all_chunks:
                    db_result = st.session_state.db.ingest_unstructured_data(all_chunks, file.name)
                    results.append({
                        "name": file.name,
                        "status": "success",
                        "type": "unstructured",
                        "info": f"{db_result['chunks']} chunks indexed"
                    })
            
        except Exception as e:
            results.append({
                "name": file.name,
                "status": "error",
                "error": str(e)
            })
        
        finally:
            os.unlink(tmp_path)
        
        progress_bar.progress((idx + 1) / len(files))
    
    status_text.text("All files processed!")
    return results


def create_new_session():
    st.session_state.session_id = str(uuid.uuid4())[:8]
    st.session_state.messages = []


def load_session(session_id):
    st.session_state.session_id = session_id
    history = st.session_state.db.get_chat_history(session_id)
    st.session_state.messages = []
    for h in history:
        st.session_state.messages.append({"role": "user", "content": h["user_query"]})
        st.session_state.messages.append({"role": "assistant", "content": h["final_answer"]})


st.markdown("<h1 class='main-header'>Document Chatbot</h1>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div class='sidebar-header'>Navigation</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Upload", use_container_width=True):
            st.session_state.active_tab = "upload"
    with col2:
        if st.button("Chat", use_container_width=True):
            st.session_state.active_tab = "chat"
    
    st.markdown("---")
    
    if st.session_state.active_tab == "chat":
        st.markdown("<div class='sidebar-header'>Chat History</div>", unsafe_allow_html=True)
        
        if st.button("➕ New Chat", use_container_width=True):
            create_new_session()
            st.rerun()
        
        st.markdown(f"**Current:** `{st.session_state.session_id}`")
        st.markdown("---")
        
        try:
            sessions = st.session_state.db.get_all_sessions()
            if sessions:
                st.caption(f"📝 {len(sessions)} conversation(s)")
                for sess in sessions[:10]:
                    is_current = sess['session_id'] == st.session_state.session_id
                    label = f"{'🔵' if is_current else '⚪'} {sess['session_id'][:6]}... ({sess['message_count']} msgs)"
                    
                    if st.button(label, key=f"sess_{sess['session_id']}", use_container_width=True, 
                                disabled=is_current):
                        load_session(sess['session_id'])
                        st.rerun()
            else:
                st.caption("No previous chats")
        except Exception as e:
            st.caption("No chat history available")
    
    st.markdown("---")
    
    st.markdown("<div class='sidebar-header'>Knowledge Base</div>", unsafe_allow_html=True)
    try:
        docs = st.session_state.db.get_all_documents()
        structured = sum(1 for d in docs if d.get("is_structured"))
        unstructured = len(docs) - structured
        
        st.metric("Structured Docs", structured)
        st.metric("Unstructured Docs", unstructured)
    except:
        st.metric("Documents", 0)


if st.session_state.active_tab == "upload":
    st.markdown("### Upload Documents")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("**Structured (SQL Path):** CSV, XLSX")
    with col2:
        st.info("**Unstructured (RAG Path):** PDF, DOCX, TXT, MD, PPTX, ZIP, Images")
    
    uploaded_files = st.file_uploader(
        "Drop files here",
        type=["pdf", "docx", "txt", "md", "csv", "xlsx", "pptx", "zip", "png", "jpg", "jpeg"],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        st.info(f"{len(uploaded_files)} file(s) selected")
        
        if st.button("Process Files"):
            with st.spinner("Processing..."):
                results = process_uploaded_files(uploaded_files)
            
            for r in results:
                if r["status"] == "success":
                    badge = "structured-badge" if r["type"] == "structured" else "unstructured-badge"
                    st.markdown(f"""
                    <div class='doc-card'>
                        <span class='{badge}'>{r['type'].upper()}</span>
                        <strong> {r['name']}</strong><br>
                        <small>{r['info']}</small>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error(f"{r['name']}: {r.get('error', 'Error')}")
    
    st.markdown("---")
    st.markdown("### Uploaded Documents")
    
    try:
        docs = st.session_state.db.get_all_documents()
        for doc in docs:
            badge_class = "structured-badge" if doc.get("is_structured") else "unstructured-badge"
            badge_text = "STRUCTURED" if doc.get("is_structured") else "UNSTRUCTURED"
            table_info = f" | Table: {doc.get('table_name')}" if doc.get('table_name') else ""
            
            with st.expander(f"{doc['doc_name']}{table_info}"):
                st.markdown(f"<span class='{badge_class}'>{badge_text}</span>", unsafe_allow_html=True)
                st.write(doc.get("summary_text", "No summary"))
    except:
        st.write("No documents uploaded yet.")


elif st.session_state.active_tab == "chat":
    st.markdown(f"### Chat Session: {st.session_state.session_id}")
    
    chat_container = st.container()
    
    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f"""
                <div class='chat-message user-message'>
                    <strong>You:</strong><br>{msg['content']}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class='chat-message assistant-message'>
                    <strong>Assistant:</strong><br>{msg['content']}
                </div>
                """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([6, 1])
    
    with col1:
        user_input = st.text_input(
            "Ask about your documents...",
            key="user_input",
            placeholder="Type your question..."
        )
    
    with col2:
        send = st.button("Send")
    
    if send and user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with st.spinner("Processing query..."):
            result = st.session_state.db.process_user_query(
                st.session_state.session_id,
                user_input
            )
        
        st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
        
        if result.get("source") != "none":
            routing_info = f"Route: {result['source'].upper()}"
            if result.get("docs"):
                doc_names = [d["doc_name"] for d in result["docs"][:3]]
                routing_info += f" | Docs: {', '.join(doc_names)}"
            st.session_state.last_routing = routing_info
        
        if result.get("sql"):
            st.session_state.last_sql = result["sql"]
            st.session_state.last_sql_data = result.get("data", [])
        else:
            st.session_state.last_sql = None
        
        if result.get("chunks"):
            st.session_state.last_chunks = result["chunks"]
        else:
            st.session_state.last_chunks = None
        
        st.rerun()
    
    if hasattr(st.session_state, 'last_routing') and st.session_state.last_routing:
        st.markdown(f"<div class='routing-info'>{st.session_state.last_routing}</div>", unsafe_allow_html=True)
    
    if hasattr(st.session_state, 'last_sql') and st.session_state.last_sql:
        with st.expander("SQL Query"):
            st.markdown(f"<div class='sql-box'>{st.session_state.last_sql}</div>", unsafe_allow_html=True)
            if st.session_state.last_sql_data:
                st.dataframe(pd.DataFrame(st.session_state.last_sql_data))
    
    if hasattr(st.session_state, 'last_chunks') and st.session_state.last_chunks:
        with st.expander("Retrieved Chunks"):
            for i, chunk in enumerate(st.session_state.last_chunks):
                st.markdown(f"**[{chunk['source']} | Page {chunk['page_num']} | Score: {chunk['score']:.2f}]**")
                st.write(chunk["text"][:300] + "..." if len(chunk["text"]) > 300 else chunk["text"])
                st.markdown("---")


st.markdown("---")
st.markdown("<p style='text-align: center; color: #888;'>Hybrid AI Chatbot | Structured (SQL) + Unstructured (RAG)</p>", unsafe_allow_html=True)
