"""
情感分析器模块
使用OpenAI API进行新闻情感分析
"""

import asyncio
import json
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger
import openai

from ..interfaces import IAnalyzer, NewsItem


class SentimentAnalyzer(IAnalyzer):
    """
    情感分析器
    使用OpenAI API分析新闻的情感倾向
    """
    
    def __init__(self, model_name: str = "gpt-3.5-turbo", 
                 api_key: str = "", 
                 base_url: str = "https://api.openai.com/v1"):
        """
        初始化情感分析器
        
        Args:
            model_name: 使用的模型名称
            api_key: OpenAI API密钥
            base_url: OpenAI API基础URL
        """
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        
        # 初始化OpenAI客户端
        if api_key:
            self.client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            logger.info(f"SentimentAnalyzer initialized with model: {model_name}")
        else:
            self.client = None
            logger.warning("OpenAI API key not provided, sentiment analysis will be disabled")
    
    def _construct_sentiment_prompt(self, news_content: str) -> str:
        """
        构建情感分析提示语句
        
        Args:
            news_content: 新闻内容
            
        Returns:
            提示语句
        """
        return f"""
        请分析以下新闻文本的情感倾向。返回一个JSON格式的结果，包含以下字段：
        - score: 情感分数，范围从-1（负面）到1（正面），0表示中性
        - sentiment: 情感分类（positive, negative, neutral）
        - confidence: 分析置信度（0-1）
        - key_points: 影响情感判断的关键点列表
        
        新闻内容：
        {news_content[:2000]}  # 限制内容长度以控制成本
        """
    
    async def _analyze_single_news(self, item: NewsItem) -> Dict[str, Any]:
        """
        分析单个新闻项目
        
        Args:
            item: 新闻项目
            
        Returns:
            分析结果
        """
        if not self.client:
            # 如果没有API密钥，返回默认值
            return {
                'score': 0.0,
                'sentiment': 'neutral',
                'confidence': 0.0,
                'key_points': []
            }
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一个专业的新闻情感分析助手。请准确分析新闻文本的情感倾向。"},
                    {"role": "user", "content": self._construct_sentiment_prompt(item.content)}
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # 解析响应
            result = json.loads(response.choices[0].message.content)
            
            # 验证结果格式
            if not isinstance(result, dict):
                raise ValueError("Invalid response format")
            
            # 验证必需字段
            required_fields = ['score', 'sentiment', 'confidence', 'key_points']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse sentiment analysis response: {e}")
            return {
                'score': 0.0,
                'sentiment': 'neutral',
                'confidence': 0.0,
                'key_points': []
            }
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return {
                'score': 0.0,
                'sentiment': 'neutral',
                'confidence': 0.0,
                'key_points': []
            }
        except Exception as e:
            logger.error(f"Unexpected error in sentiment analysis: {e}")
            return {
                'score': 0.0,
                'sentiment': 'neutral',
                'confidence': 0.0,
                'key_points': []
            }
    
    async def analyze(self, items: List[NewsItem]) -> Dict[str, Any]:
        """
        分析新闻项目的整体情感趋势
        
        Args:
            items: 新闻项目列表
            
        Returns:
            分析结果字典
        """
        logger.info(f"Analyzing sentiment for {len(items)} news items")
        
        if not items:
            logger.warning("No news items to analyze")
            return {
                'overall_sentiment_score': 0.0,
                'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0},
                'average_confidence': 0.0,
                'top_positive_items': [],
                'top_negative_items': [],
                'trending_topics': [],
                'time_series': []
            }
        
        # 并发分析所有新闻项目
        analysis_tasks = [self._analyze_single_news(item) for item in items]
        individual_results = await asyncio.gather(*analysis_tasks)
        
        # 计算总体统计信息
        scores = [result['score'] for result in individual_results]
        sentiments = [result['sentiment'] for result in individual_results]
        confidences = [result['confidence'] for result in individual_results]
        
        # 总体情感得分
        overall_score = sum(scores) / len(scores) if scores else 0.0
        
        # 情感分布
        sentiment_dist = {
            'positive': sentiments.count('positive'),
            'negative': sentiments.count('negative'),
            'neutral': sentiments.count('neutral')
        }
        
        # 平均置信度
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # 按情感得分排序找出最积极和最消极的项目
        scored_pairs = list(zip(items, individual_results, scores))
        sorted_by_score = sorted(scored_pairs, key=lambda x: x[2], reverse=True)
        
        # 获取最积极和最消极的项目
        top_positive = [
            {
                'id': item.id,
                'title': item.title,
                'score': result['score'],
                'content_snippet': item.content[:200] + "..." if len(item.content) > 200 else item.content
            }
            for item, result, score in sorted_by_score[:5]
            if result['score'] > 0
        ]
        
        top_negative = [
            {
                'id': item.id,
                'title': item.title,
                'score': result['score'],
                'content_snippet': item.content[:200] + "..." if len(item.content) > 200 else item.content
            }
            for item, result, score in sorted_by_score[-5:]
            if result['score'] < 0
        ]
        
        # 提取热门话题（基于标签）
        all_tags = []
        for item in items:
            all_tags.extend(item.tags)
        
        from collections import Counter
        tag_counter = Counter(all_tags)
        trending_topics = [
            {'topic': topic, 'frequency': count}
            for topic, count in tag_counter.most_common(10)
            if topic  # 只包括非空标签
        ]
        
        # 时间序列分析
        time_series = []
        for item, result in zip(items, individual_results):
            time_series.append({
                'timestamp': item.publish_time.isoformat() if item.publish_time else '',
                'sentiment_score': result['score'],
                'category': item.category
            })
        
        analysis_result = {
            'overall_sentiment_score': overall_score,
            'sentiment_distribution': sentiment_dist,
            'average_confidence': avg_confidence,
            'top_positive_items': top_positive,
            'top_negative_items': top_negative,
            'trending_topics': trending_topics,
            'time_series': time_series
        }
        
        logger.info(f"Sentiment analysis completed. Overall score: {overall_score:.3f}")
        return analysis_result


