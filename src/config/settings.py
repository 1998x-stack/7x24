"""
应用配置模块
定义所有配置选项和设置
"""

import os
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv


# 加载环境变量
load_dotenv()


@dataclass
class Settings:
    """
    应用配置类
    包含所有应用运行所需的配置选项
    """
    
    # 新浪API配置
    sina_base_url: str = field(default_factory=lambda: os.getenv("SINA_BASE_URL", "https://zhibo.sina.com.cn/api"))
    sina_zhibo_id: int = field(default_factory=lambda: int(os.getenv("SINA_ZHIBO_ID", "152")))
    sina_delay: float = field(default_factory=lambda: float(os.getenv("SINA_DELAY", "0.5")))
    sina_timeout: int = field(default_factory=lambda: int(os.getenv("SINA_TIMEOUT", "15")))
    
    # OpenAI配置
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4-turbo"))
    
    # Neo4j配置
    neo4j_uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_username: str = field(default_factory=lambda: os.getenv("NEO4J_USERNAME", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"))
    
    # 请求配置
    request_timeout: int = field(default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT", "30")))
    request_delay: float = field(default_factory=lambda: float(os.getenv("REQUEST_DELAY", "1.0")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))
    
    # 数据目录配置
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "./data"))
    report_output_dir: str = field(default_factory=lambda: os.getenv("REPORT_OUTPUT_DIR", "./reports"))
    log_dir: str = field(default_factory=lambda: os.getenv("LOG_DIR", "./logs"))
    
    # 调度配置
    collection_interval_minutes: int = field(default_factory=lambda: int(os.getenv("COLLECTION_INTERVAL_MINUTES", "30")))
    daily_report_hour: int = field(default_factory=lambda: int(os.getenv("DAILY_REPORT_HOUR", "8")))
    
    # 日志配置
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_retention_days: int = field(default_factory=lambda: int(os.getenv("LOG_RETENTION_DAYS", "30")))
    
    def __post_init__(self):
        """
        初始化后处理
        验证配置的有效性
        """
        # 验证必要配置
        if not self.openai_api_key:
            print("警告: OPENAI_API_KEY 未设置，AI功能将不可用")
        
        # 确保目录存在
        import os
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.report_output_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)


# 全局配置实例
settings = Settings()