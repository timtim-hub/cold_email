"""
Email module for crafting and sending personalized cold emails
"""

import json
import smtplib
import imaplib
import email.utils
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from openai import OpenAI
import config


class EmailSender:
    def __init__(self):
        self.smtp_host = config.SMTP_HOST
        self.smtp_port = config.SMTP_PORT
        self.smtp_username = config.SMTP_USERNAME
        self.smtp_password = config.SMTP_PASSWORD
        self.from_email = config.FROM_EMAIL
        self.openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.current_sender_index = 0  # For rotating sender addresses
        
    def get_rotating_sender(self) -> str:
        """
        Get next rotating sender address from catch-all domain.
        This bypasses per-address rate limits while all emails go to your inbox.
        """
        if config.USE_ROTATING_SENDERS:
            prefix = config.ROTATING_SENDER_PREFIXES[self.current_sender_index % len(config.ROTATING_SENDER_PREFIXES)]
            self.current_sender_index += 1
            return f"{prefix}@{config.CATCH_ALL_DOMAIN}"
        return self.from_email
        
    def clean_company_name(self, raw_name: str) -> str:
        """
        Clean up scraped company names by removing page titles, separators, etc.
        Examples:
        - "Contact – OR Concrete Inc." -> "OR Concrete Inc."
        - "Home | Vice Heating" -> "Vice Heating"
        - "About Us - Deck Builder" -> "Deck Builder"
        """
        import re
        
        # Remove common page title prefixes
        prefixes_to_remove = [
            r'^Contact\s*[-–|:]\s*',
            r'^Home\s*[-–|:]\s*',
            r'^About\s*(Us)?\s*[-–|:]\s*',
            r'^Welcome\s*(to)?\s*[-–|:]\s*',
            r'^Index\s*[-–|:]\s*',
        ]
        
        cleaned = raw_name
        for prefix in prefixes_to_remove:
            cleaned = re.sub(prefix, '', cleaned, flags=re.IGNORECASE)
        
        # Remove "Welcome to" from anywhere
        cleaned = re.sub(r'\bWelcome to\b\s*', '', cleaned, flags=re.IGNORECASE)
        
        # If there are separators, intelligently pick the company name
        # Priority: | then – then - then :
        separators = ['|', '–', ' - ', ':']
        for sep in separators:
            if sep in cleaned:
                parts = [p.strip() for p in cleaned.split(sep)]
                # Filter out very short parts and common page words
                page_words = ['home', 'contact', 'about', 'welcome', 'services']
                filtered_parts = [p for p in parts if len(p) > 3 and p.lower() not in page_words]
                
                if filtered_parts:
                    # Take the first substantial part (usually the company name)
                    cleaned = filtered_parts[0]
                break
            
        return cleaned.strip()
    
    def generate_personalized_email(self, company_data: Dict) -> Dict:
        """
        Generate a hyper-personalized email using OpenAI API
        """
        raw_company_name = company_data.get("name", "there")
        company_name = self.clean_company_name(raw_company_name)
        website_url = company_data.get("url", "")
        website_content = company_data.get("website_content", "")[:2000]  # Limit for token efficiency
        speed_test = company_data.get("speed_test", {})
        
        # Extract speed test metrics
        load_time = speed_test.get("load_time", "N/A")
        page_size = speed_test.get("page_size", "N/A")
        grade = speed_test.get("grade", "N/A")
        
        # Craft detailed prompt for GPT - SHORTER VERSION
        prompt = f"""You are Jonas from {config.COMPANY_NAME}, {config.COMPANY_DESCRIPTION}.

Write a SHORT, punchy cold email about their website performance issues.

🚨 NO PLACEHOLDERS - Sign as "Jonas" (not [Your Name])

EMAIL STRUCTURE (120-180 words MAX):

GREETING:
Dear {company_name} Team,

BODY:
1. Hook: "I ran a speed test on {website_url}"
2. Their metrics: Load time {load_time}, Grade: {grade}
3. Impact: Lost customers, poor SEO, wasted ads
4. DO NOT give tips on HOW to fix - that's our service
5. Offer: We can fix this fast
6. CTA: Reply or email {config.CONTACT_EMAIL}
7. Professional, urgent, direct

SIGNATURE:
Best regards,

Jonas
LeSavoir.Agency
{config.CONTACT_EMAIL}

IMPORTANT: Start with "Dear {company_name} Team," and sign as "Jonas" - NOT [Your Name] or placeholders.

Company Details:
- Company: {company_name}
- Website: {website_url}
- Website Title/Info: {company_data.get('website_title', 'N/A')}
- Speed Test Results:
  * Load Time: {load_time}
  * Page Size: {page_size}
  * Performance Grade: {grade}

Website Content Sample (use this to show you understand their business):
{website_content}

Write ONLY the email body (no subject line in the body). Be specific about their business based on the content. Make it feel like a human wrote it after carefully analyzing their website.

Email body:"""

        try:
            print(f"Generating personalized email for {company_name}...")
            
            # Use OpenAI Chat Completions API with GPT-4.1 for high-quality personalization
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-2025-04-14",  # GPT-4.1 - latest model with best instruction following
                messages=[
                    {"role": "system", "content": "You are a professional website performance consultant writing personalized outreach emails."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.7,
                top_p=1.0,
                frequency_penalty=0.3,
                presence_penalty=0.3
            )
            
            email_body = response.choices[0].message.content.strip()
            
            # Don't add extra signature - GPT should sign as Jonas
            # But ensure contact email is at the end if not present
            if config.CONTACT_EMAIL not in email_body:
                email_body += f"\n\n{config.CONTACT_EMAIL}"
            
            # Generate subject line
            subject = config.EMAIL_SUBJECT_TEMPLATE.format(company_name=company_name)
            
            print(f"Email generated successfully for {company_name}")
            
            return {
                "subject": subject,
                "body": email_body,
                "success": True
            }
            
        except Exception as e:
            print(f"Error generating email for {company_name}: {e}")
            self.log_error(f"generate_personalized_email error for {company_name}: {e}")
            return {
                "subject": "",
                "body": "",
                "success": False,
                "error": str(e)
            }
    
    def save_to_sent_folder(self, msg: MIMEMultipart):
        """
        Save email to Sent folder via IMAP.
        This works even with rotating sender addresses because we authenticate
        with the main account and save the complete message.
        """
        try:
            # Connect to IMAP (Namecheap uses same host)
            imap_host = self.smtp_host.replace('mail.', 'mail.')  # Keep as is for Namecheap
            imap = imaplib.IMAP4_SSL(imap_host, 993)
            imap.login(self.smtp_username, self.smtp_password)
            
            # Save to Sent folder - the complete message with rotating sender
            imap.append('Sent', '\\Seen', imaplib.Time2Internaldate(time.time()), 
                       msg.as_bytes())
            imap.logout()
            print(f"  ✓ Saved to Sent folder")
        except Exception as e:
            # If saving to Sent fails, it's not critical - email was still sent
            print(f"  ⚠ Could not save to Sent folder: {e}")
    
    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Send email via SMTP with rotating sender addresses and save to Sent folder.
        
        How it works:
        1. Authenticate with main account (contact@lesavoir.agency)
        2. Send FROM rotating address (jonas@, j.weber@, etc.)
        3. All replies go to your main inbox (catch-all)
        4. Save complete message to Sent folder for tracking
        """
        print(f"Sending email to: {to_email}")
        
        try:
            # Get rotating sender for this email (bypasses rate limits)
            from_address = self.get_rotating_sender()
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"Jonas from LeSavoir.Agency <{from_address}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Date'] = email.utils.formatdate(localtime=True)
            msg['Reply-To'] = config.CONTACT_EMAIL  # All replies go to main address
            
            # Attach body
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server and send
            # Note: We authenticate with main account but send FROM rotating address
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.set_debuglevel(0)  # Set to 1 for debugging
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            print(f"  ✓ Email sent successfully to {to_email} (from: {from_address})")
            
            # Save to Sent folder (authenticated with main account)
            self.save_to_sent_folder(msg)
            
            return True
            
        except Exception as e:
            print(f"  ✗ Failed to send email to {to_email}: {e}")
            self.log_error(f"send_email error to {to_email}: {e}")
            return False
    
    def load_sent_emails(self) -> set:
        """
        Load list of already sent email addresses
        """
        try:
            with open(config.SENT_EMAILS_FILE, 'r') as f:
                sent_data = json.load(f)
                # Handle both list and dict formats
                if isinstance(sent_data, dict):
                    return set(sent_data.get("sent_emails", []))
                elif isinstance(sent_data, list):
                    # Old format - convert
                    return set()
                return set()
        except FileNotFoundError:
            return set()
        except Exception as e:
            print(f"Error loading sent emails: {e}")
            return set()
    
    def save_sent_email(self, email: str, company_data: Dict):
        """
        Save email to sent list
        """
        try:
            # Load existing sent emails
            try:
                with open(config.SENT_EMAILS_FILE, 'r') as f:
                    sent_data = json.load(f)
            except FileNotFoundError:
                sent_data = {"sent_emails": [], "detailed_history": []}
            
            # Add email to set
            if email not in sent_data["sent_emails"]:
                sent_data["sent_emails"].append(email)
            
            # Add detailed history
            sent_data["detailed_history"].append({
                "email": email,
                "company": company_data.get("name"),
                "url": company_data.get("url"),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Save back
            with open(config.SENT_EMAILS_FILE, 'w') as f:
                json.dump(sent_data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving sent email: {e}")
            self.log_error(f"save_sent_email error: {e}")
    
    def log_error(self, error_message: str):
        """
        Log errors to file
        """
        try:
            with open(config.ERROR_LOG_FILE, 'a') as f:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {error_message}\n")
        except Exception as e:
            print(f"Failed to log error: {e}")


def main():
    """
    Main function to run the emailer standalone
    """
    import os
    
    # Create data directory if it doesn't exist
    os.makedirs(config.DATA_DIR, exist_ok=True)
    
    print("="*80)
    print("COLD EMAIL SENDER - Standalone Mode")
    print("="*80)
    
    # Check if scraped data exists
    if not os.path.exists(config.SCRAPED_COMPANIES_FILE):
        print(f"\nError: Scraped companies file not found at {config.SCRAPED_COMPANIES_FILE}")
        print("Please run the scraper first (python scraper.py)")
        return
    
    # Load scraped companies
    with open(config.SCRAPED_COMPANIES_FILE, 'r') as f:
        companies = json.load(f)
    
    print(f"\nLoaded {len(companies)} companies from scraped data")
    
    # Use defaults (automated execution)
    max_emails = config.MAX_EMAILS_PER_RUN
    delay = config.DELAY_BETWEEN_EMAILS
    
    print(f"\nConfiguration:")
    print(f"  - Max emails: {max_emails}")
    print(f"  - Delay: {delay} seconds")
    print(f"  - Rotating senders: {config.USE_ROTATING_SENDERS}")
    if config.USE_ROTATING_SENDERS:
        print(f"  - Sender prefixes: {len(config.ROTATING_SENDER_PREFIXES)} addresses")
    
    # Initialize email sender
    sender = EmailSender()
    
    # Load sent emails list
    sent_emails = sender.load_sent_emails()
    print(f"\nAlready sent to {len(sent_emails)} addresses")
    
    # Filter out law companies and already contacted
    def is_law_company(company):
        name = company.get('name', '').lower()
        content = company.get('website_content', '').lower()[:1000]
        law_keywords = ['law firm', 'attorney', 'lawyer', 'legal services', 'counsel', 'esquire']
        return any(kw in name or kw in content for kw in law_keywords)
    
    available_companies = [
        c for c in companies 
        if c.get("email") 
        and c.get("email") not in sent_emails
        and not is_law_company(c)
    ]
    
    print(f"Available companies to email: {len(available_companies)}")
    
    if not available_companies:
        print("\nNo new companies to email. All available companies have been contacted.")
        return
    
    # Auto-start sending
    print(f"\nSending up to {max_emails} emails with {delay}s delay between each...")
    print("Starting in 3 seconds...\n")
    time.sleep(3)
    
    # Send emails
    print("\n" + "="*80)
    print("STARTING EMAIL CAMPAIGN")
    print("="*80)
    
    sent_count = 0
    failed_count = 0
    sent_company_emails = []  # Track which companies to remove
    
    for i, company in enumerate(available_companies[:max_emails], 1):
        print(f"\n[{i}/{min(max_emails, len(available_companies))}] Processing: {company.get('name')}")
        
        # CRITICAL: Reload sent emails before each send to prevent duplicates
        # This prevents race conditions when parallel_runner restarts the emailer
        current_sent_emails = sender.load_sent_emails()
        if company.get("email") in current_sent_emails:
            print(f"⚠️  Already sent to {company.get('email')} - Skipping to prevent duplicate")
            continue
        
        # Generate personalized email
        email_data = sender.generate_personalized_email(company)
        
        if not email_data.get("success"):
            print(f"Skipping due to email generation error")
            failed_count += 1
            continue
        
        # Send email
        success = sender.send_email(
            company.get("email"),
            email_data.get("subject"),
            email_data.get("body")
        )
        
        if success:
            # Save to sent list
            sender.save_sent_email(company.get("email"), company)
            sent_company_emails.append(company.get("email"))
            sent_count += 1
        else:
            failed_count += 1
        
        # Wait before next email (except for last one)
        if i < min(max_emails, len(available_companies)):
            print(f"Waiting {delay} seconds before next email...")
            time.sleep(delay)
    
    # Remove sent companies from scraped list
    if sent_company_emails:
        print(f"\n🗑️  Removing {len(sent_company_emails)} sent companies from scraped list...")
        companies = [c for c in companies if c.get('email') not in sent_company_emails]
        with open(config.SCRAPED_COMPANIES_FILE, 'w') as f:
            json.dump(companies, f, indent=2)
        print(f"✓ Scraped list updated: {len(companies)} companies remaining")
    
    # Print summary
    print("\n" + "="*80)
    print("EMAIL CAMPAIGN COMPLETE")
    print("="*80)
    print(f"Emails sent successfully: {sent_count}")
    print(f"Failed: {failed_count}")
    print(f"Total processed: {sent_count + failed_count}")
    print("="*80)


if __name__ == "__main__":
    main()

