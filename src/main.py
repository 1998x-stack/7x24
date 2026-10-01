"""
主应用程序入口
工业级新浪7x24金融新闻收集分析系统
"""

import asyncio
import argparse
import sys
import traceback
import os
from datetime import datetime
from loguru import logger

# Add the src directory to the path
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import modules
from src.factories import SinaCollectorFactory, factory_registry
from src.config.settings import settings

# Import orchestrator separately to handle import issues
import importlib
orchestrator_module = importlib.import_module('src.orchestrator')
PluggableNewsSystem = orchestrator_module.PluggableNewsSystem


def setup_logger():
    """设置日志记录器"""
    # 移除默认处理器并添加新的处理器
    logger.remove()
    
    # 添加控制台日志
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level
    )
    
    # 添加文件日志
    logger.add(
        f"{settings.log_dir}/sina_collector_{datetime.now().strftime('%Y%m%d')}.log",
        rotation="1 day",
        retention=f"{settings.log_retention_days} days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.log_level
    )


async def main():
    """主异步入口函数"""
    # 设置日志
    setup_logger()
    
    logger.info("Industrial Sina 7x24 News Collector Starting...")
    logger.info(f"Configuration loaded: data_dir={settings.data_dir}, report_dir={settings.report_output_dir}")
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='Industrial Sina 7x24 News Collector')
    parser.add_argument('--mode', choices=['single', 'continuous', 'daily-report'], 
                       default='single', help='运行模式')
    parser.add_argument('--category', default='全部', help='新闻分类')
    parser.add_argument('--count', type=int, default=20, help='处理数量')
    parser.add_argument('--interval', type=int, default=30, help='收集间隔（分钟）')
    parser.add_argument('--report-hour', type=int, default=8, help='报告生成小时（24小时制）')
    
    args = parser.parse_args()
    
    # 创建工厂并注册
    factory = SinaCollectorFactory(settings)
    factory_registry.register_factory('sina', factory)
    
    # 创建可插拔新闻系统
    system = PluggableNewsSystem()
    
    # 系统配置
    config = {
        'collector': {
            'base_url': settings.sina_base_url,
            'timeout': settings.request_timeout
        },
        'processor': {
            'max_length': 1000,
            'min_length': 10,
            'language': 'zh'
        },
        'analyzer': {
            'model_name': settings.openai_model,
            'api_key': settings.openai_api_key,
            'base_url': settings.openai_base_url
        },
        'reporter': {
            'template_path': './templates/daily_report.md',
            'output_dir': settings.report_output_dir
        },
        'storage': {
            'type': 'json',  # 可以改为 'neo4j' 如果需要图数据库
            'data_dir': settings.data_dir
        }
    }
    
    try:
        # 设置系统组件
        await system.setup_with_factory(factory, config)
        
        logger.info(f"System initialized in {args.mode} mode")
        
        if args.mode == 'single':
            # 运行单次收集周期
            result = await system.run_single_cycle(args.category, args.count)
            logger.info(f"Single cycle completed: {result}")
            
        elif args.mode == 'continuous':
            # 运行连续收集模式
            logger.info("Starting continuous collection mode...")
            await system.run_continuous_mode(args.interval, args.category, args.count)
            
        elif args.mode == 'daily-report':
            # 运行每日报告模式
            logger.info("Starting daily report mode...")
            await system.run_daily_report_mode(args.report_hour, args.category, args.count)
            
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        exc_type, exc_value, exc_traceback = sys.exc_info()
        error_message = repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.error(f"Detailed error: {error_message}")
    finally:
        logger.info("Industrial Sina 7x24 News Collector Shutting Down...")


def run_as_script():
    """作为脚本运行"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_as_script()