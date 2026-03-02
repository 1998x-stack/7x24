#!/usr/bin/env python3
"""
Analysis of Sina 7x24 Financial News Page
This script analyzes the structure and API endpoints of the Sina 7x24 financial news page.
"""

import re
import json
from urllib.parse import urlparse

def extract_categories_from_html(html_content):
    """Extract news categories from the HTML"""
    # Look for the feedData array in the JavaScript
    categories_pattern = r'var feedData = (\[[^\]]*\]);'
    match = re.search(categories_pattern, html_content, re.DOTALL)
    
    if match:
        # Extract the JSON-like array string
        array_str = match.group(1)
        # Replace single quotes with double quotes for valid JSON
        array_str = array_str.replace("'", '"')
        try:
            categories = json.loads(array_str)
            return categories
        except json.JSONDecodeError:
            # If direct parsing fails, try to parse manually
            category_list = []
            # Look for objects in the form {"title": "...", "tag": "..."}
            obj_pattern = r'{\s*"title"\s*:\s*"([^"]+)"\s*,\s*"tag"\s*:\s*"([^"]+)"\s*}'
            for obj_match in re.finditer(obj_pattern, array_str):
                title, tag = obj_match.groups()
                category_list.append({"title": title, "tag": tag})
            return category_list
    
    return []

def extract_api_endpoints_from_html(html_content):
    """Extract API endpoints from the HTML"""
    endpoints = {}
    
    # Look for API endpoint in the JavaScript configuration
    api_pattern = r'"list":\s*["\']([^"\']+)["\']'
    matches = re.findall(api_pattern, html_content)
    
    for match in matches:
        if 'api' in match.lower() or 'zhibo' in match.lower():
            endpoints['news_feed'] = match
    
    # Look for other potential API endpoints
    zhibo_pattern = r'https?://[^\s"\'<>]*zhibo[^\s"\'<>]*'
    zhibo_matches = re.findall(zhibo_pattern, html_content)
    
    for match in zhibo_matches:
        if 'api' in match:
            endpoints['zhibo_api'] = match
    
    # Look for sys_time endpoint
    time_pattern = r'src=["\']([^"\']*sys_time[^\s"\'<>]*)["\']'
    time_matches = re.findall(time_pattern, html_content)
    if time_matches:
        endpoints['time_endpoint'] = time_matches[0]
    
    # Look for config endpoint
    config_pattern = r'src=["\']([^"\']*PCHomeConfig[^\s"\'<>]*)["\']'
    config_matches = re.findall(config_pattern, html_content)
    if config_matches:
        endpoints['config_endpoint'] = config_matches[0]
    
    return endpoints

def extract_auto_refresh_settings(html_content):
    """Extract auto-refresh settings from the HTML"""
    settings = {}
    
    # Look for autorefresh checkbox and settings
    autorefresh_pattern = r'<input[^>]*type="checkbox"[^>]*id="autorefresh"[^>]*>'
    if re.search(autorefresh_pattern, html_content):
        settings['has_autorefresh'] = True
    
    # Look for refresh interval (60 seconds mentioned in the HTML)
    refresh_interval_pattern = r'autorefreshsecs[^>]*>(\d+)<'
    interval_match = re.search(refresh_interval_pattern, html_content)
    if interval_match:
        settings['refresh_interval_seconds'] = int(interval_match.group(1))
    
    return settings

def main():
    # Since we don't have the actual HTML file, I'll create a sample based on the patterns I identified
    print("Sina 7x24 Financial News Page Analysis")
    print("=" * 50)
    
    # Simulated extraction based on the HTML patterns
    print("\n1. News Categories Available:")
    categories = [
        {"title": "全部", "tag": "0"},
        {"title": "A股", "tag": "10"},
        {"title": "宏观", "tag": "1"},
        {"title": "产业", "tag": "110"},
        {"title": "公司", "tag": "3"},
        {"title": "数据", "tag": "4"},
        {"title": "市场", "tag": "5"},
        {"title": "国际", "tag": "102"},
        {"title": "观点", "tag": "6"},
        {"title": "央行", "tag": "7"},
        {"title": "其他", "tag": "8"}
    ]
    
    for cat in categories:
        print(f"  - {cat['title']}: tag={cat['tag']}")
    
    print("\n2. API Endpoints Identified:")
    endpoints = {
        "news_feed": "//zhibo.sina.com.cn/api/zhibo/feed",
        "time_endpoint": "https://hq.sinajs.cn/?format=json&list=sys_time",
        "config_endpoint": "https://finance.sina.com.cn/7x24/PCHomeConfig.js"
    }
    
    for name, endpoint in endpoints.items():
        print(f"  - {name}: {endpoint}")
    
    print("\n3. Auto-refresh Settings:")
    refresh_settings = {
        "has_autorefresh": True,
        "refresh_interval_seconds": 60
    }
    
    print(f"  - Auto-refresh enabled: {refresh_settings['has_autorefresh']}")
    print(f"  - Refresh interval: {refresh_settings['refresh_interval_seconds']} seconds")
    
    print("\n4. News Feed API Parameters:")
    print("  - Parameters likely include:")
    print("    * zhibo_id: ID of the live broadcast")
    print("    * tag: News category tag (from categories above)")
    print("    * pagesize: Number of items to return")
    print("    * dire: Direction (f for forward, b for backward)")
    print("    * dpc: Device parameter")
    
    print("\n5. Key Elements for Automation:")
    print("  - Main container: #liveList01")
    print("  - News items: .bd_i elements")
    print("  - Timestamp: .bd_i_time_c elements")
    print("  - Content: .bd_i_txt_c elements")
    print("  - Auto-refresh checkbox: #autorefresh")
    print("  - Refresh button: .btn_refresh")

if __name__ == "__main__":
    main()