#!/usr/bin/env python3
"""
Playwright Automation Script for Sina 7x24 Financial News
This script automates the collection of financial news from Sina 7x24 page.
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from datetime import datetime
import json
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Sina7x24Collector:
    def __init__(self, headless: bool = True, slow_mo: int = 0):
        self.headless = headless
        self.slow_mo = slow_mo
        self.browser = None
        self.context = None
        self.page = None
        
    def launch_browser(self):
        """Launch the browser with appropriate settings"""
        logger.info("Launching browser...")
        playwright = sync_playwright().start()
        self.browser = playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor"
            ]
        )
        
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        
        self.page = self.context.new_page()
        logger.info("Browser launched successfully")
        
    def navigate_to_page(self):
        """Navigate to the Sina 7x24 page"""
        url = "https://finance.sina.com.cn/7x24/"
        logger.info(f"Navigating to {url}")
        
        try:
            self.page.goto(url, wait_until="networkidle", timeout=30000)
            logger.info("Page loaded successfully")
            
            # Wait for the main content to load
            self.page.wait_for_selector("#liveList01", timeout=10000)
            logger.info("Main content loaded")
            
        except PlaywrightTimeout:
            logger.warning("Page load timed out, but continuing...")
            
    def get_available_categories(self) -> List[Dict[str, str]]:
        """Get available news categories from the page"""
        logger.info("Getting available categories...")
        
        # Wait for categories to be loaded
        try:
            self.page.wait_for_selector(".bd_topic a", timeout=5000)
        except PlaywrightTimeout:
            logger.error("Could not find categories")
            return []
        
        # Extract category links using JavaScript
        categories_js = """
        Array.from(document.querySelectorAll('.bd_topic a')).map(el => ({
            title: el.textContent.trim(),
            tag: el.getAttribute('data-tag'),
            url: el.href
        }))
        """
        
        categories = self.page.evaluate(categories_js)
        logger.info(f"Found {len(categories)} categories")
        
        return categories
        
    def collect_news_items(self, max_items: int = 20) -> List[Dict]:
        """Collect news items from the current view"""
        logger.info(f"Collecting up to {max_items} news items...")
        
        # JavaScript to extract news items
        news_extraction_js = f"""
        const items = Array.from(document.querySelectorAll('#liveList01 .bd_i')).slice(0, {max_items}).map(item => {{
            const timeEl = item.querySelector('.bd_i_time_c');
            const contentEl = item.querySelector('.bd_i_txt_c a');
            const linkEl = item.querySelector('.bd_i_txt_c a');
            
            return {{
                id: item.getAttribute('data-id'),
                time: timeEl ? timeEl.textContent.trim() : '',
                content: contentEl ? contentEl.textContent.trim() : '',
                link: linkEl ? linkEl.href : '',
                timestamp: new Date().toISOString()
            }};
        }}).filter(item => item.content); // Only return items with content
        
        // Remove duplicates based on content
        const uniqueItems = [];
        const seenContents = new Set();
        for (const item of items) {{
            if (!seenContents.has(item.content)) {{
                seenContents.add(item.content);
                uniqueItems.push(item);
            }}
        }}
        
        uniqueItems;
        """
        
        news_items = self.page.evaluate(news_extraction_js)
        logger.info(f"Collected {len(news_items)} unique news items")
        
        return news_items
        
    def filter_by_category(self, tag: str):
        """Filter news by category using the tag"""
        logger.info(f"Filtering by category tag: {tag}")
        
        # Find the link for the specified tag
        selector = f".bd_topic a[data-tag='{tag}']"
        
        try:
            # Click the category link
            self.page.click(selector, timeout=5000)
            
            # Wait for content to reload
            self.page.wait_for_timeout(2000)  # Brief pause for content to load
            
            logger.info(f"Successfully filtered by category tag: {tag}")
        except PlaywrightTimeout:
            logger.error(f"Could not find category with tag: {tag}")
            
    def enable_disable_auto_refresh(self, enable: bool = False):
        """Enable or disable auto-refresh"""
        logger.info(f"Setting auto-refresh to: {enable}")
        
        try:
            # Find the auto-refresh checkbox
            checkbox = self.page.locator("#autorefresh")
            
            if enable:
                checkbox.check(timeout=3000)
            else:
                checkbox.uncheck(timeout=3000)
                
            logger.info(f"Auto-refresh {'enabled' if enable else 'disabled'}")
        except PlaywrightTimeout:
            logger.error("Could not control auto-refresh")
            
    def collect_news_by_categories(self, max_items_per_category: int = 10) -> Dict[str, List[Dict]]:
        """Collect news from all available categories"""
        logger.info("Starting collection from all categories...")
        
        all_news = {}
        
        # Get available categories
        categories = self.get_available_categories()
        
        if not categories:
            logger.error("No categories found, collecting from default view")
            all_news["全部"] = self.collect_news_items(max_items_per_category)
            return all_news
        
        # For each category, navigate and collect
        for category in categories:
            logger.info(f"Processing category: {category['title']}")
            
            # Navigate to category
            self.filter_by_category(category['tag'])
            
            # Wait a bit for content to load
            self.page.wait_for_timeout(2000)
            
            # Collect news items
            news_items = self.collect_news_items(max_items_per_category)
            all_news[category['title']] = news_items
            
            logger.info(f"Collected {len(news_items)} items from {category['title']}")
            
            # Return to "全部" category for next iteration
            if category['tag'] != '0':
                self.filter_by_category('0')
                self.page.wait_for_timeout(1000)
        
        return all_news
        
    def close(self):
        """Close the browser"""
        if self.browser:
            self.browser.close()
            logger.info("Browser closed")


def send_email_notification(data: Dict, smtp_server: str, smtp_port: int, sender_email: str, 
                           sender_password: str, recipient_email: str):
    """Send collected data via email"""
    logger.info("Preparing email notification...")
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"Sina 7x24 Financial News - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Create email body
        body = f"""
        Sina 7x24 Financial News Report
        
        Collection Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        """
        
        # Add news by category
        for category, items in data.items():
            body += f"\n=== {category} ({len(items)} items) ===\n"
            for i, item in enumerate(items[:5], 1):  # Show first 5 items per category
                body += f"{i}. [{item['time']}] {item['content'][:100]}...\n"
                body += f"   Link: {item['link']}\n\n"
        
        body += f"\nTotal categories processed: {len(data)}"
        body += f"\nTotal news items collected: {sum(len(items) for items in data.values())}"
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Connect to server and send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        logger.info("Email notification sent successfully")
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")


def main():
    """Main function to demonstrate the automation"""
    collector = Sina7x24Collector(headless=True, slow_mo=0)
    
    try:
        # Launch browser
        collector.launch_browser()
        
        # Navigate to the page
        collector.navigate_to_page()
        
        # Disable auto-refresh to prevent interference
        collector.enable_disable_auto_refresh(enable=False)
        
        # Collect news from all categories
        all_news = collector.collect_news_by_categories(max_items_per_category=10)
        
        # Print summary
        print("\n" + "="*60)
        print("SINA 7x24 NEWS COLLECTION SUMMARY")
        print("="*60)
        
        total_items = 0
        for category, items in all_news.items():
            print(f"\n{category}: {len(items)} items")
            total_items += len(items)
            
            # Print first 3 items for each category
            for i, item in enumerate(items[:3]):
                print(f"  {i+1}. [{item['time']}] {item['content'][:80]}...")
        
        print(f"\nTOTAL: {total_items} news items collected from {len(all_news)} categories")
        
        # Save to file
        filename = f"sina_7x24_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(all_news, f, ensure_ascii=False, indent=2)
        
        print(f"\nData saved to: {filename}")
        
        # Example of sending email (uncomment and configure to use)
        """
        # Email configuration (use environment variables for security)
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        sender_email = os.getenv('SENDER_EMAIL', '')
        sender_password = os.getenv('SENDER_PASSWORD', '')
        recipient_email = os.getenv('RECIPIENT_EMAIL', '')
        
        if sender_email and sender_password and recipient_email:
            send_email_notification(
                all_news, smtp_server, smtp_port, 
                sender_email, sender_password, recipient_email
            )
        """
        
    except Exception as e:
        logger.error(f"Error during collection: {str(e)}")
    finally:
        collector.close()


if __name__ == "__main__":
    main()