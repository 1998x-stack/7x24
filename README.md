# Sina 7x24 Financial News Collector

This project automates the collection of financial news from Sina's 7x24 live news feed and sends email notifications with the latest updates.

## Features

- Automated collection of financial news from Sina 7x24
- Support for multiple news categories (A股, 宏观, 产业, 公司, 数据, 市场, 国际, 观点, 央行, 其他)
- Email notifications with collected news
- GitHub Actions integration for scheduled execution
- Respectful scraping practices to avoid overloading the source site

## Requirements

- Python 3.8+
- Playwright: `pip install playwright`
- Chromium browser: `playwright install chromium`

## Usage

### Local Execution

1. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

2. Set up environment variables:
```bash
export SENDER_EMAIL="your-email@gmail.com"
export SENDER_PASSWORD="your-app-password"
export RECIPIENT_EMAIL="recipient@email.com"
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
```

3. Run the collector:
```bash
python sina_7x24_collector.py
```

### GitHub Actions Deployment

1. Fork this repository
2. Add the following secrets to your repository:
   - `SENDER_EMAIL`: Your email address
   - `SENDER_PASSWORD`: Your email app password
   - `RECIPIENT_EMAIL`: Recipient email address
   - `SMTP_SERVER`: SMTP server (default: smtp.gmail.com)
   - `SMTP_PORT`: SMTP port (default: 587)
3. The workflow will run automatically every 30 minutes

## Configuration

The script can be configured using environment variables:

- `SCRAPE_INTERVAL`: Time between scrapes in seconds (default: 1800 for 30 minutes)
- `MAX_ITEMS_PER_CATEGORY`: Maximum items to collect per category (default: 10)
- `HEADLESS`: Whether to run browser in headless mode (default: true)
- `SLOW_MO`: Slow down operations by specified milliseconds (default: 0)

## Data Structure

The collected data is saved in JSON format with the following structure:

```json
{
  "全部": [
    {
      "id": "news_item_id",
      "time": "HH:MM",
      "content": "News content text",
      "link": "https://link.to.full.article",
      "timestamp": "ISO 8601 timestamp"
    }
  ],
  "A股": [...],
  "宏观": [...],
  ...
}
```

## Best Practices

- The script respects the site's 60-second refresh cycle
- Rate limiting is implemented to avoid overloading the server
- Data is deduplicated to avoid sending duplicate news
- Proper error handling ensures graceful degradation

## Legal Notice

This tool is designed to scrape publicly available information only. Please ensure compliance with:

- Sina's Terms of Service
- Applicable data protection regulations
- Local laws regarding web scraping
- Robots.txt guidelines

Use responsibly and avoid excessive requests that could impact the service for other users.

## Troubleshooting

- If emails are not sending, check your SMTP settings and app password
- If scraping fails, the site may have changed its structure - update selectors accordingly
- For GitHub Actions failures, check the workflow logs for specific error details