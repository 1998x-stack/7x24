"""
新浪新闻收集器模块
负责从新浪7x24 API收集新闻数据
"""

import re
import json
import time
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from loguru import logger

from ..interfaces import ICollector, NewsItem


class SinaNewsCollector(ICollector):
    """
    新浪新闻收集器
    从新浪7x24 API收集金融新闻数据
    """
    
    def __init__(self, base_url: str = "https://zhibo.sina.com.cn/api", 
                 api_key: Optional[str] = None, 
                 timeout: int = 30):
        """
        初始化收集器
        
        Args:
            base_url: API基础URL
            api_key: API密钥（可选）
            timeout: 请求超时时间
        """
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        
        # 设置请求头
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://finance.sina.com.cn/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        })
        
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"
        
        logger.info(f"SinaNewsCollector initialized with base_url: {base_url}")
        
        # 分类映射
        self.category_mapping = {
            "全部": 0,
            "宏观": 1,
            "行业": 2, 
            "公司": 3,
            "市场": 5,
            "其他": 8,
            "焦点": 9,
            "A股": 10,
            "国际": 102,
            "两会": 110,
            "原创": 202
        }
    
    def _strip_jsonp(self, text: str) -> str:
        """
        移除JSONP包装
        
        Args:
            text: 原始响应文本
            
        Returns:
            JSON字符串
        """
        # 移除JSONP包装 (callback(...) 格式)
        pattern = r'^[^(]+\((.+)\);\s*$'
        match = re.match(pattern, text.strip(), re.DOTALL)
        if match:
            return match.group(1)
        return text
    
    def _parse_datetime(self, dt_str: str) -> datetime:
        """
        解析日期时间字符串
        
        Args:
            dt_str: 日期时间字符串
            
        Returns:
            datetime对象
        """
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # 如果解析失败，返回当前时间
            logger.warning(f"Failed to parse datetime: {dt_str}, using current time")
            return datetime.now()
    
    def _parse_news_item(self, raw_item: Dict[str, Any]) -> NewsItem:
        """
        解析原始新闻项为NewsItem对象
        
        Args:
            raw_item: 原始新闻数据
            
        Returns:
            NewsItem对象
        """
        # 解析扩展数据
        ext_data = {}
        try:
            ext_str = raw_item.get("ext", "{}")
            ext_data = json.loads(ext_str) if isinstance(ext_str, str) else ext_str
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse ext data: {raw_item.get('ext', '{}')}")
        
        # 解析多媒体数据
        multimedia = raw_item.get("multimedia", {})
        images = multimedia.get("img_url", []) if isinstance(multimedia, dict) else []
        
        # 解析标签
        tags = [tag.get("name", "") for tag in raw_item.get("tag", []) if tag.get("name")]
        
        return NewsItem(
            id=str(raw_item.get("id", "")),
            title="",
            content=raw_item.get("rich_text", ""),
            publish_time=self._parse_datetime(raw_item.get("create_time", "")),
            source="sina_7x24",
            category=raw_item.get("category", "unknown"),
            tags=tags,
            sentiment_score=0.0,
            entities=[]
        )
    
    async def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送API请求
        
        Args:
            params: 请求参数
            
        Returns:
            响应数据
            
        Raises:
            requests.RequestException: 请求异常
        """
        url = f"{self.base_url}/zhibo/feed"
        params["_"] = int(time.time() * 1000)  # 添加时间戳防止缓存
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            # 尝试解析JSON
            try:
                json_data = response.json()
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试移除JSONP包装
                text = response.text
                cleaned_text = self._strip_jsonp(text)
                json_data = json.loads(cleaned_text)
            
            # 检查API状态
            result = json_data.get("result", {})
            if result.get("status", {}).get("code") != 0:
                error_msg = result.get("status", {}).get("msg", "Unknown error")
                raise requests.RequestException(f"API Error: {error_msg}")
            
            return json_data
            
        except requests.Timeout:
            logger.error(f"Request timeout for params: {params}")
            raise
        except requests.RequestException as e:
            logger.error(f"Request failed for params: {params}, error: {e}")
            raise
    
    async def collect(self, category: str = "全部", count: int = 20) -> List[NewsItem]:
        """
        收集指定分类的新闻
        
        Args:
            category: 新闻分类
            count: 收集数量
            
        Returns:
            新闻项目列表
        """
        logger.info(f"Collecting {count} news items for category: {category}")
        
        try:
            # 获取分类ID
            category_id = self.category_mapping.get(category, 0)
            
            # 构建请求参数
            params = {
                "page": 1,
                "page_size": min(count, 50),  # API限制最大50条
                "pagesize": min(count, 50),
                "zhibo_id": 152,  # 固定直播间ID
                "tag_id": category_id,
                "tag_id": category_id,
                "dire": "f",  # 正向（新→旧）
                "dpc": 1,
                "id": 9999999,  # 初始游标
                "type": 0
            }
            
            # 发送请求
            data = await self._make_request(params)
            feed = data.get("result", {}).get("data", {}).get("feed", {})
            raw_items = feed.get("list", [])
            
            # 过滤已删除的项目
            filtered_items = [item for item in raw_items if not item.get("is_delete")]
            
            # 解析新闻项目
            news_items = []
            for raw_item in filtered_items[:count]:
                try:
                    parsed_item = self._parse_news_item(raw_item)
                    parsed_item.category = category  # 设置分类
                    news_items.append(parsed_item)
                except Exception as e:
                    logger.warning(f"Failed to parse news item: {raw_item.get('id', 'unknown')}, error: {e}")
                    continue
            
            logger.info(f"Successfully collected {len(news_items)} news items for category: {category}")
            return news_items
            
        except Exception as e:
            logger.error(f"Failed to collect news for category {category}: {e}")
            return []
    
    async def get_categories(self) -> List[str]:
        """
        获取所有可用分类
        
        Returns:
            分类列表
        """
        categories = list(self.category_mapping.keys())
        logger.info(f"Available categories: {categories}")
        return categories
    
    async def collect_by_time_range(self, category: str, start_time: datetime, 
                                   end_time: datetime, max_items: int = 100) -> List[NewsItem]:
        """
        根据时间范围收集新闻
        
        Args:
            category: 新闻分类
            start_time: 开始时间
            end_time: 结束时间
            max_items: 最大收集数量
            
        Returns:
            新闻项目列表
        """
        logger.info(f"Collecting news for {category} from {start_time} to {end_time}")
        
        all_items = []
        category_id = self.category_mapping.get(category, 0)
        cursor_id = 9999999  # 初始游标
        page = 1
        
        while len(all_items) < max_items:
            try:
                params = {
                    "page": page,
                    "page_size": 20,
                    "pagesize": 20,
                    "zhibo_id": 152,  # 固定直播间ID
                    "tag_id": category_id,
                    "tag_id": category_id,
                    "dire": "f",
                    "dpc": 1,
                    "id": cursor_id,
                    "type": 0
                }
                
                data = await self._make_request(params)
                feed = data.get("result", {}).get("data", {}).get("feed", {})
                raw_items = feed.get("list", [])
                
                if not raw_items:
                    break  # 没有更多数据
                
                # 过滤时间范围内的数据
                for raw_item in raw_items:
                    if len(all_items) >= max_items:
                        break
                        
                    item_time = self._parse_datetime(raw_item.get("create_time", ""))
                    
                    if start_time <= item_time <= end_time:
                        try:
                            parsed_item = self._parse_news_item(raw_item)
                            parsed_item.category = category
                            all_items.append(parsed_item)
                        except Exception as e:
                            logger.warning(f"Failed to parse news item: {raw_item.get('id', 'unknown')}, error: {e}")
                
                # 更新游标和页码
                min_id = feed.get("min_id", 0)
                total_pages = feed.get("page_info", {}).get("totalPage", 1)
                
                if page >= total_pages:
                    if min_id == 0 or min_id >= cursor_id:
                        break  # 到达末尾
                    cursor_id = min_id
                    page = 1
                else:
                    page += 1
                
                # 添加延迟以避免过于频繁的请求
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error collecting news by time range: {e}")
                break
        
        logger.info(f"Collected {len(all_items)} news items in time range for category: {category}")
        return all_items


from ..config.settings import settings
SinaNewsCollector._settings = settings