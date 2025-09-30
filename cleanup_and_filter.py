#!/usr/bin/env python3
"""
Utility script to clean, filter, and deduplicate data
"""
import json
import os
from urllib.parse import urlparse

def normalize_url(url):
    """Normalize URL for better comparison (remove www, trailing slash, protocol)"""
    if not url:
        return ""
    
    parsed = urlparse(url.lower())
    domain = parsed.netloc or parsed.path
    domain = domain.replace('www.', '')
    domain = domain.rstrip('/')
    return domain

def is_law_company(company):
    """Check if company is law-related"""
    name = company.get('name', '').lower()
    content = company.get('website_content', '').lower()[:1000]  # First 1000 chars
    query = company.get('source_query', '').lower()
    url = company.get('url', '').lower()
    title = company.get('website_title', '').lower()
    
    # Law-related keywords
    law_keywords = [
        'law firm', 'law office', 'attorney', 'lawyer', 'legal services',
        'counsel', 'esquire', 'esq', 'barrister', 'advocate',
        'litigation', 'legal aid', 'law group', 'legal practice'
    ]
    
    # Check in multiple places
    for keyword in law_keywords:
        if (keyword in name or 
            keyword in url or 
            keyword in query or
            keyword in title or
            keyword in content):
            return True
    
    return False

def main():
    print("="*80)
    print("DATA CLEANUP & FILTER UTILITY")
    print("="*80)
    
    # Load scraped companies
    scraped_file = 'data/scraped_companies.json'
    sent_file = 'data/sent_emails.json'
    
    if not os.path.exists(scraped_file):
        print(f"\n❌ {scraped_file} not found!")
        return
    
    with open(scraped_file, 'r') as f:
        companies = json.load(f)
    
    print(f"\n📊 Initial: {len(companies)} companies")
    
    # Step 1: Remove law companies
    law_companies = [c for c in companies if is_law_company(c)]
    companies = [c for c in companies if not is_law_company(c)]
    print(f"🚫 Removed {len(law_companies)} law companies")
    print(f"   Remaining: {len(companies)} companies")
    
    # Step 2: Deduplicate by normalized URL
    seen_urls = {}
    unique_companies = []
    duplicates = 0
    
    for company in companies:
        url = company.get('url', '')
        normalized = normalize_url(url)
        
        if normalized and normalized not in seen_urls:
            seen_urls[normalized] = True
            unique_companies.append(company)
        else:
            duplicates += 1
    
    print(f"🔄 Removed {duplicates} duplicate URLs")
    print(f"   Remaining: {len(unique_companies)} companies")
    
    # Step 3: Ensure sent_emails.json has proper structure
    if os.path.exists(sent_file):
        with open(sent_file, 'r') as f:
            try:
                sent_data = json.load(f)
                if isinstance(sent_data, list):
                    # Convert old format to new
                    sent_data = {
                        "sent_emails": [],
                        "detailed_history": []
                    }
            except:
                sent_data = {
                    "sent_emails": [],
                    "detailed_history": []
                }
    else:
        sent_data = {
            "sent_emails": [],
            "detailed_history": []
        }
    
    # Step 4: Remove companies whose URLs are in sent_emails
    sent_urls = set()
    for entry in sent_data.get('detailed_history', []):
        url = entry.get('url', '')
        if url:
            sent_urls.add(normalize_url(url))
    
    for email in sent_data.get('sent_emails', []):
        # Try to find URL from detailed history
        pass
    
    companies_before = len(unique_companies)
    unique_companies = [
        c for c in unique_companies 
        if normalize_url(c.get('url', '')) not in sent_urls
    ]
    already_emailed = companies_before - len(unique_companies)
    
    if already_emailed > 0:
        print(f"📧 Removed {already_emailed} already-emailed companies")
        print(f"   Remaining: {len(unique_companies)} companies")
    
    # Save cleaned data
    with open(scraped_file, 'w') as f:
        json.dump(unique_companies, f, indent=2)
    
    with open(sent_file, 'w') as f:
        json.dump(sent_data, f, indent=2)
    
    print("\n" + "="*80)
    print("✅ CLEANUP COMPLETE")
    print("="*80)
    print(f"Final count: {len(unique_companies)} companies")
    print(f"All have emails: {sum(1 for c in unique_companies if c.get('email'))}")
    print(f"Data saved to: {scraped_file}")
    print("="*80)

if __name__ == "__main__":
    main()

