"""
Scraper module for extracting company information, website content, and speed tests
"""

import json
import re
import time
import http.client
import urllib.parse
from typing import List, Dict, Optional
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
        return matches[0] if matches else None
    
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
                retry=False,  # Disable retry for speed
                timeout=10000  # 10 second timeout
            )
            
            result = self.scrapfly_client.scrape(config_obj)
            
            if result.success:
                # Parse HTML and extract clean text
                soup = BeautifulSoup(result.content, 'lxml')
                
                # Remove script and style elements
                for script in soup(["script", "style", "meta", "link"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text(separator=' ', strip=True)
                
                # Clean up whitespace
                text = ' '.join(text.split())
                
                # Limit to first 3000 characters for API efficiency
                text = text[:3000] if len(text) > 3000 else text
                
                # Try to extract email if not found yet
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
    
    def scrape_full_company_data(self, company: Dict) -> Dict:
        """
        Scrape complete data for a company including content and speed test
        """
        url = company.get("url", "")
        
        print(f"\n[{company.get('name', 'Unknown')[:60]}]")
        
        # Scrape website content
        content_data = self.scrape_website_content(url)
        
        # Perform speed test
        speed_data = self.perform_speed_test(url)
        
        # Update email if found in content
        if content_data.get("email") and not company.get("email"):
            company["email"] = content_data["email"]
        
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
    Load search queries from file, skipping comments and empty lines
    """
    queries = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    queries.append(line)
        return queries
    except FileNotFoundError:
        print(f"Warning: {file_path} not found. Using default query.")
        return [config.DEFAULT_SEARCH_QUERY]


def main():
    """
    Main function to run the scraper standalone
    Processes multiple search queries with 50 results each
    """
    import os
    
    # Create data directory if it doesn't exist
    os.makedirs(config.DATA_DIR, exist_ok=True)
    
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
    
    # Load existing data if available
    all_scraped_data = []
    if os.path.exists(config.SCRAPED_COMPANIES_FILE):
        try:
            with open(config.SCRAPED_COMPANIES_FILE, 'r') as f:
                all_scraped_data = json.load(f)
            print(f"\nLoaded {len(all_scraped_data)} existing companies from previous runs")
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
        
        print(f"\nFound {len(companies)} companies. Starting detailed scraping...")
        
        # Scrape full data for each company
        for i, company in enumerate(companies, 1):
            print(f"[Q{query_num}/{len(search_queries)}][{i}/{len(companies)}]", end=" ")
            company_data = scraper.scrape_full_company_data(company)
            company_data['source_query'] = query  # Track which query found this company
            all_scraped_data.append(company_data)
            total_new_companies += 1
            
            # Save progress every 10 companies
            if total_new_companies % 10 == 0:
                with open(config.SCRAPED_COMPANIES_FILE, 'w') as f:
                    json.dump(all_scraped_data, f, indent=2)
                print(f"  💾 Saved {total_new_companies} companies")
        
        print(f"\n✓ Completed query {query_num}/{len(search_queries)}")
    
    # Save final results
    with open(config.SCRAPED_COMPANIES_FILE, 'w') as f:
        json.dump(all_scraped_data, f, indent=2)
    
    # Print summary
    print("\n" + "="*80)
    print("SCRAPING COMPLETE - ALL QUERIES PROCESSED")
    print("="*80)
    print(f"Total queries processed: {len(search_queries)}")
    print(f"Total companies processed: {len(all_scraped_data)}")
    print(f"New companies added: {total_new_companies}")
    print(f"Successfully scraped: {sum(1 for c in all_scraped_data if c.get('scraped_successfully'))}")
    print(f"Companies with emails: {sum(1 for c in all_scraped_data if c.get('email'))}")
    print(f"\nData saved to: {config.SCRAPED_COMPANIES_FILE}")
    print("="*80)


if __name__ == "__main__":
    main()

