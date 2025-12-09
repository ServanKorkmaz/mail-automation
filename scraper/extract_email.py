"""Extract email addresses from school websites."""
import asyncio
import logging
import re
from typing import Optional, List
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EmailExtractor:
    def __init__(self):
        self.session = None
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
        )

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

    def extract_emails_from_text(self, text: str) -> List[str]:
        """Extract email addresses from text."""
        emails = self.email_pattern.findall(text)
        # Filter out common false positives
        filtered = [
            e for e in emails
            if not any(x in e.lower() for x in ["example.com", "test.com", "domain.com", "email.com"])
        ]
        return list(set(filtered))

    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL."""
        if not self.session:
            logger.error("Session not initialized")
            return None
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None
                return await response.text()
        except Exception as e:
            logger.debug(f"Error fetching {url}: {e}")
            return None

    async def extract_from_page(self, url: str) -> Optional[str]:
        """Extract email from a single page."""
        html = await self.fetch_page(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, "lxml")
        
        # Check footer
        footer = soup.find("footer")
        if not footer:
            footer = soup.find("div", class_=lambda x: x and "footer" in x.lower() if x else False)
        if footer:
            emails = self.extract_emails_from_text(footer.get_text())
            if emails:
                return emails[0]
        
        # Check mailto links
        mailto_links = soup.find_all("a", href=re.compile(r"^mailto:", re.I))
        for link in mailto_links:
            href = link.get("href", "")
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email and "@" in email:
                return email
        
        # Check contact/iletisim sections
        contact_keywords = ["iletişim", "contact", "iletisim"]
        for keyword in contact_keywords:
            sections = soup.find_all(string=re.compile(keyword, re.I))
            for section in sections:
                if section:
                    parent = section.find_parent()
                    if parent:
                        emails = self.extract_emails_from_text(parent.get_text())
                        if emails:
                            return emails[0]
        
        # Check entire page
        page_text = soup.get_text()
        emails = self.extract_emails_from_text(page_text)
        if emails:
            return emails[0]
        
        return None

    async def find_contact_page(self, base_url: str) -> List[str]:
        """Find contact/iletisim page URLs."""
        html = await self.fetch_page(base_url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "lxml")
        contact_urls = []
        
        # Find links with contact keywords
        keywords = ["iletişim", "contact", "iletisim", "bize-ulasin", "bize-ulaşın"]
        seen_urls = set()
        
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True).lower()
            
            if any(keyword in text or keyword in href.lower() for keyword in keywords):
                full_url = urljoin(base_url, href)
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    contact_urls.append(full_url)
        
        return contact_urls

    async def extract_email(self, website_url: str) -> Optional[str]:
        """Extract email from website, checking multiple pages."""
        if not website_url:
            return None
        
        # Try main page first
        email = await self.extract_from_page(website_url)
        if email:
            logger.info(f"Found email on main page: {email}")
            return email
        
        # Try contact pages
        contact_urls = await self.find_contact_page(website_url)
        for contact_url in contact_urls[:3]:  # Limit to 3 contact pages
            email = await self.extract_from_page(contact_url)
            if email:
                logger.info(f"Found email on contact page: {email}")
                return email
        
        logger.warning(f"No email found for {website_url}")
        return None

    async def extract_emails_batch(
        self, websites: dict[str, Optional[str]], max_concurrent: int = 5
    ) -> dict[str, Optional[str]]:
        """Extract emails for multiple websites concurrently."""
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}
        
        async def extract_with_limit(school_name: str, website: Optional[str]):
            async with semaphore:
                email = await self.extract_email(website) if website else None
                results[school_name] = email or "NOT FOUND"
                await asyncio.sleep(0.5)  # Rate limiting
        
        tasks = [
            extract_with_limit(name, website)
            for name, website in websites.items()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results

