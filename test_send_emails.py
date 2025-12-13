"""Test script to send emails to 5 schools."""
import pandas as pd
import logging
from dotenv import load_dotenv
from send_email import EmailSender

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_send_emails(csv_path: str = "schools.csv", limit: int = 5):
    """Send test emails to a limited number of schools."""
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    
    # Filter eligible schools (have email, not contacted)
    eligible = df[
        (df["email"].notna()) &
        (df["email"] != "NOT FOUND") &
        (df["email"] != "") &
        (df["contacted"].str.lower() != "yes")
    ].copy()
    
    if eligible.empty:
        logger.error("No eligible schools found to contact")
        return
    
    # Filter for actual schools first (prefer .k12.tr, .edu.tr domains or school names)
    school_domains = [".k12.tr", ".edu.tr"]
    school_keywords = ["ortaokul", "koleji", "okul"]
    
    actual_schools = eligible[
        eligible["email"].str.contains("|".join(school_domains), case=False, na=False) |
        eligible["name"].str.contains("|".join(school_keywords), case=False, na=False)
    ].head(limit)
    
    # If not enough actual schools, fill with any eligible
    if len(actual_schools) < limit:
        remaining = limit - len(actual_schools)
        additional = eligible[~eligible.index.isin(actual_schools.index)].head(remaining)
        actual_schools = pd.concat([actual_schools, additional])
    
    if actual_schools.empty:
        logger.warning("No schools found, using any available emails")
        actual_schools = eligible.head(limit)
    
    logger.info(f"\nSending test emails to {len(actual_schools)} schools:")
    for idx, row in actual_schools.iterrows():
        logger.info(f"  - {row['name'][:60]}: {row['email']}")
    
    print("\n" + "=" * 60)
    print(f"Ready to send {len(actual_schools)} test emails")
    print("=" * 60)
    
    # Initialize email sender
    try:
        sender = EmailSender()
    except ValueError as e:
        logger.error(f"Cannot send emails: {e}")
        logger.error("Make sure OUTLOOK_USER and OUTLOOK_PASS are set in .env file")
        return
    
    # Send emails
    sent_count = 0
    failed_count = 0
    
    for idx, row in actual_schools.iterrows():
        school_name = row["name"]
        email = row["email"]
        
        logger.info(f"\nSending email to {school_name[:50]} ({email})...")
        
        try:
            success = sender.send_email(email, school_name)
            
            if success:
                df.at[idx, "contacted"] = "yes"
                sent_count += 1
                logger.info(f"✓ Email sent successfully")
            else:
                failed_count += 1
                logger.warning(f"✗ Failed to send email")
                
        except Exception as e:
            logger.error(f"✗ Error: {e}")
            failed_count += 1
    
    # Save updated CSV
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST EMAIL SUMMARY")
    print("=" * 60)
    print(f"Total attempted: {len(actual_schools)}")
    print(f"Successfully sent: {sent_count}")
    print(f"Failed: {failed_count}")
    print("=" * 60)
    print(f"\nUpdated {csv_path} with contact status")


if __name__ == "__main__":
    test_send_emails(limit=5)

