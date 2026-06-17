import re
import logging
import urllib.parse
from typing import Dict, Any, List
import httpx
from tools.base import BaseTool

logger = logging.getLogger("jarvis.tools.local_browse")

class LocalBrowseTool(BaseTool):
    """
    Scrapes search results from DuckDuckGo HTML search asynchronously without tracking.
    """
    @property
    def name(self) -> str:
        return "local_browse"

    @property
    def description(self) -> str:
        return "Queries the web using DuckDuckGo and returns search results containing titles, URLs, and text snippets."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to lookup."
                }
            },
            "required": ["query"],
            "additionalProperties": False
        }

    def _strip_tags(self, text: str) -> str:
        """
        Remove HTML tags and clean up whitespace.
        """
        # Remove tags
        clean = re.sub(r"<[^>]*>", "", text)
        # Unescape common HTML entities
        clean = clean.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#x27;", "'").replace("&nbsp;", " ")
        # Clean double spaces
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()

    async def run(self, **kwargs) -> str:
        query = kwargs.get("query", "")
        if not query:
            return "Error: No search query provided."

        logger.info(f"Web search query: '{query}'")
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code != 200:
                    logger.error(f"DuckDuckGo returned status {response.status_code}")
                    return f"Error: Unable to fetch search results. DuckDuckGo returned status {response.status_code}."

                html = response.text
                
                # Split the document by result container
                blocks = html.split('<div class="result results_links results_links_deep web-result')
                if len(blocks) <= 1:
                    blocks = html.split('<div class="result result--links')
                if len(blocks) <= 1:
                    return f"No search results found for query: '{query}'."

                results: List[str] = []
                # Parse top 5 results
                for block in blocks[1:6]:
                    # Extract URL and Title
                    # HTML structure: <a class="result__a" href="[URL]">[TITLE]</a>
                    title_url_match = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
                    # Extract Snippet
                    # HTML structure: <a class="result__snippet" ...>[SNIPPET]</a>
                    snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, re.DOTALL)
                    
                    if title_url_match:
                        raw_url = title_url_match.group(1)
                        raw_title = title_url_match.group(2)
                        
                        # Unescape redirect URLs if they are proxied through DDG
                        # e.g., //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com
                        if "uddg=" in raw_url:
                            parsed_url = urllib.parse.urlparse(raw_url)
                            query_dict = urllib.parse.parse_qs(parsed_url.query)
                            url_val = query_dict.get("uddg", [raw_url])[0]
                        else:
                            url_val = raw_url

                        title = self._strip_tags(raw_title)
                        snippet = self._strip_tags(snippet_match.group(1)) if snippet_match else "No snippet available."
                        
                        results.append(f"Title: {title}\nURL: {url_val}\nSnippet: {snippet}\n---")

                if not results:
                    return f"No results could be parsed for query: '{query}'."

                return "\n".join(results)

        except httpx.RequestError as req_err:
            logger.error(f"HTTP request error during search: {req_err}")
            return f"Error requesting web search: {req_err}"
        except Exception as e:
            logger.error(f"Error scraping search results: {e}", exc_info=True)
            return f"Error performing web search: {str(e)}"
