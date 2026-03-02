#!/usr/bin/env python3
"""
Example runner for Sina 7x24 Financial News Collector
This script demonstrates the functionality and generates JSON output files
"""

import subprocess
import sys
import os
from datetime import datetime

def run_example_scripts():
    """Run example scripts to generate JSON output"""
    print("Running Sina 7x24 Financial News Collector examples...")
    
    # Make sure we have the required dependencies
    try:
        import playwright
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Installing required dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    
    # Import our collector
    try:
        from sina_7x24_collector import Sina7x24Collector
        
        # Create collector instance (with headless mode for examples)
        collector = Sina7x24Collector(headless=True, slow_mo=0)
        
        print("Starting collection example...")
        
        try:
            # Launch browser
            collector.launch_browser()
            
            # Navigate to the page
            collector.navigate_to_page()
            
            # Disable auto-refresh to prevent interference
            collector.enable_disable_auto_refresh(enable=False)
            
            # Collect a small sample of news (limiting to 3 per category for example)
            print("Collecting sample news data...")
            all_news = collector.collect_news_by_categories(max_items_per_category=3)
            
            # Print summary
            print("\n" + "="*60)
            print("SINA 7x24 NEWS COLLECTION EXAMPLE")
            print("="*60)
            
            total_items = 0
            for category, items in all_news.items():
                print(f"\n{category}: {len(items)} items")
                total_items += len(items)
                
                # Print first few items for each category
                for i, item in enumerate(items):
                    print(f"  {i+1}. [{item['time']}] {item['content'][:100]}...")
            
            print(f"\nTOTAL: {total_items} news items collected from {len(all_news)} categories")
            
            # Save to example JSON file
            filename = f"example_sina_7x24_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            import json
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(all_news, f, ensure_ascii=False, indent=2)
            
            print(f"\nExample data saved to: {filename}")
            
            # Also save a simplified version for easy viewing
            simplified_filename = f"simplified_example_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            simplified_data = {}
            for category, items in all_news.items():
                simplified_data[category] = [
                    {
                        "time": item["time"],
                        "content": item["content"][:200] + "..." if len(item["content"]) > 200 else item["content"],
                        "link_preview": item["link"]
                    }
                    for item in items
                ]
            
            with open(simplified_filename, 'w', encoding='utf-8') as f:
                json.dump(simplified_data, f, ensure_ascii=False, indent=2)
            
            print(f"Simplified example data saved to: {simplified_filename}")
            
        except Exception as e:
            print(f"Error during collection: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            if hasattr(collector, 'close'):
                collector.close()
    
    except ImportError as e:
        print(f"Could not import collector: {e}")
        print("Please make sure sina_7x24_collector.py exists and dependencies are installed")
        return False
    
    return True

def run_examples():
    """Main function to run all examples"""
    print("Running Sina 7x24 Financial News Collector Examples")
    print("=" * 50)
    
    success = run_example_scripts()
    
    if success:
        print("\n✓ Examples completed successfully!")
        print("Generated JSON files:")
        import glob
        json_files = glob.glob("example_sina_7x24_news_*.json") + glob.glob("simplified_example_*.json")
        for file in sorted(json_files, reverse=True)[:5]:  # Show last 5 files
            print(f"  - {file}")
    else:
        print("\n✗ Examples failed to run")
        return False
    
    return True

if __name__ == "__main__":
    run_examples()