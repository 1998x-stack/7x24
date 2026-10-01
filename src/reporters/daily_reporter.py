"""
报告生成器模块
根据分析结果生成专业金融报告
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
from loguru import logger

from ..interfaces import IReporter, NewsItem


class DailyReporter(IReporter):
    """
    日报报告生成器
    生成每日金融新闻分析报告
    """
    
    def __init__(self, template_path: str = "templates/daily_report.md", 
                 output_dir: str = "./reports"):
        """
        初始化日报生成器
        
        Args:
            template_path: 报告模板路径
            output_dir: 输出目录
        """
        self.template_path = Path(template_path)
        self.output_dir = Path(output_dir)
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"DailyReporter initialized with template: {template_path}, output_dir: {output_dir}")
    
    def _generate_executive_summary(self, analysis_results: Dict[str, Any]) -> str:
        """
        生成执行摘要
        
        Args:
            analysis_results: 分析结果
            
        Returns:
            执行摘要文本
        """
        overall_score = analysis_results.get('overall_sentiment_score', 0.0)
        sentiment_dist = analysis_results.get('sentiment_distribution', {})
        
        sentiment_desc = "中性"
        if overall_score > 0.1:
            sentiment_desc = "积极"
        elif overall_score < -0.1:
            sentiment_desc = "消极"
        
        positive_count = sentiment_dist.get('positive', 0)
        negative_count = sentiment_dist.get('negative', 0)
        neutral_count = sentiment_dist.get('neutral', 0)
        
        summary = f"""
### 执行摘要

