import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any

class WebScraper:
    def __init__(self, llm=None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        self.current_keywords = ['today', 'now', 'current', 'live', 'latest', 'update', 'score', 'match', 'news', 'trending', 'viral']
        self.llm = llm
    
    def is_current_event_query(self, query):
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.current_keywords)
    
    def search_rss(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Use Google News RSS to find latest information/news related to query"""
        results = []
        try:
            # Optimize query using LLM if available
            search_query = query
            if self.llm:
                search_query = self.llm.optimize_search_query(query)
            
            print(f"🔍 Searching RSS (Google News) for: {search_query}")
            url = f"https://news.google.com/rss/search?q={search_query.replace(' ', '+')}"
            
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                print(f"❌ RSS search failed with status: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'xml')
            items = soup.find_all('item')
            
            for item in items[:max_results]:
                title = item.title.text if item.title else ""
                link = item.link.text if item.link else ""
                pub_date = item.pubDate.text if item.pubDate else ""
                source = item.source.text if item.source else ""
                
                # Description often contains HTML, let's clean it up for a snippet
                description = item.description.text if item.description else ""
                snippet = BeautifulSoup(description, 'html.parser').get_text() if description else ""
                
                if title and link:
                    results.append({
                        "title": title,
                        "link": link,
                        "snippet": snippet[:500],
                        "date": pub_date,
                        "source": source
                    })
            
            print(f"📰 Found {len(results)} RSS results")
            return results
            
        except Exception as e:
            print(f"❌ RSS search error: {str(e)}")
            return []

    def get_page_content(self, url: str) -> Dict[str, Any]:
        """Try to get page content using simple requests"""
        try:
            print(f"📄 Fetching content from: {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return {"success": False, "title": "", "content": "", "error": f"Status {response.status_code}"}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.extract()
            
            title = soup.title.string if soup.title else ""
            
            # Simple heuristic for main content
            content_parts = []
            # Try to find common content areas
            main_content = soup.find(['article', 'main', 'div.content', 'div.main-content', 'div.article-body'])
            
            if main_content:
                paragraphs = main_content.find_all(['p', 'h1', 'h2', 'h3'])
            else:
                paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3'])
                
            for p in paragraphs[:20]:
                text = p.get_text().strip()
                if len(text) > 40:
                    content_parts.append(text)
            
            return {
                "success": True,
                "title": title,
                "content": "\n\n".join(content_parts),
                "error": None
            }
        except Exception as e:
            return {"success": False, "title": "", "content": "", "error": str(e)}

    def search(self, query):
        """Main search method - using RSS as primary source"""
        results = self.search_rss(query)
        return {
            "success": len(results) > 0,
            "results": results,
            "error": "No results found" if len(results) == 0 else None
        }

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
        
        # Try to get more detail from the first result
        top_url = search_results["results"][0]["link"]
        page_content = scraper.get_page_content(top_url)
        if page_content["success"] and page_content["content"]:
            combined_content["detailed_content"] = f"Content from {top_url}:\n\n{page_content['content']}"
            
        return combined_content
    
    return {
        "success": False,
        "search_results": [],
        "detailed_content": "",
        "error": search_results.get("error", "No results found")
    }
