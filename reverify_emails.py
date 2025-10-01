#!/usr/bin/env python3
"""
Re-verify all emails in database with STRICT SMTP checks
Remove companies with unverifiable emails
"""
import json
import dns.resolver
import smtplib
from concurrent.futures import ThreadPoolExecutor, as_completed

def verify_email_strict(email):
    """Strict email verification - only accept 250/251 SMTP codes"""
    if not email or '@' not in email:
        return False
    
    try:
        domain = email.split('@')[1].lower()
        
        # Check MX records
        try:
            mx_records = dns.resolver.resolve(domain, 'MX', lifetime=3)
            if not mx_records:
                return False
            mx_host = str(mx_records[0].exchange).rstrip('.')
        except:
            return False
        
        # SMTP verification
        try:
            server = smtplib.SMTP(timeout=5)
            server.set_debuglevel(0)
            server.connect(mx_host, 25)
            server.helo('mail.lesavoir.agency')
            server.mail('verify@lesavoir.agency')
            code, message = server.rcpt(email)
            server.quit()
            
            # ONLY 250 or 251 = valid
            return code in [250, 251]
        except:
            return False
    except:
        return False

def main():
    print("="*80)
    print("RE-VERIFYING ALL EMAILS WITH STRICT SMTP CHECKS")
    print("="*80)
    
    # Load companies
    with open('data/scraped_companies.json', 'r') as f:
        companies = json.load(f)
    
    print(f"\n📊 Found {len(companies)} companies")
    print(f"🔍 Verifying emails with strict SMTP checks...")
    print(f"   (This may take a few minutes)\n")
    
    # Verify in parallel (20 workers)
    valid_companies = []
    invalid_count = 0
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_company = {
            executor.submit(verify_email_strict, c.get('email')): c 
            for c in companies if c.get('email')
        }
        
        for i, future in enumerate(as_completed(future_to_company), 1):
            company = future_to_company[future]
            email = company.get('email')
            
            try:
                is_valid = future.result(timeout=10)
                
                if is_valid:
                    valid_companies.append(company)
                    print(f"[{i}/{len(companies)}] ✓ {email[:40]}")
                else:
                    invalid_count += 1
                    print(f"[{i}/{len(companies)}] ✗ {email[:40]} - INVALID")
            except Exception as e:
                invalid_count += 1
                print(f"[{i}/{len(companies)}] ✗ {email[:40]} - ERROR")
    
    # Save cleaned data
    with open('data/scraped_companies.json', 'w') as f:
        json.dump(valid_companies, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"✅ VERIFICATION COMPLETE")
    print(f"{'='*80}")
    print(f"   Valid companies: {len(valid_companies)}")
    print(f"   Removed invalid: {invalid_count}")
    print(f"   Success rate: {len(valid_companies)/len(companies)*100:.1f}%")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()

