# Email Automation System

Automated system to scrape schools in Istanbul, find their official websites, extract email addresses, and send personalized emails.

## Features

- Async/concurrent web scraping with pagination support
- Google Custom Search API integration to find official school websites
- Intelligent email extraction from multiple page sections
- CSV data storage with progress tracking
- Outlook SMTP email sending with rate limiting
- Comprehensive logging and error handling

## Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set up environment variables:**
```bash
cp env.example .env
# Edit .env and add:
# - Outlook credentials (OUTLOOK_USER, OUTLOOK_PASS)
# - Google Custom Search API credentials (GOOGLE_API_KEY, GOOGLE_CSE_ID)
```

3. **Get Google Custom Search API credentials:**
   - Go to https://console.cloud.google.com/
   - Create a project and enable "Custom Search API"
   - Create an API key in Credentials
   - Go to https://programmablesearchengine.google.com/
   - Create a Custom Search Engine (search entire web: `*`)
   - Copy the Search Engine ID (CSE ID)
   - Add both to your `.env` file

## Usage

### Basic Usage (Scraping Only)

```bash
python main.py
```

This will:
1. Scrape all schools from the website
2. Find official websites via Google search
3. Extract email addresses
4. Save results to `schools.csv`

### Sending Emails

To enable email sending, set the environment variable:

```bash
# Windows PowerShell
$env:SEND_EMAILS="true"
python main.py

# Linux/Mac
export SEND_EMAILS=true
python main.py
```

Or edit `.env` file:
```
SEND_EMAILS=true
```

## Project Structure

```
mail_automation/
├── scraper/
│   ├── scrape_schools.py    # Web scraping with pagination
│   ├── find_websites.py      # Google search for official sites
│   └── extract_email.py     # Email extraction from websites
├── send_email.py            # Outlook SMTP email sender
├── main.py                  # Main orchestrator
├── schools.csv              # Generated output file
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
└── README.md               # This file
```

## CSV Output Format

The `schools.csv` file contains:

| Column    | Description                          |
|-----------|--------------------------------------|
| name      | School name                          |
| website   | Official website URL                 |
| email     | Contact email or "NOT FOUND"        |
| contacted | "yes" or "no" (email sent status)    |

## Configuration

### Email Settings

- **SMTP Server:** `smtp.office365.com`
- **Port:** `587`
- **Encryption:** STARTTLS
- **Rate Limiting:** 15-45 seconds between emails

### Concurrency Settings

- Website finding: 5 concurrent requests
- Email extraction: 5 concurrent requests
- Adjustable in respective modules

## Logging

All operations are logged to:
- Console output
- `automation.log` file

## Error Handling

The system includes:
- Retry logic for failed requests
- Graceful error handling
- Progress saving after each email
- Duplicate detection

## Notes

- The system respects rate limits to avoid being blocked
- Emails are only sent to schools with valid emails and `contacted="no"`
- Progress is saved incrementally to prevent data loss
- Existing CSV data is preserved when adding new schools

