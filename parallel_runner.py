#!/usr/bin/env python3
"""
Parallel Runner - Run scraper and emailer simultaneously
Continuously scrapes new companies while sending emails to already-scraped ones
"""
import time
import threading
import subprocess
import json
import os
from datetime import datetime

# Configuration
RUN_PARALLEL = True  # Set to True to run both at once
CHECK_INTERVAL = 30  # Check for new companies every 30 seconds
MIN_COMPANIES_TO_START_EMAILING = 20  # Wait for at least 20 companies before starting emailer

class ParallelRunner:
    def __init__(self):
        self.scraper_running = False
        self.emailer_running = False
        self.stop_threads = False
        
    def run_scraper(self):
        """Run scraper in background"""
        print("🔍 Starting scraper thread...")
        self.scraper_running = True
        
        try:
            process = subprocess.Popen(
                ['python', 'scraper.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Stream output
            for line in process.stdout:
                if not self.stop_threads:
                    print(f"[SCRAPER] {line.rstrip()}")
                else:
                    process.terminate()
                    break
                    
            process.wait()
            
        except Exception as e:
            print(f"❌ Scraper error: {e}")
        finally:
            self.scraper_running = False
            print("🔍 Scraper thread finished")
    
    def run_emailer_continuous(self):
        """Run emailer continuously - checks for new companies every interval"""
        print("📧 Starting emailer thread...")
        self.emailer_running = True
        
        try:
            while not self.stop_threads:
                # Check how many companies we have
                if os.path.exists('data/scraped_companies.json'):
                    with open('data/scraped_companies.json', 'r') as f:
                        companies = json.load(f)
                    
                    # Load sent emails
                    sent_emails = set()
                    if os.path.exists('data/sent_emails.json'):
                        with open('data/sent_emails.json', 'r') as f:
                            sent_data = json.load(f)
                            if isinstance(sent_data, dict):
                                sent_emails = set(sent_data.get('sent_emails', []))
                    
                    # Count available companies
                    available = [c for c in companies if c.get('email') and c.get('email') not in sent_emails]
                    
                    if len(available) >= MIN_COMPANIES_TO_START_EMAILING:
                        print(f"\n📧 [EMAILER] Found {len(available)} companies to email. Starting batch...")
                        
                        # Run emailer
                        process = subprocess.Popen(
                            ['python', 'emailer.py'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            bufsize=1
                        )
                        
                        # Stream output
                        for line in process.stdout:
                            if not self.stop_threads:
                                print(f"[EMAILER] {line.rstrip()}")
                            else:
                                process.terminate()
                                break
                        
                        process.wait()
                        print(f"📧 [EMAILER] Batch complete. Waiting {CHECK_INTERVAL}s before next check...")
                        
                    else:
                        print(f"📧 [EMAILER] Only {len(available)} companies available. Waiting for more... (need {MIN_COMPANIES_TO_START_EMAILING})")
                    
                    # Wait before checking again
                    time.sleep(CHECK_INTERVAL)
                else:
                    print(f"📧 [EMAILER] Waiting for scraper to create data file...")
                    time.sleep(CHECK_INTERVAL)
                    
        except Exception as e:
            print(f"❌ Emailer error: {e}")
        finally:
            self.emailer_running = False
            print("📧 Emailer thread finished")
    
    def run_parallel(self):
        """Run scraper and emailer in parallel"""
        print("="*80)
        print("🚀 PARALLEL MODE - SCRAPER + EMAILER")
        print("="*80)
        print(f"⚙️  Configuration:")
        print(f"   - Check interval: {CHECK_INTERVAL}s")
        print(f"   - Min companies before emailing: {MIN_COMPANIES_TO_START_EMAILING}")
        print(f"   - Mode: {'PARALLEL' if RUN_PARALLEL else 'SEQUENTIAL'}")
        print("="*80 + "\n")
        
        if not RUN_PARALLEL:
            print("ℹ️  Parallel mode disabled. Run scraper only.")
            self.run_scraper()
            return
        
        # Start both threads
        scraper_thread = threading.Thread(target=self.run_scraper, daemon=True)
        emailer_thread = threading.Thread(target=self.run_emailer_continuous, daemon=True)
        
        scraper_thread.start()
        time.sleep(5)  # Give scraper a head start
        emailer_thread.start()
        
        try:
            # Keep main thread alive and show status
            while scraper_thread.is_alive() or emailer_thread.is_alive():
                time.sleep(60)  # Status update every minute
                
                # Show status
                if os.path.exists('data/scraped_companies.json'):
                    with open('data/scraped_companies.json', 'r') as f:
                        companies = json.load(f)
                    
                    sent_count = 0
                    if os.path.exists('data/sent_emails.json'):
                        with open('data/sent_emails.json', 'r') as f:
                            sent_data = json.load(f)
                            if isinstance(sent_data, dict):
                                sent_count = len(sent_data.get('sent_emails', []))
                    
                    print(f"\n{'='*80}")
                    print(f"📊 STATUS UPDATE - {datetime.now().strftime('%H:%M:%S')}")
                    print(f"{'='*80}")
                    print(f"   🔍 Scraper: {'Running' if self.scraper_running else 'Stopped'}")
                    print(f"   📧 Emailer: {'Running' if self.emailer_running else 'Stopped'}")
                    print(f"   💾 Companies scraped: {len(companies)}")
                    print(f"   ✅ Emails sent: {sent_count}")
                    print(f"   📋 Remaining to email: {len(companies) - sent_count}")
                    print(f"{'='*80}\n")
                
        except KeyboardInterrupt:
            print("\n⚠️  Stopping threads...")
            self.stop_threads = True
            time.sleep(2)
        
        print("\n✅ All threads finished!")

def main():
    import fcntl
    
    # LOCK FILE: Prevent multiple parallel_runner instances
    lock_file_path = 'data/parallel_runner.lock'
    os.makedirs('data', exist_ok=True)
    lock_file = open(lock_file_path, 'w')
    
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("✓ Acquired parallel_runner lock - no other instances running\n")
    except IOError:
        print("⚠️  Another parallel_runner instance is already running. Exiting to prevent conflicts.")
        print("   To force restart, delete data/parallel_runner.lock and try again.")
        return
    
    try:
        runner = ParallelRunner()
        runner.run_parallel()
    finally:
        # Release lock
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            os.remove(lock_file_path)
            print("\n✓ Released parallel_runner lock")
        except:
            pass

if __name__ == "__main__":
    main()

