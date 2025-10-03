"""
Migration script to convert single-account to multi-account system
"""

import json
import os
from database import (
    init_database, create_account, set_active_account,
    save_smtp_settings, save_api_keys
)
import config


def migrate_existing_data():
    """Migrate existing JSON data to new multi-account database"""
    print("🚀 Starting migration to multi-account system...")
    print()
    
    # Initialize database
    print("📊 Initializing database...")
    os.makedirs("data", exist_ok=True)
    init_database()
    print("✅ Database initialized")
    print()
    
    # Create first account from existing config
    print("🏢 Creating account from existing configuration...")
    account_name = config.COMPANY_NAME or "Default Account"
    
    account_id = create_account(
        name=account_name,
        company_name=config.COMPANY_NAME,
        contact_email=config.CONTACT_EMAIL
    )
    print(f"✅ Account created: {account_name} (ID: {account_id})")
    set_active_account(account_id)
    print()
    
    # Migrate SMTP settings
    print("📧 Migrating SMTP settings...")
    # Build rotating sender list from prefixes
    rotating_senders = []
    if hasattr(config, 'ROTATING_SENDER_PREFIXES') and config.ROTATING_SENDER_PREFIXES:
        domain = config.FROM_EMAIL.split('@')[1]
        rotating_senders = [f"{prefix}@{domain}" for prefix in config.ROTATING_SENDER_PREFIXES]
    
    smtp_settings = {
        'smtp_host': config.SMTP_HOST,
        'smtp_port': config.SMTP_PORT,
        'smtp_username': config.SMTP_USERNAME,
        'smtp_password': config.SMTP_PASSWORD,
        'from_email': config.FROM_EMAIL,
        'use_rotating_senders': config.USE_ROTATING_SENDERS,
        'rotating_senders': rotating_senders
    }
    save_smtp_settings(account_id, smtp_settings)
    print("✅ SMTP settings migrated")
    print()
    
    # Migrate API keys
    print("🔑 Migrating API keys...")
    api_keys = {
        'openai_key': config.OPENAI_API_KEY,
        'scrapfly_key': config.SCRAPFLY_API_KEY,
        'serper_key': config.SERPER_API_KEY,
        'rapidapi_key': config.RAPIDAPI_KEY
    }
    save_api_keys(account_id, api_keys)
    print("✅ API keys migrated")
    print()
    
    # Migrate search queries
    print("🔍 Migrating search queries...")
    if os.path.exists(config.SEARCH_QUERIES_FILE):
        from database import get_db
        with open(config.SEARCH_QUERIES_FILE, 'r') as f:
            queries = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        with get_db() as conn:
            cursor = conn.cursor()
            for query in queries:
                cursor.execute(
                    "INSERT INTO search_queries (account_id, query) VALUES (?, ?)",
                    (account_id, query)
                )
        print(f"✅ Migrated {len(queries)} search queries")
    else:
        print("⚠️  No search queries file found")
    print()
    
    # Migrate scraped companies
    print("🏢 Migrating scraped companies...")
    if os.path.exists(config.SCRAPED_COMPANIES_FILE):
        try:
            with open(config.SCRAPED_COMPANIES_FILE, 'r') as f:
                companies = json.load(f)
            
            from database import get_db
            with get_db() as conn:
                cursor = conn.cursor()
                count = 0
                for company in companies:
                    try:
                        cursor.execute("""
                            INSERT INTO scraped_companies 
                            (account_id, company_name, website, email, speed_score, content_preview)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            account_id,
                            company.get('company_name'),
                            company.get('website'),
                            company.get('email'),
                            company.get('speed_score'),
                            (company.get('content', '') or '')[:500]  # Preview only
                        ))
                        count += 1
                    except Exception as e:
                        pass  # Skip duplicates/errors
            
            print(f"✅ Migrated {count} companies")
        except Exception as e:
            print(f"⚠️  Error migrating companies: {e}")
    else:
        print("⚠️  No scraped companies file found")
    print()
    
    # Migrate sent emails
    print("📨 Migrating sent emails history...")
    if os.path.exists(config.SENT_EMAILS_FILE):
        try:
            with open(config.SENT_EMAILS_FILE, 'r') as f:
                sent_data = json.load(f)
            
            from database import get_db
            with get_db() as conn:
                cursor = conn.cursor()
                count = 0
                for email_entry in sent_data.get('sent_emails', []):
                    try:
                        email_addr = email_entry if isinstance(email_entry, str) else email_entry.get('email')
                        cursor.execute("""
                            INSERT INTO sent_emails 
                            (account_id, email)
                            VALUES (?, ?)
                        """, (account_id, email_addr))
                        count += 1
                    except:
                        pass  # Skip duplicates
            
            print(f"✅ Migrated {count} sent emails")
        except Exception as e:
            print(f"⚠️  Error migrating sent emails: {e}")
    else:
        print("⚠️  No sent emails file found")
    print()
    
    # Create default email prompts
    print("✉️  Creating default email prompts...")
    from database import save_email_prompt
    
    # Default prompt text (you'll customize this in the UI)
    default_prompt = """You are Jonas from {company_name}. Write a SHORT, punchy cold email (120-180 words MAX) about website performance issues."""
    
    save_email_prompt(
        account_id,
        'Variant A - No Pricing',
        default_prompt,
        include_pricing=False
    )
    
    save_email_prompt(
        account_id,
        'Variant B - With Pricing',
        default_prompt + "\nMention our $299 service.",
        include_pricing=True,
        price_amount=299
    )
    
    print("✅ Default email prompts created")
    print()
    
    # Summary
    print("=" * 60)
    print("✅ MIGRATION COMPLETE!")
    print("=" * 60)
    print()
    print(f"🏢 Account: {account_name} (ID: {account_id})")
    print()
    print("🌐 Next steps:")
    print("1. Restart the server")
    print("2. Visit http://localhost:5000")
    print("3. You'll see the new account switcher in the top-right")
    print("4. Click 'Settings' to configure email prompts and other settings")
    print("5. Click '+ New Account' to add more accounts")
    print()


if __name__ == "__main__":
    migrate_existing_data()

