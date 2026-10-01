#!/bin/bash
# Restart script for Industrial Sina 7x24 News Collector

set -e  # Exit on any error

echo "==========================================="
echo "Industrial Sina 7x24 News Collector"
echo "Restart Script"
echo "==========================================="

if [ -f "sina_collector.pid" ]; then
    PID=$(cat sina_collector.pid)
    echo "Stopping existing process with PID: $PID"
    
    # Check if process is running
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo "Process $PID terminated"
    else
        echo "Process $PID not found, continuing..."
    fi
    
    # Remove PID file
    rm sina_collector.pid
else
    echo "No existing process found"
fi

echo "Starting new process..."
sleep 2

# Start the application again
./run_background.sh "$@"