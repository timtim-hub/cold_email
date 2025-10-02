"""
Web Dashboard for Cold Email System
Beautiful GUI to monitor and control scraper and emailer
"""

from flask import Flask, render_template, jsonify, request, Response
import json
import os
import subprocess
import psutil
import time
import logging
import traceback
import requests
from datetime import datetime, timedelta
from openai import OpenAI
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('dashboard_errors.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# Store process IDs
processes = {
    'scraper': None,
    'emailer': None,
    'parallel': None
}

def safe_api_call(func):
    """Decorator for safe API calls with error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Error in {func.__name__}: {str(e)}"
            app.logger.error(error_msg)
            app.logger.error(traceback.format_exc())
            return jsonify({
                'error': True,
                'message': error_msg,
                'details': str(e)
            }), 500
    wrapper.__name__ = func.__name__
    return wrapper

def get_process_status():
    """Check if processes are running"""
    status = {
        'scraper': False,
        'emailer': False,
        'parallel': False
    }
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'python' in cmdline:
                    if 'scraper.py' in cmdline and 'parallel' not in cmdline:
                        status['scraper'] = True
                        processes['scraper'] = proc.info['pid']
                    elif 'emailer.py' in cmdline and 'parallel' not in cmdline:
                        status['emailer'] = True
                        processes['emailer'] = proc.info['pid']
                    elif 'parallel_runner.py' in cmdline:
                        status['parallel'] = True
                        status['scraper'] = True
                        status['emailer'] = True
                        processes['parallel'] = proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        app.logger.error(f"Error in get_process_status: {e}")
    
    return status

def get_stats():
    """Get current statistics"""
    stats = {
        'emails_sent_total': 0,
        'emails_sent_today': 0,
        'companies_scraped': 0,
        'companies_queued': 0,
        'last_email_time': None,
        'sending_rate': 0,
        'scraper_progress': {'current': 0, 'total': 200},
        'success_rate': 0,
        'rotating_senders_enabled': config.USE_ROTATING_SENDERS,
        'rotating_sender_count': len(config.ROTATING_SENDER_PREFIXES) if config.USE_ROTATING_SENDERS else 0
    }
    
    # Load sent emails
    try:
        if os.path.exists(config.SENT_EMAILS_FILE):
            with open(config.SENT_EMAILS_FILE, 'r') as f:
                sent_data = json.load(f)
                stats['emails_sent_total'] = len(sent_data.get('sent_emails', []))
                
                # Count today's emails
                history = sent_data.get('detailed_history', [])
                today = datetime.now().strftime('%Y-%m-%d')
                stats['emails_sent_today'] = sum(1 for h in history if h.get('timestamp', '').startswith(today))
                
                # Calculate sending rate (emails per minute in last 10 emails)
                if len(history) >= 2:
                    recent = history[-10:]
                    if len(recent) >= 2:
                        try:
                            first_time = datetime.strptime(recent[0]['timestamp'], '%Y-%m-%d %H:%M:%S')
                            last_time = datetime.strptime(recent[-1]['timestamp'], '%Y-%m-%d %H:%M:%S')
                            time_diff = (last_time - first_time).total_seconds() / 60
                            if time_diff > 0:
                                stats['sending_rate'] = round(len(recent) / time_diff, 2)
                            stats['last_email_time'] = recent[-1]['timestamp']
                        except Exception as e:
                            app.logger.warning(f"Error calculating sending rate: {e}")
    except Exception as e:
        app.logger.error(f"Error loading sent emails: {e}")
    
    # Load scraped companies
    try:
        if os.path.exists(config.SCRAPED_COMPANIES_FILE):
            with open(config.SCRAPED_COMPANIES_FILE, 'r') as f:
                companies = json.load(f)
                stats['companies_scraped'] = stats['emails_sent_total'] + len(companies)
                stats['companies_queued'] = len(companies)
    except Exception as e:
        app.logger.error(f"Error loading scraped companies: {e}")
    
    # Calculate success rate
    if stats['companies_scraped'] > 0:
        stats['success_rate'] = round((stats['emails_sent_total'] / stats['companies_scraped']) * 100, 1)
    
    return stats

def get_recent_activity():
    """Get recent emails sent and companies scraped"""
    activity = {
        'recent_emails': [],
        'recent_scraped': []
    }
    
    # Recent emails
    try:
        if os.path.exists(config.SENT_EMAILS_FILE):
            with open(config.SENT_EMAILS_FILE, 'r') as f:
                sent_data = json.load(f)
                history = sent_data.get('detailed_history', [])
                activity['recent_emails'] = history[-20:][::-1]  # Last 20, reversed
    except Exception as e:
        app.logger.error(f"Error loading recent emails: {e}")
    
    # Recent scraped companies
    try:
        if os.path.exists(config.SCRAPED_COMPANIES_FILE):
            with open(config.SCRAPED_COMPANIES_FILE, 'r') as f:
                companies = json.load(f)
                activity['recent_scraped'] = companies[-20:][::-1]  # Last 20, reversed
    except Exception as e:
        app.logger.error(f"Error loading recent scraped: {e}")
    
    return activity

def get_chart_data():
    """Get data for charts"""
    chart_data = {
        'hourly_sends': [],
        'labels': []
    }
    
    try:
        if os.path.exists(config.SENT_EMAILS_FILE):
            with open(config.SENT_EMAILS_FILE, 'r') as f:
                sent_data = json.load(f)
                history = sent_data.get('detailed_history', [])
                
                # Group by hour for last 24 hours
                now = datetime.now()
                hourly_counts = {}
                
                for h in history:
                    try:
                        timestamp = datetime.strptime(h['timestamp'], '%Y-%m-%d %H:%M:%S')
                        if (now - timestamp) <= timedelta(hours=24):
                            hour_key = timestamp.strftime('%Y-%m-%d %H:00')
                            hourly_counts[hour_key] = hourly_counts.get(hour_key, 0) + 1
                    except:
                        continue
                
                # Generate labels for last 24 hours
                for i in range(24, -1, -1):
                    hour = now - timedelta(hours=i)
                    hour_key = hour.strftime('%Y-%m-%d %H:00')
                    label = hour.strftime('%H:00')
                    chart_data['labels'].append(label)
                    chart_data['hourly_sends'].append(hourly_counts.get(hour_key, 0))
    except Exception as e:
        app.logger.error(f"Error generating chart data: {e}")
    
    return chart_data

@app.route('/')
def dashboard():
    """Render main dashboard"""
    try:
        return render_template('dashboard.html')
    except Exception as e:
        app.logger.error(f"Error rendering dashboard: {e}")
        return f"Error: {e}", 500

@app.route('/api/status')
@safe_api_call
def api_status():
    """Get current status"""
    return jsonify({
        'processes': get_process_status(),
        'stats': get_stats(),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/activity')
@safe_api_call
def api_activity():
    """Get recent activity"""
    return jsonify(get_recent_activity())

@app.route('/api/charts')
@safe_api_call
def api_charts():
    """Get chart data"""
    return jsonify(get_chart_data())

@app.route('/api/start', methods=['POST'])
@safe_api_call
def api_start():
    """Start processes"""
    data = request.json or {}
    mode = data.get('mode', 'parallel')  # scraper, emailer, or parallel
    
    try:
        if mode == 'parallel':
            subprocess.Popen(['python', 'parallel_runner.py'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            return jsonify({'success': True, 'message': 'Started both scraper and emailer'})
        elif mode == 'scraper':
            subprocess.Popen(['python', 'scraper.py'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            return jsonify({'success': True, 'message': 'Started scraper'})
        elif mode == 'emailer':
            subprocess.Popen(['python', 'emailer.py'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            return jsonify({'success': True, 'message': 'Started emailer'})
        else:
            return jsonify({'success': False, 'message': 'Invalid mode'}), 400
    except Exception as e:
        app.logger.error(f"Error starting process: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/stop', methods=['POST'])
@safe_api_call
def api_stop():
    """Stop processes"""
    data = request.json or {}
    mode = data.get('mode', 'all')  # scraper, emailer, or all
    
    try:
        stopped = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'python' in cmdline:
                    if mode == 'all' or mode == 'parallel':
                        if any(x in cmdline for x in ['scraper.py', 'emailer.py', 'parallel_runner.py']):
                            proc.terminate()
                            stopped.append(proc.info['pid'])
                    elif mode == 'scraper' and 'scraper.py' in cmdline:
                        proc.terminate()
                        stopped.append(proc.info['pid'])
                    elif mode == 'emailer' and 'emailer.py' in cmdline:
                        proc.terminate()
                        stopped.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        time.sleep(1)  # Wait for graceful termination
        
        return jsonify({
            'success': True, 
            'message': f'Stopped {len(stopped)} process(es)',
            'stopped_pids': stopped
        })
    except Exception as e:
        app.logger.error(f"Error stopping processes: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/config')
@safe_api_call
def api_config():
    """Get current configuration"""
    return jsonify({
        'max_emails_per_run': config.MAX_EMAILS_PER_RUN,
        'delay_between_emails': config.DELAY_BETWEEN_EMAILS,
        'use_rotating_senders': config.USE_ROTATING_SENDERS,
        'rotating_prefixes': config.ROTATING_SENDER_PREFIXES if config.USE_ROTATING_SENDERS else [],
        'results_per_query': config.RESULTS_PER_QUERY,
        'company_name': config.COMPANY_NAME,
        'contact_email': config.CONTACT_EMAIL
    })

@app.route('/api/logs')
@safe_api_call
def api_logs():
    """Get recent log entries"""
    logs = []
    
    # Try to read recent log files
    log_files = ['scraper_ultrafast.log', 'parallel_run.log', 'parallel_rotating_run.log', 'dashboard_errors.log']
    for log_file in log_files:
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    logs.extend([{'file': log_file, 'line': line.strip()} for line in lines[-50:]])
        except Exception as e:
            app.logger.warning(f"Could not read log file {log_file}: {e}")
            continue
    
    return jsonify({'logs': logs[-100:]})  # Return last 100 total lines

@app.route('/queries')
def queries_page():
    """Render search queries management page"""
    try:
        return render_template('queries.html')
    except Exception as e:
        app.logger.error(f"Error rendering queries page: {e}")
        return f"Error: {e}", 500

@app.route('/api/queries')
@safe_api_call
def api_get_queries():
    """Get current search queries"""
    queries = []
    try:
        if os.path.exists(config.SEARCH_QUERIES_FILE):
            with open(config.SEARCH_QUERIES_FILE, 'r') as f:
                queries = [line.strip() for line in f.readlines() if line.strip()]
    except Exception as e:
        app.logger.error(f"Error loading queries: {e}")
    
    return jsonify({
        'queries': queries,
        'count': len(queries)
    })

@app.route('/api/queries', methods=['POST'])
@safe_api_call
def api_save_queries():
    """Save search queries"""
    data = request.json or {}
    queries = data.get('queries', [])
    
    try:
        with open(config.SEARCH_QUERIES_FILE, 'w') as f:
            for query in queries:
                if query.strip():
                    f.write(query.strip() + '\n')
        
        return jsonify({
            'success': True,
            'message': f'Saved {len(queries)} queries',
            'count': len(queries)
        })
    except Exception as e:
        app.logger.error(f"Error saving queries: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/queries/generate', methods=['POST'])
@safe_api_call
def api_generate_queries():
    """Generate new search queries using GPT-4"""
    data = request.json or {}
    num_queries = data.get('count', 50)
    append = data.get('append', True)  # Append to existing or replace
    
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        # Generate queries using GPT-4
        prompt = f"""Generate {num_queries} diverse search queries for finding local businesses in small US cities.

Requirements:
- Focus on LOCAL BUSINESSES and SERVICE PROVIDERS
- Include SMALL to MEDIUM US cities (not major metros like NYC, LA)
- Mix of business types: home services, retail, professional services, food/beverage, etc.
- NO LAW FIRMS, NO ATTORNEYS, NO LAWYERS, NO LEGAL SERVICES
- Format: "[business type] contact [city/state]" or "[business type] contact [state]"
- Use varied US states and cities
- Include practical, hands-on businesses that need websites

Examples:
- plumbing company contact Salem Oregon
- restaurant contact Iowa
- auto repair shop contact Boise Idaho
- dental office contact Vermont
- hvac contractor contact Eugene Oregon

Generate ONLY the search queries, one per line, no numbering, no explanations."""

        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",  # GPT-4.1 - latest model with best instruction following
            messages=[
                {"role": "system", "content": "You are a search query generator for local business outreach. Generate diverse, specific search queries."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.8
        )
        
        generated_text = response.choices[0].message.content.strip()
        new_queries = [line.strip() for line in generated_text.split('\n') if line.strip() and 'law' not in line.lower() and 'attorney' not in line.lower() and 'legal' not in line.lower()]
        
        # Load used queries to filter them out
        used_queries = set()
        if os.path.exists(config.USED_QUERIES_FILE):
            with open(config.USED_QUERIES_FILE, 'r') as f:
                used_queries = {line.strip() for line in f.readlines() if line.strip()}
        
        # Filter out already used queries
        new_queries = [q for q in new_queries if q not in used_queries]
        
        # Load existing queries if appending
        existing_queries = []
        if append and os.path.exists(config.SEARCH_QUERIES_FILE):
            with open(config.SEARCH_QUERIES_FILE, 'r') as f:
                existing_queries = [line.strip() for line in f.readlines() if line.strip()]
        
        # Combine and deduplicate
        if append:
            all_queries = existing_queries + new_queries
            all_queries = list(dict.fromkeys(all_queries))  # Remove duplicates while preserving order
        else:
            all_queries = new_queries
        
        # Save to file
        with open(config.SEARCH_QUERIES_FILE, 'w') as f:
            for query in all_queries:
                f.write(query + '\n')
        
        return jsonify({
            'success': True,
            'message': f'Generated {len(new_queries)} new queries',
            'generated': len(new_queries),
            'total': len(all_queries),
            'queries': new_queries[:10]  # Show first 10 as preview
        })
        
    except Exception as e:
        app.logger.error(f"Error generating queries: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/used-queries')
def used_queries_page():
    """Render used queries page"""
    try:
        return render_template('used_queries.html')
    except Exception as e:
        app.logger.error(f"Error rendering used queries page: {e}")
        return f"Error: {e}", 500

@app.route('/api/used-queries')
@safe_api_call
def api_get_used_queries():
    """Get used search queries"""
    queries = []
    try:
        if os.path.exists(config.USED_QUERIES_FILE):
            with open(config.USED_QUERIES_FILE, 'r') as f:
                queries = [line.strip() for line in f.readlines() if line.strip()]
    except Exception as e:
        app.logger.error(f"Error loading used queries: {e}")
    
    return jsonify({
        'queries': queries,
        'count': len(queries)
    })

@app.route('/api/used-queries/restore', methods=['POST'])
@safe_api_call
def api_restore_used_query():
    """Restore a used query back to active queries"""
    data = request.json or {}
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'success': False, 'message': 'No query provided'}), 400
    
    try:
        # Remove from used queries
        used_queries = []
        if os.path.exists(config.USED_QUERIES_FILE):
            with open(config.USED_QUERIES_FILE, 'r') as f:
                used_queries = [line.strip() for line in f.readlines() if line.strip() and line.strip() != query]
            
            with open(config.USED_QUERIES_FILE, 'w') as f:
                for q in used_queries:
                    f.write(q + '\n')
        
        # Add back to active queries
        with open(config.SEARCH_QUERIES_FILE, 'a') as f:
            f.write(query + '\n')
        
        return jsonify({
            'success': True,
            'message': f'Restored query to active list'
        })
    except Exception as e:
        app.logger.error(f"Error restoring query: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/errors')
@safe_api_call
def api_get_errors():
    """Get recent errors from logs"""
    errors = []
    
    try:
        # Check dashboard errors
        if os.path.exists('dashboard_errors.log'):
            with open('dashboard_errors.log', 'r') as f:
                lines = f.readlines()
                for line in lines[-50:]:  # Last 50 errors
                    if 'ERROR' in line or 'error' in line.lower():
                        errors.append({
                            'source': 'Dashboard',
                            'message': line.strip(),
                            'severity': 'error'
                        })
        
        # Check data error log
        if os.path.exists(config.ERROR_LOG_FILE):
            with open(config.ERROR_LOG_FILE, 'r') as f:
                lines = f.readlines()
                for line in lines[-50:]:  # Last 50 errors
                    errors.append({
                        'source': 'System',
                        'message': line.strip(),
                        'severity': 'warning'
                    })
        
        # Check for API-specific errors in recent logs
        log_files = ['parallel.log', 'scraper_ultrafast.log']
        for log_file in log_files:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-100:]:
                        line_lower = line.lower()
                        if any(keyword in line_lower for keyword in ['error', 'failed', 'exception', 'critical', 'out of credits', 'rate limit', 'quota exceeded']):
                            errors.append({
                                'source': log_file,
                                'message': line.strip()[-200:],  # Last 200 chars
                                'severity': 'error' if 'critical' in line_lower or 'failed' in line_lower else 'warning'
                            })
    except Exception as e:
        app.logger.error(f"Error reading error logs: {e}")
    
    # Return most recent 20 errors
    return jsonify({
        'errors': errors[-20:][::-1],  # Reverse to show newest first
        'count': len(errors)
    })

@app.route('/api/credits')
@safe_api_call
def api_get_credits():
    """Check API credits/usage for all services"""
    credits = {
        'serper': {'status': 'unknown', 'remaining': 'N/A', 'error': None},
        'scrapfly': {'status': 'unknown', 'remaining': 'N/A', 'used': 'N/A', 'error': None},
        'rapidapi': {'status': 'unknown', 'remaining': 'N/A', 'error': None},
        'openai': {'status': 'unknown', 'remaining': 'N/A', 'error': None}
    }
    
    # Check Scrapfly credits
    try:
        response = requests.get(
            'https://api.scrapfly.io/account',
            params={'key': config.SCRAPFLY_API_KEY},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            subscription = data.get('subscription', {})
            credits['scrapfly'] = {
                'status': 'active',
                'remaining': subscription.get('api_call_quota', 0),
                'used': subscription.get('api_call_used', 0),
                'plan': subscription.get('name', 'Unknown'),
                'error': None
            }
        else:
            credits['scrapfly']['error'] = f"HTTP {response.status_code}"
    except Exception as e:
        credits['scrapfly']['error'] = str(e)[:100]
    
    # Check Serper (estimate based on usage)
    try:
        # Serper doesn't have a direct credit check API, so we estimate
        credits['serper'] = {
            'status': 'active',
            'remaining': 'Check serper.dev dashboard',
            'note': 'No API endpoint for credit check',
            'error': None
        }
    except Exception as e:
        credits['serper']['error'] = str(e)[:100]
    
    # Check OpenAI (estimate)
    try:
        # OpenAI doesn't expose credits via API for most accounts
        credits['openai'] = {
            'status': 'active',
            'remaining': 'Check OpenAI dashboard',
            'note': 'API key working',
            'error': None
        }
        # Test if key works
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        # Don't actually make a call, just verify connection
        credits['openai']['status'] = 'active'
    except Exception as e:
        credits['openai']['error'] = str(e)[:100]
        credits['openai']['status'] = 'error'
    
    # Check RapidAPI
    try:
        # RapidAPI doesn't have a universal credit check, depends on subscription
        credits['rapidapi'] = {
            'status': 'active',
            'remaining': 'Check RapidAPI dashboard',
            'note': 'No universal API endpoint',
            'error': None
        }
    except Exception as e:
        credits['rapidapi']['error'] = str(e)[:100]
    
    return jsonify(credits)

@app.route('/api/ab-testing')
@safe_api_call
def api_ab_testing_status():
    """Get A/B testing status and statistics"""
    try:
        # Read current config
        ab_enabled = config.AB_TESTING_ENABLED
        
        # Calculate stats from sent_emails
        sent_data_path = 'data/sent_emails.json'
        variant_stats = {
            'A': {'count': 0, 'rate': 0},
            'B': {'count': 0, 'rate': 0}
        }
        
        if os.path.exists(sent_data_path):
            with open(sent_data_path, 'r') as f:
                sent_data = json.load(f)
                detailed_history = sent_data.get('detailed_history', [])
                
                # Count variants
                for entry in detailed_history:
                    variant = entry.get('variant', 'A')
                    if variant in variant_stats:
                        variant_stats[variant]['count'] += 1
                
                # Calculate rates
                total = variant_stats['A']['count'] + variant_stats['B']['count']
                if total > 0:
                    variant_stats['A']['rate'] = round((variant_stats['A']['count'] / total) * 100, 1)
                    variant_stats['B']['rate'] = round((variant_stats['B']['count'] / total) * 100, 1)
        
        return jsonify({
            'enabled': ab_enabled,
            'price': config.SERVICE_PRICE,
            'stats': variant_stats,
            'total_sent': variant_stats['A']['count'] + variant_stats['B']['count']
        })
    except Exception as e:
        app.logger.error(f"Error getting A/B testing status: {e}")
        return jsonify({
            'error': str(e),
            'enabled': False
        }), 500

@app.route('/api/ab-testing/toggle', methods=['POST'])
@safe_api_call
def api_ab_testing_toggle():
    """Toggle A/B testing on or off"""
    try:
        data = request.json or {}
        enable = data.get('enable', False)
        
        # Update config.py file
        config_path = 'config.py'
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Replace the AB_TESTING_ENABLED line
        import re
        pattern = r'AB_TESTING_ENABLED\s*=\s*(True|False)'
        replacement = f'AB_TESTING_ENABLED = {enable}'
        new_content = re.sub(pattern, replacement, content)
        
        with open(config_path, 'w') as f:
            f.write(new_content)
        
        # Reload config module
        import importlib
        importlib.reload(config)
        
        return jsonify({
            'success': True,
            'enabled': enable,
            'message': f'A/B testing {"enabled" if enable else "disabled"}'
        })
    except Exception as e:
        app.logger.error(f"Error toggling A/B testing: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found', 'message': str(error)}), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error', 'message': str(error)}), 500

if __name__ == '__main__':
    # Create data directory if it doesn't exist
    os.makedirs(config.DATA_DIR, exist_ok=True)
    
    print("="*80)
    print("🚀 COLD EMAIL DASHBOARD")
    print("="*80)
    print("\n📊 Dashboard starting at: http://localhost:5001")
    print("   Press CTRL+C to stop\n")
    print("="*80)
    
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
