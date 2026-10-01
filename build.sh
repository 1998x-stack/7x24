#!/bin/bash
# Build script for Industrial Sina 7x24 News Collector

set -e  # Exit on any error

echo "==========================================="
echo "Industrial Sina 7x24 News Collector"
echo "Build & Setup Script"
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
pip install -r requirements.txt

echo "Step 2: Setting up directories..."
mkdir -p data reports logs templates

echo "Step 3: Creating configuration file..."
if [ ! -f ".env" ]; then
    echo "Creating .env file from example..."
    cat > .env << EOF
# Sina API Configuration
SINA_BASE_URL=https://zhibo.sina.com.cn/api
SINA_ZHIBO_ID=152
SINA_DELAY=0.5
SINA_TIMEOUT=15

# OpenAI Configuration (required for AI features)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4-turbo

# Neo4j Configuration (optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Request Configuration
REQUEST_TIMEOUT=30
REQUEST_DELAY=1.0
MAX_RETRIES=3

# Directory Configuration
DATA_DIR=./data
REPORT_OUTPUT_DIR=./reports
LOG_DIR=./logs

# Schedule Configuration
COLLECTION_INTERVAL_MINUTES=30
DAILY_REPORT_HOUR=8

# Logging Configuration
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=30
EOF
    echo "  ⚠️  IMPORTANT: Edit .env with your actual API keys!"
fi

echo "Step 4: Creating templates directory..."
cat > templates/daily_report.md << EOF
# 每日金融新闻分析报告

**报告时间**: \{\{datetime.now()\}\}

**统计时段**: \{\{period_start}\} - \{\{period_end}\}

---

\{\{executive_summary}\}

---

\{\{topic_breakdown}\}

---

\{\{significant_events}\}

---

\{\{risk_opportunity_analysis}\}

---

**数据来源**: 新浪7x24财经资讯
**分析时间**: \{\{datetime.now()\}\}
EOF

echo "Step 5: Testing basic functionality..."
# We'll skip the complex Python test for now to avoid shell parsing issues
python -c "
import sys
sys.path.insert(0, '.')

try:
    from src.interfaces import NewsItem
    print('✓ Interfaces module loaded successfully')
    
    from src.config.settings import settings
    print('✓ Configuration module loaded successfully')
    
    print('✓ Build completed successfully!')
    print('')
    print('Next steps:')
    print('- Edit .env with your API keys')
    print('- Run: python -m src.main --help for usage options')
    print('- Run: python -m src.main --mode single for a test run')
    
except ImportError as e:
    print(f'✗ Build failed: {e}')
    sys.exit(1)
"
python -c "
import sys
sys.path.insert(0, '.')

try:
    from src.interfaces import NewsItem
    print('✓ Interfaces module loaded successfully')
    
    from src.config.settings import settings
    print('✓ Configuration module loaded successfully')
    
    print('✓ Build completed successfully!')
    print('')
    echo 'Next steps:'
    echo '- Edit .env with your API keys'
    echo '- Run: python -m src.main --help for usage options'
    echo '- Run: python -m src.main --mode single for a test run'
    
except ImportError as e:
    echo '✗ Build failed: $e'
    exit 1
"

echo ""
echo "==========================================="
echo "Build completed successfully!"
echo "==========================================="
echo ""
echo "Next steps:"
echo "1. Configure your environment:"
echo "   - Edit .env with your OpenAI API key"
echo "   - Set other configuration as needed"
echo ""
echo "2. Run a test collection:"
echo "   python -m src.main --mode single --category A股 --count 10"
echo ""
echo "3. Run in continuous mode:"
echo "   python -m src.main --mode continuous --interval 30"
echo ""
echo "4. Run daily report mode:"
echo "   python -m src.main --mode daily-report --report-hour 8"
echo ""
echo "5. Check output in:"
echo "   - data/ : Raw news data"
echo "   - reports/ : Generated reports" 
echo "   - logs/ : Application logs"
echo "==========================================="