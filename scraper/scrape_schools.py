"""Scrape school names from okul.com.tr with pagination support using Playwright."""
import asyncio
import logging
import random
from typing import List

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)


class SchoolScraper:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.browser: Browser | None = None
        self.playwright = None

    async def __aenter__(self):
        # Launch Playwright browser with stealth settings
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def fetch_with_playwright(self, url: str, max_retries: int = 3) -> str | None:
        """Fetch URL using Playwright with retry logic."""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = random.uniform(3, 6) * (attempt + 1)
                    logger.info(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s delay")
                    await asyncio.sleep(delay)
                
                # Create a new context for each request to avoid cookie/session issues
                context = await self.browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='tr-TR',
                    timezone_id='Europe/Istanbul',
                )
                
                page: Page = await context.new_page()
                
                try:
                    # Navigate to page and wait for network to be idle
                    response = await page.goto(
                        url,
                        wait_until='networkidle',
                        timeout=60000
                    )
                    
                    if not response:
                        logger.warning(f"No response for {url} (attempt {attempt + 1})")
                        await context.close()
                        if attempt < max_retries - 1:
                            continue
                        return None
                    
                    # Check for Cloudflare challenge
                    if response.status == 403 or response.status == 521:
                        logger.warning(f"Cloudflare protection detected (status {response.status}, attempt {attempt + 1})")
                        # Wait a bit for Cloudflare to potentially resolve
                        await asyncio.sleep(random.uniform(5, 10))
                        await context.close()
                        if attempt < max_retries - 1:
                            continue
                        return None
                    
                    # Wait a bit for any JavaScript to execute
                    await asyncio.sleep(random.uniform(2, 4))
                    
                    # Get page content
                    html = await page.content()
                    
                    # Check for Cloudflare challenge in content
                    if "challenge-platform" in html.lower() or "cf-browser-verification" in html.lower() or "just a moment" in html.lower():
                        logger.warning(f"Cloudflare challenge page detected (attempt {attempt + 1})")
                        await context.close()
                        if attempt < max_retries - 1:
                            await asyncio.sleep(random.uniform(10, 15))
                            continue
                        return None
                    
                    await context.close()
                    return html
                    
                except Exception as e:
                    await context.close()
                    raise e
                    
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
            html = await self.fetch_with_playwright(self.base_url)
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
            await asyncio.sleep(random.uniform(2, 4))
            
            html = await self.fetch_with_playwright(url)
            if not html:
                logger.warning(f"Failed to fetch page {page_num}")
                return []
            
            soup = BeautifulSoup(html, "lxml")
            
            school_names = []
            
            # Try to find school links - common patterns for school listing sites
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
        
        # Process pages with limited concurrency to avoid overwhelming the server
        semaphore = asyncio.Semaphore(2)  # Only 2 concurrent pages
        
        async def scrape_with_limit(page_num: int):
            async with semaphore:
                return await self.scrape_page(page_num)
        
        tasks = [scrape_with_limit(page) for page in range(1, total_pages + 1)]
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
