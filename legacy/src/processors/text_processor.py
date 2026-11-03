"""
文本处理器模块
负责处理和清洗新闻文本数据
"""

import re
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger

from ..interfaces import IProcessor, NewsItem


class TextProcessor(IProcessor):
    """
    文本处理器
    负责清洗、标准化新闻文本数据
    """
    
    def __init__(self, max_length: int = 1000, min_length: int = 10, 
                 language: str = "zh"):
        """
        初始化处理器
        
        Args:
            max_length: 最大文本长度
            min_length: 最小文本长度
            language: 语言类型
        """
        self.max_length = max_length
        self.min_length = min_length
        self.language = language
        
        # 编译正则表达式以提高性能
        self._html_tag_pattern = re.compile(r'<[^>]+>')
        self._whitespace_pattern = re.compile(r'\s+')
        self._emoji_pattern = re.compile(
            r'[\U0001F600-\U0001F64F'
            r'\U0001F300-\U0001F5FF'
            r'\U0001F680-\U0001F6FF'
            r'\U0001F1E0-\U0001F1FF]+',
            flags=re.UNICODE
        )
        
        logger.info(f"TextProcessor initialized with max_length={max_length}, min_length={min_length}, language={language}")
    
    def _clean_html_tags(self, text: str) -> str:
        """
        移除HTML标签
        
        Args:
            text: 原始文本
            
        Returns:
            移除HTML标签后的文本
        """
        return self._html_tag_pattern.sub('', text)
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        标准化空白字符
        
        Args:
            text: 输入文本
            
        Returns:
            标准化后的文本
        """
        return self._whitespace_pattern.sub(' ', text).strip()
    
    def _remove_emojis(self, text: str) -> str:
        """
        移除表情符号
        
        Args:
            text: 输入文本
            
        Returns:
            移除表情符号后的文本
        """
        return self._emoji_pattern.sub('', text)
    
    def _truncate_text(self, text: str) -> str:
        """
        截断过长的文本
        
        Args:
            text: 输入文本
            
        Returns:
            截断后的文本
        """
        if len(text) <= self.max_length:
            return text
        return text[:self.max_length] + "..."
    
    def _validate_length(self, text: str) -> bool:
        """
        验证文本长度是否符合要求
        
        Args:
            text: 输入文本
            
        Returns:
            长度是否符合要求
        """
        return len(text) >= self.min_length
    
    async def process(self, items: List[NewsItem]) -> List[NewsItem]:
        """
        处理新闻项目列表
        
        Args:
            items: 待处理的新闻项目列表
            
        Returns:
            处理后的新闻项目列表
        """
        logger.info(f"Processing {len(items)} news items")
        
        processed_items = []
        for item in items:
            try:
                # 清洗内容
                cleaned_content = self._clean_html_tags(item.content)
                normalized_content = self._normalize_whitespace(cleaned_content)
                content_without_emojis = self._remove_emojis(normalized_content)
                truncated_content = self._truncate_text(content_without_emojis)
                
                # 验证长度
                if not self._validate_length(truncated_content):
                    logger.warning(f"News item {item.id} has content too short, skipping")
                    continue
                
                # 创建处理后的新闻项目
                processed_item = NewsItem(
                    id=item.id,
                    title=self._clean_html_tags(item.title),
                    content=truncated_content,
                    publish_time=item.publish_time,
                    source=item.source,
                    category=item.category,
                    tags=item.tags,
                    sentiment_score=item.sentiment_score,
                    entities=item.entities
                )
                
                processed_items.append(processed_item)
                
            except Exception as e:
                logger.error(f"Error processing news item {item.id}: {e}")
                continue
        
        logger.info(f"Successfully processed {len(processed_items)} out of {len(items)} news items")
        return processed_items


class EntityExtractor(IProcessor):
    """
    实体提取器
    从新闻文本中提取命名实体
    """
    
    def __init__(self):
        """初始化实体提取器"""
        # 定义常见实体类型的正则表达式
        self.patterns = {
            'company': re.compile(r'[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*(?:\s+(?:Inc|Ltd|Corp|Co|LLC|Group|Holdings|Bank|Insurance|Fund))?\b'),
            'person': re.compile(r'(?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'),
            'location': re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2,3}|,\s*[A-Z][a-z]+)*\b'),
            'organization': re.compile(r'(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:University|Institute|College|School|Hospital|Government|Department|Ministry)\b'),
            'financial_instrument': re.compile(r'\b[A-Z]{1,5}(?:\.[A-Z]{1,3})?\b'),  # 股票代码
        }
        
        logger.info("EntityExtractor initialized")
    
    async def process(self, items: List[NewsItem]) -> List[NewsItem]:
        """
        从新闻项目中提取实体
        
        Args:
            items: 待处理的新闻项目列表
            
        Returns:
            包含提取实体的新闻项目列表
        """
        logger.info(f"Extracting entities from {len(items)} news items")
        
        processed_items = []
        for item in items:
            try:
                entities = []
                
                # 对每个实体类型进行匹配
                for entity_type, pattern in self.patterns.items():
                    matches = pattern.findall(item.content)
                    for match in matches:
                        entity = {
                            'text': match.strip(),
                            'type': entity_type,
                            'confidence': 0.8  # 默认置信度
                        }
                        entities.append(entity)
                
                # 创建包含实体信息的新项目
                processed_item = NewsItem(
                    id=item.id,
                    title=item.title,
                    content=item.content,
                    publish_time=item.publish_time,
                    source=item.source,
                    category=item.category,
                    tags=item.tags,
                    sentiment_score=item.sentiment_score,
                    entities=entities
                )
                
                processed_items.append(processed_item)
                
            except Exception as e:
                logger.error(f"Error extracting entities from news item {item.id}: {e}")
                # 即使出现错误也添加原始项目
                processed_items.append(item)
        
        logger.info(f"Entity extraction completed for {len(processed_items)} news items")
        return processed_items