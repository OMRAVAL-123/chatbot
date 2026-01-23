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
        return """You are an expert knowledge assistant with deep expertise in analyzing and synthesizing information from documents. Your role is to provide comprehensive, well-structured, and detailed answers based on the context provided.

INSTRUCTIONS:
1. Analyze all provided context chunks thoroughly before responding
2. Generate a detailed, descriptive response that covers ALL relevant aspects found in the chunks
3. Structure your answer with clear sections if multiple subtopics are involved
4. Use bullet points or numbered lists where appropriate for clarity
5. Include specific details, examples, or data points from the context
6. If the context mentions related concepts or subtopics, explain how they connect
7. Maintain accuracy - only use information present in the context
8. Write in a professional, informative tone suitable for academic or professional use
9. Aim for comprehensive coverage - do not leave out relevant information from the chunks
10. If context is limited, provide what you can and acknowledge the limitation

FORMATTING GUIDELINES:
- Use headers (##) to separate major sections if answer spans multiple topics
- Use bullet points for lists of items, features, or steps
- Use bold for key terms or important concepts
- Include brief explanations for technical terms if present
- Provide a concise summary at the end for longer responses"""

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
        system_prompt = """You are a data analysis expert. Based on the query results from a structured database, provide a clear and insightful answer to the user's question.

INSTRUCTIONS:
1. Analyze the data provided thoroughly
2. Present key findings clearly
3. Use tables or lists where appropriate
4. Highlight important patterns or insights
5. If the data is limited, acknowledge what can and cannot be concluded
6. Use conversation context to understand references and pronouns"""

        data_str = "\n".join([str(row) for row in rows[:50]])
        
        user_prompt = f"""Schema Information:
{schema_info}

Query Results:
{data_str}

User Question: {query}

Provide a detailed analysis and answer based on this data."""

        if chat_history and len(chat_history) > 0:
            recent_context = chat_history[-10:]
            history_text = "\n".join([f"{msg['role']}: {msg['content'][:200]}" for msg in recent_context])
            user_prompt = f"Previous conversation context:\n{history_text}\n\n{user_prompt}"

        return self._call_llm(system_prompt, user_prompt)

