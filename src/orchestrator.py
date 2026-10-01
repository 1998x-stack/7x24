"""
主协调器模块
负责整个新闻收集、处理、分析和报告流程的编排
"""

import asyncio
import sys
import traceback
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger

# Add the src directory to the path to enable imports
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Handle import based on execution context
try:
    from src.interfaces import ICollector, IProcessor, IAnalyzer, IReporter, IStorage, NewsItem
    from src.config.settings import settings
except ImportError:
    # For when run as script
    try:
        from interfaces import ICollector, IProcessor, IAnalyzer, IReporter, IStorage, NewsItem
        from config.settings import settings
    except ImportError:
        # Final fallback
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.dirname(current_dir)
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        from interfaces import ICollector, IProcessor, IAnalyzer, IReporter, IStorage, NewsItem
        from config.settings import settings


class NewsCollectionOrchestrator:
    """
    新闻收集协调器
    协调整个新闻收集、处理、分析和报告流程
    """
    
    def __init__(self, 
                 collector: ICollector,
                 processor: IProcessor,
                 analyzer: IAnalyzer,
                 reporter: IReporter,
                 storage: IStorage):
        """
        初始化协调器
        
        Args:
            collector: 新闻收集器
            processor: 新闻处理器
            analyzer: 新闻分析器
            reporter: 报告生成器
            storage: 存储组件
        """
        self.collector = collector
        self.processor = processor
        self.analyzer = analyzer
        self.reporter = reporter
        self.storage = storage
        
        # 设置异常处理钩子
        sys.excepthook = self._handle_global_exception
        
        logger.info("NewsCollectionOrchestrator initialized")
    
    def _handle_global_exception(self, exc_type, exc_value, exc_traceback):
        """
        全局异常处理器
        
        Args:
            exc_type: 异常类型
            exc_value: 异常值
            exc_traceback: 异常追踪信息
        """
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        error_message = repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.error(f"Global exception occurred: {error_message}")
    
    async def collect_process_store(self, 
                                  category: str = "全部", 
                                  count: int = 20) -> List[NewsItem]:
        """
        收集、处理并存储新闻数据
        
        Args:
            category: 新闻分类
            count: 收集数量
            
        Returns:
            处理后的新闻项目列表
        """
        logger.info(f"Starting collection process for category: {category}, count: {count}")
        
        try:
            # 1. 收集新闻
            logger.info("Step 1: Collecting news items")
            raw_items = await self.collector.collect(category, count)
            logger.info(f"Collected {len(raw_items)} raw news items")
            
            if not raw_items:
                logger.warning("No news items collected")
                return []
            
            # 2. 处理新闻
            logger.info("Step 2: Processing news items")
            processed_items = await self.processor.process(raw_items)
            logger.info(f"Processed {len(processed_items)} news items")
            
            # 3. 存储新闻
            logger.info("Step 3: Storing news items")
            storage_success = await self.storage.save(processed_items)
            if storage_success:
                logger.info("News items stored successfully")
            else:
                logger.error("Failed to store news items")
            
            logger.info(f"Collection process completed successfully, {len(processed_items)} items processed")
            return processed_items
            
        except Exception as e:
            logger.error(f"Error in collection process: {e}")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error_message = repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
            logger.error(f"Detailed error: {error_message}")
            return []
    
    async def analyze_news(self, items: List[NewsItem]) -> Dict[str, Any]:
        """
        分析新闻数据
        
        Args:
            items: 待分析的新闻项目列表
            
        Returns:
            分析结果字典
        """
        logger.info(f"Starting analysis for {len(items)} news items")
        
        try:
            analysis_results = await self.analyzer.analyze(items)
            logger.info("Analysis completed successfully")
            return analysis_results
        except Exception as e:
            logger.error(f"Error in analysis: {e}")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error_message = repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
            logger.error(f"Detailed error: {error_message}")
            return {}
    
    async def generate_report(self, 
                            analysis_results: Dict[str, Any],
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
        logger.info(f"Generating report for period {period_start} to {period_end}")
        
        try:
            report_content = await self.reporter.generate_report(analysis_results, period_start, period_end)
            logger.info("Report generated successfully")
            return report_content
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error_message = repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
            logger.error(f"Detailed error: {error_message}")
            return ""
    
    async def run_full_cycle(self, 
                           category: str = "全部", 
                           count: int = 20) -> Dict[str, Any]:
        """
        运行完整的收集-处理-分析-报告周期
        
        Args:
            category: 新闻分类
            count: 处理数量
            
        Returns:
            完整周期的结果字典
        """
        logger.info(f"Starting full cycle for category: {category}, count: {count}")
        
        start_time = datetime.now()
        
        try:
            # 收集和处理
            items = await self.collect_process_store(category, count)
            
            if not items:
                logger.warning("No items to analyze, skipping analysis and reporting")
                return {
                    'success': True,
                    'items_processed': 0,
                    'analysis_results': {},
                    'report_generated': False,
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            
            # 分析
            analysis_results = await self.analyze_news(items)
            
            # 生成报告（使用当前时间段）
            period_end = datetime.now()
            period_start = period_end - timedelta(hours=24)  # 24小时时间段
            report_content = await self.generate_report(analysis_results, period_start, period_end)
            
            result = {
                'success': True,
                'items_processed': len(items),
                'analysis_results': analysis_results,
                'report_generated': bool(report_content),
                'execution_time': (datetime.now() - start_time).total_seconds()
            }
            
            logger.info(f"Full cycle completed successfully in {result['execution_time']:.2f} seconds")
            return result
            
        except Exception as e:
            logger.error(f"Error in full cycle: {e}")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error_message = repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
            logger.error(f"Detailed error: {error_message}")
            
            return {
                'success': False,
                'items_processed': 0,
                'analysis_results': {},
                'report_generated': False,
                'execution_time': (datetime.now() - start_time).total_seconds(),
                'error': str(e)
            }
    
    async def run_continuous_collection(self, 
                                      interval_minutes: int = 30,
                                      category: str = "全部",
                                      count: int = 20) -> None:
        """
        运行连续收集任务
        
        Args:
            interval_minutes: 收集间隔（分钟）
            category: 新闻分类
            count: 每次收集数量
        """
        logger.info(f"Starting continuous collection for category: {category}, interval: {interval_minutes} minutes")
        
        while True:
            try:
                result = await self.run_full_cycle(category, count)
                
                if result['success']:
                    logger.info(f"Cycle completed successfully. Processed {result['items_processed']} items.")
                else:
                    logger.error(f"Cycle failed: {result.get('error', 'Unknown error')}")
                
                # 等待指定的时间间隔
                await asyncio.sleep(interval_minutes * 60)
                
            except asyncio.CancelledError:
                logger.info("Continuous collection was cancelled")
                break
            except Exception as e:
                logger.error(f"Error in continuous collection: {e}")
                # 发生错误后等待一段时间再重试
                await asyncio.sleep(60)  # 1分钟后重试
    
    async def run_daily_report_cycle(self, 
                                   report_hour: int = 8,
                                   category: str = "全部",
                                   count: int = 100) -> None:
        """
        运行每日报告生成循环
        
        Args:
            report_hour: 生成报告的小时（24小时制）
            category: 新闻分类
            count: 分析的数量
        """
        logger.info(f"Starting daily report cycle, report hour: {report_hour}")
        
        while True:
            try:
                now = datetime.now()
                
                # 计算今天报告时间
                report_time_today = now.replace(hour=report_hour, minute=0, second=0, microsecond=0)
                
                # 如果已经过了今天的报告时间，则安排到明天
                if now > report_time_today:
                    report_time_today = report_time_today + timedelta(days=1)
                
                # 计算等待时间
                wait_seconds = (report_time_today - now).total_seconds()
                
                logger.info(f"Next report scheduled for: {report_time_today}")
                logger.info(f"Waiting {wait_seconds:.0f} seconds until report time")
                
                # 等待到报告时间
                await asyncio.sleep(wait_seconds)
                
                # 在报告时间收集和分析数据
                logger.info("Time for daily report generation")
                
                # 收集过去24小时的数据
                items = await self.collect_process_store(category, count)
                
                if items:
                    # 分析过去24小时的数据
                    analysis_results = await self.analyze_news(items)
                    
                    # 生成报告（针对过去24小时）
                    period_end = datetime.now()
                    period_start = period_end - timedelta(hours=24)
                    report_content = await self.generate_report(analysis_results, period_start, period_end)
                    
                    logger.info("Daily report generated successfully")
                else:
                    logger.warning("No items collected for daily report")
                
                # 额外等待1分钟，确保不会重复生成
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info("Daily report cycle was cancelled")
                break
            except Exception as e:
                logger.error(f"Error in daily report cycle: {e}")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                error_message = repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
                logger.error(f"Detailed error: {error_message}")
                
                # 发生错误后等待1小时再重试
                await asyncio.sleep(3600)


class PluggableNewsSystem:
    """
    可插拔新闻系统
    通过工厂模式创建和管理不同类型的组件
    """
    
    def __init__(self):
        """初始化可插拔新闻系统"""
        self.orchestrator: Optional[NewsCollectionOrchestrator] = None
        logger.info("PluggableNewsSystem initialized")
    
    async def setup_with_factory(self, factory, config: Dict[str, Any]) -> None:
        """
        使用工厂设置系统组件
        
        Args:
            factory: 组件工厂
            config: 组件配置
        """
        logger.info("Setting up system with factory")
        
        # 创建各个组件
        collector = factory.create_collector(config.get('collector', {}))
        processor = factory.create_processor(config.get('processor', {}))
        analyzer = factory.create_analyzer(config.get('analyzer', {}))
        reporter = factory.create_reporter(config.get('reporter', {}))
        storage = factory.create_storage(config.get('storage', {}))
        
        # 创建协调器
        self.orchestrator = NewsCollectionOrchestrator(
            collector=collector,
            processor=processor,
            analyzer=analyzer,
            reporter=reporter,
            storage=storage
        )
        
        logger.info("System components created successfully")
    
    async def run_continuous_mode(self, 
                                 interval_minutes: int = 30,
                                 category: str = "全部", 
                                 count: int = 20) -> None:
        """
        运行连续模式
        
        Args:
            interval_minutes: 收集间隔（分钟）
            category: 新闻分类
            count: 每次收集数量
        """
        if not self.orchestrator:
            logger.error("Orchestrator not initialized")
            return
        
        logger.info("Starting continuous mode")
        await self.orchestrator.run_continuous_collection(interval_minutes, category, count)
    
    async def run_daily_report_mode(self, 
                                   report_hour: int = 8,
                                   category: str = "全部",
                                   count: int = 100) -> None:
        """
        运行每日报告模式
        
        Args:
            report_hour: 生成报告的小时（24小时制）
            category: 新闻分类
            count: 分析的数量
        """
        if not self.orchestrator:
            logger.error("Orchestrator not initialized")
            return
        
        logger.info("Starting daily report mode")
        await self.orchestrator.run_daily_report_cycle(report_hour, category, count)
    
    async def run_single_cycle(self, 
                              category: str = "全部", 
                              count: int = 20) -> Dict[str, Any]:
        """
        运行单次周期
        
        Args:
            category: 新闻分类
            count: 处理数量
            
        Returns:
            周期执行结果
        """
        if not self.orchestrator:
            logger.error("Orchestrator not initialized")
            return {'success': False, 'error': 'Orchestrator not initialized'}
        
        logger.info("Running single collection cycle")
        return await self.orchestrator.run_full_cycle(category, count)