class TopicAnalyzer(IAnalyzer):
    """
    主题分析器
    识别新闻中的主要话题和趋势
    """
    
    def __init__(self, model_name: str = "gpt-3.5-turbo", 
                 api_key: str = "", 
                 base_url: str = "https://api.openai.com/v1"):
        """
        初始化主题分析器
        
        Args:
            model_name: 使用的模型名称
            api_key: OpenAI API密钥
            base_url: OpenAI API基础URL
        """
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        
        if api_key:
            self.client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            logger.info(f"TopicAnalyzer initialized with model: {model_name}")
        else:
            self.client = None
            logger.warning("OpenAI API key not provided, topic analysis will be disabled")
    
    def _construct_topic_prompt(self, news_contents: List[str]) -> str:
        """
        构建主题分析提示语句
        
        Args:
            news_contents: 新闻内容列表
            
        Returns:
            提示语句
        """
        combined_content = "\n\n".join(news_contents[:20])  # 限制数量以控制成本
        
        return f"""
        请分析以下新闻集合的主要话题和趋势。返回一个JSON格式的结果，包含以下字段：
        - main_topics: 主要话题列表，每个话题包含name、relevance_score、description
        - emerging_trends: 新兴趋势列表，每个趋势包含topic、growth_rate、description
        - market_sentiment: 整体市场情绪（bullish, bearish, neutral）
        - key_drivers: 市场变动的主要驱动因素
        - risk_factors: 潜在风险因素
        - opportunity_areas: 潜在机会领域
        
        新闻内容：
        {combined_content}
        """
    
    async def analyze(self, items: List[NewsItem]) -> Dict[str, Any]:
        """
        分析新闻项目的主要话题和趋势
        
        Args:
            items: 新闻项目列表
            
        Returns:
            主题分析结果字典
        """
        logger.info(f"Analyzing topics for {len(items)} news items")
        
        if not items or not self.client:
            # 返回默认结果
            return {
                'main_topics': [],
                'emerging_trends': [],
                'market_sentiment': 'neutral',
                'key_drivers': [],
                'risk_factors': [],
                'opportunity_areas': []
            }
        
        try:
            # 准备内容用于分析
            contents = [item.content for item in items if item.content]
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一个专业的金融新闻分析助手。请准确识别新闻中的主要话题和市场趋势。"},
                    {"role": "user", "content": self._construct_topic_prompt(contents)}
                ],
                temperature=0.3,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # 验证结果结构
            if not isinstance(result, dict):
                raise ValueError("Invalid response format")
            
            logger.info(f"Topic analysis completed with {len(result.get('main_topics', []))} main topics")
            return result
            
        except Exception as e:
            logger.error(f"Error in topic analysis: {e}")
            return {
                'main_topics': [],
                'emerging_trends': [],
                'market_sentiment': 'neutral',
                'key_drivers': [],
                'risk_factors': [],
                'opportunity_areas': []
            }