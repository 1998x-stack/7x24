"""
工厂模式接口定义
工厂模式用于创建不同类型的新闻收集器和处理器
遵循Google风格指南和PEP 8/257规范
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Protocol
from datetime import datetime
import logging
from dataclasses import dataclass, field


@dataclass
class NewsItem:
    """
    新闻项目的数据结构
    
    Attributes:
        id: 新闻唯一标识符
        title: 新闻标题
        content: 新闻内容
        publish_time: 发布时间
        source: 新闻来源
        category: 新闻分类
        tags: 关键词标签
        sentiment_score: 情感得分
        entities: 实体信息
    """
    id: str
    title: str
    content: str
    publish_time: datetime
    source: str
    category: str
    tags: List[str] = field(default_factory=list)
    sentiment_score: float = 0.0
    entities: List[Dict[str, Any]] = field(default_factory=list)


class ICollector(Protocol):
    """新闻收集器协议"""
    
    async def collect(self, category: str, count: int) -> List[NewsItem]:
        """
        收集指定分类的新闻
        
        Args:
            category: 新闻分类
            count: 收集数量
            
        Returns:
            新闻项目列表
        """
        ...
    
    async def get_categories(self) -> List[str]:
        """
        获取所有可用分类
        
        Returns:
            分类列表
        """
        ...


class IProcessor(Protocol):
    """新闻处理器协议"""
    
    async def process(self, items: List[NewsItem]) -> List[NewsItem]:
        """
        处理新闻项目
        
        Args:
            items: 待处理的新闻项目列表
            
        Returns:
            处理后的新闻项目列表
        """
        ...


class IAnalyzer(Protocol):
    """新闻分析器协议"""
    
    async def analyze(self, items: List[NewsItem]) -> Dict[str, Any]:
        """
        分析新闻项目
        
        Args:
            items: 待分析的新闻项目列表
            
        Returns:
            分析结果字典
        """
        ...


class IReporter(Protocol):
    """报告生成器协议"""
    
    async def generate_report(self, analysis_results: Dict[str, Any], 
                            period_start: datetime, 
                            period_end: datetime) -> str:
        """
        生成分析报告
        
        Args:
            analysis_results: 分析结果
            period_start: 统计周期开始时间
            period_end: 统计周期结束时间
            
        Returns:
            生成的报告内容
        """
        ...


class IStorage(Protocol):
    """存储接口协议"""
    
    async def save(self, items: List[NewsItem]) -> bool:
        """
        保存新闻项目到存储
        
        Args:
            items: 要保存的新闻项目列表
            
        Returns:
            保存是否成功
        """
        ...
    
    async def load_latest(self, count: int) -> List[NewsItem]:
        """
        加载最新的新闻项目
        
        Args:
            count: 加载数量
            
        Returns:
            新闻项目列表
        """
        ...