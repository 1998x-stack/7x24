#!/bin/bash
# Background run script for Industrial Sina 7x24 News Collector

set -e  # Exit on any error

echo "==========================================="
echo "Industrial Sina 7x24 News Collector"
echo "Background Run Script"
echo "==========================================="

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found. Run build script first."
    exit 1
fi

# Source environment variables
source .env

# Create logs directory if it doesn't exist
mkdir -p logs

echo "Starting Industrial Sina 7x24 News Collector in background mode..."
echo "Log file: logs/application.log"

# Determine the mode from command line argument or use default
MODE=${1:-continuous}
CATEGORY=${2:-"全部"}
COUNT=${3:-20}
INTERVAL=${4:-30}

echo "Parameters:"
echo "  Mode: $MODE"
echo "  Category: $CATEGORY" 
echo "  Count: $COUNT"
echo "  Interval: $INTERVAL minutes"

# Run the application in background
nohup python -u -m src.main --mode "$MODE" --category "$CATEGORY" --count "$COUNT" --interval "$INTERVAL" > logs/application.log 2>&1 &

# Get the PID of the background process
PID=$!
echo "Process started with PID: $PID"

# Save PID to file for later management
echo $PID > sina_collector.pid

echo ""
echo "==========================================="
echo "Industrial Sina 7x24 News Collector started in background!"
echo "==========================================="
echo ""
echo "Status Information:"
echo "- Process ID: $PID (saved to sina_collector.pid)"
echo "- Log file: logs/application.log"
echo "- Data directory: $DATA_DIR (from .env)"
echo "- Reports directory: $REPORT_OUTPUT_DIR (from .env)"
echo ""
echo "Management Commands:"
echo "- Check status:   ps aux | grep src.main"
echo "- View logs:      tail -f logs/application.log"
echo "- Stop process:   kill \$(cat sina_collector.pid)"
echo "- Restart:        ./restart.sh"
echo ""
echo "Note: The process is running in the background."
echo "Monitor the logs to verify it's working correctly."
echo "==========================================="