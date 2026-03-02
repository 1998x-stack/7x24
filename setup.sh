#!/bin/bash
# Setup script for Sina 7x24 Financial News Collector

echo "Setting up Sina 7x24 Financial News Collector..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

# Check if pip is installed
if ! command -v pip &> /dev/null; then
    echo "pip is not installed. Please install pip first."
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install chromium

# Check if the installation was successful
if python3 -c "import playwright" &> /dev/null; then
    echo "Dependencies installed successfully!"
else
    echo "Failed to install dependencies."
    exit 1
fi

echo ""
echo "Setup complete! To run the collector:"
echo "1. Set up your environment variables:"
echo "   export SENDER_EMAIL=\"your-email@gmail.com\""
echo "   export SENDER_PASSWORD=\"your-app-password\""
echo "   export RECIPIENT_EMAIL=\"recipient@email.com\""
echo "2. Run: python sina_7x24_collector.py"

echo ""
echo "For GitHub Actions deployment:"
echo "- Add the required secrets to your repository settings"
echo "- The workflow will run automatically every 30 minutes"