#!/bin/bash
# Build script for Sina 7x24 Financial News Collector
# This script runs examples and generates JSON output files

set -e  # Exit on any error

echo "==========================================="
echo "Sina 7x24 Financial News Collector - Build"
echo "==========================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
fi

# Check if pip is available
if ! command -v pip &> /dev/null; then
    echo "Error: pip is not installed"
    exit 1
fi

echo "Step 1: Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    pip install playwright
fi

echo "Step 2: Installing Playwright browsers..."
playwright install chromium

echo "Step 3: Running examples to generate JSON output..."
python3 run_examples.py

echo "Step 4: Validating generated JSON files..."
for json_file in example_sina_7x24_news_*.json simplified_example_*.json; do
    if [ -f "$json_file" ]; then
        echo "Validating: $json_file"
        python3 -m json.tool "$json_file" > /dev/null
        if [ $? -eq 0 ]; then
            echo "✓ $json_file is valid JSON"
            # Show brief summary
            news_count=$(python3 -c "
import json
with open('$json_file') as f:
    data = json.load(f)
    count = sum(len(items) for items in data.values() if isinstance(items, list))
    print(f'Total news items: {count}')
")
            echo "  $news_count"
        else
            echo "✗ $json_file is invalid JSON"
        fi
    fi
done

echo "Step 5: Displaying sample of generated data..."
echo ""
sample_file=$(ls -t simplified_example_*.json 2>/dev/null | head -n 1)
if [ -n "$sample_file" ]; then
    echo "Sample from $sample_file:"
    echo "----------------------------------------"
    python3 -c "
import json
with open('$sample_file') as f:
    data = json.load(f)
    
for category, items in list(data.items())[:3]:  # Show first 3 categories
    print(f'\\n{category}: ({len(items)} items)')
    for i, item in enumerate(items[:2]):  # Show first 2 items per category
        print(f'  {i+1}. [{item[\"time\"]}] {item[\"content\"][:80]}...')
"
else
    echo "No JSON files were generated"
fi

echo ""
echo "==========================================="
echo "Build completed successfully!"
echo "Generated JSON files are in the current directory"
echo "==========================================="