"""
Multi-Account Database (No Authentication)
Simple account switching with full data isolation
"""

import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager


DATABASE_PATH = "data/accounts.db"


@contextmanager
def get_db():
    """Get database connection with context manager"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database():
    """Initialize database with multi-account schema"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Accounts table (top-level entity)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                company_name TEXT,
                contact_email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        # SMTP Settings per account
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smtp_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER UNIQUE NOT NULL,
                smtp_host TEXT NOT NULL,
                smtp_port INTEGER NOT NULL,
                smtp_username TEXT NOT NULL,
                smtp_password TEXT NOT NULL,
                from_email TEXT NOT NULL,
                use_rotating_senders BOOLEAN DEFAULT 1,
                rotating_senders TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )
        """)
        
        # API Keys per account
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER UNIQUE NOT NULL,
                openai_key TEXT,
                scrapfly_key TEXT,
                serper_key TEXT,
                rapidapi_key TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )
        """)
        
        # Email Prompts per account
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                variant_name TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                include_pricing BOOLEAN DEFAULT 0,
                price_amount INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )
        """)
        
        # Search Queries per account
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )
        """)
        
        # Scraped Companies per account
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scraped_companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                company_name TEXT,
                website TEXT,
                email TEXT NOT NULL,
                speed_score REAL,
                content_preview TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_sent BOOLEAN DEFAULT 0,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )
        """)
        
        # Sent Emails per account
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                company_id INTEGER,
                email TEXT NOT NULL,
                subject TEXT,
                body TEXT,
                variant TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
                FOREIGN KEY (company_id) REFERENCES scraped_companies(id)
            )
        """)
        
        # Campaign Settings per account
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaign_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER UNIQUE NOT NULL,
                max_emails_per_run INTEGER DEFAULT 50,
                delay_between_emails INTEGER DEFAULT 20,
                ab_testing_enabled BOOLEAN DEFAULT 0,
                scraper_max_workers INTEGER DEFAULT 100,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )
        """)
        
        # Active account tracker (stores which account is currently selected)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                account_id INTEGER,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_account ON scraped_companies(account_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sent_emails_account ON sent_emails(account_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_queries_account ON search_queries(account_id)")


# Account Management
def create_account(name: str, company_name: str = None, contact_email: str = None) -> int:
    """Create new account"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO accounts (name, company_name, contact_email) VALUES (?, ?, ?)",
            (name, company_name, contact_email)
        )
        account_id = cursor.lastrowid
        
        # Initialize default campaign settings
        cursor.execute(
            "INSERT INTO campaign_settings (account_id) VALUES (?)",
            (account_id,)
        )
        
        # If this is the first account, set it as active (within same transaction)
        cursor.execute("SELECT COUNT(*) FROM accounts")
        if cursor.fetchone()[0] == 1:
            cursor.execute(
                "INSERT OR REPLACE INTO active_account (id, account_id) VALUES (1, ?)",
                (account_id,)
            )
        
        return account_id


def get_all_accounts() -> list:
    """Get all accounts"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM accounts WHERE is_active = 1 ORDER BY created_at DESC"
        )
        return [dict(row) for row in cursor.fetchall()]


def get_account(account_id: int) -> dict:
    """Get account by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        account = cursor.fetchone()
        return dict(account) if account else None


def update_account(account_id: int, name: str = None, company_name: str = None, contact_email: str = None):
    """Update account details"""
    with get_db() as conn:
        cursor = conn.cursor()
        updates = []
        params = []
        
        if name:
            updates.append("name = ?")
            params.append(name)
        if company_name is not None:
            updates.append("company_name = ?")
            params.append(company_name)
        if contact_email is not None:
            updates.append("contact_email = ?")
            params.append(contact_email)
        
        if updates:
            params.append(account_id)
            cursor.execute(
                f"UPDATE accounts SET {', '.join(updates)} WHERE id = ?",
                params
            )


def delete_account(account_id: int):
    """Delete account (soft delete)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET is_active = 0 WHERE id = ?", (account_id,))


def get_active_account() -> dict:
    """Get currently active account"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.* FROM accounts a
            JOIN active_account aa ON a.id = aa.account_id
            WHERE aa.id = 1
        """)
        account = cursor.fetchone()
        return dict(account) if account else None


def set_active_account(account_id: int):
    """Set active account"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO active_account (id, account_id) VALUES (1, ?)",
            (account_id,)
        )


# SMTP Settings
def save_smtp_settings(account_id: int, settings: dict):
    """Save SMTP settings for account"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO smtp_settings 
            (account_id, smtp_host, smtp_port, smtp_username, smtp_password, from_email, use_rotating_senders, rotating_senders)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            account_id,
            settings.get('smtp_host'),
            settings.get('smtp_port'),
            settings.get('smtp_username'),
            settings.get('smtp_password'),
            settings.get('from_email'),
            settings.get('use_rotating_senders', 1),
            json.dumps(settings.get('rotating_senders', []))
        ))


def get_smtp_settings(account_id: int) -> dict:
    """Get SMTP settings for account"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM smtp_settings WHERE account_id = ?", (account_id,))
        settings = cursor.fetchone()
        if settings:
            data = dict(settings)
            data['rotating_senders'] = json.loads(data['rotating_senders']) if data['rotating_senders'] else []
            return data
        return None


# API Keys
def save_api_keys(account_id: int, keys: dict):
    """Save API keys for account"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO api_keys 
            (account_id, openai_key, scrapfly_key, serper_key, rapidapi_key)
            VALUES (?, ?, ?, ?, ?)
        """, (
            account_id,
            keys.get('openai_key'),
            keys.get('scrapfly_key'),
            keys.get('serper_key'),
            keys.get('rapidapi_key')
        ))


def get_api_keys(account_id: int) -> dict:
    """Get API keys for account"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM api_keys WHERE account_id = ?", (account_id,))
        keys = cursor.fetchone()
        return dict(keys) if keys else None


# Email Prompts
def save_email_prompt(account_id: int, variant_name: str, prompt_text: str, include_pricing: bool = False, price_amount: int = None):
    """Save or update email prompt"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO email_prompts 
            (account_id, variant_name, prompt_text, include_pricing, price_amount)
            VALUES (?, ?, ?, ?, ?)
        """, (account_id, variant_name, prompt_text, include_pricing, price_amount))


def get_email_prompts(account_id: int) -> list:
    """Get all email prompts for account"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM email_prompts WHERE account_id = ? AND is_active = 1 ORDER BY created_at DESC",
            (account_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


# Campaign Settings
def get_campaign_settings(account_id: int) -> dict:
    """Get campaign settings for account"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM campaign_settings WHERE account_id = ?", (account_id,))
        settings = cursor.fetchone()
        return dict(settings) if settings else None


def update_campaign_settings(account_id: int, settings: dict):
    """Update campaign settings"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE campaign_settings 
            SET max_emails_per_run = ?, delay_between_emails = ?, 
                ab_testing_enabled = ?, scraper_max_workers = ?
            WHERE account_id = ?
        """, (
            settings.get('max_emails_per_run', 50),
            settings.get('delay_between_emails', 20),
            settings.get('ab_testing_enabled', 0),
            settings.get('scraper_max_workers', 100),
            account_id
        ))


if __name__ == "__main__":
    # Initialize database
    import os
    os.makedirs("data", exist_ok=True)
    init_database()
    print("✅ Database initialized successfully!")
