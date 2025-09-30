# Cold Email Tool - LeSavoir.Agency

A comprehensive cold emailing tool that scrapes company information, analyzes website performance, and sends hyper-personalized emails using AI.

## Features

- **Company Scraper**: Uses Serper.dev API to find companies and their websites
- **Website Content Extraction**: Uses Scrapfly API to extract clean website content (no scripts/styles)
- **Speed Test Analysis**: Uses RapidAPI Website Speed Test to analyze website performance
- **AI-Powered Personalization**: Uses OpenAI GPT-4 to craft hyper-personalized emails
- **Email Tracking**: Prevents duplicate emails by tracking sent addresses
- **SMTP Integration**: Sends emails via Namecheap Private Email
- **Robust Error Handling**: Comprehensive logging and error recovery
- **Configurable Settings**: Adjustable email limits and delays

## Installation

1. **Install Python 3.8 or higher**

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configuration**:

Copy the `.env.example` file to `.env` and add your API keys:

```bash
cp .env.example .env
```

Then edit `.env` with your actual credentials:
- `SERPER_API_KEY`: Your Serper.dev API key
- `SCRAPFLY_API_KEY`: Your Scrapfly API key
- `RAPIDAPI_KEY`: Your RapidAPI key
- `OPENAI_API_KEY`: Your OpenAI API key
- `SMTP_USERNAME`: Your email address
- `SMTP_PASSWORD`: Your email password
- `FROM_EMAIL`: Your from email address

Additional settings can be modified in `config.py`:
- Search queries
- Email limits
- Delays between emails
- File paths

## Usage

### Option 1: Interactive Mode (Recommended)

Run the main script for an interactive menu:

```bash
python main.py
```

You'll see a menu with options:
1. Run Scraper (collect company data)
2. Run Email Sender (send emails to scraped companies)
3. Run Full Workflow (scrape then email)
4. Show Statistics
5. Exit

### Option 2: Standalone Scraper

Run the scraper independently to collect company data:

```bash
python scraper.py
```

This will:
- Search for companies using Serper.dev
- Extract website content with Scrapfly
- Perform speed tests on each website
- Save data to `data/scraped_companies.json`

### Option 3: Standalone Email Sender

Send emails to previously scraped companies:

```bash
python emailer.py
```

This will:
- Load scraped company data
- Generate personalized emails using OpenAI
- Send emails via SMTP
- Track sent emails to avoid duplicates

## Directory Structure

```
cold_email/
├── main.py                 # Main orchestration script
├── scraper.py             # Company scraper module
├── emailer.py             # Email sender module
├── config.py              # Configuration and API keys
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── data/                 # Data directory (created automatically)
│   ├── scraped_companies.json    # Scraped company data
│   ├── sent_emails.json          # Tracking sent emails
│   └── error_log.txt             # Error logs
└── .gitignore            # Git ignore file
```

## Configuration

### Email Settings

Current settings (can be modified in `config.py`):
- **Max emails per run**: 50
- **Delay between emails**: 20 seconds
- **Subject template**: "Critical Performance Issue Detected on {company_name}'s Website"

### API Keys (Required)

You need to obtain and configure these API keys in your `.env` file:

- **Serper.dev**: For company search - Get key at https://serper.dev
- **Scrapfly**: For website scraping - Get key at https://scrapfly.io
- **RapidAPI**: For speed testing - Get key at https://rapidapi.com
- **OpenAI**: For email personalization - Get key at https://platform.openai.com

### SMTP Settings (Configurable)

Configure in your `.env` file:
- **Host**: Your SMTP host (default: mail.privateemail.com)
- **Port**: SMTP port (default: 587)
- **Username**: Your email address
- **Password**: Your email password
- **From Email**: Sender email address

## How It Works

### Scraper Process

1. **Search**: Uses Serper.dev to search for companies based on your query
2. **Extract**: Scrapes each company's website using Scrapfly
3. **Analyze**: Performs speed test on each website
4. **Save**: Stores all data in JSON format

### Email Process

1. **Load**: Reads scraped company data
2. **Filter**: Excludes already-contacted companies
3. **Generate**: Creates personalized email using GPT-4 based on:
   - Company name and website
   - Speed test results
   - Website content analysis
4. **Send**: Delivers email via SMTP
5. **Track**: Records sent email to prevent duplicates

### Email Content

Each email includes:
- Attention-grabbing subject about website issues
- Specific speed test metrics
- Analysis of business impact (SEO, PPC, bounce rates)
- Reference to their actual website content
- Clear call-to-action
- Professional signature

## Data Management

### Preventing Duplicates

The tool maintains `data/sent_emails.json` to track:
- List of all sent email addresses
- Detailed history with timestamps
- Company information

Before sending, it checks this list and skips already-contacted addresses.

### Data Files

- **scraped_companies.json**: All scraped company data
- **sent_emails.json**: Email tracking and history
- **error_log.txt**: Error logs with timestamps

## Error Handling

The tool includes robust error handling:
- API request failures are logged
- Failed scrapes are marked but don't stop the process
- Failed emails are logged and counted
- Progress is saved periodically during scraping
- All errors are logged to `data/error_log.txt`

## Tips for Best Results

1. **Start Small**: Test with a few emails first (5-10) to verify everything works
2. **Check Data**: After scraping, review `data/scraped_companies.json` to ensure quality
3. **Monitor Logs**: Check `data/error_log.txt` if you encounter issues
4. **Respect Limits**: Keep delays between emails to avoid being flagged as spam
5. **Customize Queries**: Modify search queries in `config.py` for better targeting

## Compliance Note

This tool is for legitimate business outreach. Ensure you:
- Comply with CAN-SPAM Act and GDPR
- Include unsubscribe options if sending at scale
- Respect recipient preferences
- Follow email marketing best practices

## Troubleshooting

### No Companies Found
- Check your search query
- Verify Serper.dev API key is valid
- Try different search terms

### Scraping Failures
- Some websites may block scraping
- Check Scrapfly API credits
- Verify URLs are accessible

### Email Sending Failures
- Verify SMTP credentials
- Check internet connection
- Ensure recipient emails are valid
- Check if SMTP server is rate-limiting

### API Errors
- Verify all API keys are correct
- Check API rate limits
- Ensure you have sufficient API credits

## Support

For issues or questions:
- Check error logs in `data/error_log.txt`
- Review API documentation for rate limits
- Contact: contact@lesavoir.agency

## License

Proprietary - LeSavoir.Agency

---

**Built with ❤️ by LeSavoir.Agency**

