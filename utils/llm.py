import os
import re
from typing import List, Dict, Any, Tuple
from groq import Groq


class LLMHandler:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.model = "llama-3.1-8b-instant"
        self.client = None
        self.max_input_tokens = 4000
        self.max_output_tokens = 1024

    def _get_client(self):
        if self.client is None:
            self.client = Groq(api_key=self.api_key)
        return self.client

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(text) // 4 + 1

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        if not text:
            return ""
        estimated = self._estimate_tokens(text)
        if estimated <= max_tokens:
            return text
        max_chars = max_tokens * 4
        return text[:max_chars] + "... [truncated]"

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Tuple[str, int]:
        try:
            client = self._get_client()
            
            system_tokens = self._estimate_tokens(system_prompt)
            user_tokens = self._estimate_tokens(user_prompt)
            total_input = system_tokens + user_tokens
            
            if total_input > self.max_input_tokens:
                available_for_user = self.max_input_tokens - system_tokens - 100
                if available_for_user < 500:
                    system_prompt = self._truncate_to_tokens(system_prompt, 800)
                    available_for_user = self.max_input_tokens - 800 - 100
                user_prompt = self._truncate_to_tokens(user_prompt, max(500, available_for_user))
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=self.max_output_tokens
            )
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            return content, tokens
        except Exception as e:
            error_msg = str(e)
            if "rate_limit" in error_msg.lower() or "413" in error_msg:
                return "Error: Request too large. Please try a shorter query or select fewer documents.", 0
            return f"Error: {error_msg}", 0

    def split_questions(self, text: str) -> List[str]:
        """Split input text into multiple questions if present"""
        if not text or not text.strip():
            return []
        
        questions = []
        
        # First split by newlines
        parts = text.split('\n')
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Split by question marks
            if '?' in part:
                sub_parts = part.split('?')
                for sub in sub_parts:
                    sub = sub.strip()
                    if sub and len(sub) > 5:  # Minimum question length
                        # Add back the question mark if it's a question
                        if any(word in sub.lower() for word in ['what', 'where', 'when', 'who', 'why', 'how', 'is', 'are', 'can', 'do', 'does', 'show', 'get', 'find', 'list']):
                            questions.append(sub + '?')
                        else:
                            questions.append(sub)
            else:
                # Check if it contains 'and' that separates two questions
                if ' and ' in part.lower():
                    # Simple heuristic: if both sides have question words, split
                    and_parts = re.split(r'\s+and\s+', part, flags=re.IGNORECASE)
                    if len(and_parts) == 2:
                        left, right = and_parts
                        left_is_q = any(word in left.lower() for word in ['what', 'where', 'when', 'who', 'why', 'how', 'show', 'get', 'find', 'list'])
                        right_is_q = any(word in right.lower() for word in ['what', 'where', 'when', 'who', 'why', 'how', 'show', 'get', 'find', 'list'])
                        
                        if left_is_q and right_is_q:
                            questions.append(left.strip())
                            questions.append(right.strip())
                        else:
                            questions.append(part)
                    else:
                        questions.append(part)
                else:
                    questions.append(part)
        
        # If no questions found, return original text as single question
        if not questions:
            questions = [text.strip()]
        
        return questions
    
    def should_use_web_scraping(self, query: str, available_schema: str = "") -> Tuple[bool, str]:
        """Use LLM to intelligently decide if web scraping is needed"""
        system_prompt = """You are an intelligent query router. Your job is to determine if a user's question can be answered using the available database schema, or if it requires live/external web data.

CRITICAL DECISION RULES:

Answer "WEB" if the query requires:
- Live/real-time data (sports scores, stock prices, weather, news)
- Current events or breaking news
- Information that changes frequently (today, now, current, latest, ongoing, currently)
- External knowledge not in a typical business database
- Celebrity news, entertainment, viral content
- Time-sensitive information (match scores, live updates)
- Sports matches, games, tournaments happening NOW
- Keywords: "currently", "going on", "live", "happening now", "today's", "right now"

Answer "DATABASE" if the query:
- Can be answered using the provided schema (products, employees, sales, etc.)
- Asks about historical data that would be in a database
- Involves aggregations, counts, or analysis of structured data
- References columns/tables that exist in the schema
- Asks about inventory, ratings, prices, categories in the database

SPECIFIC EXAMPLES:

"show me currently going cricket matches" → WEB (live sports data)
"what is top rated formal wear" → DATABASE (product ratings in schema)
"today's cricket score" → WEB (live data)
"best selling products" → DATABASE (sales data)
"current weather" → WEB (real-time data)
"expensive shoes" → DATABASE (product price data)

RESPONSE FORMAT:
Return ONLY one word: either "WEB" or "DATABASE"
Then on a new line, provide a brief reason (max 10 words)

Example responses:
WEB
Live cricket scores require real-time data

DATABASE
Product inventory query matches available schema"""

        user_prompt = f"""Available Database Schema:
{available_schema if available_schema else "No database schema available"}

User Question: {query}

Decision (WEB or DATABASE):"""

        response, _ = self._call_llm(system_prompt, user_prompt)
        
        lines = response.strip().split('\n')
        decision = lines[0].strip().upper()
        reason = lines[1].strip() if len(lines) > 1 else "No reason provided"
        
        needs_web = decision == "WEB"
        
        return needs_web, reason

    def route_between_structured_unstructured(self, query: str, structured_docs: List[Dict[str, Any]], unstructured_docs: List[Dict[str, Any]]) -> str:
        """Decide between structured (SQL) and unstructured (RAG) path"""
        if not structured_docs and not unstructured_docs:
            return "none"
        if not structured_docs:
            return "unstructured"
        if not unstructured_docs:
            return "structured"

        system_prompt = """You are a query router for a hybrid RAG system.
You must decide if the user's question is best answered by querying a STRUCTURED database (SQL) or reading UNSTRUCTURED documents (RAG).

STRUCTURED (SQL) is best for:
- Statistical queries (counts, sums, averages, totals)
- Comparison queries (highest price, lowest rating, top categories)
- Filtering on specific attributes (list all products with rating > 4)
- Questions about inventory, sales, or product listings that fit a table

UNSTRUCTURED (RAG) is best for:
- Explanatory questions (how to, why, what is the policy on...)
- Sentiment or descriptive analysis (what do customers think about...)
- Extracting specific facts from long documents, PDFs, or articles
- General knowledge or history contained in text

RESPONSE FORMAT:
Return ONLY one word: "STRUCTURED" or "UNSTRUCTURED"."""

        structured_info = "\n".join([f"- {d['doc_name']}: {d.get('summary', '')[:200]}" for d in structured_docs])
        unstructured_info = "\n".join([f"- {d['doc_name']}: {d.get('summary', '')[:200]}" for d in unstructured_docs])

        user_prompt = f"""User Question: {query}

Available Structured Sources:
{structured_info}

Available Unstructured Sources:
{unstructured_info}

Decision:"""

        response, _ = self._call_llm(system_prompt, user_prompt)
        decision = response.strip().upper()
        
        if "STRUCTURED" in decision:
            return "structured"
        if "UNSTRUCTURED" in decision:
            return "unstructured"
        return "unstructured" # Default to unstructured for safety

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

    def optimize_search_query(self, user_query: str) -> str:
        """Use LLM to optimize user query for web search engines"""
        if not user_query or not user_query.strip():
            return user_query or ""
        
        system_prompt = """You are a search query optimization expert. Your job is to transform natural language questions into effective search engine queries.

OPTIMIZATION RULES:
1. Remove filler words (show, me, tell, get, find, what, are, is, the, a, an)
2. Focus on key terms and entities
3. Add relevant context keywords for better results
4. Keep it concise (3-6 words typically)
5. Use present tense and active voice
6. For time-sensitive queries, add temporal keywords (today, now, live, current, latest)

EXAMPLES:
- "show me currently going cricket matches" → "live cricket matches today"
- "what is the weather like today" → "weather today"
- "tell me latest news about AI" → "latest AI news"
- "who won the election" → "election results latest"
- "find me cheap flights to Paris" → "cheap flights Paris"

RESPONSE FORMAT:
Return ONLY the optimized search query, nothing else. No explanations, no quotes, just the query."""

        user_prompt = f"""User Query: {user_query}

Optimized Search Query:"""

        try:
            optimized_query, _ = self._call_llm(system_prompt, user_prompt)
            optimized_query = optimized_query.strip().strip('"').strip("'")
            
            # Check if the response contains error messages
            if 'error' in optimized_query.lower() or len(optimized_query) > 100:
                print(f"⚠️ LLM returned invalid optimization, using original query")
                return user_query
            
            print(f"🔧 Query optimization: '{user_query}' → '{optimized_query}'")
            return optimized_query if optimized_query else user_query
        except Exception as e:
            print(f"⚠️ Query optimization failed: {e}, using original query")
            return user_query


