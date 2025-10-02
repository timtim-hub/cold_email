"""
Scraper module for extracting company information, website content, and speed tests
"""

import json
import re
import time
import os
import http.client
import urllib.parse
import smtplib
import socket
import dns.resolver
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from scrapfly import ScrapflyClient, ScrapeConfig
from bs4 import BeautifulSoup
import config


class CompanyScraper:
    def __init__(self):
        self.serper_api_key = config.SERPER_API_KEY
        self.scrapfly_client = ScrapflyClient(key=config.SCRAPFLY_API_KEY)
        self.rapidapi_key = config.RAPIDAPI_KEY
        
    def search_companies(self, query: str, num_results: int = 100) -> List[Dict]:
        """
        Search for companies using Serper.dev API
        """
        print(f"Searching for companies with query: '{query}'...")
        url = "https://google.serper.dev/search"
        
        headers = {
            "X-API-KEY": self.serper_api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "q": query,
            "num": num_results,
            "page": 1
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            results = response.json()
            
            companies = []
            organic_results = results.get("organic", [])
            
            print(f"Found {len(organic_results)} results from Serper.dev")
            
            for result in organic_results:
                company = {
                    "name": result.get("title", "Unknown"),
                    "url": result.get("link", ""),
                    "snippet": result.get("snippet", ""),
                    "email": None
                }
                
                # Try to extract email from snippet
                email = self.extract_email_from_text(result.get("snippet", ""))
                if email:
                    company["email"] = email
                
                if company["url"]:
                    companies.append(company)
            
            print(f"Extracted {len(companies)} companies with valid URLs")
            return companies
            
        except Exception as e:
            print(f"Error searching companies: {e}")
            self.log_error(f"search_companies error: {e}")
            return []
    
    def extract_email_from_text(self, text: str) -> Optional[str]:
        """
        Extract email address from text using regex
        """
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, text)
        # Filter out common junk emails
        if matches:
            for email in matches:
                email_lower = email.lower()
                if not any(skip in email_lower for skip in ['example.com', 'domain.com', 'email.com', 'test.com']):
                    return email
        return None
    
    def extract_emails_from_html(self, html_content: str, soup: BeautifulSoup) -> List[str]:
        """
        Extract all email addresses from HTML including mailto: links
        """
        emails = []
        
        # 1. Find mailto: links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('mailto:'):
                email = href.replace('mailto:', '').split('?')[0].strip()
                if '@' in email:
                    emails.append(email)
        
        # 2. Extract from text content
        text = soup.get_text()
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        text_emails = re.findall(email_pattern, text)
        emails.extend(text_emails)
        
        # 3. Look in HTML attributes (data-email, etc.)
        for tag in soup.find_all(attrs={'data-email': True}):
            emails.append(tag['data-email'])
        
        # Filter and return first valid email
        for email in emails:
            email_lower = email.lower()
            if not any(skip in email_lower for skip in ['example.com', 'domain.com', 'email.com', 'test.com', 'sentry.io', 'wixpress.com']):
                return [email]
        
        return []
    
    def guess_common_emails(self, domain: str) -> List[str]:
        """
        Generate common email patterns for a domain
        Ordered by likelihood of working
        """
        domain = domain.replace('www.', '').replace('http://', '').replace('https://', '')
        # Most common patterns first
        common_prefixes = ['info', 'contact', 'hello', 'office', 'admin', 'support', 'sales']
        return [f"{prefix}@{domain}" for prefix in common_prefixes]
    
    def verify_email_exists(self, email: str, found_on_site: bool = False) -> bool:
        """
        ULTRA-STRICT email verification to prevent bounces
        Always does full SMTP verification, even for emails found on websites
        """
        if not email or '@' not in email:
            return False
        
        try:
            email_local = email.split('@')[0].lower()
            domain = email.split('@')[1].lower()
            full_email = email.lower()
            
            # Filter out government, education, law firms, and directory sites
            excluded_domains = [
                '.gov',      # Government emails - not potential customers
                '.edu',      # Educational institutions - not potential customers
                'yelp.com',  # Yelp directory emails - not real businesses
                'yellowpages.com',  # Yellow pages directory
                'bbb.org',   # Better Business Bureau
            ]
            if any(excluded in domain for excluded in excluded_domains):
                print(f"      ⚠️  Skipping excluded domain: {email}")
                return False
            
            # Filter out law-related emails
            law_patterns = ['law', 'attorney', 'legal', 'lawyer', 'esquire', 'esq']
            if any(pattern in full_email for pattern in law_patterns):
                print(f"      ⚠️  Skipping law-related email: {email}")
                return False
            
            # Filter out high-bounce risk email patterns
            high_risk_patterns = [
                'noreply', 'no-reply', 'donotreply', 'do-not-reply',
                'bounce', 'mailer-daemon', 'postmaster',
                'abuse', 'spam', 'devnull', 'null'
            ]
            if any(pattern in email_local for pattern in high_risk_patterns):
                return False
            
            # Check DNS MX records (required)
            try:
                mx_records = dns.resolver.resolve(domain, 'MX', lifetime=8)
                if not mx_records:
                    return False
                mx_host = str(mx_records[0].exchange).rstrip('.')
            except Exception:
                # No MX records = no email server
                return False
            
            # ALWAYS do SMTP verification (even for emails found on site)
            # This is critical to prevent bounces
            try:
                server = smtplib.SMTP(timeout=10)  # Increased timeout for reliability
                server.set_debuglevel(0)
                server.connect(mx_host, 25)
                server.helo('mail.lesavoir.agency')
                server.mail('verify@lesavoir.agency')
                
                # The critical check
                code, message = server.rcpt(email)
                server.quit()
                
                # ONLY accept if explicitly confirmed (250 = OK, 251 = will forward)
                if code in [250, 251]:
                    return True
                    
                # Reject everything else:
                # 450/451 = greylisting (might work later but unreliable)
                # 452 = mailbox full
                # 550 = mailbox unavailable (most common bounce)
                # 551 = user not local
                # 552 = exceeded storage
                # 553 = mailbox name not allowed
                # 554 = transaction failed
                return False
                
            except smtplib.SMTPServerDisconnected:
                # Server disconnected = can't verify = reject
                return False
            except smtplib.SMTPConnectError:
                # Can't connect to mail server = reject
                return False
            except smtplib.SMTPHeloError:
                # HELO command failed = reject
                return False
            except socket.timeout:
                # Timeout = unreliable server = reject
                return False
            except Exception as e:
                # Any other error = reject to be safe
                print(f"      ⚠️  SMTP error for {email}: {type(e).__name__}")
                return False
                
        except Exception as e:
            return False
    
    def scrape_website_content(self, url: str) -> Optional[Dict]:
        """
        Scrape website content using Scrapfly API
        Extract clean text content without scripts
        """
        print(f"Scraping: {url[:50]}...")
        
        try:
            # Configure Scrapfly to extract clean content - fast mode
            config_obj = ScrapeConfig(
                url=url,
                render_js=False,  # Faster without JS rendering
                asp=False,  # Disable ASP to avoid conflicts
                retry=False  # Disable retry for speed
            )
            
            result = self.scrapfly_client.scrape(config_obj)
            
            if result.success:
                # Parse HTML and extract clean text
                soup = BeautifulSoup(result.content, 'lxml')
                
                # Try to extract emails from HTML first (mailto links, etc.)
                emails = self.extract_emails_from_html(result.content, soup)
                email = emails[0] if emails else None
                
                # Remove script and style elements
                for script in soup(["script", "style", "meta", "link"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text(separator=' ', strip=True)
                
                # Clean up whitespace
                text = ' '.join(text.split())
                
                # Limit to first 3000 characters for API efficiency
                text = text[:3000] if len(text) > 3000 else text
                
                # Try text extraction if no email found yet
                if not email:
                    email = self.extract_email_from_text(text)
                
                # Extract title
                title = soup.title.string if soup.title else "No title"
                
                return {
                    "content": text,
                    "title": title,
                    "email": email,
                    "success": True
                }
            else:
                print(f"✗ Failed")
                return {"success": False, "content": "", "title": "", "email": None}
                
        except Exception as e:
            print(f"✗ Error (skipping)")
            return {"success": False, "content": "", "title": "", "email": None}
    
    def perform_speed_test(self, url: str) -> Dict:
        """
        Perform website speed test using RapidAPI
        """
        print(f"Speed test...", end=" ")
        
        try:
            encoded_url = urllib.parse.quote(url, safe='')
            conn = http.client.HTTPSConnection("website-speed-test.p.rapidapi.com")
            
            headers = {
                'x-rapidapi-key': self.rapidapi_key,
                'x-rapidapi-host': "website-speed-test.p.rapidapi.com"
            }
            
            conn.request("GET", f"/speed-check.php?url={encoded_url}", headers=headers)
            res = conn.getresponse()
            data = res.read()
            
            result = json.loads(data.decode("utf-8"))
            
            # Extract key metrics from API response
            client_metrics = result.get("client_metrics", {})
            server_metrics = result.get("server_metrics", {})
            
            # Convert milliseconds to seconds for readability
            load_time_ms = client_metrics.get("full_load_time_ms", 0)
            load_time = f"{load_time_ms / 1000:.2f}s" if load_time_ms else "N/A"
            
            speed_data = {
                "success": True,
                "load_time": load_time,
                "load_time_ms": load_time_ms,
                "page_size": f"{server_metrics.get('content_size_kb', 0):.2f} KB",
                "requests": server_metrics.get("request_count", "N/A"),
                "performance_score": client_metrics.get("performance_score", "N/A"),
                "lcp_ms": client_metrics.get("lcp_ms", "N/A"),
                "issues": result.get("issues", []),
                "raw_data": result
            }
            
            print(f"✓ {speed_data['load_time']}")
            return speed_data
            
        except Exception as e:
            print(f"✗ (skipping)")
            # Skip logging for speed
            return {
                "success": False,
                "load_time": "N/A",
                "page_size": "N/A",
                "requests": "N/A",
                "grade": "N/A",
                "error": str(e)
            }
    
    def find_email_on_pages(self, base_url: str) -> tuple[Optional[str], bool]:
        """
        Try to find email on homepage only
        Returns (email, found_on_site) tuple
        """
        from urllib.parse import urlparse
        
        domain = urlparse(base_url).netloc
        
        # Only scrape homepage - simpler and faster
        try:
            content_data = self.scrape_website_content(base_url)
            if content_data.get("email"):
                print(f"✓ Found: {content_data['email']}")
                return content_data["email"], True
        except:
            pass
        
        # If no email found, use common patterns
        # These work 80%+ of the time for businesses
        print(f"Generating email...", end=" ")
        common_emails = self.guess_common_emails(domain)
        if common_emails:
            # Return the most common one: info@domain
            return common_emails[0], False
        
        return None, False
    
    def scrape_full_company_data(self, company: Dict) -> Optional[Dict]:
        """
        Scrape complete data for a company including content and speed test
        Returns None if no email found (to skip saving)
        """
        url = company.get("url", "")
        
        print(f"\n[{company.get('name', 'Unknown')[:60]}]")
        
        # Try to find email on homepage OR generate from domain
        email = company.get("email")
        found_on_site = False
        
        if not email:
            email, found_on_site = self.find_email_on_pages(url)
        
        # If still no email, generate one
        if not email:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.replace('www.', '')
            email = f"info@{domain}"
            print(f"Generated: {email}", end=" ")
            found_on_site = False
        
        # Only verify emails we actually found on site
        # Generated emails (info@, contact@) work 90% of the time, so trust them
        if found_on_site:
            print(f"Verifying...", end=" ")
            if not self.verify_email_exists(email, found_on_site=True):
                print("✗ Invalid (skipping)")
                return None
            print("✓ Verified!")
        else:
            # Generated email - MUST verify via SMTP
            print(f"Verifying generated email...", end=" ")
            if self.verify_email_exists(email, found_on_site=False):
                print("✓ SMTP verified!")
            else:
                print("✗ SMTP rejected (skipping)")
                return None
        
        company["email"] = email
        
        # Scrape website content from homepage
        content_data = self.scrape_website_content(url)
        
        # Perform speed test
        speed_data = self.perform_speed_test(url)
        
        # Compile all data
        company_data = {
            **company,
            "website_content": content_data.get("content", ""),
            "website_title": content_data.get("title", ""),
            "speed_test": speed_data,
            "scraped_successfully": content_data.get("success", False) and speed_data.get("success", False)
        }
        
        return company_data
    
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


def load_search_queries(file_path: str = "search_queries.txt") -> List[str]:
    """
    Load search queries from file, skipping comments, empty lines, and already used queries
    """
    queries = []
    used_queries = load_used_queries()
    
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments, empty lines, and used queries
                if line and not line.startswith('#') and line not in used_queries:
                    queries.append(line)
        return queries
    except FileNotFoundError:
        print(f"Warning: {file_path} not found. Using default query.")
        return [config.DEFAULT_SEARCH_QUERY]


def load_used_queries() -> set:
    """
    Load set of already used queries
    """
    used = set()
    try:
        if os.path.exists(config.USED_QUERIES_FILE):
            with open(config.USED_QUERIES_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        used.add(line)
    except Exception as e:
        print(f"Warning: Could not load used queries: {e}")
    return used


def mark_query_as_used(query: str):
    """
    Mark a query as used by adding it to used_queries.txt and removing from search_queries.txt
    """
    try:
        # Add to used queries
        with open(config.USED_QUERIES_FILE, 'a') as f:
            f.write(query + '\n')
        
        # Remove from active queries
        remaining_queries = []
        try:
            with open(config.SEARCH_QUERIES_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and line != query:
                        remaining_queries.append(line)
            
            with open(config.SEARCH_QUERIES_FILE, 'w') as f:
                for q in remaining_queries:
                    f.write(q + '\n')
        except FileNotFoundError:
            pass
        
        print(f"  📝 Marked query as used: {query}")
    except Exception as e:
        print(f"  ⚠ Could not mark query as used: {e}")


def normalize_url(url: str) -> str:
    """Normalize URL for better comparison (remove www, trailing slash, protocol)"""
    if not url:
        return ""
    
    from urllib.parse import urlparse
    parsed = urlparse(url.lower())
    domain = parsed.netloc or parsed.path
    domain = domain.replace('www.', '')
    domain = domain.rstrip('/')
    return domain


def get_already_scraped_urls():
    """
    Get all URLs we've already scraped to avoid duplicates
    Checks both current scraped data and sent emails history
    Uses normalized URLs for better duplicate detection
    """
    scraped_urls = set()
    
    # Check current scraped companies
    if os.path.exists(config.SCRAPED_COMPANIES_FILE):
        try:
            with open(config.SCRAPED_COMPANIES_FILE, 'r') as f:
                companies = json.load(f)
            for company in companies:
                if company.get('url'):
                    scraped_urls.add(normalize_url(company['url']))
        except:
            pass
    
    # Check sent emails history
    if os.path.exists(config.SENT_EMAILS_FILE):
        try:
            with open(config.SENT_EMAILS_FILE, 'r') as f:
                sent_data = json.load(f)
            # Handle both list and dict formats
            if isinstance(sent_data, dict):
                for entry in sent_data.get('detailed_history', []):
                    if entry.get('url'):
                        scraped_urls.add(normalize_url(entry['url']))
        except:
            pass
    
    return scraped_urls


def main():
    """
    Main function to run the scraper standalone
    Processes multiple search queries with 50 results each
    """
    import os
    import fcntl
    
    # Create data directory if it doesn't exist
    os.makedirs(config.DATA_DIR, exist_ok=True)
    
    # LOCK FILE: Prevent multiple scraper instances from running simultaneously
    lock_file_path = os.path.join(config.DATA_DIR, 'scraper.lock')
    lock_file = open(lock_file_path, 'w')
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("✓ Acquired scraper lock - no other instances running")
    except IOError:
        print("⚠️  Another scraper instance is already running. Exiting to prevent conflicts.")
        return
    
    print("="*80)
    print("COLD EMAIL SCRAPER - Multi-Query Mode")
    print("="*80)
    
    # Load search queries from file
    search_queries = load_search_queries("search_queries.txt")
    
    print(f"\nLoaded {len(search_queries)} search queries:")
    for i, query in enumerate(search_queries, 1):
        print(f"  {i}. {query}")
    
    results_per_query = 50
    print(f"\nWill scrape {results_per_query} results per query")
    print(f"Total expected results: ~{len(search_queries) * results_per_query}")
    print("\nStarting scraper...\n")
    
    # Initialize scraper
    scraper = CompanyScraper()
    
    # Get already scraped URLs to avoid duplicates
    already_scraped = get_already_scraped_urls()
    print(f"Already scraped {len(already_scraped)} unique URLs (will skip)\n")
    
    # Load existing data if available
    all_scraped_data = []
    if os.path.exists(config.SCRAPED_COMPANIES_FILE):
        try:
            with open(config.SCRAPED_COMPANIES_FILE, 'r') as f:
                all_scraped_data = json.load(f)
            print(f"Loaded {len(all_scraped_data)} existing companies from previous runs")
        except:
            pass
    
    # Process each query
    total_new_companies = 0
    
    for query_num, query in enumerate(search_queries, 1):
        print("\n" + "="*80)
        print(f"QUERY {query_num}/{len(search_queries)}: {query}")
        print("="*80)
        
        # Search for companies
        companies = scraper.search_companies(query, results_per_query)
        
        if not companies:
            print(f"No companies found for query: {query}")
            continue
        
        # Filter out already scraped URLs (using normalized URLs)
        new_companies = [c for c in companies if normalize_url(c.get('url', '')) not in already_scraped]
        skipped = len(companies) - len(new_companies)
        
        print(f"\nFound {len(companies)} companies ({skipped} already scraped, {len(new_companies)} new)")
        
        if not new_companies:
            print("All companies already scraped, moving to next query...")
            continue
        
        print(f"Starting detailed scraping of {len(new_companies)} new companies...")
        companies = new_companies  # Use only new companies
        
        # Scrape with MAXIMUM PARALLEL processing (100 concurrent workers)
        print(f"Scraping {len(companies)} companies with 100 workers...")
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        with ThreadPoolExecutor(max_workers=100) as executor:
            future_to_company = {
                executor.submit(scraper.scrape_full_company_data, company): company 
                for company in companies
            }
            
            for i, future in enumerate(as_completed(future_to_company), 1):
                print(f"[Q{query_num}/{len(search_queries)}][{i}/{len(companies)}]", end=" ")
                
                try:
                    company_data = future.result(timeout=60)
                    
                    # Only save if email was found AND not a law company
                    if company_data is not None:
                        # Double-check not a law company
                        name_lower = company_data.get('name', '').lower()
                        content_lower = company_data.get('website_content', '').lower()[:1000]
                        law_keywords = ['law firm', 'attorney', 'lawyer', 'legal services', 'counsel', 'esquire']
                        
                        is_law = any(kw in name_lower or kw in content_lower for kw in law_keywords)
                        
                        if not is_law:
                            company_data['source_query'] = query
                            all_scraped_data.append(company_data)
                            already_scraped.add(normalize_url(company_data.get('url', '')))
                            total_new_companies += 1
                            
                            # Save progress every 10 companies
                            if total_new_companies % 10 == 0:
                                with open(config.SCRAPED_COMPANIES_FILE, 'w') as f:
                                    json.dump(all_scraped_data, f, indent=2)
                                print(f"  💾 Saved {total_new_companies} companies")
                        else:
                            print(f"✗ Skipped (law)")
                            already_scraped.add(normalize_url(future_to_company[future].get('url', '')))
                except Exception as e:
                    print(f"✗ Error: {str(e)[:30]}")
        
        # No delay - maximum speed
        pass
        
        continue  # Skip the old parallel code
        
        # OLD PARALLEL CODE (disabled)
        """        
        with ThreadPoolExecutor(max_workers=2) as executor:  # Reduced from 5 to 2
            future_to_company = {
                executor.submit(scraper.scrape_full_company_data, company): company 
                for company in companies
            }
            
            for i, future in enumerate(as_completed(future_to_company), 1):
                try:
                    print(f"[Q{query_num}/{len(search_queries)}][{i}/{len(companies)}]", end=" ")
                    company_data = future.result(timeout=60)
                    
                    # Only save if email was found
                    if company_data is not None:
                        company_data['source_query'] = query
                        all_scraped_data.append(company_data)
                        total_new_companies += 1
                        
                        # Save progress every 5 companies with emails
                        if total_new_companies % 5 == 0:
                            with open(config.SCRAPED_COMPANIES_FILE, 'w') as f:
                                json.dump(all_scraped_data, f, indent=2)
                            print(f"  💾 Saved {total_new_companies} companies")
                except Exception as e:
                    print(f"✗ Error: {str(e)[:30]}")
                    continue
        """
        
        print(f"\n✓ Completed query {query_num}/{len(search_queries)}")
        
        # Mark query as used
        mark_query_as_used(query)
        
        # No delay between queries
        pass
    
    # Save final results
    with open(config.SCRAPED_COMPANIES_FILE, 'w') as f:
        json.dump(all_scraped_data, f, indent=2)
    
    # Print summary
    print("\n" + "="*80)
    print("SCRAPING COMPLETE - ALL QUERIES PROCESSED")
    print("="*80)
    print(f"Total queries processed: {len(search_queries)}")
    print(f"NEW companies added THIS RUN: {total_new_companies}")
    print(f"TOTAL companies in database: {len(all_scraped_data)}")
    print(f"All have verified emails: {sum(1 for c in all_scraped_data if c.get('email'))}")
    print(f"\nData saved to: {config.SCRAPED_COMPANIES_FILE}")
    print("="*80)
    
    # Release lock
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
        os.remove(lock_file_path)
        print("✓ Released scraper lock")
    except:
        pass


if __name__ == "__main__":
    main()

