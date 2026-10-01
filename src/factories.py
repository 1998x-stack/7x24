"""
工厂模式实现
用于创建不同类型的新闻收集器、处理器、分析器等组件
"""

from abc import ABC, abstractmethod
from typing import Dict, Type, Any, Optional, List
import logging
from loguru import logger

from .interfaces import ICollector, IProcessor, IAnalyzer, IReporter, IStorage
from .config.settings import Settings


class ComponentFactory(ABC):
    """
    组件工厂抽象基类
    提供创建各种组件的通用接口
    """
    
    @abstractmethod
    def create_collector(self, config: Dict[str, Any]) -> ICollector:
        """创建新闻收集器"""
        pass
    
    @abstractmethod
    def create_processor(self, config: Dict[str, Any]) -> IProcessor:
        """创建新闻处理器"""
        pass
    
    @abstractmethod
    def create_analyzer(self, config: Dict[str, Any]) -> IAnalyzer:
        """创建新闻分析器"""
        pass
    
    @abstractmethod
    def create_reporter(self, config: Dict[str, Any]) -> IReporter:
        """创建报告生成器"""
        pass
    
    @abstractmethod
    def create_storage(self, config: Dict[str, Any]) -> IStorage:
        """创建存储组件"""
        pass


class SinaCollectorFactory(ComponentFactory):
    """
    新浪新闻组件工厂
    专门用于创建新浪7x24新闻系统的各个组件
    """
    
    def __init__(self, settings: Settings):
        """
        初始化工厂
        
        Args:
            settings: 应用配置
        """
        self._settings = settings
        logger.info("SinaCollectorFactory initialized")
    
    def create_collector(self, config: Dict[str, Any]) -> ICollector:
        """
        创建新浪新闻收集器
        
        Args:
            config: 收集器配置
            
        Returns:
            新闻收集器实例
        """
        from .collectors.sina_collector import SinaNewsCollector
        return SinaNewsCollector(
            base_url=config.get("base_url", self._settings.sina_base_url),
            api_key=config.get("api_key", getattr(self._settings, 'api_key', None)),
            timeout=config.get("timeout", self._settings.request_timeout)
        )
    
    def create_processor(self, config: Dict[str, Any]) -> IProcessor:
        """
        创建新闻处理器
        
        Args:
            config: 处理器配置
            
        Returns:
            新闻处理器实例
        """
        from .processors.text_processor import TextProcessor
        return TextProcessor(
            max_length=config.get("max_length", 1000),
            min_length=config.get("min_length", 10),
            language=config.get("language", "zh")
        )
    
    def create_analyzer(self, config: Dict[str, Any]) -> IAnalyzer:
        """
        创建新闻分析器
        
        Args:
            config: 分析器配置
            
        Returns:
            新闻分析器实例
        """
        from .analyzers.sentiment_analyzer import SentimentAnalyzer
        return SentimentAnalyzer(
            model_name=config.get("model_name", self._settings.openai_model),
            api_key=config.get("api_key", self._settings.openai_api_key),
            base_url=config.get("base_url", self._settings.openai_base_url)
        )
    
    def create_reporter(self, config: Dict[str, Any]) -> IReporter:
        """
        创建报告生成器
        
        Args:
            config: 报告生成器配置
            
        Returns:
            报告生成器实例
        """
        from .reporters.daily_reporter import DailyReporter
        return DailyReporter(
            template_path=config.get("template_path", "templates/daily_report.md"),
            output_dir=config.get("output_dir", self._settings.report_output_dir)
        )
    
    def create_storage(self, config: Dict[str, Any]) -> IStorage:
        """
        创建存储组件
        
        Args:
            config: 存储组件配置
            
        Returns:
            存储组件实例
        """
        storage_type = config.get("type", "json")
        if storage_type == "neo4j":
            from .storage.neo4j_storage import Neo4jStorage
            return Neo4jStorage(
                uri=config.get("uri", self._settings.neo4j_uri),
                username=config.get("username", self._settings.neo4j_username),
                password=config.get("password", self._settings.neo4j_password)
            )
        else:
            from .storage.json_storage import JSONStorage
            return JSONStorage(
                data_dir=config.get("data_dir", self._settings.data_dir)
            )


class FactoryRegistry:
    """
    工厂注册表
    管理不同的工厂实例
    """
    
    def __init__(self):
        """初始化注册表"""
        self._factories: Dict[str, ComponentFactory] = {}
        logger.info("FactoryRegistry initialized")
    
    def register_factory(self, name: str, factory: ComponentFactory) -> None:
        """
        注册工厂实例
        
        Args:
            name: 工厂名称
            factory: 工厂实例
        """
        self._factories[name] = factory
        logger.info(f"Factory '{name}' registered successfully")
    
    def get_factory(self, name: str) -> Optional[ComponentFactory]:
        """
        获取工厂实例
        
        Args:
            name: 工厂名称
            
        Returns:
            工厂实例，如果不存在则返回None
        """
        factory = self._factories.get(name)
        if factory:
            logger.info(f"Factory '{name}' retrieved successfully")
        else:
            logger.warning(f"Factory '{name}' not found")
        return factory
    
    def list_factories(self) -> List[str]:
        """
        列出所有注册的工厂
        
        Returns:
            工厂名称列表
        """
        factories = list(self._factories.keys())
        logger.debug(f"Available factories: {factories}")
        return factories


# 全局注册表实例
factory_registry = FactoryRegistry()