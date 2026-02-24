import os
import sys
from dotenv import load_dotenv

# Add the current directory to sys.path to import local modules
sys.path.append(os.getcwd())

from utils.db import DatabaseManager

def test_routing():
    load_dotenv()
    db = DatabaseManager()
    
    query = "update about ind vs pak"
    session_id = "test_session"
    
    print(f"\nTesting Query: {query}")
    print("-" * 30)
    
    # We won't call process_user_query directly to avoid making many network calls/db hits
    # but we will test the logic we just added.
    
    all_docs = db.get_all_documents()
    kb_description = "The knowledge base contains sections about: " + ", ".join([d['doc_name'] for d in all_docs[:5]]) if all_docs else "The knowledge base is empty."
    
    needs_web, web_reason = db.llm.should_use_web_scraping(query, kb_description)
    print(f"Routing Decision: {'WEB' if needs_web else 'DATABASE'}")
    print(f"Reason: {web_reason}")
    
    relevant_docs = db.select_relevant_documents(query, top_k=3)
    if relevant_docs:
        print(f"Top KB Match: {relevant_docs[0]['doc_name']} (Score: {relevant_docs[0]['score']:.2f})")
    else:
        print("No KB matches found.")

if __name__ == "__main__":
    test_routing()
