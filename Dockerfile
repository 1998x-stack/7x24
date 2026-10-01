FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY enhanced_requirements.txt .
RUN pip install --no-cache-dir -r enhanced_requirements.txt

# Install playwright browsers
RUN playwright install chromium

# Copy the application code
COPY . .

# Create necessary directories
RUN mkdir -p daily_reports knowledge_graph_exports jsonl_data

# Expose any necessary ports (though this is primarily a background service)
EXPOSE 8000

# Set up environment
ENV PYTHONPATH=/app

# Run the application
CMD ["python", "main_app.py", "--mode", "scheduler"]