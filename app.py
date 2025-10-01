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
from datetime import datetime, timedelta
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
