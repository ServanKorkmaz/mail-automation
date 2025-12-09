"""Scrape school names from okul.com.tr with pagination support."""
import asyncio
import logging
from typing import List
from urllib.parse import urljoin, urlparse, parse_qs

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SchoolScraper:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_total_pages(self) -> int:
        """Extract total number of pages from pagination."""
        try:
            async with self.session.get(self.base_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch base URL: {response.status}")
                    return 1
                
                html = await response.text()
                soup = BeautifulSoup(html, "lxml")
                
                # Find pagination elements
                pagination = soup.find("div", class_="pagination") or soup.find("ul", class_="pagination")
                if not pagination:
                    logger.warning("No pagination found, assuming single page")
                    return 1
                
                page_links = pagination.find_all("a", href=True)
                max_page = 1
                
                for link in page_links:
                    href = link.get("href", "")
                    if "?page=" in href or "&page=" in href:
                        try:
                            page_num = int(href.split("page=")[-1].split("&")[0])
                            max_page = max(max_page, page_num)
                        except ValueError:
                            continue
                
                # Also check for page numbers in text
                for link in page_links:
                    text = link.get_text(strip=True)
                    if text.isdigit():
                        max_page = max(max_page, int(text))
                
                logger.info(f"Found {max_page} pages")
                return max_page
        except Exception as e:
            logger.error(f"Error getting total pages: {e}")
            return 1

    async def scrape_page(self, page_num: int = 1) -> List[str]:
        """Scrape school names from a specific page."""
        url = self.base_url
        if page_num > 1:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}page={page_num}"
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"Page {page_num} returned status {response.status}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, "lxml")
                
                # Common selectors for school names
                school_names = []
                
                # Try multiple selectors
                selectors = [
                    ("h2", {"class": "school-name"}),
                    ("h3", {"class": "school-name"}),
                    ("a", {"class": "school-link"}),
                    ("div", {"class": "school-title"}),
                    ("span", {"class": "school-name"}),
                ]
                
                for tag, attrs in selectors:
                    elements = soup.find_all(tag, attrs)
                    if elements:
                        for elem in elements:
                            name = elem.get_text(strip=True)
                            if name and len(name) > 3:
                                school_names.append(name)
                        break
                
                # Fallback: look for any h2/h3 with school-like content
                if not school_names:
                    for tag in ["h2", "h3", "h4"]:
                        elements = soup.find_all(tag)
                        for elem in elements:
                            text = elem.get_text(strip=True)
                            if text and ("okul" in text.lower() or "ortaokul" in text.lower() or len(text.split()) <= 5):
                                school_names.append(text)
                
                # Remove duplicates while preserving order
                seen = set()
                unique_names = []
                for name in school_names:
                    if name not in seen:
                        seen.add(name)
                        unique_names.append(name)
                
                logger.info(f"Page {page_num}: Found {len(unique_names)} schools")
                return unique_names
                
        except Exception as e:
            logger.error(f"Error scraping page {page_num}: {e}")
            return []

    async def scrape_all(self) -> List[str]:
        """Scrape all pages and return unique school names."""
        total_pages = await self.get_total_pages()
        
        tasks = [self.scrape_page(page) for page in range(1, total_pages + 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_schools = []
        for result in results:
            if isinstance(result, list):
                all_schools.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Task failed: {result}")
        
        # Final deduplication
        seen = set()
        unique_schools = []
        for school in all_schools:
            if school not in seen:
                seen.add(school)
                unique_schools.append(school)
        
        logger.info(f"Total unique schools found: {len(unique_schools)}")
        return unique_schools

