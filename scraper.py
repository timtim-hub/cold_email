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
        print(f"Scraping content from: {url}")
        
        try:
            # Configure Scrapfly to extract clean content
            config_obj = ScrapeConfig(
                url=url,
                render_js=False,  # Faster without JS rendering
                asp=True  # Anti-scraping protection
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
                print(f"Failed to scrape {url}")
                return {"success": False, "content": "", "title": "", "email": None}
                
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            self.log_error(f"scrape_website_content error for {url}: {e}")
            return {"success": False, "content": "", "title": "", "email": None}
    
    def perform_speed_test(self, url: str) -> Dict:
        """
        Perform website speed test using RapidAPI
        """
        print(f"Performing speed test for: {url}")
        
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
            
            # Extract key metrics
            speed_data = {
                "success": True,
                "load_time": result.get("load_time", "N/A"),
                "page_size": result.get("page_size", "N/A"),
                "requests": result.get("requests", "N/A"),
                "grade": result.get("grade", "N/A"),
                "raw_data": result
            }
            
            print(f"Speed test completed: Load time = {speed_data['load_time']}")
            return speed_data
            
        except Exception as e:
            print(f"Error performing speed test for {url}: {e}")
            self.log_error(f"perform_speed_test error for {url}: {e}")
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
        
        print(f"\n{'='*60}")
        print(f"Processing: {company.get('name', 'Unknown')}")
        print(f"URL: {url}")
        print(f"{'='*60}")
        
        # Scrape website content
        content_data = self.scrape_website_content(url)
        time.sleep(2)  # Small delay between requests
        
        # Perform speed test
        speed_data = self.perform_speed_test(url)
        time.sleep(2)  # Small delay between requests
        
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


def main():
    """
    Main function to run the scraper standalone
    """
    import os
    
    # Create data directory if it doesn't exist
    os.makedirs(config.DATA_DIR, exist_ok=True)
    
    print("="*80)
    print("COLD EMAIL SCRAPER - Standalone Mode")
    print("="*80)
    
    # Get user input
    query = input(f"\nEnter search query (default: '{config.DEFAULT_SEARCH_QUERY}'): ").strip()
    if not query:
        query = config.DEFAULT_SEARCH_QUERY
    
    num_results = input(f"Enter number of results to scrape (default: {config.DEFAULT_NUM_RESULTS}): ").strip()
    try:
        num_results = int(num_results) if num_results else config.DEFAULT_NUM_RESULTS
    except ValueError:
        num_results = config.DEFAULT_NUM_RESULTS
    
    # Initialize scraper
    scraper = CompanyScraper()
    
    # Search for companies
    companies = scraper.search_companies(query, num_results)
    
    if not companies:
        print("\nNo companies found. Exiting.")
        return
    
    print(f"\nFound {len(companies)} companies. Starting detailed scraping...")
    
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
            print(f"\nProgress saved: {i}/{len(companies)} companies")
    
    # Save final results
    with open(config.SCRAPED_COMPANIES_FILE, 'w') as f:
        json.dump(scraped_data, f, indent=2)
    
    # Print summary
    print("\n" + "="*80)
    print("SCRAPING COMPLETE")
    print("="*80)
    print(f"Total companies processed: {len(scraped_data)}")
    print(f"Successfully scraped: {sum(1 for c in scraped_data if c.get('scraped_successfully'))}")
    print(f"Companies with emails: {sum(1 for c in scraped_data if c.get('email'))}")
    print(f"\nData saved to: {config.SCRAPED_COMPANIES_FILE}")
    print("="*80)


if __name__ == "__main__":
    main()