- **总体情绪**: {sentiment_desc} (综合得分: {overall_score:.2f})
- **新闻分布**: 积极 {positive_count} 条, 消极 {negative_count} 条, 中性 {neutral_count} 条
- **市场趋势**: {self._determine_market_trend(analysis_results)}
"""
        return summary
    
    def _determine_market_trend(self, analysis_results: Dict[str, Any]) -> str:
        """
        判断市场趋势
        
        Args:
            analysis_results: 分析结果
            
        Returns:
            市场趋势描述
        """
        overall_score = analysis_results.get('overall_sentiment_score', 0.0)
        trending_topics = analysis_results.get('trending_topics', [])
        
        if overall_score > 0.2:
            trend = "看涨"
        elif overall_score < -0.2:
            trend = "看跌"
        else:
            trend = "震荡"
        
        # 添加热门话题作为支撑
        if trending_topics:
            top_topic = trending_topics[0]['topic'] if trending_topics else "无"
            return f"{trend} (热门话题: {top_topic})"
        else:
            return trend
    
    def _generate_topic_breakdown(self, analysis_results: Dict[str, Any]) -> str:
        """
        生成话题分解
        
        Args:
            analysis_results: 分析结果
            
        Returns:
            话题分解文本
        """
        main_topics = analysis_results.get('main_topics', [])
        trending_topics = analysis_results.get('trending_topics', [])
        
        if not main_topics and not trending_topics:
            return "### 话题分解\n\n暂无话题数据。\n"
        
        breakdown = "### 话题分解\n\n"
        
        if main_topics:
            breakdown += "#### 主要话题\n\n"
            for i, topic in enumerate(main_topics[:5]):  # 只显示前5个
                topic_name = topic.get('name', '未知话题')
                relevance = topic.get('relevance_score', 0.0)
                description = topic.get('description', '无描述')
                breakdown += f"{i+1}. **{topic_name}** (相关性: {relevance:.2f})\n   - {description}\n\n"
        
        if trending_topics:
            breakdown += "#### 热门话题\n\n"
            for i, topic in enumerate(trending_topics[:5]):  # 只显示前5个
                topic_name = topic.get('topic', '未知话题')
                frequency = topic.get('frequency', 0)
                breakdown += f"{i+1}. **{topic_name}** (提及次数: {frequency})\n\n"
        
        return breakdown
    
    def _generate_significant_events(self, analysis_results: Dict[str, Any]) -> str:
        """
        生成重要事件
        
        Args:
            analysis_results: 分析结果
            
        Returns:
            重要事件文本
        """
        top_positive = analysis_results.get('top_positive_items', [])
        top_negative = analysis_results.get('top_negative_items', [])
        
        if not top_positive and not top_negative:
            return "### 重要事件\n\n暂无重要事件。\n"
        
        events = "### 重要事件\n\n"
        
        if top_positive:
            events += "#### 积极事件\n\n"
            for i, item in enumerate(top_positive[:3]):  # 只显示前3个
                events += f"{i+1}. **{item.get('title', '无标题')}**\n"
                events += f"   - 情感得分: {item.get('score', 0.0):+.2f}\n"
                events += f"   - 内容: {item.get('content_snippet', '无内容')}\n\n"
        
        if top_negative:
            events += "#### 消极事件\n\n"
            for i, item in enumerate(top_negative[:3]):  # 只显示前3个
                events += f"{i+1}. **{item.get('title', '无标题')}**\n"
                events += f"   - 情感得分: {item.get('score', 0.0):+.2f}\n"
                events += f"   - 内容: {item.get('content_snippet', '无内容')}\n\n"
        
        return events
    
    def _generate_risk_opportunity_analysis(self, analysis_results: Dict[str, Any]) -> str:
        """
        生成风险机会分析
        
        Args:
            analysis_results: 分析结果
            
        Returns:
            风险机会分析文本
        """
        # 从话题分析结果中获取信息
        topic_analysis = analysis_results.get('topic_analysis', {})
        risk_factors = topic_analysis.get('risk_factors', [])
        opportunity_areas = topic_analysis.get('opportunity_areas', [])
        
        analysis = "### 风险与机会分析\n\n"
        
        if risk_factors:
            analysis += "#### 风险因素\n\n"
            for factor in risk_factors[:5]:
                analysis += f"- {factor}\n"
            analysis += "\n"
        else:
            analysis += "#### 风险因素\n\n暂无明显风险因素\n\n"
        
        if opportunity_areas:
            analysis += "#### 机会领域\n\n"
            for area in opportunity_areas[:5]:
                analysis += f"- {area}\n"
            analysis += "\n"
        else:
            analysis += "#### 机会领域\n\n暂无明显机会领域\n\n"
        
        return analysis
    
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
        logger.info(f"Generating daily report for period {period_start} to {period_end}")
        
        # 生成报告内容
        report_content = f"""# 每日金融新闻分析报告

**报告时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

**统计时段**: {period_start.strftime('%Y年%m月%d日 %H:%M')} - {period_end.strftime('%Y年%m月%d日 %H:%M')}

---

{self._generate_executive_summary(analysis_results)}

---

{self._generate_topic_breakdown(analysis_results)}

---

{self._generate_significant_events(analysis_results)}

---

{self._generate_risk_opportunity_analysis(analysis_results)}

---

**数据来源**: 新浪7x24财经资讯
**分析时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}
"""
        
        # 生成文件名
        filename = f"daily_report_{period_end.strftime('%Y%m%d_%H%M')}.md"
        filepath = self.output_dir / filename
        
        # 写入文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"Daily report saved to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save report to {filepath}: {e}")
        
        return report_content


class WeeklyReporter(IReporter):
    """
    周报报告生成器
    生成每周金融新闻分析报告
    """
    
    def __init__(self, template_path: str = "templates/weekly_report.md", 
                 output_dir: str = "./reports"):
        """
        初始化周报生成器
        
        Args:
            template_path: 报告模板路径
            output_dir: 输出目录
        """
        self.template_path = Path(template_path)
        self.output_dir = Path(output_dir)
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"WeeklyReporter initialized with template: {template_path}, output_dir: {output_dir}")
    
    async def generate_report(self, analysis_results: Dict[str, Any], 
                            period_start: datetime, 
                            period_end: datetime) -> str:
        """
        生成周分析报告
        
        Args:
            analysis_results: 分析结果
            period_start: 统计周期开始时间
            period_end: 统计周期结束时间
            
        Returns:
            生成的报告内容
        """
        logger.info(f"Generating weekly report for period {period_start} to {period_end}")
        
        # 这里可以实现更详细的周报逻辑
        report_content = f"""# 每周金融新闻分析报告

