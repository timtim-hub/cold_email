"""
Configuration file for Cold Email Tool
Contains API keys and SMTP settings
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys - Load from environment variables
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SCRAPFLY_API_KEY = os.getenv("SCRAPFLY_API_KEY", "")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# SMTP Configuration - Load from environment variables
SMTP_HOST = os.getenv("SMTP_HOST", "mail.privateemail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")  # Main account for authentication
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "")

# Catch-all domain for rotating sender addresses (bypasses per-address rate limits)
CATCH_ALL_DOMAIN = "lesavoir.agency"  # All emails to *@lesavoir.agency go to your inbox
USE_ROTATING_SENDERS = True  # Enable rotating sender addresses
ROTATING_SENDER_PREFIXES = [
    "jonas",           # Real person name
    "j.weber",         # First initial + common surname
    "j.mueller",       # First initial + common surname
    "j.schmidt",       # First initial + common surname
    "jonas.m",         # First name + initial
    "jonas.k",         # First name + initial
    "jm",              # Initials only
    "jk",              # Initials only
    "consulting",      # Department (not obviously sales)
    "projects",        # Department (not obviously sales)
    "web",             # Department (technical)
    "digital",         # Department (technical)
    "hello",           # Friendly
    "team",            # Generic but not salesy
    "info"             # Standard contact
]

# Company Information
COMPANY_NAME = "LeSavoir.Agency"
COMPANY_DESCRIPTION = "a full-service AI, web development and marketing agency"
CONTACT_EMAIL = "contact@lesavoir.agency"

# Email Settings
MAX_EMAILS_PER_RUN = 50
DELAY_BETWEEN_EMAILS = 20  # seconds
EMAIL_SUBJECT_TEMPLATE = "Critical Performance Issue Detected on {company_name}'s Website"

# File Paths
DATA_DIR = "data"
SCRAPED_COMPANIES_FILE = f"{DATA_DIR}/scraped_companies.json"
SENT_EMAILS_FILE = f"{DATA_DIR}/sent_emails.json"
ERROR_LOG_FILE = f"{DATA_DIR}/error_log.txt"
SEARCH_QUERIES_FILE = "search_queries.txt"

# Scraper Settings
DEFAULT_SEARCH_QUERY = "web development companies contact"
DEFAULT_NUM_RESULTS = 100
RESULTS_PER_QUERY = 50  # Number of results to scrape per query

