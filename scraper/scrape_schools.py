"""Scrape school names from okul.com.tr with pagination support."""
import asyncio
import logging
import random
from typing import List
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SchoolScraper:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    async def __aenter__(self):
        # Use cookie jar for session management
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60, connect=30),
            headers=self.headers,
            cookie_jar=cookie_jar,
            connector=connector
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_with_retry(self, url: str, max_retries: int = 3) -> str | None:
        """Fetch URL with retry logic and Cloudflare handling."""
        for attempt in range(max_retries):
            try:
                # Add random delay to avoid rate limiting
                if attempt > 0:
                    delay = random.uniform(2, 5) * (attempt + 1)
                    logger.info(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s delay")
                    await asyncio.sleep(delay)
                
                async with self.session.get(url, allow_redirects=True) as response:
                    # Handle Cloudflare challenge pages
                    if response.status == 403:
                        logger.warning(f"403 Forbidden - Cloudflare protection detected (attempt {attempt + 1})")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(random.uniform(5, 10))
                            continue
                        return None
                    
                    if response.status == 521:
                        logger.warning(f"521 Cloudflare error (attempt {attempt + 1})")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(random.uniform(5, 10))
                            continue
                        return None
                    
                    if response.status != 200:
                        logger.warning(f"Status {response.status} for {url}")
                        if attempt < max_retries - 1:
                            continue
                        return None
                    
                    html = await response.text()
                    
                    # Check if we got a Cloudflare challenge page
                    if "challenge-platform" in html.lower() or "cf-browser-verification" in html.lower():
                        logger.warning(f"Cloudflare challenge page detected (attempt {attempt + 1})")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(random.uniform(10, 15))
                            continue
                        return None
                    
                    return html
                    
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    continue
            except Exception as e:
                logger.error(f"Error fetching {url} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    continue
        
        return None

    async def get_total_pages(self) -> int:
        """Extract total number of pages from pagination."""
        try:
            html = await self.fetch_with_retry(self.base_url)
            if not html:
                logger.error("Failed to fetch base URL after retries")
                return 1
            
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
            # Add small delay between requests
            await asyncio.sleep(random.uniform(1, 3))
            
            html = await self.fetch_with_retry(url)
            if not html:
                logger.warning(f"Failed to fetch page {page_num}")
                return []
            
            soup = BeautifulSoup(html, "lxml")
            
            school_names = []
            
            # Try to find school links - common patterns for school listing sites
            # Look for links that contain school names (usually in list items or cards)
            school_links = []
            
            # Pattern 1: Links in list items with school-related classes
            for li in soup.find_all("li", class_=lambda x: x and any(word in str(x).lower() for word in ["school", "okul", "item", "card"])):
                link = li.find("a", href=True)
                if link:
                    text = link.get_text(strip=True)
                    if text and len(text) > 5 and len(text) < 100:
                        school_links.append(text)
            
            # Pattern 2: Direct links with school-related href patterns
            for link in soup.find_all("a", href=True):
                href = link.get("href", "").lower()
                text = link.get_text(strip=True)
                # Check if link looks like a school detail page
                if any(pattern in href for pattern in ["/okul/", "/school/", "/ortaokul/", "/orta-okul/"]):
                    if text and len(text) > 5 and len(text) < 100:
                        # Filter out common UI text
                        if not any(ui_text in text.lower() for ui_text in [
                            "detay", "görüntüle", "tüm detaylar", "devam", "daha fazla",
                            "view", "details", "more", "continue", "istanbul ortaokulları"
                        ]):
                            school_links.append(text)
            
            # Pattern 3: Look for headings in school cards/items
            for card in soup.find_all(["div", "article", "section"], class_=lambda x: x and any(
                word in str(x).lower() for word in ["card", "item", "school", "okul", "list"]
            )):
                # Find the main heading or link in the card
                heading = card.find(["h2", "h3", "h4", "h5"])
                if heading:
                    text = heading.get_text(strip=True)
                    if text and len(text) > 5 and len(text) < 100:
                        if not any(ui_text in text.lower() for ui_text in [
                            "detay", "görüntüle", "tüm detaylar", "istanbul ortaokulları"
                        ]):
                            school_links.append(text)
                else:
                    # Try to find a link in the card
                    link = card.find("a", href=True)
                    if link:
                        text = link.get_text(strip=True)
                        if text and len(text) > 5 and len(text) < 100:
                            if not any(ui_text in text.lower() for ui_text in [
                                "detay", "görüntüle", "tüm detaylar", "istanbul ortaokulları"
                            ]):
                                school_links.append(text)
            
            # Pattern 4: Look for table rows with school data
            for row in soup.find_all("tr"):
                cells = row.find_all(["td", "th"])
                for cell in cells:
                    link = cell.find("a", href=True)
                    if link:
                        text = link.get_text(strip=True)
                        if text and len(text) > 5 and len(text) < 100:
                            if not any(ui_text in text.lower() for ui_text in [
                                "detay", "görüntüle", "tüm detaylar", "istanbul ortaokulları"
                            ]):
                                school_links.append(text)
            
            school_names = school_links
            
            # Remove duplicates while preserving order
            seen = set()
            unique_names = []
            for name in school_names:
                # Additional filtering: exclude common UI text and very short/long names
                name_lower = name.lower()
                exclude_patterns = [
                    "istanbul ortaokulları", "istanbul ortaokullar",
                    "aradığınız", "görüntüleyin", "detaylarını",
                    "tüm detaylar", "devamını", "daha fazla",
                    "view", "details", "more", "continue",
                    "okul listesi", "school list", "sayfa", "page"
                ]
                if any(pattern in name_lower for pattern in exclude_patterns):
                    logger.debug(f"Excluding UI text: {name}")
                    continue
                
                if name not in seen and 5 < len(name) < 100:
                    seen.add(name)
                    unique_names.append(name)
            
            if unique_names:
                logger.debug(f"Page {page_num} sample names: {unique_names[:3]}")
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

