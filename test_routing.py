import os
import sys
from dotenv import load_dotenv

# Add the current directory to sys.path to import local modules
sys.path.append(os.getcwd())

from utils.db import DatabaseManager

def test_routing():
    load_dotenv()
    db = DatabaseManager()
    
    queries = [
        "update about ind vs pak", # Should be WEB/DATABASE decision, then unstructured if in docs
        "what is backrefetrence in sed?",
        "total sales in last 3 months" # Should be structured
    ]
    
    session_id = "test_session"
    
    all_docs = db.get_all_documents()
    kb_description = "The knowledge base contains sections about: " + ", ".join([d['doc_name'] for d in all_docs[:5]]) if all_docs else "The knowledge base is empty."

    for query in queries:
        print(f"\nTesting Query: {query}")
        print("-" * 30)
        
        needs_web, web_reason = db.llm.should_use_web_scraping(query, kb_description)
        print(f"Web Decision: {'WEB' if needs_web else 'DATABASE'} | Reason: {web_reason}")
        
        if not needs_web:
            relevant_docs = db.select_relevant_documents(query, top_k=3)
            if relevant_docs:
                decision = db.route_query(query, relevant_docs)
                print(f"Routing Decision: {decision.upper()}")
                for doc in relevant_docs:
                    print(f"  - {doc['doc_name']} (Score: {doc['score']:.2f}, Structured: {doc['is_structured']})")
            else:
                print("No KB matches found.")

if __name__ == "__main__":
    test_routing()
