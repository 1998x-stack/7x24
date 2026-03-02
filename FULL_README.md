# Sina 7x24 Financial News Collector

Complete solution for automated collection of financial news from Sina's 7x24 live news feed with GitHub Actions deployment and email notifications.

## 🚀 Features

- **Automated Collection**: Scrape financial news from all categories using Playwright
- **Multi-Categories**: Support for all 10 news categories (A股, 宏观, 公司, 数据, 市场, 国际, 观点, 央行, 其他, 全部)
- **Email Notifications**: Send collected news via email with rich HTML formatting
- **GitHub Actions**: Scheduled execution with configurable intervals
- **JSON Export**: Structured data export for further processing
- **Respectful Scraping**: Implements rate limiting and ethical scraping practices

## 📁 Project Structure

```
├── sina_7x24_collector.py      # Main Playwright automation script
├── run_examples.py             # Example runner script
├── email_notification_example.py # Email notification example
├── analyze_sina_structure.py   # Analysis of Sina 7x24 structure
├── requirements.txt            # Python dependencies
├── build.sh                   # Build automation script
├── setup.sh                   # Setup script
├── AUTOMATION_GUIDE.md        # Comprehensive setup guide
├── BUILD_SUMMARY.md           # Build results summary
├── README.md                  # This file
└── *.json                     # Generated JSON examples
```

## 🛠️ Setup and Installation

### Prerequisites
- Python 3.8+
- Playwright: `pip install playwright`
- Chromium browser: `playwright install chromium`

### Quick Setup
```bash
# Clone the repository
git clone <your-repo-url>

# Run setup script
chmod +x setup.sh
./setup.sh

# Or install manually
pip install -r requirements.txt
playwright install chromium
```

## ▶️ Usage

### Local Execution
```bash
# Run the collector directly
python sina_7x24_collector.py

# Run examples to generate JSON files
python run_examples.py

# Run build process
chmod +x build.sh
./build.sh
```

### Environment Variables for Email
```bash
export SENDER_EMAIL="your-gmail@gmail.com"
export SENDER_PASSWORD="your-app-password"
export RECIPIENT_EMAIL="recipient@email.com"
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
```

## 📊 Data Structure

The collected data follows this JSON structure:

```json
{
  "全部": [
    {
      "id": "news_item_id",
      "time": "HH:MM:SS",
      "content": "Full news content text",
      "link": "https://link.to.full.article",
      "timestamp": "ISO 8601 timestamp"
    }
  ],
  "A股": [...],
  "宏观": [...],
  // ... other categories
}
```

## 🔄 GitHub Actions Deployment

### Workflow Configuration
Create `.github/workflows/sina-news-scraper.yml`:

```yaml
name: Sina 7x24 News Collector

on:
  schedule:
    # Run every 30 minutes
    - cron: '*/30 * * * *'
  workflow_dispatch: # Allow manual trigger

jobs:
  scrape-news:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        pip install playwright
        playwright install chromium

    - name: Run news collector
      env:
        SENDER_EMAIL: ${{ secrets.SENDER_EMAIL }}
        SENDER_PASSWORD: ${{ secrets.SENDER_PASSWORD }}
        RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
        SMTP_SERVER: ${{ secrets.SMTP_SERVER }}
        SMTP_PORT: ${{ secrets.SMTP_PORT }}
      run: |
        python sina_7x24_collector.py

    - name: Upload results
      uses: actions/upload-artifact@v3
      if: success()
      with:
        name: sina-news-results
        path: sina_7x24_news_*.json
```

### Required Repository Secrets
- `SENDER_EMAIL`: Your email address
- `SENDER_PASSWORD`: Your email app password
- `RECIPIENT_EMAIL`: Recipient email address  
- `SMTP_SERVER`: SMTP server (default: smtp.gmail.com)
- `SMTP_PORT`: SMTP port (default: 587)

## 📈 Generated Output

The system generates two types of JSON files:

### Full Data (`example_sina_7x24_news_*.json`)
Complete data with all fields including IDs, timestamps, and full content.

### Simplified Data (`simplified_example_*.json`)  
Streamlined format perfect for email notifications and quick viewing.

## 🔐 Email Configuration

### Gmail Setup
1. Enable 2-factor authentication
2. Generate an app password (not your regular password)
3. Configure the SMTP settings:
   - Server: `smtp.gmail.com`
   - Port: `587` (TLS) or `465` (SSL)
   - Encryption: TLS

## 🛡️ Ethical Scraping Practices

- ✅ Respects robots.txt guidelines
- ✅ Implements rate limiting (30+ second intervals)
- ✅ Uses realistic user agent strings
- ✅ Mimics human browsing behavior
- ✅ Handles errors gracefully
- ✅ Complies with terms of service

## 📋 Data Categories

| Category | Tag | Description |
|----------|-----|-------------|
| 全部 | 0 | All news combined |
| A股 | 10 | China A-share market |
| 宏观 | 1 | Macroeconomic news |
| 产业 | 110 | Industry developments |
| 公司 | 3 | Company news |
| 数据 | 4 | Financial data |
| 市场 | 5 | Market updates |
| 国际 | 102 | International news |
| 观点 | 6 | Market opinions |
| 央行 | 7 | Central bank news |
| 其他 | 8 | Other news |

## 🧪 Example Output

The system successfully collected 30 news items across 10 categories, including:
- International news about Iran conflict
- Market data on silver and gold prices  
- A-share market analysis
- Company earnings and updates
- Economic indicators and central bank policies

## 🚀 Deployment Options

### Option 1: GitHub Actions (Recommended)
Automatic scheduling with cloud execution and email notifications.

### Option 2: Local Cron Job
Schedule on your own server using cron or Task Scheduler.

### Option 3: Cloud Functions
Deploy to AWS Lambda, Google Cloud Functions, or Azure Functions.

## 🔧 Customization

### Change Collection Frequency
Modify the GitHub Actions cron schedule or local cron job.

### Adjust News Volume
Change `MAX_ITEMS_PER_CATEGORY` in the configuration.

### Filter Categories
Modify the category filtering logic to focus on specific news types.

## 📊 Monitoring

- GitHub Actions provides execution logs
- JSON artifacts stored for review
- Email notifications for successful collections
- Error handling for failed attempts

## 📄 License and Legal

This tool is designed to scrape publicly available information only. Please ensure compliance with:

- Sina's Terms of Service
- Applicable data protection regulations (GDPR, CCPA)
- Local laws regarding web scraping
- Robots.txt guidelines

Use responsibly and avoid excessive requests that could impact the service for other users.

## 🤝 Contributing

Feel free to submit issues and enhancement requests. Contributions to improve the scraping logic, add new features, or enhance error handling are welcome.

## 🆘 Support

For issues with the code:
1. Check the troubleshooting section
2. Review GitHub Actions logs
3. Verify your environment variables
4. Ensure Playwright dependencies are installed