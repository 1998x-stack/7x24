"""
存储模块
提供多种存储后端以保存新闻数据
"""

import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
from dataclasses import asdict

from ..interfaces import IStorage, NewsItem


class JSONStorage(IStorage):
    """
    JSON文件存储
    将新闻数据保存为JSON格式文件
    """
    
    def __init__(self, data_dir: str = "./data"):
        """
        初始化JSON存储
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.news_file = self.data_dir / "news_data.json"
        self.index_file = self.data_dir / "news_index.json"
        
        logger.info(f"JSONStorage initialized with data_dir: {data_dir}")
        
        # 初始化索引文件
        if not self.index_file.exists():
            self._save_index({})
    
    def _serialize_news_item(self, item: NewsItem) -> Dict[str, Any]:
        """
        序列化新闻项目为字典
        
        Args:
            item: 新闻项目
            
        Returns:
            序列化后的字典
        """
        item_dict = asdict(item)
        # 将datetime转换为ISO字符串
        if isinstance(item_dict['publish_time'], datetime):
            item_dict['publish_time'] = item_dict['publish_time'].isoformat()
        return item_dict
    
    def _deserialize_news_item(self, item_dict: Dict[str, Any]) -> NewsItem:
        """
        反序列化字典为新闻项目
        
        Args:
            item_dict: 字典格式的新闻项目
            
        Returns:
            新闻项目对象
        """
        # 将ISO字符串转换回datetime
        if 'publish_time' in item_dict and isinstance(item_dict['publish_time'], str):
            item_dict['publish_time'] = datetime.fromisoformat(item_dict['publish_time'])
        
        return NewsItem(**item_dict)
    
    def _load_data(self) -> List[Dict[str, Any]]:
        """
        从文件加载数据
        
        Returns:
            新闻数据列表
        """
        if not self.news_file.exists():
            return []
        
        try:
            with open(self.news_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {self.news_file}, returning empty list")
            return []
        except Exception as e:
            logger.error(f"Error reading {self.news_file}: {e}")
            return []
    
    def _save_data(self, data: List[Dict[str, Any]]) -> bool:
        """
        保存数据到文件
        
        Args:
            data: 要保存的数据
            
        Returns:
            保存是否成功
        """
        try:
            with open(self.news_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error writing to {self.news_file}: {e}")
            return False
    
    def _load_index(self) -> Dict[str, Any]:
        """
        加载索引数据
        
        Returns:
            索引字典
        """
        if not self.index_file.exists():
            return {}
        
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {self.index_file}, returning empty dict")
            return {}
        except Exception as e:
            logger.error(f"Error reading {self.index_file}: {e}")
            return {}
    
    def _save_index(self, index: Dict[str, Any]) -> bool:
        """
        保存索引数据
        
        Args:
            index: 索引字典
            
        Returns:
            保存是否成功
        """
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error writing to {self.index_file}: {e}")
            return False
    
    async def save(self, items: List[NewsItem]) -> bool:
        """
        保存新闻项目到存储
        
        Args:
            items: 要保存的新闻项目列表
            
        Returns:
            保存是否成功
        """
        logger.info(f"Saving {len(items)} news items to JSON storage")
        
        # 加载现有数据
        existing_data = self._load_data()
        
        # 转换新闻项目为字典
        serialized_items = [self._serialize_news_item(item) for item in items]
        
        # 添加新项目到现有数据
        updated_data = existing_data + serialized_items
        
        # 保持数据量在合理范围内（保留最近的10000条记录）
        if len(updated_data) > 10000:
            updated_data = updated_data[-10000:]
        
        # 保存数据
        success = self._save_data(updated_data)
        
        if success:
            logger.info(f"Successfully saved {len(items)} news items to JSON storage")
        else:
            logger.error("Failed to save news items to JSON storage")
        
        return success
    
    async def load_latest(self, count: int) -> List[NewsItem]:
        """
        加载最新的新闻项目
        
        Args:
            count: 加载数量
            
        Returns:
            新闻项目列表
        """
        logger.info(f"Loading latest {count} news items from JSON storage")
        
        data = self._load_data()
        
        # 获取最新的项目
        latest_items = data[-count:] if len(data) >= count else data
        
        # 转换为新闻项目对象
        news_items = [self._deserialize_news_item(item) for item in latest_items]
        
        logger.info(f"Loaded {len(news_items)} news items from JSON storage")
        return news_items
    
    async def load_by_category(self, category: str, count: int) -> List[NewsItem]:
        """
        根据分类加载新闻项目
        
        Args:
            category: 新闻分类
            count: 加载数量
            
        Returns:
            新闻项目列表
        """
        logger.info(f"Loading {count} news items for category '{category}' from JSON storage")
        
        data = self._load_data()
        
        # 过滤指定分类的项目
        filtered_data = [item for item in data if item.get('category') == category]
        
        # 获取最新的项目
        latest_items = filtered_data[-count:] if len(filtered_data) >= count else filtered_data
        
        # 转换为新闻项目对象
        news_items = [self._deserialize_news_item(item) for item in latest_items]
        
        logger.info(f"Loaded {len(news_items)} news items for category '{category}'")
        return news_items
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        获取存储统计数据
        
        Returns:
            统计信息字典
        """
        data = self._load_data()
        
        if not data:
            return {
                'total_count': 0,
                'categories': [],
                'date_range': {'start': None, 'end': None}
            }
        
        # 统计分类
        categories = set(item.get('category', 'unknown') for item in data)
        
        # 计算时间范围
        dates = []
        for item in data:
            dt_str = item.get('publish_time')
            if dt_str:
                try:
                    dates.append(datetime.fromisoformat(dt_str))
                except ValueError:
                    continue
        
        date_range = {
            'start': min(dates).isoformat() if dates else None,
            'end': max(dates).isoformat() if dates else None
        }
        
        return {
            'total_count': len(data),
            'categories': list(categories),
            'date_range': date_range
        }


