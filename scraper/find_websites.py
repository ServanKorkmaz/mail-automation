"""Find official school websites via Google Custom Search API."""
import asyncio
import logging
import os
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class WebsiteFinder:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")
        self.service = None
        self.official_domains = [".k12.tr", ".edu.tr", ".gov.tr", "bel.tr", "meb.gov.tr"]
        
        if not self.api_key or not self.cse_id:
            raise ValueError(
                "GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables must be set. "
                "Get them from: https://console.cloud.google.com/ and https://programmablesearchengine.google.com/"
            )

    async def __aenter__(self):
        # Build service synchronously (it's fast, no need for executor)
        self.service = build("customsearch", "v1", developerKey=self.api_key)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def is_official_domain(self, url: str) -> bool:
        """Check if URL belongs to an official domain."""
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.official_domains)

    def search_google_api(self, query: str, max_results: int = 10) -> list[str]:
        """Perform Google search using Custom Search API."""
        try:
            result = self.service.cse().list(
                q=query,
                cx=self.cse_id,
                num=min(max_results, 10)  # API limit is 10 per request
            ).execute()
            
            urls = []
            if "items" in result:
                for item in result["items"]:
                    url = item.get("link", "")
                    if url:
                        urls.append(url)
            
            return urls
            
        except HttpError as e:
            if e.resp.status == 429:
                logger.error("Google API rate limit exceeded. Free tier: 100 searches/day")
            else:
                logger.error(f"Google API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error searching Google API: {e}")
            return []

    def find_official_website(self, school_name: str) -> Optional[str]:
        """Find official website for a school."""
        query = f'"{school_name}" resmi web sitesi'
        
        try:
            urls = self.search_google_api(query, max_results=10)
            
            # Prioritize official domains
            for url in urls:
                if self.is_official_domain(url):
                    logger.info(f"Found official website for {school_name}: {url}")
                    return url
            
            # If no official domain found, return first result
            if urls:
                logger.info(f"Found website for {school_name}: {urls[0]}")
                return urls[0]
            
            logger.warning(f"No website found for {school_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding website for {school_name}: {e}")
            return None

    async def find_websites_batch(self, school_names: list[str], max_concurrent: int = 5) -> dict[str, Optional[str]]:
        """Find websites for multiple schools concurrently."""
        # Note: Google API is synchronous, so we run it in executor
        loop = asyncio.get_event_loop()
        results = {}
        
        async def find_with_delay(school_name: str, index: int):
            # Small delay to respect rate limits (100 requests/day free tier)
            if index > 0:
                await asyncio.sleep(0.5)  # 0.5s delay between requests
            
            # Run synchronous API call in executor
            website = await loop.run_in_executor(
                None, 
                self.find_official_website, 
                school_name
            )
            results[school_name] = website
        
        tasks = [find_with_delay(name, idx) for idx, name in enumerate(school_names)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
