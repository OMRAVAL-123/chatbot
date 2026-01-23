import os
from typing import List, Dict, Any, Tuple
from groq import Groq


class LLMHandler:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.model = "llama-3.1-8b-instant"
        self.client = None

    def _get_client(self):
        if self.client is None:
            self.client = Groq(api_key=self.api_key)
        return self.client

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Tuple[str, int]:
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2048
            )
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            return content, tokens
        except Exception as e:
            return f"Error: {str(e)}", 0

    def summarize(self, text: str, filename: str) -> Tuple[str, int]:
        system_prompt = """You are a document summarization expert. Create a concise but comprehensive summary of the provided document content. 
For structured data like CSV/XLSX, include:
- Schema information (column names and types)
- Key statistics or patterns
- Sample data description

For unstructured documents:
- Main topics covered
- Key points and findings
- Document structure overview"""

        user_prompt = f"""Document: {filename}

Content:
{text[:8000]}

Provide a detailed summary of this document."""

        return self._call_llm(system_prompt, user_prompt)

    def summarize_chat(self, chat_history: List[Dict[str, str]]) -> Tuple[str, int]:
        system_prompt = """You are a conversation summarizer. Create a concise summary of the chat conversation that captures:
- Main topics discussed
- Key questions asked
- Important answers or conclusions
- Any pending questions or topics"""

        chat_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        user_prompt = f"""Chat History:
{chat_text}

Summarize this conversation."""

        return self._call_llm(system_prompt, user_prompt)

    def _build_rag_system_prompt(self) -> str:
        return """You are an expert knowledge assistant. Your role is to provide accurate answers based ONLY on the context provided.

CRITICAL RULES - NEVER VIOLATE:
1. ONLY use information that is EXPLICITLY present in the provided context chunks
2. NEVER invent, fabricate, or hallucinate any data, names, products, or facts
3. If the context doesn't contain relevant information, say "The documents do not contain information about [topic]"
4. If asked about something not in the context, clearly state it's not available

RESPONSE FORMAT:
1. Analyze all provided context chunks thoroughly before responding
2. Generate a response that covers ONLY what is found in the chunks
3. Structure your answer with clear sections if multiple subtopics are involved
4. Use bullet points or numbered lists where appropriate for clarity
5. Include specific details from the context - quote when helpful
6. Maintain accuracy - only use information present in the context
7. If context is limited or doesn't match the question, acknowledge this clearly

FORBIDDEN ACTIONS:
- Do NOT create example data or made-up information
- Do NOT assume information exists if it's not in the context
- Do NOT provide general knowledge not found in the context
- Do NOT invent product names, prices, or any specific values"""

    def _build_rag_user_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        context_parts = []
        for i, chunk in enumerate(chunks):
            source = chunk.get('source', 'Unknown')
            page = chunk.get('page_num', '?')
            score = chunk.get('score', 0)
            text = chunk.get('text', '')
            context_parts.append(f"[Source {i+1}: {source} | Page: {page} | Relevance: {score:.2f}]\n{text}")
        
        context_str = "\n\n---\n\n".join(context_parts)
        
        return f"""CONTEXT FROM KNOWLEDGE BASE:
{context_str}

---

USER QUESTION: {query}

---

Based on the above context, provide a comprehensive and detailed answer to the user's question. 
Cover all relevant subtopics, include specific details from the sources, and structure your response clearly.
If the context covers multiple aspects related to the question, address each aspect thoroughly."""

    def rag_retrieval(self, query: str, chunks: List[Dict[str, Any]], 
                      chat_history: List[Dict[str, str]] = None) -> Tuple[str, int]:
        system_prompt = self._build_rag_system_prompt()
        user_prompt = self._build_rag_user_prompt(query, chunks)
        
        if chat_history and len(chat_history) > 0:
            recent_context = chat_history[-10:]
            history_text = "\n".join([f"{msg['role']}: {msg['content'][:200]}" for msg in recent_context])
            user_prompt = f"Previous conversation context:\n{history_text}\n\n{user_prompt}"
        
        return self._call_llm(system_prompt, user_prompt)

    def structured_db_retrieval(self, query: str, rows: List[Dict[str, Any]], 
                                 schema_info: str = "", 
                                 chat_history: List[Dict[str, str]] = None) -> Tuple[str, int]:
        system_prompt = """You are a data analysis expert. You MUST follow these STRICT rules:

CRITICAL RULES - NEVER VIOLATE:
1. ONLY use data that is EXPLICITLY provided in the "Query Results" section below
2. NEVER invent, fabricate, or hallucinate any data, products, names, or values
3. If no data is provided or data is empty, say "No matching data found in the database"
4. If the query results don't contain what the user asked for, say "The database does not contain [what user asked for]"
5. Show the ACTUAL rows returned - do not modify or add to them
6. If there are 0 rows, clearly state that no results were found

RESPONSE FORMAT:
- First, state how many rows were retrieved
- Then show the actual data from the results
- Finally, provide analysis ONLY based on the actual data shown
- Use conversation context to understand references and pronouns

FORBIDDEN ACTIONS:
- Do NOT create example data
- Do NOT make up product names, brands, or any values
- Do NOT assume data exists if it's not in the results"""

        if not rows or len(rows) == 0:
            return "No matching data found in the database for your query. The search returned 0 results.", 0
        
        data_str = "\n".join([str(row) for row in rows[:50]])
        
        user_prompt = f"""Schema Information:
{schema_info}

Query Results ({len(rows)} rows retrieved):
{data_str}

User Question: {query}

IMPORTANT: Only analyze the EXACT data shown above. Do not invent any additional data."""

        if chat_history and len(chat_history) > 0:
            recent_context = chat_history[-10:]
            history_text = "\n".join([f"{msg['role']}: {msg['content'][:200]}" for msg in recent_context])
            user_prompt = f"Previous conversation context:\n{history_text}\n\n{user_prompt}"

        return self._call_llm(system_prompt, user_prompt)