class Neo4jStorage(IStorage):
    """
    Neo4j图数据库存储
    将新闻数据以图结构存储在Neo4j中
    """
    
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 username: str = "neo4j", 
                 password: str = "password"):
        """
        初始化Neo4j存储
        
        Args:
            uri: Neo4j连接地址
            username: 用户名
            password: 密码
        """
        try:
            from neo4j import AsyncGraphDatabase
            self.driver = AsyncGraphDatabase(uri, auth=(username, password))
            self.connected = True
            logger.info(f"Neo4jStorage initialized with URI: {uri}")
        except ImportError:
            logger.warning("Neo4j driver not installed, Neo4j storage will be disabled")
            self.driver = None
            self.connected = False
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.driver = None
            self.connected = False
    
    async def save(self, items: List[NewsItem]) -> bool:
        """
        保存新闻项目到Neo4j存储
        
        Args:
            items: 要保存的新闻项目列表
            
        Returns:
            保存是否成功
        """
        if not self.connected or not self.driver:
            logger.warning("Neo4j not connected, skipping save operation")
            return False
        
        logger.info(f"Saving {len(items)} news items to Neo4j storage")
        
        try:
            async with self.driver.session() as session:
                for item in items:
                    # 创建新闻节点
                    await session.run(
                        "MERGE (n:News {id: $id}) "
                        "SET n.title = $title, n.content = $content, "
                        "n.publish_time = $publish_time, n.source = $source, "
                        "n.category = $category, n.sentiment_score = $sentiment_score",
                        id=item.id,
                        title=item.title,
                        content=item.content,
                        publish_time=item.publish_time.isoformat() if item.publish_time else "",
                        source=item.source,
                        category=item.category,
                        sentiment_score=item.sentiment_score
                    )
                    
                    # 创建标签节点并建立关系
                    for tag in item.tags:
                        await session.run(
                            "MERGE (t:Tag {name: $tag_name}) "
                            "WITH t "
                            "MATCH (n:News {id: $news_id}) "
                            "MERGE (n)-[:HAS_TAG]->(t)",
                            tag_name=tag,
                            news_id=item.id
                        )
                    
                    # 创建实体节点并建立关系
                    for entity in item.entities:
                        entity_text = entity.get('text', '')
                        entity_type = entity.get('type', 'unknown')
                        if entity_text:
                            await session.run(
                                "MERGE (e:Entity {text: $entity_text, type: $entity_type}) "
                                "WITH e "
                                "MATCH (n:News {id: $news_id}) "
                                "MERGE (n)-[:MENTIONS]->(e)",
                                entity_text=entity_text,
                                entity_type=entity_type,
                                news_id=item.id
                            )
            
            logger.info(f"Successfully saved {len(items)} news items to Neo4j storage")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to Neo4j: {e}")
            return False
    
    async def load_latest(self, count: int) -> List[NewsItem]:
        """
        从Neo4j加载最新的新闻项目
        
        Args:
            count: 加载数量
            
        Returns:
            新闻项目列表
        """
        if not self.connected or not self.driver:
            logger.warning("Neo4j not connected, returning empty list")
            return []
        
        logger.info(f"Loading latest {count} news items from Neo4j storage")
        
        try:
            async with self.driver.session() as session:
                # 查询最新的新闻项目
                result = await session.run(
                    "MATCH (n:News) "
                    "RETURN n.id as id, n.title as title, n.content as content, "
                    "n.publish_time as publish_time, n.source as source, "
                    "n.category as category, n.sentiment_score as sentiment_score "
                    "ORDER BY n.publish_time DESC LIMIT $limit",
                    limit=count
                )
                
                items = []
                async for record in result:
                    # 获取标签
                    tag_result = await session.run(
                        "MATCH (n:News {id: $news_id})-[:HAS_TAG]->(t:Tag) "
                        "RETURN t.name as tag_name",
                        news_id=record['id']
                    )
                    tags = [record['tag_name'] async for record in tag_result]
                    
                    # 获取实体
                    entity_result = await session.run(
                        "MATCH (n:News {id: $news_id})-[:MENTIONS]->(e:Entity) "
                        "RETURN e.text as entity_text, e.type as entity_type",
                        news_id=record['id']
                    )
                    entities = [
                        {'text': record['entity_text'], 'type': record['entity_type']}
                        async for record in entity_result
                    ]
                    
                    item = NewsItem(
                        id=record['id'],
                        title=record['title'],
                        content=record['content'],
                        publish_time=datetime.fromisoformat(record['publish_time']),
                        source=record['source'],
                        category=record['category'],
                        tags=tags,
                        sentiment_score=record['sentiment_score'],
                        entities=entities
                    )
                    items.append(item)
            
            logger.info(f"Loaded {len(items)} news items from Neo4j storage")
            return items
            
        except Exception as e:
            logger.error(f"Error loading from Neo4j: {e}")
            return []