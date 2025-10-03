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
from account_config import get_account_config


class EmailSender:
    def __init__(self):
        self.account_config = get_account_config()
        self.smtp_host = self.account_config.SMTP_HOST
        self.smtp_port = self.account_config.SMTP_PORT
        self.smtp_username = self.account_config.SMTP_USERNAME
        self.smtp_password = self.account_config.SMTP_PASSWORD
        self.from_email = self.account_config.FROM_EMAIL
        self.openai_client = OpenAI(api_key=self.account_config.OPENAI_API_KEY)
        self.current_sender_index = 0  # For rotating sender addresses
        
    def get_rotating_sender(self) -> str:
        """
        Get next rotating sender address from catch-all domain.
        This bypasses per-address rate limits while all emails go to your inbox.
        """
        if self.account_config.USE_ROTATING_SENDERS and self.account_config.ROTATING_SENDER_PREFIXES:
            prefix = self.account_config.ROTATING_SENDER_PREFIXES[
                self.current_sender_index % len(self.account_config.ROTATING_SENDER_PREFIXES)
            ]
            self.current_sender_index += 1
            domain = self.from_email.split('@')[1]
            return f"{prefix}@{domain}"
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
    
    def get_email_prompt_variant_a(self, company_name, website_url, load_time, page_size, grade, website_content):
        """Variant A: No pricing mentioned (control group)"""
        return f"""You are Jonas from {self.account_config.company_name} - a premium agency specializing in website optimization for local businesses.

MISSION: Write a highly personalized, conversion-focused cold email that gets replies.

===== EMAIL STRUCTURE (120-180 words) =====

GREETING (Warm & Professional):
Hi {company_name} Team,

OPENING (Pattern Interrupt - NOT the usual "I ran a test"):
- Start with a compliment about their business (based on website content)
- Then transition: "That's why I was surprised to see..."
- Example: "Your deck portfolio is impressive—that Tetherow project is stunning. That's why I was surprised when..."

BODY (Problem + Urgency + Curiosity):
1. REVEAL: Mention the performance issue (load time: {load_time}, grade: {grade})
2. IMPACT: Quantify the loss - "Every extra second costs you X% of visitors" or "Your competitors load in 2.1s"
3. EMPATHY: "I know you're busy running the business..." (show understanding)
4. AUTHORITY: "We've helped 100+ local businesses fix this..." (brief social proof)
5. NO TIPS: Do NOT tell them HOW to fix it - that's what we do
6. URGENCY: "This is costing you leads right now"

CLOSING (Soft CTA + Value):
- Not pushy: "Worth a quick chat?"
- Offer value: "I can send you a detailed performance report"
- Easy action: "Just reply with 'interested' or email {config.CONTACT_EMAIL}"

SIGNATURE (Professional + Approachable):
Jonas
{self.account_config.company_name}
{self.account_config.contact_email}

===== CRITICAL RULES =====
✓ GREETING MUST BE: "Hi {company_name} Team," (CAPITAL T in "Team" - this is mandatory)
✓ NEVER write "Hi {company_name} team," with lowercase t - that's grammatically incorrect
✓ Use their actual company name: {company_name}
✓ Reference specific details from their website content
✓ Sound like a helpful consultant, NOT a salesperson
✓ Create curiosity (don't give away solutions)
✓ Be conversational but professional
✓ NO placeholders like [Your Name] or [Company]
✓ Keep it tight: 120-180 words MAX

===== COMPANY INTEL =====
Company: {company_name}
Website: {website_url}
Performance Data:
- Load Time: {load_time}
- Page Size: {page_size}  
- Grade: {grade}

Website Content (use to personalize):
{website_content}

===== TONE =====
Confident but humble. Helpful, not pushy. Like you're doing them a favor by reaching out. Use industry stats if relevant (e.g., "Sites loading under 3s convert 2x better").

Write ONLY the email body. Make it feel like you spent 10 minutes researching them (because you did via their website content)."""

    def get_email_prompt_variant_b(self, company_name, website_url, load_time, page_size, grade, website_content):
        """Variant B: Includes pricing ($299) - tests if transparency increases conversion"""
        return f"""You are Jonas from {self.account_config.company_name} - a premium agency specializing in website optimization for local businesses.

MISSION: Write a highly personalized, conversion-focused cold email that gets replies.

===== EMAIL STRUCTURE (120-180 words) =====

GREETING (Warm & Professional):
Hi {company_name} Team,

OPENING (Pattern Interrupt - NOT the usual "I ran a test"):
- Start with a compliment about their business (based on website content)
- Then transition: "That's why I was surprised to see..."
- Example: "Your deck portfolio is impressive—that Tetherow project is stunning. That's why I was surprised when..."

BODY (Problem + Urgency + Curiosity):
1. REVEAL: Mention the performance issue (load time: {load_time}, grade: {grade})
2. IMPACT: Quantify the loss - "Every extra second costs you X% of visitors" or "Your competitors load in 2.1s"
3. EMPATHY: "I know you're busy running the business..." (show understanding)
4. AUTHORITY: "We've helped 100+ local businesses fix this..." (brief social proof)
5. NO TIPS: Do NOT tell them HOW to fix it - that's what we do
6. URGENCY: "This is costing you leads right now"
7. PRICING: Naturally mention "We can fix this for ${config.SERVICE_PRICE}" - be transparent about pricing

CLOSING (Soft CTA + Value with Price):
- Not pushy: "Worth a quick chat?"
- Offer value: "I can send you a detailed performance report"
- Price anchor: "The fix is ${config.SERVICE_PRICE} - typically pays for itself in a week"
- Easy action: "Just reply with 'interested' or email {config.CONTACT_EMAIL}"

SIGNATURE (Professional + Approachable):
Jonas
{self.account_config.company_name}
{self.account_config.contact_email}

===== CRITICAL RULES =====
✓ GREETING MUST BE: "Hi {company_name} Team," (CAPITAL T in "Team" - this is mandatory)
✓ NEVER write "Hi {company_name} team," with lowercase t - that's grammatically incorrect
✓ Use their actual company name: {company_name}
✓ Reference specific details from their website content
✓ Sound like a helpful consultant, NOT a salesperson
✓ Create curiosity (don't give away solutions)
✓ Be conversational but professional
✓ NO placeholders like [Your Name] or [Company]
✓ MUST mention the price ${config.SERVICE_PRICE} naturally in the email
✓ Keep it tight: 120-180 words MAX

===== COMPANY INTEL =====
Company: {company_name}
Website: {website_url}
Performance Data:
- Load Time: {load_time}
- Page Size: {page_size}  
- Grade: {grade}

Website Content (use to personalize):
{website_content}

===== TONE =====
Confident but humble. Helpful, not pushy. Transparent about pricing. Like you're doing them a favor by reaching out. Use industry stats if relevant (e.g., "Sites loading under 3s convert 2x better").

Write ONLY the email body. Make it feel like you spent 10 minutes researching them (because you did via their website content)."""

    def generate_personalized_email(self, company_data: Dict) -> Dict:
        """
        Generate a hyper-personalized email using OpenAI API
        Supports A/B testing with pricing variant
        """
        import random
        
        raw_company_name = company_data.get("name", "there")
        company_name = self.clean_company_name(raw_company_name)
        website_url = company_data.get("url", "")
        website_content = company_data.get("website_content", "")[:2000]  # Limit for token efficiency
        speed_test = company_data.get("speed_test", {})
        
        # Extract speed test metrics
        load_time = speed_test.get("load_time", "N/A")
        page_size = speed_test.get("page_size", "N/A")
        grade = speed_test.get("grade", "N/A")
        
        # A/B Testing: Select variant
        if config.AB_TESTING_ENABLED:
            variant = random.choice(['A', 'B'])
        else:
            variant = 'A'  # Default to variant A when A/B testing is off
        
        # Get appropriate prompt based on variant
        if variant == 'B':
            prompt = self.get_email_prompt_variant_b(company_name, website_url, load_time, page_size, grade, website_content)
        else:
            prompt = self.get_email_prompt_variant_a(company_name, website_url, load_time, page_size, grade, website_content)
        
        print(f"Using variant {variant} {'(with $' + str(config.SERVICE_PRICE) + ' pricing)' if variant == 'B' else '(no pricing)'}")
        
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
                "success": True,
                "variant": variant  # Track which variant was used for A/B testing
            }
            
        except Exception as e:
            print(f"Error generating email for {company_name}: {e}")
            self.log_error(f"generate_personalized_email error for {company_name}: {e}")
            return {
                "subject": "",
                "body": "",
                "success": False,
                "error": str(e),
                "variant": variant
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
    
    def save_sent_email(self, email: str, company_data: Dict, variant: str = 'A'):
        """
        Save email to sent list with A/B testing variant tracking
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
            
            # Add detailed history with A/B variant
            sent_data["detailed_history"].append({
                "email": email,
                "company": company_data.get("name"),
                "url": company_data.get("url"),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "variant": variant  # Track which email variant was sent
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
    Main function to run the emailer standalone - Multi-Account Mode
    """
    import os
    import fcntl
    
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # LOCK FILE: Prevent multiple emailer instances from running simultaneously
    lock_file_path = os.path.join("data", 'emailer.lock')
    lock_file = open(lock_file_path, 'w')
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("✓ Acquired emailer lock - no other instances running")
    except IOError:
        print("⚠️  Another emailer instance is already running. Exiting to prevent duplicate emails.")
        return
    
    print("="*80)
    print("COLD EMAIL SENDER - Multi-Account Mode")
    print("="*80)
    
    # Initialize email sender (loads account config)
    sender = EmailSender()
    account_config = sender.account_config
    
    if not account_config.account_id:
        print("❌ No active account found. Please create an account in the dashboard first.")
        return
    
    print(f"✓ Active Account: {account_config.account_name}")
    print(f"  Company: {account_config.company_name}")
    print()
    
    # Get unsent companies from database
    companies = account_config.get_unsent_companies()
    
    print(f"\nLoaded {len(companies)} unsent companies from database")
    
    # Use account-specific settings
    max_emails = account_config.MAX_EMAILS_PER_RUN
    delay = account_config.DELAY_BETWEEN_EMAILS
    
    print(f"\nConfiguration:")
    print(f"  - Max emails: {max_emails}")
    print(f"  - Delay: {delay} seconds")
    print(f"  - Rotating senders: {account_config.USE_ROTATING_SENDERS}")
    if account_config.USE_ROTATING_SENDERS and account_config.ROTATING_SENDER_PREFIXES:
        print(f"  - Sender prefixes: {len(account_config.ROTATING_SENDER_PREFIXES)} addresses")
    
    # Filter out already sent emails
    available_companies = [
        c for c in companies 
        if c.get("email") and not account_config.is_email_already_sent(c.get("email"))
    ]
    
    print(f"Available companies to email: {len(available_companies)}")
    
    if not available_companies:
        print("\nNo new companies to email. All available companies have been contacted.")
        return
    
    # Check minimum threshold
    if len(available_companies) < 20:
        print(f"\n⚠️  Only {len(available_companies)} companies available.")
        print("   Waiting for scraper to find more leads (minimum 20 recommended).")
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
    
    for i, company in enumerate(available_companies[:max_emails], 1):
        company_name = company.get('company_name', 'Unknown')
        print(f"\n[{i}/{min(max_emails, len(available_companies))}] Processing: {company_name}")
        
        # Check again if already sent (race condition protection)
        if account_config.is_email_already_sent(company.get("email")):
            print(f"⚠️  Already sent to {company.get('email')} - Skipping to prevent duplicate")
            continue
        
        # Generate personalized email
        # Convert database format to expected format
        company_for_email = {
            'name': company_name,
            'website': company.get('website'),
            'email': company.get('email'),
            'speed_score': company.get('speed_score'),
            'website_content': company.get('content', '')
        }
        
        email_data = sender.generate_personalized_email(company_for_email)
        
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
            # Save to database
            account_config.save_sent_email({
                'company_id': company.get('id'),
                'email': company.get('email'),
                'subject': email_data.get('subject'),
                'body': email_data.get('body'),
                'variant': email_data.get('variant', 'A')
            })
            
            # Mark company as sent
            account_config.mark_company_as_sent(company.get('id'))
            
            sent_count += 1
        else:
            failed_count += 1
        
        # Wait before next email (except for last one)
        if i < min(max_emails, len(available_companies)):
            print(f"Waiting {delay} seconds before next email...")
            time.sleep(delay)
    
    # Print summary
    print("\n" + "="*80)
    print("EMAIL CAMPAIGN COMPLETE")
    print("="*80)
    print(f"Emails sent successfully: {sent_count}")
    print(f"Failed: {failed_count}")
    print(f"Total processed: {sent_count + failed_count}")
    print("="*80)
    
    # Release lock
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
        os.remove(lock_file_path)
        print("✓ Released emailer lock")
    except:
        pass


if __name__ == "__main__":
    main()

