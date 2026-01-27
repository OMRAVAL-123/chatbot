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
        system_prompt = """You are a data analysis expert. Your job is to analyze the query results and provide meaningful insights.

CRITICAL RULES:
1. The actual data table is already shown to the user - DO NOT repeat it
2. DO NOT just restate the user's question or query
3. ANALYZE the actual data in the results and provide insights
4. Focus on WHAT THE DATA SHOWS, not what was asked
5. If the data doesn't exactly match what user asked for, CLEARLY state this
   Example: "Note: The database doesn't have 'formal wear' category. Showing 'Formal Shoes' instead."
6. Be honest about what columns/categories actually exist in the data
7. NEVER invent or make up any data - only refer to what's in the results

RESPONSE FORMAT:
## 💡 Data Analysis

[If data doesn't match query exactly, state this first]

**Key Findings:**
- Insight 1 based on actual data values
- Insight 2 based on actual data values  
- Insight 3 based on actual data values

**Summary:**
[Provide a brief summary of what the data reveals]

Focus on:
- Actual values, counts, ranges in the data
- Patterns or trends you observe
- Comparisons between different data points
- Recommendations based on the actual data

Keep it concise and visual. Use bullet points and bold for key terms."""

        if not rows or len(rows) == 0:
            return "The query returned no results.", 0
        
        data_str = "\n".join([str(row) for row in rows[:15]])
        
        user_prompt = f"""Query Results ({len(rows)} rows):
{data_str}

User Question: {query}

IMPORTANT: 
1. Analyze the ACTUAL DATA shown above
2. DO NOT just repeat the question
3. Provide insights based on what you see in the data
4. If the data category differs from what user asked, state this clearly
5. Focus on data values, patterns, and insights"""

        if chat_history and len(chat_history) > 0:
            recent_context = chat_history[-10:]
            history_text = "\n".join([f"{msg['role']}: {msg['content'][:200]}" for msg in recent_context])
            user_prompt = f"Previous conversation context:\n{history_text}\n\n{user_prompt}"

        return self._call_llm(system_prompt, user_prompt)

    def web_retrieval(self, query: str, web_content: str) -> Tuple[str, int]:
        system_prompt = """You are a helpful assistant that answers questions based on web search results.

CRITICAL RULES:
1. Clearly state that this information is from web search, not from uploaded documents
2. Only use information from the provided web content
3. Be concise and accurate
4. If the web content doesn't fully answer the question, acknowledge this
5. Cite specific sources when mentioning facts

RESPONSE FORMAT:
- Provide a direct answer to the question
- Include relevant details from the web content
- Use bullet points for clarity when listing multiple items
- Be honest if information is incomplete"""

        user_prompt = f"""Web Search Results:
{web_content[:4000]}

User Question: {query}

Based on the above web search results, provide a comprehensive answer to the user's question."""

        return self._call_llm(system_prompt, user_prompt)
