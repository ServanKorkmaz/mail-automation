"""Send emails via Outlook SMTP using OAuth2 (alternative method)."""
import logging
import os
import random
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pandas as pd

logger = logging.getLogger(__name__)


class EmailSenderOAuth:
    """
    Alternative email sender using OAuth2.
    Note: This requires setting up an Azure App Registration.
    For simpler solution, try creating a NEW app password after enabling 2FA.
    """
    def __init__(self, smtp_server: str = "smtp.office365.com", smtp_port: int = 587):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = os.getenv("OUTLOOK_USER")
        self.password = os.getenv("OUTLOOK_PASS")
        
        if not self.username or not self.password:
            raise ValueError("OUTLOOK_USER and OUTLOOK_PASS environment variables must be set")

    def create_email(self, school_name: str, recipient_email: str) -> MIMEMultipart:
        """Create email message with Turkish template."""
        msg = MIMEMultipart()
        msg["From"] = self.username
        msg["To"] = recipient_email
        msg["Subject"] = "Öğrenciler için modern KRLE/Din Kültürü öğrenme aracı – Relingo"
        
        body = """Merhaba,

Ben Norveç'ten Servan Korkmaz, eğitim teknolojileri geliştiren bir veri mühendisiyim.

Dinler, kültürler ve etik değerler üzerine etkileşimli öğrenme sunan "Relingo" adlı yapay zekâ destekli bir uygulama geliştirdim.
Türkiye'deki okullara bu öğrenme yaklaşımını tanıtmak isteriz.

Okulunuzun uygulamanın ilk deneme sürecine katılmasını çok isteriz.
2 hafta ücretsiz deneyip kısa bir geri bildirim verebilirseniz bizim icin cok degerli olur.

İnceleme bağlantısı:
🌐 https://relingo-qs8k.vercel.app/


Saygılarımla,
Servan Korkmaz"""
        
        msg.attach(MIMEText(body, "plain", "utf-8"))
        return msg

    def send_email(self, recipient_email: str, school_name: str) -> bool:
        """Send email via SMTP with app password."""
        try:
            msg = self.create_email(school_name, recipient_email)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"✓ Email sent to {school_name} ({recipient_email})")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = str(e)
            if "basic authentication is disabled" in error_msg.lower() or "535" in error_msg:
                logger.error(f"❌ Authentication failed: Basic auth is disabled")
                logger.error(f"")
                logger.error(f"🔧 Try these solutions:")
                logger.error(f"   1. Create a NEW app password AFTER enabling 2FA:")
                logger.error(f"      - Go to: https://account.microsoft.com/security")
                logger.error(f"      - Click 'Administrer' under 'Totrinnskontroll'")
                logger.error(f"      - Find 'App passwords' section")
                logger.error(f"      - Create a NEW app password")
                logger.error(f"      - Update OUTLOOK_PASS in .env")
                logger.error(f"")
                logger.error(f"   2. If that doesn't work, Microsoft may have disabled")
                logger.error(f"      basic auth for your account. Consider using:")
                logger.error(f"      - Gmail SMTP instead (easier setup)")
                logger.error(f"      - Or a different email service")
            else:
                logger.error(f"Authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {e}")
            return False

    def send_emails_from_csv(self, csv_path: str = "schools.csv", delay_min: int = 15, delay_max: int = 45):
        """Send emails to all eligible schools in CSV."""
        df = pd.read_csv(csv_path)
        
        # Filter eligible schools
        eligible = df[
            (df["email"] != "NOT FOUND") & 
            (df["contacted"].str.lower() == "no")
        ].copy()
        
        if eligible.empty:
            logger.info("No eligible schools to contact")
            return
        
        logger.info(f"Sending emails to {len(eligible)} schools")
        
        sent_count = 0
        for idx, row in eligible.iterrows():
            success = self.send_email(row["email"], row["name"])
            
            if success:
                df.at[idx, "contacted"] = "yes"
                sent_count += 1
                
                # Save progress after each email
                df.to_csv(csv_path, index=False)
                
                # Random delay between emails
                if idx < len(eligible) - 1:  # Don't delay after last email
                    delay = random.randint(delay_min, delay_max)
                    logger.info(f"Waiting {delay} seconds before next email...")
                    time.sleep(delay)
        
        logger.info(f"Sent {sent_count} emails successfully")

