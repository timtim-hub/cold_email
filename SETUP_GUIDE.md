# Setup Guide - Cold Email Tool

## Quick Start

### 1. Install Dependencies

```bash
cd /Users/macbookpro13/cold_email
pip install -r requirements.txt
```

### 2. Configure Environment Variables

The `.env` file is already set up with your API keys. If you need to modify them:

```bash
nano .env
```

Current configuration:
- ✓ Serper.dev API Key
- ✓ Scrapfly API Key  
- ✓ RapidAPI Key
- ✓ OpenAI API Key
- ✓ SMTP Credentials (Namecheap Private Email)

### 3. Test the Setup

Run a quick test to verify all APIs are working:

```bash
# Test scraper (scrape just 5 companies)
python scraper.py
# When prompted: Enter 5 for number of results

# Check the output in data/scraped_companies.json
cat data/scraped_companies.json | python -m json.tool | head -50
```

### 4. Run Your First Campaign

#### Option A: Interactive Menu (Recommended)
```bash
python main.py
```

Follow the prompts:
1. Choose option 1 (Scraper) to collect companies
2. Choose option 2 (Email Sender) to send emails
3. Or choose option 3 to run both

#### Option B: Run Separately
```bash
# Step 1: Scrape companies
python scraper.py

# Step 2: Send emails
python emailer.py
```

## Configuration Recommendations

### For Testing
- Set max emails to 5-10
- Use delay of 30 seconds
- Test with a small search query

### For Production
- Max emails: 50 (as configured)
- Delay: 20 seconds (as configured)
- Use specific industry queries

## API Usage Limits

Be aware of your API limits:

1. **Serper.dev**: Check your plan limits
2. **Scrapfly**: Monitor your API credits
3. **RapidAPI**: Free tier has limits
4. **OpenAI**: Monitor token usage (GPT-4 is more expensive)

## Troubleshooting

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

### API Errors
- Check `.env` file has correct keys
- Verify API keys are active
- Check API rate limits

### SMTP Errors
- Verify SMTP credentials in `.env`
- Check if Namecheap allows SMTP access
- Test with a single email first

## File Structure

```
cold_email/
├── .env                    # Your API keys (gitignored)
├── .env.example           # Template for new setups
├── config.py              # Configuration loader
├── scraper.py             # Scraping module
├── emailer.py             # Email module
├── main.py                # Main orchestration
├── data/
│   ├── scraped_companies.json    # Scraped data
│   ├── sent_emails.json          # Email tracking
│   └── error_log.txt             # Error logs
└── README.md              # Full documentation
```

## Next Steps

1. **Test with small batch**: Start with 5-10 emails
2. **Review generated emails**: Check quality before scaling
3. **Monitor deliverability**: Watch for bounce rates
4. **Adjust search queries**: Target specific industries
5. **Scale gradually**: Increase volume after testing

## Support

- Documentation: See README.md
- Logs: Check data/error_log.txt
- GitHub: https://github.com/timtim-hub/cold_email

---

**Ready to go! 🚀**

Start with: `python main.py`

