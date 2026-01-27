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
from utils.audio_handler import AudioInputHandler

st.set_page_config(
    page_title="Document Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background: #ffe4e9 !important;
    }
    
    [data-testid="stAppViewContainer"] {
        background: #ffe4e9 !important;
    }
    
    [data-testid="stHeader"] {
        background: #fff0f3 !important;
    }
    
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #be185d 0%, #ec4899 50%, #f472b6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 3rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    
    .chat-message {
        padding: 1.2rem 1.5rem;
        border-radius: 20px;
        margin: 1rem 0;
        animation: slideIn 0.3s ease-out;
    }
    
    .user-message {
        background: linear-gradient(135deg, #ec4899 0%, #f472b6 100%);
        color: white;
        margin-left: 20%;
        border-radius: 20px 20px 5px 20px;
        box-shadow: 0 8px 32px rgba(236, 72, 153, 0.3);
    }
    
    .assistant-message {
        background: #ffffff;
        color: #000000;
        margin-right: 10%;
        border-radius: 20px 20px 20px 5px;
        border: 1px solid #fda4af;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }
    
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .sidebar-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #be185d;
        padding: 0.5rem 0;
        border-bottom: 2px solid #ec4899;
        margin-bottom: 1rem;
    }
    
    .doc-card {
        background: #ffffff;
        border: 1px solid #fda4af;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.3s ease;
    }
    
    .doc-card:hover {
        background: #fff0f3;
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(236, 72, 153, 0.2);
    }
    
    .structured-badge {
        background: #10b981;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    .unstructured-badge {
        background: #f59e0b;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    .routing-info {
        background: #fce7f3;
        color: #9f1239;
        padding: 0.75rem 1.25rem;
        border-radius: 12px;
        border: 1px solid #ec4899;
        font-size: 0.9rem;
        margin: 1rem 0;
    }
    
    .sql-box {
        background: #1f2937;
        color: #10b981;
        padding: 1.2rem;
        border-radius: 12px;
        border: 1px solid #374151;
        font-family: 'Courier New', monospace;
        overflow-x: auto;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #ec4899 0%, #f472b6 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 25px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 20px rgba(236, 72, 153, 0.4) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 30px rgba(236, 72, 153, 0.6) !important;
    }
    
    .delete-warning {
        background: #fee2e2;
        color: #991b1b;
        padding: 1.2rem;
        border-radius: 12px;
        margin: 1rem 0;
        border-left: 5px solid #dc2626;
    }
    
    .stats-card {
        background: #ffffff;
        border: 1px solid #fda4af;
        padding: 1.2rem;
        border-radius: 12px;
        text-align: center;
        color: #000000;
    }
    
    [data-testid="stSidebar"] {
        background: #fff0f3 !important;
        border-right: 1px solid #fda4af !important;
    }
    
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3 {
        color: #be185d !important;
    }
    
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown {
        color: #000000 !important;
    }
    
    [data-testid="stSidebar"] .stButton > button {
        background: linear-gradient(135deg, #10b981 0%, #34d399 100%) !important;
        color: white !important;
    }
    
    .stTextInput > div > div > input {
        background: #ffffff !important;
        border: 2px solid #fda4af !important;
        border-radius: 25px !important;
        color: #000000 !important;
        padding: 1rem 1.5rem !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #ec4899 !important;
        box-shadow: 0 0 20px rgba(236, 72, 153, 0.3) !important;
    }
    
    .stTextInput > div > div > input::placeholder {
        color: #9ca3af !important;
    }
    
    .stFileUploader > div {
        background: #ffffff !important;
        border: 2px dashed #fda4af !important;
        border-radius: 12px !important;
    }
    
    .stFileUploader label {
        color: #000000 !important;
    }
    
    .stExpander {
        background: #ffffff !important;
        border: 1px solid #fda4af !important;
        border-radius: 12px !important;
    }
    
    .stExpander summary {
        color: #be185d !important;
        font-weight: 600 !important;
    }
    
    .stMarkdown, p, span, div {
        color: #000000 !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #be185d !important;
    }
    
    .stMetric {
        background: #ffffff !important;
        padding: 1rem !important;
        border-radius: 12px !important;
        border: 1px solid #fda4af !important;
    }
    
    .stMetric label {
        color: #000000 !important;
    }
    
    .stMetric [data-testid="stMetricValue"] {
        color: #be185d !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
    
    .stAlert {
        background: #fef3c7 !important;
        border: 1px solid #f59e0b !important;
        color: #92400e !important;
    }
    
    .stSuccess {
        background: #d1fae5 !important;
        border: 1px solid #10b981 !important;
        color: #065f46 !important;
    }
    
    .stError {
        background: #fee2e2 !important;
        border: 1px solid #ef4444 !important;
        color: #991b1b !important;
    }
    
    .stWarning {
        background: #fef3c7 !important;
        border: 1px solid #f59e0b !important;
        color: #92400e !important;
    }
    
    .stInfo {
        background: #fce7f3 !important;
        border: 1px solid #ec4899 !important;
        color: #9f1239 !important;
    }
    
    .stDataFrame {
        background: #ffffff !important;
        border: 1px solid #fda4af !important;
        border-radius: 12px !important;
    }
    
    hr {
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, #fda4af, transparent) !important;
        margin: 2rem 0 !important;
    }
    
    .stSpinner > div {
        border-top-color: #ec4899 !important;
    }
    
    .stProgress > div > div {
        background: #ec4899 !important;
    }
    
    a {
        color: #be185d !important;
        text-decoration: none !important;
    }
    
    a:hover {
        color: #9f1239 !important;
        text-decoration: underline !important;
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

if "audio_handler" not in st.session_state:
    st.session_state.audio_handler = AudioInputHandler()

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
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📤", help="Upload", use_container_width=True):
            st.session_state.active_tab = "upload"
    with col2:
        if st.button("💬", help="Chat", use_container_width=True):
            st.session_state.active_tab = "chat"
    with col3:
        if st.button("⚙️", help="Settings", use_container_width=True):
            st.session_state.active_tab = "settings"
    
    st.markdown("---")
    
    if st.session_state.active_tab == "chat":
        st.markdown("<div class='sidebar-header'>💬 Chats</div>", unsafe_allow_html=True)
        
        if st.button("✨ New Chat", use_container_width=True):
            create_new_session()
            st.rerun()
        
        st.caption(f"Active: {st.session_state.session_id}")
        
        try:
            sessions = st.session_state.db.get_all_sessions()
            if sessions:
                for sess in sessions[:8]:
                    is_current = sess['session_id'] == st.session_state.session_id
                    icon = "💬" if is_current else "○"
                    label = f"{icon} {sess['session_id'][:6]}"
                    
                    col_a, col_b = st.columns([5, 1])
                    with col_a:
                        if st.button(label, key=f"sess_{sess['session_id']}", 
                                    use_container_width=True, disabled=is_current):
                            load_session(sess['session_id'])
                            st.rerun()
                    with col_b:
                        if st.button("🗑", key=f"del_{sess['session_id']}", use_container_width=True):
                            st.session_state.db.delete_chat_session(sess['session_id'])
                            if is_current:
                                create_new_session()
                            st.rerun()
        except:
            pass
    
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
            placeholder="Type your question or record audio below..."
        )
    
    with col2:
        send = st.button("Send", use_container_width=True)
    
    # Audio input widget
    audio_file = st.audio_input("🎤 Record your question")
    
    final_query = None
    
    # Handle audio input
    if audio_file is not None:
        with st.spinner("🎤 Transcribing audio..."):
            result = st.session_state.audio_handler.transcribe_audio_file(audio_file)
            if result["success"]:
                final_query = result["text"]
                st.success(f"✅ Transcribed: {final_query}")
                st.session_state.last_transcription = final_query
            else:
                st.error(f"❌ {result['error']}")
    
    # Use transcription if no text input
    if hasattr(st.session_state, 'last_transcription') and st.session_state.last_transcription and not user_input:
        user_input = st.session_state.last_transcription
    
    # Use text input if provided
    if user_input:
        final_query = user_input
    
    # Process query when send button is clicked
    if send and final_query:
        if hasattr(st.session_state, 'last_transcription'):
            del st.session_state.last_transcription
        st.session_state.messages.append({"role": "user", "content": final_query})
        
        with st.spinner("Processing query..."):
            result = st.session_state.db.process_user_query(
                st.session_state.session_id,
                final_query
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
            st.session_state.last_sql_full_data = result.get("full_data", [])
        else:
            st.session_state.last_sql = None
            st.session_state.last_sql_full_data = None
        
        if result.get("chunks"):
            st.session_state.last_chunks = result["chunks"]
        else:
            st.session_state.last_chunks = None
        
        if result.get("web_sources"):
            st.session_state.last_web_sources = result["web_sources"]
        else:
            st.session_state.last_web_sources = None
        
        st.rerun()
    
    if hasattr(st.session_state, 'last_routing') and st.session_state.last_routing:
        st.markdown(f"<div class='routing-info'>{st.session_state.last_routing}</div>", unsafe_allow_html=True)
    
    if hasattr(st.session_state, 'last_sql') and st.session_state.last_sql:
        with st.expander("📊 SQL Query & Full Data", expanded=False):
            st.markdown("**Generated SQL Query:**")
            st.markdown(f"<div class='sql-box'>{st.session_state.last_sql}</div>", unsafe_allow_html=True)
            
            if hasattr(st.session_state, 'last_sql_full_data') and st.session_state.last_sql_full_data:
                st.markdown(f"**Complete Query Results ({len(st.session_state.last_sql_full_data)} rows):**")
                st.dataframe(pd.DataFrame(st.session_state.last_sql_full_data), use_container_width=True)
                
                csv = pd.DataFrame(st.session_state.last_sql_full_data).to_csv(index=False)
                st.download_button(
                    label="📥 Download Full Data (CSV)",
                    data=csv,
                    file_name="query_results.csv",
                    mime="text/csv"
                )
    
    if hasattr(st.session_state, 'last_chunks') and st.session_state.last_chunks:
        with st.expander("Retrieved Chunks"):
            for i, chunk in enumerate(st.session_state.last_chunks):
                st.markdown(f"**[{chunk['source']} | Page {chunk['page_num']} | Score: {chunk['score']:.2f}]**")
                st.write(chunk["text"][:300] + "..." if len(chunk["text"]) > 300 else chunk["text"])
                st.markdown("---")
    
    if hasattr(st.session_state, 'last_web_sources') and st.session_state.last_web_sources:
        with st.expander("🌐 Web Sources"):
            for source in st.session_state.last_web_sources:
                st.markdown(f"**[{source['title']}]({source['link']})**")
                st.write(source.get('snippet', '')[:200])
                st.markdown("---")


elif st.session_state.active_tab == "settings":
    st.markdown("### ⚙️ Settings & Management")
    
    st.markdown("---")
    st.markdown("#### 🗑️ Delete Entire Database")
    st.warning("⚠️ This action will delete ALL documents, chat history, and data tables. This cannot be undone!")
    
    password = st.text_input("Enter password to confirm deletion:", type="password", key="delete_password")
    
    if st.button("🗑️ Delete All Data", type="primary"):
        if password == "Jaymahadev@789":
            with st.spinner("Deleting all data..."):
                try:
                    st.session_state.db.delete_all_data()
                    st.success("✅ All data has been deleted successfully!")
                    create_new_session()
                    st.info("Please refresh the page to continue.")
                except Exception as e:
                    st.error(f"❌ Error deleting data: {str(e)}")
        elif password:
            st.error("❌ Incorrect password! Access denied.")
        else:
            st.warning("⚠️ Please enter the password to proceed.")
    
    st.markdown("---")
    st.markdown("#### 📊 Database Statistics")
    
    try:
        docs = st.session_state.db.get_all_documents()
        sessions = st.session_state.db.get_all_sessions()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Documents", len(docs))
        with col2:
            st.metric("Total Chats", len(sessions))
        with col3:
            total_msgs = sum(s['message_count'] for s in sessions)
            st.metric("Total Messages", total_msgs)
    except Exception as e:
        st.error(f"Error loading statistics: {str(e)}")


st.markdown("---")
st.markdown("<p style='text-align: center; color: #888;'>Hybrid AI Chatbot | Structured (SQL) + Unstructured (RAG)</p>", unsafe_allow_html=True)
