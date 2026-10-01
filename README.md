# Industrial Sina 7x24 Financial News Collector

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![OpenAI](https://img.shields.io/badge/OpenAI-API-green.svg)](https://platform.openai.com/)

## 🚀 Advanced Financial News Intelligence Platform

Industrial-grade system for collecting, processing, analyzing, and reporting financial news from Sina 7x24 API. Features include AI-powered sentiment analysis, knowledge graph construction, automated reporting, and scalable architecture.

### ✨ Key Features

- **🤖 AI-Powered Analysis**: Leverages OpenAI GPT models for sentiment analysis, topic modeling, and content classification
- **🏗️ Scalable Architecture**: Pluggable factory pattern allowing easy component swapping and extension
- **📊 Rich Analytics**: Sentiment scoring, topic modeling, entity extraction, trend analysis
- **📈 Automated Reporting**: Daily/weekly reports with market insights and trend analysis
- **💾 Multiple Storage Backends**: JSON file storage and Neo4j graph database support
- **🔄 Continuous Operation**: Background collection and processing with configurable schedules
- **🔍 Knowledge Graphs**: Entity relationship mapping and graph-based analysis
- **🎯 Real-time Monitoring**: Continuous news monitoring with alert capabilities

### 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Collector     │────│   Processor     │────│   Analyzer      │
│   (Sina API)    │    │   (Cleaning)    │    │   (AI Models)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Storage       │    │   Orchestrator  │────│   Reporter      │
│   (JSON/Neo4j)  │    │   (Workflow)    │    │   (MD/HTML)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 📋 System Components

#### 1. **Factories** - Pluggable Component Creation
- **SinaCollectorFactory**: Creates news collection components
- **FactoryRegistry**: Manages and registers component factories
- **ComponentFactory**: Abstract base for all factories

#### 2. **Interfaces** - Standardized Contracts  
- **ICollector**: News collection interface
- **IProcessor**: Text processing interface  
- **IAnalyzer**: Analysis interface
- **IReporter**: Report generation interface
- **IStorage**: Data storage interface

#### 3. **Collectors** - Data Acquisition
- **SinaNewsCollector**: Collects from Sina 7x24 API
- **Time-based collection**: Historical data retrieval

#### 4. **Processors** - Data Transformation
- **TextProcessor**: Cleans and normalizes text
- **EntityExtractor**: Extracts named entities

#### 5. **Analyzers** - AI-Powered Insights
- **SentimentAnalyzer**: Emotion analysis using OpenAI
- **TopicAnalyzer**: Topic modeling and trend analysis

#### 6. **Reporters** - Output Generation
- **DailyReporter**: Daily market reports
- **WeeklyReporter**: Weekly trend analysis
- **TrendingTopicsReporter**: Hot topic tracking

#### 7. **Storage** - Data Persistence
- **JSONStorage**: File-based storage
- **Neo4jStorage**: Graph database storage

#### 8. **Orchestrator** - Workflow Management
- **NewsCollectionOrchestrator**: Manages collection pipelines
- **PluggableNewsSystem**: Main system controller

### 🛠️ Installation

#### Prerequisites
- Python 3.8+
- OpenAI API key (optional for AI features)
- Neo4j database (optional for graph storage)

#### Setup Steps

1. **Clone the repository**
```bash
git clone <repository-url>
cd sina-7x24-collector
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

### 🔧 Configuration

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SINA_BASE_URL` | Sina API base URL | `https://zhibo.sina.com.cn/api` |
| `SINA_ZHIBO_ID` | Sina live broadcast ID | `152` |
| `SINA_DELAY` | Delay between requests (seconds) | `0.5` |
| `OPENAI_API_KEY` | OpenAI API key (required for AI features) | `` |
| `OPENAI_BASE_URL` | OpenAI API base URL | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4-turbo` |
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USERNAME` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `password` |
| `DATA_DIR` | Data storage directory | `./data` |
| `REPORT_OUTPUT_DIR` | Report output directory | `./reports` |
| `LOG_DIR` | Log directory | `./logs` |
| `COLLECTION_INTERVAL_MINUTES` | Collection interval (minutes) | `30` |
| `DAILY_REPORT_HOUR` | Daily report generation hour | `8` |

#### Available Categories

- `全部` - All news
- `A股` - A-share market
- `宏观` - Macroeconomics  
- `公司` - Company news
- `数据` - Data & statistics
- `市场` - Market news
- `国际` - International news
- `观点` - Opinions & analysis
- `央行` - Central bank news
- `其他` - Other news

### 🚀 Usage

#### 1. Single Collection Cycle
```bash
python -m src.main --mode single --category "A股" --count 50
```

#### 2. Continuous Collection
```bash
python -m src.main --mode continuous --interval 15 --category "全部"
```

#### 3. Daily Report Generation
```bash
python -m src.main --mode daily-report --report-hour 8 --category "市场"
```

#### 4. Programmatic Usage
```python
from src.factories import SinaCollectorFactory
from src.config.settings import settings
from src.orchestrator import PluggableNewsSystem

# Initialize system
factory = SinaCollectorFactory(settings)
system = PluggableNewsSystem()
config = {...}  # See configuration above
await system.setup_with_factory(factory, config)

# Run single cycle
result = await system.run_single_cycle(category="A股", count=20)
```

### 📊 Output Formats

#### JSON Storage
```json
{
  "id": "news_id_123",
  "title": "新闻标题",
  "content": "新闻正文内容...",
  "publish_time": "2024-01-01T10:00:00",
  "source": "sina_7x24", 
  "category": "A股",
  "tags": ["股票", "市场"],
  "sentiment_score": 0.7,
  "entities": [
    {"text": "中国平安", "type": "company", "confidence": 0.9}
  ]
}
```

#### Daily Report Example
```markdown
# 每日金融新闻分析报告

**报告时间**: 2024年01月01日 08:00:00

**统计时段**: 2023年12月31日 08:00 - 2024年01月01日 08:00

### 执行摘要
- **总体情绪**: 积极 (综合得分: 0.45)
- **新闻分布**: 积极 25 条, 消极 8 条, 中性 17 条
- **市场趋势**: 看涨 (热门话题: A股)

### 话题分解
#### 主要话题
1. **A股市场** (相关性: 0.85)
   - A股市场今日表现强劲，多个板块上涨
   
#### 热门话题
1. **央行货币政策** (提及次数: 15)
2. **外资流入** (提及次数: 12)
```

### 🧪 Testing

#### Unit Tests
```bash
pytest tests/ -v
```

#### Integration Tests
```bash
pytest tests/integration/ -v
```

### 🔒 Security & Privacy

- API keys stored securely in environment variables
- No personal data collection
- GDPR compliant data handling
- Encrypted storage for sensitive information
- Rate limiting to prevent API abuse

### 📈 Scalability Features

- Async/await architecture for high concurrency
- Configurable collection intervals
- Multiple storage backends
- Distributed processing support
- Horizontal scaling ready

### 🚨 Error Handling

- Comprehensive error logging with loguru
- Graceful degradation when services unavailable
- Retry mechanisms with exponential backoff
- Detailed error reporting and diagnostics
- Circuit breaker patterns for external services

### 📚 Advanced Features

#### Knowledge Graph Integration
- Entity relationship mapping
- Semantic search capabilities
- Graph-based trend analysis
- Influence network visualization

#### Machine Learning Pipelines
- Sentiment analysis models
- Topic clustering algorithms
- Anomaly detection
- Predictive analytics

#### Real-time Processing
- Streaming data ingestion
- Real-time alerting
- Live dashboard updates
- WebSocket connections

### 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### 💬 Support

For support, please open an issue in the GitHub repository or contact the maintainers.

---

Made with ❤️ for financial professionals and data scientists

**Star this repo if you found it helpful! ⭐⭐⭐⭐⭐**