import re
import asyncio
from typing import Dict, List, Any

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


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
    
    async def _search_google_async(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Use Playwright to search Google and extract results"""
        if not PLAYWRIGHT_AVAILABLE:
            return []
        
        results = []
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self.headers["User-Agent"],
                    viewport={"width": 1280, "height": 800}
                )
                page = await context.new_page()
                
                # Navigate to Google
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                await page.goto(search_url, timeout=15000)
                
                # Wait for results to load
                await page.wait_for_selector("div#search", timeout=10000)
                
                # Extract search results
                result_elements = await page.query_selector_all("div.g")
                
                for elem in result_elements[:max_results]:
                    try:
                        # Get title
                        title_elem = await elem.query_selector("h3")
                        title = await title_elem.inner_text() if title_elem else ""
                        
                        # Get link
                        link_elem = await elem.query_selector("a")
                        link = await link_elem.get_attribute("href") if link_elem else ""
                        
                        # Get snippet
                        snippet_elem = await elem.query_selector("div[data-sncf], div.VwiC3b, span.aCOpRe")
                        snippet = await snippet_elem.inner_text() if snippet_elem else ""
                        
                        if title and link and not link.startswith("/"):
                            results.append({
                                "title": title,
                                "link": link,
                                "snippet": snippet[:500] if snippet else ""
                            })
                    except Exception:
                        continue
                
                await browser.close()
                
        except Exception as e:
            print(f"❌ Playwright search error: {type(e).__name__}: {str(e)}")
        
        return results
    
    async def _search_news_google_async(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Use Playwright to search Google News"""
        if not PLAYWRIGHT_AVAILABLE:
            return []
        
        results = []
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self.headers["User-Agent"],
                    viewport={"width": 1280, "height": 800}
                )
                page = await context.new_page()
                
                # Navigate to Google News search
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=nws"
                await page.goto(search_url, timeout=15000)
                
                # Wait for results
                await page.wait_for_selector("div#search", timeout=10000)
                
                # Extract news results
                result_elements = await page.query_selector_all("div.SoaBEf, div.g")
                
                for elem in result_elements[:max_results]:
                    try:
                        # Get title
                        title_elem = await elem.query_selector("div.n0jPhd, h3, div.mCBkyc")
                        title = await title_elem.inner_text() if title_elem else ""
                        
                        # Get link
                        link_elem = await elem.query_selector("a")
                        link = await link_elem.get_attribute("href") if link_elem else ""
                        
                        # Get snippet
                        snippet_elem = await elem.query_selector("div.GI74Re, div.VwiC3b")
                        snippet = await snippet_elem.inner_text() if snippet_elem else ""
                        
                        # Get date
                        date_elem = await elem.query_selector("span.r0bn4c, div.OSrXXb")
                        date = await date_elem.inner_text() if date_elem else ""
                        
                        if title and link and not link.startswith("/"):
                            results.append({
                                "title": title,
                                "link": link,
                                "snippet": snippet[:500] if snippet else "",
                                "date": date
                            })
                    except Exception:
                        continue
                
                await browser.close()
                
        except Exception as e:
            print(f"❌ Playwright news search error: {type(e).__name__}: {str(e)}")
        
        return results
    
    async def _get_page_content_async(self, url: str) -> Dict[str, Any]:
        """Use Playwright to get page content"""
        if not PLAYWRIGHT_AVAILABLE:
            return {"success": False, "title": "", "content": "", "error": "Playwright not available"}
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self.headers["User-Agent"],
                    viewport={"width": 1280, "height": 800}
                )
                page = await context.new_page()
                
                await page.goto(url, timeout=15000)
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                
                # Get title
                title = await page.title()
                
                # Get main content
                content_parts = []
                
                # Try to find article/main content
                selectors = ["article", "main", "div[role='main']", ".content", ".article-body", "#content"]
                content_elem = None
                
                for selector in selectors:
                    try:
                        content_elem = await page.query_selector(selector)
                        if content_elem:
                            break
                    except:
                        continue
                
                if content_elem:
                    paragraphs = await content_elem.query_selector_all("p, h2, h3, li")
                else:
                    paragraphs = await page.query_selector_all("p, h2, h3")
                
                for p in paragraphs[:30]:
                    try:
                        text = await p.inner_text()
                        if text and len(text.strip()) > 30:
                            content_parts.append(text.strip())
                    except:
                        continue
                
                await browser.close()
                
                return {
                    "success": True,
                    "title": title,
                    "content": "\n\n".join(content_parts[:25]),
                    "error": None
                }
                
        except Exception as e:
            return {"success": False, "title": "", "content": "", "error": str(e)}
    
    def search_news(self, query):
        if not query or not query.strip():
            return {"success": False, "results": [], "error": "Empty query provided"}
        
        if not PLAYWRIGHT_AVAILABLE:
            return {"success": False, "results": [], "error": "Playwright not installed. Run: pip install playwright && playwright install chromium"}
        
        try:
            # Optimize query using LLM if available
            search_query = query
            if self.llm:
                search_query = self.llm.optimize_search_query(query)
            
            print(f"🔍 Searching news for: {search_query}")
            
            # Run async search
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(self._search_news_google_async(search_query, max_results=10))
            finally:
                loop.close()
            
            print(f"📰 Found {len(results)} news results")
            
            return {"success": True, "results": results, "error": None}
        
        except Exception as e:
            error_msg = f"News search error: {type(e).__name__}: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "results": [], "error": error_msg}
    
    def search_text(self, query):
        if not query or not query.strip():
            return {"success": False, "results": [], "error": "Empty query provided"}
        
        if not PLAYWRIGHT_AVAILABLE:
            return {"success": False, "results": [], "error": "Playwright not installed. Run: pip install playwright && playwright install chromium"}
        
        try:
            # Optimize query using LLM if available
            search_query = query
            if self.llm:
                search_query = self.llm.optimize_search_query(query)
            
            print(f"🔍 Searching web for: {search_query}")
            
            # Run async search
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(self._search_google_async(search_query, max_results=10))
            finally:
                loop.close()
            
            print(f"🌐 Found {len(results)} web results")
            
            return {"success": True, "results": results, "error": None}
        
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
        if not PLAYWRIGHT_AVAILABLE:
            return {"success": False, "title": "", "content": "", "error": "Playwright not available"}
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._get_page_content_async(url))
            finally:
                loop.close()
            return result
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
        
        # Try to get detailed content from top results
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
