"""Find official school websites via Google search."""
import asyncio
import logging
import random
import re
from typing import Optional
from urllib.parse import quote_plus

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebsiteFinder:
    def __init__(self):
        self.session = None
        self.official_domains = [".k12.tr", ".edu.tr", ".gov.tr", "bel.tr", "meb.gov.tr"]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def __aenter__(self):
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60, connect=30),
            headers=self.headers,
            cookie_jar=cookie_jar
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def is_official_domain(self, url: str) -> bool:
        """Check if URL belongs to an official domain."""
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.official_domains)

    async def search_google(self, query: str, max_results: int = 10) -> list[str]:
        """Perform Google search and return result URLs."""
        try:
            encoded_query = quote_plus(query)
            # Use Google search URL
            search_url = f"https://www.google.com/search?q={encoded_query}&num={max_results}"
            
            async with self.session.get(search_url) as response:
                if response.status != 200:
                    logger.warning(f"Google search returned status {response.status}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, "lxml")
                
                urls = []
                
                # Extract links from search results
                for link in soup.find_all("a", href=True):
                    href = link.get("href", "")
                    if href.startswith("/url?q="):
                        url = href.split("/url?q=")[1].split("&")[0]
                        if url.startswith("http"):
                            urls.append(url)
                    elif href.startswith("http") and "google.com" not in href:
                        urls.append(href)
                
                # Also try data-ved links
                for div in soup.find_all("div", {"data-ved": True}):
                    link = div.find("a", href=True)
                    if link:
                        href = link.get("href", "")
                        if href.startswith("/url?q="):
                            url = href.split("/url?q=")[1].split("&")[0]
                            if url.startswith("http") and url not in urls:
                                urls.append(url)
                
                return urls[:max_results]
                
        except Exception as e:
            logger.error(f"Error searching Google: {e}")
            return []

    async def find_official_website(self, school_name: str) -> Optional[str]:
        """Find official website for a school."""
        query = f'"{school_name}" resmi web sitesi'
        
        try:
            urls = await self.search_google(query, max_results=15)
            
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
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}
        
        async def find_with_limit(school_name: str):
            async with semaphore:
                website = await self.find_official_website(school_name)
                results[school_name] = website
                await asyncio.sleep(1)  # Rate limiting
        
        tasks = [find_with_limit(name) for name in school_names]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results

