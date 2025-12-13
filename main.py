"""Main orchestrator for the email automation system."""
import asyncio
import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from scraper.scrape_schools import SchoolScraper
from scraper.find_websites import WebsiteFinder
from scraper.extract_email import EmailExtractor
from send_email import EmailSender

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("automation.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def scrape_schools(base_url: str) -> list[str]:
    """Scrape all school names from the website."""
    logger.info("Starting school scraping...")
    async with SchoolScraper(base_url) as scraper:
        schools = await scraper.scrape_all()
    logger.info(f"Scraped {len(schools)} schools")
    return schools


async def find_websites(school_names: list[str]) -> dict[str, str | None]:
    """Find official websites for all schools."""
    logger.info("Finding websites...")
    async with WebsiteFinder() as finder:
        websites = await finder.find_websites_batch(school_names, max_concurrent=5)
    logger.info(f"Found websites for {sum(1 for v in websites.values() if v)} schools")
    return websites


async def extract_emails(websites: dict[str, str | None]) -> dict[str, str]:
    """Extract emails from all websites."""
    logger.info("Extracting emails...")
    async with EmailExtractor() as extractor:
        emails = await extractor.extract_emails_batch(websites, max_concurrent=5)
    logger.info(f"Found emails for {sum(1 for v in emails.values() if v != 'NOT FOUND')} schools")
    return emails


def save_to_csv(schools_data: list[dict], csv_path: str = "schools.csv"):
    """Save school data to CSV with better organization."""
    df = pd.DataFrame(schools_data)
    
    # Ensure 'contacted' column exists with default 'no'
    if "contacted" not in df.columns:
        df["contacted"] = "no"
    
    # Ensure all required columns exist
    required_columns = ["name", "website", "email", "contacted"]
    for col in required_columns:
        if col not in df.columns:
            df[col] = ""
    
    df = df[required_columns]
    
    # Clean and organize data
    # Remove rows with invalid school names (UI text, placeholders)
    invalid_patterns = [
        "istanbul ortaokulları", "istanbul ortaokullar",
        "aradığınız", "görüntüleyin", "detaylarını",
        "tüm detaylar", "giriş yap", "devamını",
        "okul listesi", "school list", "sayfa", "page"
    ]
    
    def is_valid_school_name(name: str) -> bool:
        if not name or len(name) < 5:
            return False
        name_lower = str(name).lower()
        return not any(pattern in name_lower for pattern in invalid_patterns)
    
    df = df[df["name"].apply(is_valid_school_name)].copy()
    
    # Sort by: 1) Has email, 2) Has website, 3) Name alphabetically
    df["_sort_key"] = (
        df["email"].apply(lambda x: 0 if x == "NOT FOUND" else 1) * 100 +
        df["website"].apply(lambda x: 0 if not x or x == "" else 1) * 10 +
        df["name"].str.lower().str[0].apply(ord)
    )
    df = df.sort_values("_sort_key", ascending=False).drop("_sort_key", axis=1)
    
    # Reset index for clean numbering
    df = df.reset_index(drop=True)
    
    # Save with UTF-8 encoding and proper formatting
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    
    # Log statistics
    total = len(df)
    with_email = len(df[df["email"] != "NOT FOUND"])
    with_website = len(df[df["website"].notna() & (df["website"] != "")])
    contacted = len(df[df["contacted"].str.lower() == "yes"])
    
    logger.info(f"Saved {total} schools to {csv_path}")
    logger.info(f"Statistics: {with_email} with email, {with_website} with website, {contacted} contacted")


def load_existing_csv(csv_path: str = "schools.csv") -> pd.DataFrame | None:
    """Load existing CSV if it exists."""
    if Path(csv_path).exists():
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded existing CSV with {len(df)} schools")
            return df
        except Exception as e:
            logger.warning(f"Could not load existing CSV: {e}")
    return None


async def main():
    """Main execution function."""
    base_url = "https://okul.com.tr/ortaokul/istanbul?f-f=4"
    csv_path = "schools.csv"
    
    logger.info("=" * 60)
    logger.info("Starting Email Automation System")
    logger.info("=" * 60)
    
    # Load existing data if available
    existing_df = load_existing_csv(csv_path)
    existing_schools = set(existing_df["name"].tolist()) if existing_df is not None else set()
    
    # Step 1: Scrape schools
    all_schools = await scrape_schools(base_url)
    
    # Filter out already processed schools
    new_schools = [s for s in all_schools if s not in existing_schools]
    logger.info(f"Found {len(new_schools)} new schools to process")
    
    if not new_schools:
        logger.info("No new schools to process")
    else:
        # Step 2: Find websites
        websites = await find_websites(new_schools)
        
        # Step 3: Extract emails
        emails = await extract_emails(websites)
        
        # Prepare data for CSV
        new_data = [
            {
                "name": school,
                "website": websites.get(school, ""),
                "email": emails.get(school, "NOT FOUND"),
                "contacted": "no"
            }
            for school in new_schools
        ]
        
        # Merge with existing data
        if existing_df is not None:
            existing_data = existing_df.to_dict("records")
            all_data = existing_data + new_data
        else:
            all_data = new_data
        
        # Save to CSV
        save_to_csv(all_data, csv_path)
    
    # Step 4: Send emails (optional - can be run separately)
    send_emails = os.getenv("SEND_EMAILS", "false").lower() == "true"
    
    if send_emails:
        logger.info("Starting email sending...")
        try:
            sender = EmailSender()
            sender.send_emails_from_csv(csv_path)
        except ValueError as e:
            logger.error(f"Cannot send emails: {e}")
            logger.info("Set OUTLOOK_USER and OUTLOOK_PASS environment variables to enable email sending")
    else:
        logger.info("Email sending skipped (set SEND_EMAILS=true to enable)")
    
    logger.info("=" * 60)
    logger.info("Automation complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

