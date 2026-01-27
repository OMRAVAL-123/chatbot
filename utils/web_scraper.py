import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
import re


class WebScraper:
    def __init__(self, llm=None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        self.current_keywords = ['today', 'now', 'current', 'live', 'latest', 'update', 'score', 'match', 'news', 'trending', 'viral']
        self.llm = llm
    
    def is_current_event_query(self, query):
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.current_keywords)
    
    def search_news(self, query):
        try:
            # Optimize query using LLM if available
            search_query = query
            if self.llm:
                search_query = self.llm.optimize_search_query(query)
            
            print(f"🔍 Searching news for: {search_query}")
            with DDGS() as ddgs:
                results = list(ddgs.news(search_query, region="in-en", max_results=10))
            
            print(f"📰 Found {len(results)} news results")
            
            formatted_results = []
            for r in results:
                formatted_results.append({
                    "title": r.get("title", ""),
                    "link": r.get("url", ""),
                    "snippet": r.get("body", "")[:500],
                    "date": r.get("date", "")
                })
            
            return {"success": True, "results": formatted_results, "error": None}
        
        except Exception as e:
            error_msg = f"News search error: {type(e).__name__}: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "results": [], "error": error_msg}
    
    def search_text(self, query):
        try:
            # Optimize query using LLM if available
            search_query = query
            if self.llm:
                search_query = self.llm.optimize_search_query(query)
            
            print(f"🔍 Searching web for: {search_query}")
            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, region="in-en", timelimit="w", max_results=10))
            
            print(f"🌐 Found {len(results)} web results")
            
            formatted_results = []
            for r in results:
                formatted_results.append({
                    "title": r.get("title", ""),
                    "link": r.get("href", ""),
                    "snippet": r.get("body", "")[:500]
                })
            
            return {"success": True, "results": formatted_results, "error": None}
        
        except Exception as e:
            error_msg = f"Search error: {type(e).__name__}: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "results": [], "error": error_msg}
    
    def search(self, query):
        if self.is_current_event_query(query):
            news_results = self.search_news(query)
            if news_results["success"] and news_results["results"]:
                return news_results
        
        return self.search_text(query)
    
    def get_page_content(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript', 'iframe']):
                tag.decompose()
            
            title = ""
            title_elem = soup.find(['h1', 'title'])
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            content_parts = []
            
            article = soup.find(['article', 'main', 'div'], class_=re.compile(r'content|article|post|entry|body', re.I))
            
            if article:
                paragraphs = article.find_all(['p', 'h2', 'h3', 'li'])
            else:
                paragraphs = soup.find_all(['p', 'h2', 'h3'])
            
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 30:
                    cleaned_text = ' '.join(text.split())
                    content_parts.append(cleaned_text)
            
            return {
                "success": True,
                "title": title,
                "content": "\n\n".join(content_parts[:25]),
                "error": None
            }
        
        except Exception as e:
            return {"success": False, "title": "", "content": "", "error": str(e)}


def scrape_web_content(query, llm=None):
    scraper = WebScraper(llm=llm)
    search_results = scraper.search(query)
    
    if search_results["success"] and search_results["results"]:
        combined_content = {
            "success": True,
            "search_results": search_results["results"],
            "detailed_content": "",
            "error": None
        }
        
        for result in search_results["results"][:2]:
            try:
                page_content = scraper.get_page_content(result["link"])
                if page_content["success"] and page_content["content"]:
                    combined_content["detailed_content"] += f"\n\n--- {result['title']} ---\n{page_content['content']}"
                    break
            except:
                continue
        
        return combined_content
    
    return {
        "success": False,
        "search_results": [],
        "detailed_content": "",
        "error": search_results.get("error", "No results found")
    }
