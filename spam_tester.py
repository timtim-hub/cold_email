"""
Spam Testing Module
Automatically tests email deliverability using mail-tester.com
"""

import smtplib
import time
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import config


class SpamTester:
    def __init__(self):
        self.test_results_file = "data/spam_test_results.json"
        
    def send_test_email(self, test_address: str) -> bool:
        """
        Send a test email to mail-tester.com or similar service
        """
        try:
            # Create a realistic test email (similar to what we actually send)
            msg = MIMEMultipart('alternative')
            msg['From'] = config.FROM_EMAIL
            msg['To'] = test_address
            msg['Subject'] = "Test: Website Performance Analysis"
            
            # Create email body similar to our actual emails
            body = f"""Hi Test Business Team,

I was researching local businesses and came across your website. Your online presence looks professional, which is why I wanted to reach out about a potential performance issue I noticed.

Website speed is crucial for customer retention - studies show that even a 1-second delay can cost up to 7% of conversions. Many businesses don't realize their site might be slower than competitors.

At {config.COMPANY_NAME}, we've helped over 100 local businesses optimize their website performance, typically seeing 2-3x faster load times within a week.

Worth a quick chat? I can send you a detailed performance report. Just reply with "interested" or email {config.CONTACT_EMAIL}.

Jonas
{config.COMPANY_NAME}
{config.CONTACT_EMAIL}

---
This is a deliverability test email sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send via SMTP
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30)
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            print(f"✅ Test email sent to: {test_address}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send test email: {e}")
            return False
    
    def get_mail_tester_address(self) -> str:
        """
        Get a unique test address from mail-tester.com
        Note: This returns a format, user needs to visit site to get actual address
        """
        # Mail-tester uses format: test-xxxxx@mail-tester.com
        # The xxxxx changes each session, so user needs to get it from the website
        return "mail-tester.com"
    
    def run_manual_test(self, test_email: str) -> dict:
        """
        Run a manual spam test by sending to provided address
        Returns test info for tracking
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "test_email": test_email,
            "status": "pending",
            "score": None,
            "notes": "Manual test - check service for results"
        }
        
        # Send the test email
        if self.send_test_email(test_email):
            result["status"] = "sent"
            result["message"] = f"Test email sent successfully. Check {test_email.split('@')[1]} for results."
        else:
            result["status"] = "failed"
            result["message"] = "Failed to send test email"
        
        # Save result
        self.save_test_result(result)
        
        return result
    
    def save_test_result(self, result: dict):
        """Save test result to file"""
        try:
            # Load existing results
            if os.path.exists(self.test_results_file):
                with open(self.test_results_file, 'r') as f:
                    results = json.load(f)
            else:
                results = {"tests": []}
            
            # Add new result
            results["tests"].append(result)
            
            # Keep only last 50 tests
            results["tests"] = results["tests"][-50:]
            
            # Save
            os.makedirs("data", exist_ok=True)
            with open(self.test_results_file, 'w') as f:
                json.dump(results, f, indent=2)
                
        except Exception as e:
            print(f"Error saving test result: {e}")
    
    def get_test_history(self) -> list:
        """Get history of spam tests"""
        try:
            if os.path.exists(self.test_results_file):
                with open(self.test_results_file, 'r') as f:
                    data = json.load(f)
                    return data.get("tests", [])
            return []
        except:
            return []
    
    def get_deliverability_score(self) -> dict:
        """
        Calculate deliverability health based on recent activity
        """
        import dns.resolver
        
        score = 100
        issues = []
        recommendations = []
        
        domain = config.FROM_EMAIL.split('@')[1]
        
        # Check SPF
        try:
            txt_records = dns.resolver.resolve(domain, 'TXT')
            spf_found = False
            for record in txt_records:
                if 'v=spf1' in str(record):
                    spf_found = True
                    break
            if not spf_found:
                score -= 20
                issues.append("Missing SPF record")
                recommendations.append("Add SPF record to DNS")
        except:
            score -= 20
            issues.append("Cannot verify SPF record")
        
        # Check DMARC
        try:
            dmarc_records = dns.resolver.resolve(f'_dmarc.{domain}', 'TXT')
            if not dmarc_records:
                score -= 15
                issues.append("Missing DMARC record")
                recommendations.append("Add DMARC record: v=DMARC1; p=none; rua=mailto:contact@" + domain)
        except:
            score -= 15
            issues.append("Missing DMARC record")
            recommendations.append("Add DMARC record to DNS")
        
        # Check if using rotating senders
        if config.USE_ROTATING_SENDERS:
            recommendations.append("✅ Using rotating senders (good!)")
        else:
            score -= 5
            issues.append("Not using rotating senders")
            recommendations.append("Enable rotating sender addresses")
        
        # Check recent bounce rate
        try:
            if os.path.exists(config.SENT_EMAILS_FILE):
                with open(config.SENT_EMAILS_FILE, 'r') as f:
                    sent_data = json.load(f)
                    total_sent = len(sent_data.get('sent_emails', []))
                    
                    # Estimate bounce rate from error log
                    bounce_count = 0
                    if os.path.exists(config.ERROR_LOG_FILE):
                        with open(config.ERROR_LOG_FILE, 'r') as ef:
                            for line in ef.readlines()[-100:]:  # Last 100 errors
                                if 'bounce' in line.lower() or '550' in line or 'mailbox' in line.lower():
                                    bounce_count += 1
                    
                    if total_sent > 0:
                        bounce_rate = (bounce_count / min(total_sent, 100)) * 100
                        if bounce_rate > 5:
                            score -= 20
                            issues.append(f"High bounce rate: ~{bounce_rate:.1f}%")
                            recommendations.append("Review email verification process")
                        elif bounce_rate > 2:
                            score -= 10
                            issues.append(f"Elevated bounce rate: ~{bounce_rate:.1f}%")
        except:
            pass
        
        return {
            "score": max(0, score),
            "grade": "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D",
            "issues": issues,
            "recommendations": recommendations,
            "status": "excellent" if score >= 90 else "good" if score >= 75 else "needs_improvement"
        }


if __name__ == "__main__":
    tester = SpamTester()
    
    print("📧 Spam Tester - Standalone Mode")
    print("="*60)
    print()
    print("To test your email deliverability:")
    print("1. Visit: https://www.mail-tester.com")
    print("2. Copy the test email address shown")
    print("3. Run: python spam_tester.py <test-email>")
    print()
    
    # Show deliverability score
    score = tester.get_deliverability_score()
    print(f"Current Deliverability Score: {score['score']}/100 (Grade: {score['grade']})")
    print()
    
    if score['issues']:
        print("⚠️  Issues Found:")
        for issue in score['issues']:
            print(f"   • {issue}")
        print()
    
    if score['recommendations']:
        print("💡 Recommendations:")
        for rec in score['recommendations']:
            print(f"   • {rec}")

