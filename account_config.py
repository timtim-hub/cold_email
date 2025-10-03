"""
Account Configuration Loader
Loads settings from database for the active account to use in scraper/emailer
"""

import database


class AccountConfig:
    """Dynamic configuration loaded from database for active account"""
    
    def __init__(self):
        self.account_id = None
        self.account_name = None
        self.company_name = None
        self.contact_email = None
        
        # SMTP settings
        self.SMTP_HOST = None
        self.SMTP_PORT = None
        self.SMTP_USERNAME = None
        self.SMTP_PASSWORD = None
        self.FROM_EMAIL = None
        self.USE_ROTATING_SENDERS = False
        self.ROTATING_SENDER_PREFIXES = []
        
        # API Keys
        self.OPENAI_API_KEY = None
        self.SCRAPFLY_API_KEY = None
        self.SERPER_API_KEY = None
        self.RAPIDAPI_KEY = None
        
        # Campaign settings
        self.MAX_EMAILS_PER_RUN = 50
        self.DELAY_BETWEEN_EMAILS = 20
        self.AB_TESTING_ENABLED = False
        self.SCRAPER_MAX_WORKERS = 100
        
        # Load from database
        self.load()
    
    def load(self):
        """Load configuration from database for active account"""
        try:
            # Get active account
            active_account = database.get_active_account()
            if not active_account:
                print("⚠️  No active account found. Using default config.")
                self._load_defaults()
                return
            
            self.account_id = active_account['id']
            self.account_name = active_account['name']
            self.company_name = active_account['company_name']
            self.contact_email = active_account['contact_email']
            
            # Load SMTP settings
            smtp = database.get_smtp_settings(self.account_id)
            if smtp:
                self.SMTP_HOST = smtp['smtp_host']
                self.SMTP_PORT = smtp['smtp_port']
                self.SMTP_USERNAME = smtp['smtp_username']
                self.SMTP_PASSWORD = smtp['smtp_password']
                self.FROM_EMAIL = smtp['from_email']
                self.USE_ROTATING_SENDERS = bool(smtp['use_rotating_senders'])
                
                # Build rotating sender list
                if self.USE_ROTATING_SENDERS and smtp.get('rotating_senders'):
                    # rotating_senders is a list of full email addresses
                    self.ROTATING_SENDER_PREFIXES = [
                        email.split('@')[0] for email in smtp['rotating_senders']
                    ]
            
            # Load API keys
            api_keys = database.get_api_keys(self.account_id)
            if api_keys:
                self.OPENAI_API_KEY = api_keys['openai_key']
                self.SCRAPFLY_API_KEY = api_keys['scrapfly_key']
                self.SERPER_API_KEY = api_keys['serper_key']
                self.RAPIDAPI_KEY = api_keys['rapidapi_key']
            
            # Load campaign settings
            campaign = database.get_campaign_settings(self.account_id)
            if campaign:
                self.MAX_EMAILS_PER_RUN = campaign['max_emails_per_run']
                self.DELAY_BETWEEN_EMAILS = campaign['delay_between_emails']
                self.AB_TESTING_ENABLED = bool(campaign['ab_testing_enabled'])
                self.SCRAPER_MAX_WORKERS = campaign['scraper_max_workers']
            
            print(f"✅ Loaded configuration for account: {self.account_name}")
            
        except Exception as e:
            print(f"❌ Error loading account config: {e}")
            self._load_defaults()
    
    def _load_defaults(self):
        """Load default configuration from config.py as fallback"""
        try:
            import config
            self.SMTP_HOST = config.SMTP_HOST
            self.SMTP_PORT = config.SMTP_PORT
            self.SMTP_USERNAME = config.SMTP_USERNAME
            self.SMTP_PASSWORD = config.SMTP_PASSWORD
            self.FROM_EMAIL = config.FROM_EMAIL
            self.USE_ROTATING_SENDERS = config.USE_ROTATING_SENDERS
            self.ROTATING_SENDER_PREFIXES = config.ROTATING_SENDER_PREFIXES
            
            self.OPENAI_API_KEY = config.OPENAI_API_KEY
            self.SCRAPFLY_API_KEY = config.SCRAPFLY_API_KEY
            self.SERPER_API_KEY = config.SERPER_API_KEY
            self.RAPIDAPI_KEY = config.RAPIDAPI_KEY
            
            self.company_name = config.COMPANY_NAME
            self.contact_email = config.CONTACT_EMAIL
            
            print("⚠️  Using default config.py settings")
        except Exception as e:
            print(f"❌ Error loading default config: {e}")
    
    def get_search_queries(self):
        """Get search queries for active account from database"""
        try:
            with database.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT query FROM search_queries 
                    WHERE account_id = ? AND is_used = 0
                    ORDER BY created_at
                """, (self.account_id,))
                
                queries = [row[0] for row in cursor.fetchall()]
                return queries if queries else []
        except Exception as e:
            print(f"Error loading queries: {e}")
            return []
    
    def mark_query_as_used(self, query):
        """Mark a query as used in the database"""
        try:
            with database.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE search_queries 
                    SET is_used = 1, used_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND query = ?
                """, (self.account_id, query))
        except Exception as e:
            print(f"Error marking query as used: {e}")
    
    def get_email_prompts(self):
        """Get active email prompts for this account"""
        try:
            return database.get_email_prompts(self.account_id)
        except Exception as e:
            print(f"Error loading email prompts: {e}")
            return []
    
    def save_scraped_company(self, company_data):
        """Save scraped company to database"""
        try:
            with database.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scraped_companies 
                    (account_id, company_name, website, email, speed_score, content_preview)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self.account_id,
                    company_data.get('company_name'),
                    company_data.get('website'),
                    company_data.get('email'),
                    company_data.get('speed_score'),
                    (company_data.get('content', '') or '')[:500]
                ))
                return cursor.lastrowid
        except Exception as e:
            print(f"Error saving company: {e}")
            return None
    
    def get_unsent_companies(self, limit=None):
        """Get companies that haven't been emailed yet"""
        try:
            with database.get_db() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT id, company_name, website, email, speed_score, content_preview
                    FROM scraped_companies 
                    WHERE account_id = ? AND is_sent = 0
                    ORDER BY scraped_at DESC
                """
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query, (self.account_id,))
                
                companies = []
                for row in cursor.fetchall():
                    companies.append({
                        'id': row[0],
                        'company_name': row[1],
                        'website': row[2],
                        'email': row[3],
                        'speed_score': row[4],
                        'content': row[5]
                    })
                return companies
        except Exception as e:
            print(f"Error getting unsent companies: {e}")
            return []
    
    def mark_company_as_sent(self, company_id):
        """Mark a company as having been sent an email"""
        try:
            with database.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE scraped_companies 
                    SET is_sent = 1
                    WHERE id = ?
                """, (company_id,))
        except Exception as e:
            print(f"Error marking company as sent: {e}")
    
    def save_sent_email(self, email_data):
        """Save sent email to database"""
        try:
            with database.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sent_emails 
                    (account_id, company_id, email, subject, body, variant)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self.account_id,
                    email_data.get('company_id'),
                    email_data.get('email'),
                    email_data.get('subject'),
                    email_data.get('body'),
                    email_data.get('variant')
                ))
        except Exception as e:
            print(f"Error saving sent email: {e}")
    
    def is_email_already_sent(self, email):
        """Check if email was already sent to this address"""
        try:
            with database.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM sent_emails 
                    WHERE account_id = ? AND email = ?
                """, (self.account_id, email))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            print(f"Error checking if email sent: {e}")
            return False


# Singleton instance
_account_config = None

def get_account_config():
    """Get or create account config instance"""
    global _account_config
    if _account_config is None:
        _account_config = AccountConfig()
    return _account_config


def reload_account_config():
    """Force reload of account config from database"""
    global _account_config
    _account_config = AccountConfig()
    return _account_config


if __name__ == "__main__":
    # Test loading
    config = get_account_config()
    print(f"Account: {config.account_name}")
    print(f"Company: {config.company_name}")
    print(f"FROM_EMAIL: {config.FROM_EMAIL}")
    print(f"Has OpenAI Key: {bool(config.OPENAI_API_KEY)}")
    print(f"Has Scrapfly Key: {bool(config.SCRAPFLY_API_KEY)}")