**报告时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

**统计时段**: {period_start.strftime('%Y年%m月%d日 %H:%M')} - {period_end.strftime('%Y年%m月%d日 %H:%M')}

**本周要点**:
- 总体市场情绪: [待填充]
- 主要趋势: [待填充]
- 重要事件: [待填充]

**详细分析**:
[在此处插入详细分析内容]

**下周展望**:
[在此处插入市场展望]

---

**数据来源**: 新浪7x24财经资讯
**分析时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}
"""
        
        # 生成文件名
        filename = f"weekly_report_{period_end.strftime('%Y%m%d_%H%M')}.md"
        filepath = self.output_dir / filename
        
        # 写入文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"Weekly report saved to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save weekly report to {filepath}: {e}")
        
        return report_content


class TrendingTopicsReporter(IReporter):
    """
    热门话题报告生成器
    生成热门话题分析报告
    """
    
    def __init__(self, template_path: str = "templates/topics_report.md", 
                 output_dir: str = "./reports"):
        """
        初始化热门话题报告生成器
        
        Args:
            template_path: 报告模板路径
            output_dir: 输出目录
        """
        self.template_path = Path(template_path)
        self.output_dir = Path(output_dir)
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"TrendingTopicsReporter initialized with template: {template_path}, output_dir: {output_dir}")
    
    async def generate_report(self, analysis_results: Dict[str, Any], 
                            period_start: datetime, 
                            period_end: datetime) -> str:
        """
        生成热门话题报告
        
        Args:
            analysis_results: 分析结果
            period_start: 统计周期开始时间
            period_end: 统计周期结束时间
            
        Returns:
            生成的报告内容
        """
        logger.info(f"Generating trending topics report for period {period_start} to {period_end}")
        
        trending_topics = analysis_results.get('trending_topics', [])
        main_topics = analysis_results.get('main_topics', [])
        
        report_content = f"""# 热门话题分析报告

**报告时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

**统计时段**: {period_start.strftime('%Y年%m月%d日 %H:%M')} - {period_end.strftime('%Y年%m月%d日 %H:%M')}

## 热门话题排行

"""
        
        if trending_topics:
            for i, topic in enumerate(trending_topics[:10], 1):
                topic_name = topic.get('topic', '未知话题')
                frequency = topic.get('frequency', 0)
                report_content += f"{i}. **{topic_name}** - 提及次数: {frequency}\n"
        else:
            report_content += "暂无热门话题数据\n"
        
        report_content += "\n## 主要话题分析\n\n"
        
        if main_topics:
            for topic in main_topics[:5]:
                topic_name = topic.get('name', '未知话题')
                relevance = topic.get('relevance_score', 0.0)
                description = topic.get('description', '无描述')
                
                report_content += f"### {topic_name}\n"
                report_content += f"- 相关性评分: {relevance:.2f}\n"
                report_content += f"- 描述: {description}\n\n"
        else:
            report_content += "暂无主要话题分析\n"
        
        report_content += f"""
## 总结
- 本期共监测到 {len(trending_topics)} 个热门话题
- 主要关注领域: [待分析]
- 发展趋势: [待分析]

---

**数据来源**: 新浪7x24财经资讯
**分析时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}
"""
        
        # 生成文件名
        filename = f"topics_report_{period_end.strftime('%Y%m%d_%H%M')}.md"
        filepath = self.output_dir / filename
        
        # 写入文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"Trending topics report saved to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save trending topics report to {filepath}: {e}")
        
        return report_content