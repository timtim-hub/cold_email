"""
Main orchestration script for Cold Email Tool
Combines scraper and emailer functionalities
"""

import os
import json
import time
from scraper import CompanyScraper
from emailer import EmailSender
import config


def ensure_data_directory():
    """Create data directory if it doesn't exist"""
    os.makedirs(config.DATA_DIR, exist_ok=True)


def print_header(text):
    """Print formatted header"""
    print("\n" + "="*80)
    print(text.center(80))
    print("="*80 + "\n")


def run_scraper_mode():
    """Run the scraper to collect company data"""
    print_header("SCRAPER MODE")
    
    # Get user input
    query = input(f"Enter search query (default: '{config.DEFAULT_SEARCH_QUERY}'): ").strip()
    if not query:
        query = config.DEFAULT_SEARCH_QUERY
    
    num_results = input(f"Number of results to scrape (default: {config.DEFAULT_NUM_RESULTS}): ").strip()
    try:
        num_results = int(num_results) if num_results else config.DEFAULT_NUM_RESULTS
    except ValueError:
        num_results = config.DEFAULT_NUM_RESULTS
    
    print(f"\nStarting scraper with:")
    print(f"  - Query: {query}")
    print(f"  - Target results: {num_results}")
    
    # Initialize scraper
    scraper = CompanyScraper()
    
    # Search for companies
    print("\n" + "-"*80)
    companies = scraper.search_companies(query, num_results)
    
    if not companies:
        print("\nNo companies found. Exiting.")
        return
    
    print(f"\nFound {len(companies)} companies. Starting detailed scraping...")
    print("-"*80)
    
    # Scrape full data for each company
    scraped_data = []
    for i, company in enumerate(companies, 1):
        print(f"\n[{i}/{len(companies)}] Processing company...")
        company_data = scraper.scrape_full_company_data(company)
        scraped_data.append(company_data)
        
        # Save progress periodically
        if i % 10 == 0:
            with open(config.SCRAPED_COMPANIES_FILE, 'w') as f:
                json.dump(scraped_data, f, indent=2)
            print(f"\n✓ Progress saved: {i}/{len(companies)} companies")
    
    # Save final results
    with open(config.SCRAPED_COMPANIES_FILE, 'w') as f:
        json.dump(scraped_data, f, indent=2)
    
    # Print summary
    print_header("SCRAPING COMPLETE")
    print(f"Total companies processed: {len(scraped_data)}")
    print(f"Successfully scraped: {sum(1 for c in scraped_data if c.get('scraped_successfully'))}")
    print(f"Companies with emails: {sum(1 for c in scraped_data if c.get('email'))}")
    print(f"\nData saved to: {config.SCRAPED_COMPANIES_FILE}")


