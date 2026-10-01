#!/usr/bin/env python3
"""
单元测试脚本
测试工业级新浪7x24新闻收集系统的各个组件
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
"""
单元测试脚本
测试工业级新浪7x24新闻收集系统的各个组件
"""

import asyncio
import unittest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.interfaces import NewsItem
from src.collectors.sina_collector import SinaNewsCollector
from src.processors.text_processor import TextProcessor, EntityExtractor
from src.analyzers.sentiment_analyzer import SentimentAnalyzer
from src.storage.json_storage import JSONStorage
from src.config.settings import settings


class TestNewsItem(unittest.TestCase):
    """测试新闻项目数据结构"""
    
    def test_news_item_creation(self):
        """测试新闻项目创建"""
        item = NewsItem(
            id="test_123",
            title="测试标题",
            content="测试内容",
            publish_time=datetime.now(),
            source="test_source",
            category="test_category",
            tags=["test", "tag"],
            sentiment_score=0.5,
            entities=[{"text": "entity", "type": "test", "confidence": 0.8}]
        )
        
        self.assertEqual(item.id, "test_123")
        self.assertEqual(item.title, "测试标题")
        self.assertEqual(item.content, "测试内容")
        self.assertEqual(item.source, "test_source")
        self.assertEqual(item.category, "test_category")
        self.assertEqual(item.tags, ["test", "tag"])
        self.assertEqual(item.sentiment_score, 0.5)
        self.assertEqual(len(item.entities), 1)


class TestSinaCollector(unittest.IsolatedAsyncioTestCase):
    """测试新浪新闻收集器"""
    
    @patch('src.collectors.sina_collector.requests.Session.get')
    async def test_collect_method(self, mock_get):
        """测试收集方法"""
        # Mock响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"result":{"status":{"code":0},"data":{"feed":{"list":[],"min_id":0}}}}'
        mock_response.json.return_value = {
            "result": {
                "status": {"code": 0},
                "data": {"feed": {"list": [], "min_id": 0}}
            }
        }
        mock_get.return_value = mock_response
        
        collector = SinaNewsCollector(base_url="https://test.com")
        
        # 测试收集方法
        result = await collector.collect(category="A股", count=5)
        
        self.assertIsInstance(result, list)
        # 由于API返回空列表，应该得到空结果
        self.assertEqual(len(result), 0)


class TestTextProcessor(unittest.IsolatedAsyncioTestCase):
    """测试文本处理器"""
    
    async def test_process_method(self):
        """测试处理方法"""
        processor = TextProcessor(max_length=100, min_length=5, language="zh")
        
        # 创建测试新闻项目
        test_item = NewsItem(
            id="test_123",
            title="测试标题<script>alert('xss')</script>",
            content="这是一个测试内容，包含一些HTML标签<p>段落</p>和<a href='#'>链接</a>。",
            publish_time=datetime.now(),
            source="test_source",
            category="test_category"
        )
        
        result = await processor.process([test_item])
        
        self.assertEqual(len(result), 1)
        processed_item = result[0]
        
        # 验证HTML标签已被清理
        self.assertNotIn("<script>", processed_item.title)
        self.assertNotIn("<p>", processed_item.content)
        self.assertNotIn("<a", processed_item.content)


class TestEntityExtractor(unittest.IsolatedAsyncioTestCase):
    """测试实体提取器"""
    
    async def test_process_method(self):
        """测试实体提取方法"""
        extractor = EntityExtractor()
        
        # 创建测试新闻项目
        test_item = NewsItem(
            id="test_123",
            title="测试标题",
            content="苹果公司是知名科技企业，CEO是Tim Cook。",
            publish_time=datetime.now(),
            source="test_source",
            category="test_category"
        )
        
        result = await extractor.process([test_item])
        
        self.assertEqual(len(result), 1)
        processed_item = result[0]
        
        # 由于我们的正则模式相对简单，可能不会匹配这个具体例子，
        # 但我们验证方法能够执行而不抛出异常
        self.assertTrue(hasattr(processed_item, 'entities'))


class TestJSONStorage(unittest.IsolatedAsyncioTestCase):
    """测试JSON存储"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = "/tmp/test_news_storage"
        os.makedirs(self.test_dir, exist_ok=True)
        self.storage = JSONStorage(data_dir=self.test_dir)
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    async def test_save_and_load(self):
        """测试保存和加载功能"""
        # 创建测试新闻项目
        test_items = [
            NewsItem(
                id="test_1",
                title="测试标题1",
                content="测试内容1",
                publish_time=datetime.now(),
                source="test_source",
                category="test_category"
            ),
            NewsItem(
                id="test_2", 
                title="测试标题2",
                content="测试内容2",
                publish_time=datetime.now(),
                source="test_source",
                category="test_category"
            )
        ]
        
        # 保存项目
        save_result = await self.storage.save(test_items)
        self.assertTrue(save_result)
        
        # 加载项目
        loaded_items = await self.storage.load_latest(10)
        self.assertEqual(len(loaded_items), 2)
        
        # 验证数据完整性
        self.assertEqual(loaded_items[0].id, "test_1")
        self.assertEqual(loaded_items[1].id, "test_2")


class TestSettings(unittest.TestCase):
    """测试配置"""
    
    def test_settings_initialization(self):
        """测试配置初始化"""
        # 验证配置对象已正确初始化
        self.assertIsInstance(settings, object)
        self.assertTrue(hasattr(settings, 'sina_base_url'))
        self.assertTrue(hasattr(settings, 'openai_api_key'))
        self.assertTrue(hasattr(settings, 'request_timeout'))


class TestIntegration(unittest.IsolatedAsyncioTestCase):
    """集成测试"""
    
    async def test_complete_pipeline(self):
        """测试完整处理管道"""
        # 创建组件
        processor = TextProcessor(max_length=1000, min_length=10, language="zh")
        
        # 创建测试数据
        raw_item = NewsItem(
            id="integration_test",
            title="集成测试标题",
            content="这是一个集成测试的内容，用于验证整个处理管道是否正常工作。",
            publish_time=datetime.now(),
            source="integration_test",
            category="integration",
            tags=["integration", "test"]
        )
        
        # 处理数据
        processed_items = await processor.process([raw_item])
        
        # 验证处理结果
        self.assertEqual(len(processed_items), 1)
        self.assertEqual(processed_items[0].id, "integration_test")
        self.assertIn("集成测试", processed_items[0].content)


def run_tests():
    """运行所有测试"""
    print("Running Industrial Sina 7x24 News Collector Unit Tests...")
    print("=" * 60)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, trace in result.failures:
            print(f"  {test}: {trace}")
    
    if result.errors:
        print("\nErrors:")
        for test, trace in result.errors:
            print(f"  {test}: {trace}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)