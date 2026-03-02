# Sina 7x24 Financial News Automation Guide

## 1. Page Analysis

### URL Structure
- Main Page: https://finance.sina.com.cn/7x24/
- Categories: https://finance.sina.com.cn/7x24/?tag={category_tag}

### Available Categories
- 全部 (All): tag=0
- A股 (A Shares): tag=10
- 宏观 (Macro): tag=1
- 产业 (Industry): tag=110
- 公司 (Company): tag=3
- 数据 (Data): tag=4
- 市场 (Market): tag=5
- 国际 (International): tag=102
- 观点 (Opinion): tag=6
- 央行 (Central Bank): tag=7
- 其他 (Other): tag=8

### API Endpoint
- News feed: //zhibo.sina.com.cn/api/zhibo/feed
- Parameters likely include: zhibo_id, tag, pagesize, dire, dpc

### Key Elements for Scraping
- Main container: #liveList01
- News items: .bd_i elements
- Timestamp: .bd_i_time_c elements
- Content: .bd_i_txt_c elements

## 2. Playwright Automation Script

See sina_7x24_collector.py for the complete implementation.

## 3. GitHub Actions Workflow

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
        pip install -r requirements.txt # if you have a requirements file

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

## 4. Environment Configuration

Create configuration files with proper error handling:

```python
# config.py
import os

class Config:
    # Email settings
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SENDER_EMAIL = os.getenv('SENDER_EMAIL', '')
    SENDER_PASSWORD = os.getenv('SENDER_PASSWORD', '')
    RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL', '')
    
    # Scraping settings
    SCRAPE_INTERVAL = int(os.getenv('SCRAPE_INTERVAL', '1800'))  # 30 minutes
    MAX_ITEMS_PER_CATEGORY = int(os.getenv('MAX_ITEMS_PER_CATEGORY', '10'))
    
    # Browser settings
    HEADLESS = os.getenv('HEADLESS', 'true').lower() == 'true'
    SLOW_MO = int(os.getenv('SLOW_MO', '0'))
    
    @classmethod
    def validate(cls):
        """Validate that required environment variables are set"""
        required = ['SENDER_EMAIL', 'SENDER_PASSWORD', 'RECIPIENT_EMAIL']
        for var in required:
            if not getattr(cls, var):
                raise ValueError(f"Missing required environment variable: {var}")
```

## 5. Google Email Integration

For Gmail integration, you'll need to:

1. Enable 2-factor authentication on your Google account
2. Generate an app password (not your regular password)
3. Set up the following secrets in GitHub:
   - SENDER_EMAIL: Your Gmail address
   - SENDER_PASSWORD: Your app password
   - RECIPIENT_EMAIL: Where you want to receive the news
   - SMTP_SERVER: smtp.gmail.com
   - SMTP_PORT: 587

## 6. Best Practices for Respectful Scraping

Based on the best practices research:

### Rate Limiting
- Space requests at least 30+ seconds apart
- Respect the site's natural refresh rate (60 seconds)
- Implement exponential backoff for retries
- Monitor for rate-limiting responses

### Anti-Detection Measures
- Use realistic user agent strings
- Add random delays between actions
- Mimic human-like browsing behavior
- Avoid making too many requests from the same IP

### Error Handling
- Implement robust exception handling
- Log errors appropriately
- Have fallback mechanisms
- Gracefully handle timeouts

## 7. Deployment Instructions

1. Fork this repository to your GitHub account
2. Add the required secrets to your repository settings:
   - Go to Settings → Secrets and variables → Actions
   - Add the five email-related secrets mentioned above
3. Enable workflows in your repository
4. The workflow will run automatically every 30 minutes or can be triggered manually

## 8. Monitoring and Maintenance

- Check the workflow logs regularly for failures
- Monitor email delivery to ensure notifications are working
- Update the scraping logic if the site structure changes
- Adjust frequency based on the site's tolerance and your needs

## 9. Legal Compliance

- Only scrape publicly available information
- Respect robots.txt directives
- Don't overload the server with requests
- Comply with applicable data protection laws
- Consider the site's terms of service

## 10. Alternative Approaches

If the site implements stronger anti-bot measures:

1. Consider using official APIs if available
2. Implement rotating proxy services
3. Use browser fingerprinting evasion techniques
4. Schedule less frequent scraping intervals
5. Cache results to minimize requests