def run_emailer_mode():
    """Run the email sender to contact companies"""
    print_header("EMAIL SENDER MODE")
    
    # Check if scraped data exists
    if not os.path.exists(config.SCRAPED_COMPANIES_FILE):
        print(f"Error: Scraped companies file not found at {config.SCRAPED_COMPANIES_FILE}")
        print("Please run the scraper first (choose option 1 or 3)")
        return
    
    # Load scraped companies
    with open(config.SCRAPED_COMPANIES_FILE, 'r') as f:
        companies = json.load(f)
    
    print(f"Loaded {len(companies)} companies from scraped data")
    
    # Get user input
    max_emails = input(f"\nHow many emails to send? (default: {config.MAX_EMAILS_PER_RUN}): ").strip()
    try:
        max_emails = int(max_emails) if max_emails else config.MAX_EMAILS_PER_RUN
    except ValueError:
        max_emails = config.MAX_EMAILS_PER_RUN
    
    delay = input(f"Delay between emails in seconds? (default: {config.DELAY_BETWEEN_EMAILS}): ").strip()
    try:
        delay = int(delay) if delay else config.DELAY_BETWEEN_EMAILS
    except ValueError:
        delay = config.DELAY_BETWEEN_EMAILS
    
    # Initialize email sender
    sender = EmailSender()
    
    # Load sent emails list
    sent_emails = sender.load_sent_emails()
    print(f"\nAlready sent to {len(sent_emails)} addresses")
    
    # Filter companies with emails that haven't been contacted
    available_companies = [
        c for c in companies 
        if c.get("email") and c.get("email") not in sent_emails
    ]
    
    print(f"Available companies to email: {len(available_companies)}")
    
    if not available_companies:
        print("\nNo new companies to email. All available companies have been contacted.")
        return
    
    # Confirm before sending
    print(f"\nReady to send up to {max_emails} emails with {delay}s delay between each.")
    confirm = input("Continue? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Cancelled.")
        return
    
    # Send emails
    print_header("STARTING EMAIL CAMPAIGN")
    
    sent_count = 0
    failed_count = 0
    
    for i, company in enumerate(available_companies[:max_emails], 1):
        print(f"\n[{i}/{min(max_emails, len(available_companies))}] Processing: {company.get('name')}")
        print(f"Email: {company.get('email')}")
        
        # Generate personalized email
        email_data = sender.generate_personalized_email(company)
        
        if not email_data.get("success"):
            print(f"✗ Skipping due to email generation error")
            failed_count += 1
            continue
        
        print(f"Subject: {email_data.get('subject')}")
        
        # Send email
        success = sender.send_email(
            company.get("email"),
            email_data.get("subject"),
            email_data.get("body")
        )
        
        if success:
            # Save to sent list
            sender.save_sent_email(company.get("email"), company)
            sent_count += 1
        else:
            failed_count += 1
        
        # Wait before next email (except for last one)
        if i < min(max_emails, len(available_companies)):
            print(f"⏱  Waiting {delay} seconds before next email...")
            time.sleep(delay)
    
    # Print summary
    print_header("EMAIL CAMPAIGN COMPLETE")
    print(f"✓ Emails sent successfully: {sent_count}")
    print(f"✗ Failed: {failed_count}")
    print(f"Total processed: {sent_count + failed_count}")


def run_full_workflow():
    """Run both scraper and emailer in sequence"""
    print_header("FULL WORKFLOW MODE")
    print("This will run the scraper first, then the email sender.")
    
    confirm = input("\nContinue? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Cancelled.")
        return
    
    # Run scraper
    run_scraper_mode()
    
    # Small pause
    print("\n\nWaiting 5 seconds before starting email campaign...")
    time.sleep(5)
    
    # Run emailer
    run_emailer_mode()


def show_stats():
    """Show statistics about scraped and sent data"""
    print_header("STATISTICS")
    
    # Scraped data stats
    if os.path.exists(config.SCRAPED_COMPANIES_FILE):
        with open(config.SCRAPED_COMPANIES_FILE, 'r') as f:
            companies = json.load(f)
        
        print("SCRAPED DATA:")
        print(f"  Total companies: {len(companies)}")
        print(f"  With emails: {sum(1 for c in companies if c.get('email'))}")
        print(f"  Successfully scraped: {sum(1 for c in companies if c.get('scraped_successfully'))}")
    else:
        print("SCRAPED DATA: No data found")
    
    print()
    
    # Sent emails stats
    if os.path.exists(config.SENT_EMAILS_FILE):
        with open(config.SENT_EMAILS_FILE, 'r') as f:
            sent_data = json.load(f)
        
        print("SENT EMAILS:")
        print(f"  Total sent: {len(sent_data.get('sent_emails', []))}")
        
        if sent_data.get('detailed_history'):
            print(f"  Last sent: {sent_data['detailed_history'][-1].get('timestamp', 'N/A')}")
    else:
        print("SENT EMAILS: No data found")
    
    print()


def main():
    """Main entry point"""
    ensure_data_directory()
    
    while True:
        print_header("COLD EMAIL TOOL - LeSavoir.Agency")
        print("1. Run Scraper (collect company data)")
        print("2. Run Email Sender (send emails to scraped companies)")
        print("3. Run Full Workflow (scrape then email)")
        print("4. Show Statistics")
        print("5. Exit")
        print()
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            run_scraper_mode()
        elif choice == '2':
            run_emailer_mode()
        elif choice == '3':
            run_full_workflow()
        elif choice == '4':
            show_stats()
        elif choice == '5':
            print("\nExiting. Goodbye!")
            break
        else:
            print("\nInvalid choice. Please try again.")
        
        if choice in ['1', '2', '3', '4']:
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()

