#!/usr/bin/env python3
"""
新浪财经 7×24 直播流数据采集客户端
Sina Finance 7x24 Live Feed Client — Playwright-based

依赖安装:
    pip install playwright loguru --break-system-packages
    playwright install chromium

用法示例:
    # 采集全部最新20条
    python sina7x24_playwright.py fetch --tag all --limit 20

    # 采集A股100条，保存JSON
    python sina7x24_playwright.py fetch --tag a_share --limit 100 --output a_share.json

    # 实时流模式，每60秒采集一次
    python sina7x24_playwright.py stream --tag all --interval 60

    # 批量采集多分类
    python sina7x24_playwright.py multi --tags all,a_share,macro --output news.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import csv
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from loguru import logger
from playwright.sync_api import sync_playwright, APIRequestContext, BrowserContext

# ─────────────────────────────────────────────────────────────────────────────
# 常量与配置
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://zhibo.sina.com.cn/api/zhibo/feed"
ZHIBO_ID = 152  # 财经 7×24 固定频道 ID

# 分类 tag_id 映射
TAG_MAP: dict[str, int] = {
    "all":           0,    # 全部
    "macro":         1,    # 宏观
    "industry":      2,    # 行业
    "company":       3,    # 公司
    "market":        5,    # 市场
    "other":         8,    # 其他
    "focus":         9,    # 焦点
    "a_share":       10,   # A股
    "international": 102,  # 国际
}

# 反向映射（tag_id → 名称）
TAG_NAME: dict[int, str] = {v: k for k, v in TAG_MAP.items()}
TAG_ZH: dict[int, str] = {
    0:   "全部",
    1:   "宏观",
    2:   "行业",
    3:   "公司",
    5:   "市场",
    8:   "其他",
    9:   "焦点",
    10:  "A股",
    102: "国际",
}

DEFAULT_HEADERS = {
    "Accept":          "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer":         "https://finance.sina.com.cn/7x24/",
    "X-Requested-With": "XMLHttpRequest",
}

# ─────────────────────────────────────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StockRef:
    """关联股票引用"""
    market: str
    symbol: str
    key: str   # 中文名称


@dataclass
class FeedItem:
    """单条新闻条目，经过清洗的结构化数据"""
    id: int
    tag_id: int
    tag_name: str
    content_type: int          # 0=纯文本 1=图文
    text: str                  # 正文
    images: list[str]          # 图片 URL 列表
    create_time: str           # "2026-03-06 00:48:08"
    update_time: str
    is_deleted: bool
    is_repeat: bool
    tags: list[str]            # ["国际", "市场"]
    stocks: list[StockRef]     # 关联股票
    doc_url: str               # 完整文章链接
    doc_id: str                # 文章 ID
    like_nums: int
    raw: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        d["stocks"] = [asdict(s) for s in self.stocks]
        return d


@dataclass
class FeedPage:
    """一页 Feed 响应"""
    items: list[FeedItem]
    max_id: int
    min_id: int
    total_num: int
    total_pages: int
    current_page: int
    server_time: str


# ─────────────────────────────────────────────────────────────────────────────
# JSONP 解析工具
# ─────────────────────────────────────────────────────────────────────────────

def strip_jsonp(text: str) -> dict:
    """
    将 JSONP 字符串转换为纯 JSON 字典。
    支持格式: callback({...}) 或直接的 {...}
    """
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    # 提取括号内的 JSON
    match = re.search(r'\((\{.*\})\)', text, re.DOTALL)
    if not match:
        raise ValueError(f"无法解析 JSONP 响应: {text[:100]}...")
    return json.loads(match.group(1))


# ─────────────────────────────────────────────────────────────────────────────
# 数据解析器
# ─────────────────────────────────────────────────────────────────────────────

def parse_ext(ext_str: str) -> tuple[list[StockRef], str, str]:
    """
    解析 ext 字段（二次 JSON 解析），返回 (stocks, doc_url, doc_id)
    """
    stocks: list[StockRef] = []
    doc_url = ""
    doc_id = ""
    if not ext_str:
        return stocks, doc_url, doc_id
    try:
        ext = json.loads(ext_str)
        for s in ext.get("stocks", []):
            stocks.append(StockRef(
                market=s.get("market", ""),
                symbol=s.get("symbol", ""),
                key=s.get("key", ""),
            ))
        doc_url = ext.get("docurl", "")
        doc_id  = ext.get("docid", "")
    except (json.JSONDecodeError, TypeError):
        pass
    return stocks, doc_url, doc_id


def parse_item(raw: dict, tag_id: int = 0) -> FeedItem:
    """将原始 API 字典解析为 FeedItem"""
    # 多媒体
    multimedia = raw.get("multimedia") or {}
    images: list[str] = []
    if isinstance(multimedia, dict):
        images = multimedia.get("img_url", [])

    # ext 解析
    stocks, doc_url, doc_id = parse_ext(raw.get("ext", ""))

    # docurl 优先用 item 本身的，备用 ext 里的
    if not doc_url:
        doc_url = raw.get("docurl", "")

    # 标签名列表
    tag_names = [t.get("name", "") for t in raw.get("tag", [])]

    return FeedItem(
        id=raw["id"],
        tag_id=tag_id,
        tag_name=TAG_ZH.get(tag_id, str(tag_id)),
        content_type=raw.get("type", 0),
        text=raw.get("rich_text", "").strip(),
        images=images,
        create_time=raw.get("create_time", ""),
        update_time=raw.get("update_time", ""),
        is_deleted=bool(raw.get("is_delete", 0)),
        is_repeat=raw.get("is_repeat", "0") == "1",
        tags=tag_names,
        stocks=stocks,
        doc_url=doc_url,
        doc_id=doc_id,
        like_nums=raw.get("like_nums", 0),
        raw=raw,
    )


def parse_response(data: dict, tag_id: int = 0) -> FeedPage:
    """解析完整 API 响应为 FeedPage"""
    feed_data = data["result"]["data"]["feed"]
    items = [
        parse_item(item, tag_id)
        for item in feed_data.get("list", [])
        if not item.get("is_delete", 0)  # 过滤软删除
    ]
    page_info = feed_data.get("page_info", {})
    return FeedPage(
        items=items,
        max_id=feed_data.get("max_id", 0),
        min_id=feed_data.get("min_id", 0),
        total_num=page_info.get("totalNum", 0),
        total_pages=page_info.get("totalPage", 0),
        current_page=page_info.get("page", 1),
        server_time=data["result"].get("timestamp", ""),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Playwright 客户端核心
# ─────────────────────────────────────────────────────────────────────────────

class Sina7x24Client:
    """
    新浪财经 7×24 直播流客户端（Playwright 驱动）

    使用方式（上下文管理器）:
        with Sina7x24Client() as client:
            page = client.fetch_page(tag_id=0)
            items = list(client.fetch_all(tag_id=10, limit=100))
    """

    def __init__(
        self,
        headless: bool = True,
        request_delay: float = 0.5,
        timeout: int = 15_000,
    ):
        self._headless = headless
        self._request_delay = request_delay
        self._timeout = timeout
        self._playwright = None
        self._browser = None
        self._context: Optional[BrowserContext] = None
        self._api: Optional[APIRequestContext] = None

    # ── 上下文管理 ──────────────────────────────────────────────────────────

    def __enter__(self) -> "Sina7x24Client":
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    def start(self):
        """启动 Playwright 浏览器上下文"""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self._headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            extra_http_headers={
                "Referer": "https://finance.sina.com.cn/",
            },
        )
        self._api = self._context.request
        logger.debug("Playwright 客户端已启动")

    def stop(self):
        """释放所有资源"""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        logger.debug("Playwright 客户端已关闭")

    # ── 底层 HTTP 请求 ────────────────────────────────────────────────────────

    def _get(self, params: dict) -> dict:
        """发起 API GET 请求，自动处理 JSONP 解包"""
        # 添加缓存破坏时间戳
        params["_"] = int(time.time() * 1000)

        response = self._api.get(
            BASE_URL,
            params=params,
            headers=DEFAULT_HEADERS,
            timeout=self._timeout,
        )
        if not response.ok:
            raise RuntimeError(
                f"HTTP {response.status}: {BASE_URL} params={params}"
            )

        raw_text = response.text()
        data = strip_jsonp(raw_text)

        status = data.get("result", {}).get("status", {})
        if status.get("code") != 0:
            raise RuntimeError(
                f"API 错误 code={status.get('code')}: {status.get('msg')}"
            )

        if self._request_delay > 0:
            time.sleep(self._request_delay)

        return data

    # ── 公开 API ─────────────────────────────────────────────────────────────

    def fetch_page(
        self,
        tag_id: int = 0,
        page: int = 1,
        pagesize: int = 20,
        cursor_id: Optional[int] = None,
        direction: str = "f",
    ) -> FeedPage:
        """
        拉取单页 Feed 数据。

        Args:
            tag_id:    分类标签 ID（见 TAG_MAP）
            page:      页码（传统翻页）
            pagesize:  每页条数
            cursor_id: 游标 ID（优先级高于 page，用于增量拉取）
            direction: "f"=更新的方向，"b"=更旧的方向

        Returns:
            FeedPage 对象
        """
        params: dict = {
            "zhibo_id": ZHIBO_ID,
            "tag_id":   tag_id,
            "page":     page,
            "page_size": pagesize,
            "pagesize": pagesize,
            "dire":     direction,
            "dpc":      1,
            "type":     0,
        }
        if cursor_id is not None:
            params["id"] = cursor_id

        data = self._get(params)
        feed_page = parse_response(data, tag_id)
        logger.info(
            f"[tag={TAG_ZH.get(tag_id, tag_id)}] page={page} "
            f"获取 {len(feed_page.items)} 条 "
            f"(max_id={feed_page.max_id}, min_id={feed_page.min_id})"
        )
        return feed_page

    def fetch_all(
        self,
        tag_id: int = 0,
        limit: int = 100,
        pagesize: int = 20,
        start_page: int = 1,
    ) -> Iterator[FeedItem]:
        """
        批量翻页采集，逐条 yield FeedItem。

        Args:
            tag_id:     分类标签 ID
            limit:      最大采集条数（-1=不限）
            pagesize:   每页条数
            start_page: 起始页码

        Yields:
            FeedItem 实例
        """
        collected = 0
        page = start_page

        while True:
            feed_page = self.fetch_page(tag_id=tag_id, page=page, pagesize=pagesize)

            for item in feed_page.items:
                if limit > 0 and collected >= limit:
                    return
                yield item
                collected += 1

            # 无更多数据
            if page >= feed_page.total_pages or not feed_page.items:
                logger.info(f"已达末页（page={page}/{feed_page.total_pages}）")
                break

            page += 1

    def fetch_latest(
        self,
        tag_id: int = 0,
        since_id: Optional[int] = None,
        pagesize: int = 20,
    ) -> FeedPage:
        """
        增量拉取最新数据（游标模式）。

        Args:
            tag_id:   分类标签 ID
            since_id: 上次采集的最大 ID（首次传 None）
            pagesize: 每页条数

        Returns:
            FeedPage（仅包含比 since_id 更新的条目）
        """
        return self.fetch_page(
            tag_id=tag_id,
            page=1,
            pagesize=pagesize,
            cursor_id=since_id,
            direction="f",
        )

    def stream(
        self,
        tag_id: int = 0,
        interval: float = 60.0,
        pagesize: int = 20,
    ) -> Iterator[FeedItem]:
        """
        实时流模式：按 interval 秒间隔持续轮询，逐条 yield 新条目。

        Args:
            tag_id:   分类标签 ID
            interval: 轮询间隔（秒）
            pagesize: 每次拉取条数

        Yields:
            FeedItem（仅新增，自动去重）
        """
        seen_ids: set[int] = set()
        max_id: Optional[int] = None

        logger.info(
            f"[stream] 启动实时采集 tag={TAG_ZH.get(tag_id, tag_id)} "
            f"间隔={interval}s"
        )

        while True:
            try:
                feed_page = self.fetch_latest(
                    tag_id=tag_id,
                    since_id=max_id,
                    pagesize=pagesize,
                )

                new_items = [
                    item for item in feed_page.items
                    if item.id not in seen_ids
                ]

                for item in sorted(new_items, key=lambda x: x.id):
                    seen_ids.add(item.id)
                    yield item

                if feed_page.max_id > (max_id or 0):
                    max_id = feed_page.max_id

            except Exception as e:
                logger.warning(f"[stream] 请求失败: {e}，{interval}s 后重试")

            time.sleep(interval)

    def fetch_multi_tags(
        self,
        tag_ids: list[int],
        limit_per_tag: int = 50,
    ) -> dict[int, list[FeedItem]]:
        """
        批量采集多个分类。

        Args:
            tag_ids:       分类 ID 列表
            limit_per_tag: 每个分类最大条数

        Returns:
            {tag_id: [FeedItem, ...]}
        """
        result: dict[int, list[FeedItem]] = {}
        for tid in tag_ids:
            logger.info(f"开始采集分类: {TAG_ZH.get(tid, tid)}")
            items = list(self.fetch_all(tag_id=tid, limit=limit_per_tag))
            result[tid] = items
            logger.info(f"分类 {TAG_ZH.get(tid, tid)} 完成，共 {len(items)} 条")
        return result


# ─────────────────────────────────────────────────────────────────────────────
# 数据导出工具
# ─────────────────────────────────────────────────────────────────────────────

class DataExporter:
    """支持 JSON / JSONL / CSV / Markdown 格式导出"""

    @staticmethod
    def to_json(items: list[FeedItem], path: str, indent: int = 2):
        """导出为 JSON 数组"""
        Path(path).write_text(
            json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=indent),
            encoding="utf-8",
        )
        logger.info(f"已导出 {len(items)} 条 → {path}")

    @staticmethod
    def to_jsonl(items: list[FeedItem], path: str):
        """导出为 JSONL（每行一条 JSON）"""
        with open(path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")
        logger.info(f"已导出 {len(items)} 条 → {path}")

    @staticmethod
    def append_jsonl(item: FeedItem, path: str):
        """追加单条到 JSONL 文件（适合实时流写入）"""
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")

    @staticmethod
    def to_csv(items: list[FeedItem], path: str):
        """导出为 CSV"""
        if not items:
            logger.warning("无数据可导出")
            return
        fieldnames = [
            "id", "tag_name", "create_time", "text",
            "tags", "stocks", "doc_url", "like_nums",
            "is_deleted", "is_repeat",
        ]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                writer.writerow({
                    "id":         item.id,
                    "tag_name":   item.tag_name,
                    "create_time": item.create_time,
                    "text":       item.text,
                    "tags":       "|".join(item.tags),
                    "stocks":     "|".join(s.key for s in item.stocks),
                    "doc_url":    item.doc_url,
                    "like_nums":  item.like_nums,
                    "is_deleted": item.is_deleted,
                    "is_repeat":  item.is_repeat,
                })
        logger.info(f"已导出 {len(items)} 条 → {path}")

    @staticmethod
    def to_markdown(items: list[FeedItem], path: str):
        """导出为 Markdown 报告"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"# 新浪财经 7×24 快讯",
            f"",
            f"> 采集时间: {now} | 共 {len(items)} 条",
            f"",
        ]
        for item in items:
            stocks_str = "  ".join(f"`{s.key}`" for s in item.stocks) if item.stocks else ""
            tags_str   = " ".join(f"#{t}" for t in item.tags) if item.tags else ""
            lines += [
                f"---",
                f"",
                f"**[{item.create_time}]** {tags_str} {stocks_str}",
                f"",
                item.text,
                f"",
            ]
            if item.doc_url:
                lines.append(f"[阅读全文]({item.doc_url})")
                lines.append("")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"已导出 {len(items)} 条 → {path}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI 命令行接口
# ─────────────────────────────────────────────────────────────────────────────

def resolve_tag(tag_str: str) -> int:
    """将 tag 名称或数字字符串解析为 tag_id"""
    tag_str = tag_str.strip().lower()
    if tag_str in TAG_MAP:
        return TAG_MAP[tag_str]
    try:
        return int(tag_str)
    except ValueError:
        raise ValueError(
            f"未知分类: {tag_str!r}。"
            f"有效分类: {', '.join(TAG_MAP.keys())} 或数字 ID。"
        )


def cmd_fetch(args):
    """单次批量采集命令"""
    tag_id = resolve_tag(args.tag)
    fmt    = args.format or _infer_format(args.output)

    logger.info(f"采集分类: {TAG_ZH.get(tag_id)} (tag_id={tag_id}), 上限: {args.limit}")

    with Sina7x24Client(request_delay=args.delay) as client:
        items = list(client.fetch_all(tag_id=tag_id, limit=args.limit))

    logger.success(f"采集完成，共 {len(items)} 条")

    if args.output:
        _export(items, args.output, fmt)
    else:
        _print_items(items, args.limit)


def cmd_stream(args):
    """实时流采集命令"""
    tag_id = resolve_tag(args.tag)
    fmt    = args.format or _infer_format(args.output)

    logger.info(
        f"启动实时流 | 分类: {TAG_ZH.get(tag_id)} | "
        f"间隔: {args.interval}s | 输出: {args.output or 'stdout'}"
    )

    with Sina7x24Client(request_delay=args.delay) as client:
        count = 0
        for item in client.stream(tag_id=tag_id, interval=args.interval):
            count += 1
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] #{count} [{item.create_time}] {item.text[:80]}...")
            if args.output:
                if fmt == "jsonl":
                    DataExporter.append_jsonl(item, args.output)
                elif fmt == "json":
                    # 流模式下 JSON 只能用 JSONL
                    DataExporter.append_jsonl(item, args.output)


def cmd_multi(args):
    """多分类批量采集命令"""
    tag_ids = [resolve_tag(t) for t in args.tags.split(",")]
    fmt     = args.format or _infer_format(args.output)

    with Sina7x24Client(request_delay=args.delay) as client:
        results = client.fetch_multi_tags(tag_ids, limit_per_tag=args.limit)

    all_items: list[FeedItem] = []
    for items in results.values():
        all_items.extend(items)

    logger.success(f"多分类采集完成，合计 {len(all_items)} 条")

    if args.output:
        _export(all_items, args.output, fmt)
    else:
        _print_items(all_items, 20)


# ── 辅助函数 ─────────────────────────────────────────────────────────────────

def _infer_format(path: Optional[str]) -> str:
    if not path:
        return "json"
    ext = Path(path).suffix.lower()
    return {"json": "json", ".jsonl": "jsonl", ".csv": "csv", ".md": "markdown"}.get(ext, "json")


def _export(items: list[FeedItem], path: str, fmt: str):
    exp = DataExporter()
    dispatch = {
        "json":     exp.to_json,
        "jsonl":    exp.to_jsonl,
        "csv":      exp.to_csv,
        "markdown": exp.to_markdown,
    }
    fn = dispatch.get(fmt, exp.to_json)
    fn(items, path)


def _print_items(items: list[FeedItem], limit: int):
    for i, item in enumerate(items[:limit]):
        stocks = " ".join(s.key for s in item.stocks) if item.stocks else "-"
        print(
            f"[{item.id}] {item.create_time} "
            f"[{'/'.join(item.tags)}] {stocks}\n"
            f"  {item.text[:100]}\n"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="新浪财经 7×24 直播流采集工具（Playwright 驱动）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
分类标识（--tag 参数）:
  {'   '.join(TAG_MAP.keys())}
  或直接传数字 tag_id

示例:
  # 采集A股最新100条保存为 JSON
  python {Path(__file__).name} fetch --tag a_share --limit 100 --output a_share.json

  # 实时流，每30秒采集一次，写入 JSONL
  python {Path(__file__).name} stream --tag all --interval 30 --output news.jsonl

  # 同时采集多个分类
  python {Path(__file__).name} multi --tags all,macro,international --output combined.jsonl
        """,
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    # ── fetch ──
    p_fetch = sub.add_parser("fetch", help="单次批量采集")
    p_fetch.add_argument("--tag",    default="all", help="分类标识或 tag_id")
    p_fetch.add_argument("--limit",  type=int, default=20, help="最大条数（-1=不限）")
    p_fetch.add_argument("--output", help="输出文件路径（.json/.jsonl/.csv/.md）")
    p_fetch.add_argument("--format", choices=["json","jsonl","csv","markdown"], help="输出格式")
    p_fetch.add_argument("--delay",  type=float, default=0.5, help="请求间隔秒数")
    p_fetch.set_defaults(func=cmd_fetch)

    # ── stream ──
    p_stream = sub.add_parser("stream", help="实时流模式（持续运行）")
    p_stream.add_argument("--tag",      default="all", help="分类标识或 tag_id")
    p_stream.add_argument("--interval", type=float, default=60.0, help="轮询间隔（秒）")
    p_stream.add_argument("--output",   help="输出文件（追加 JSONL 格式）")
    p_stream.add_argument("--format",   choices=["jsonl","json"], default="jsonl")
    p_stream.add_argument("--delay",    type=float, default=0.3)
    p_stream.set_defaults(func=cmd_stream)

    # ── multi ──
    p_multi = sub.add_parser("multi", help="批量采集多个分类")
    p_multi.add_argument("--tags",   default="all,a_share,macro,international",
                         help="逗号分隔的分类列表")
    p_multi.add_argument("--limit",  type=int, default=50, help="每个分类最大条数")
    p_multi.add_argument("--output", help="输出文件路径")
    p_multi.add_argument("--format", choices=["json","jsonl","csv","markdown"])
    p_multi.add_argument("--delay",  type=float, default=0.5)
    p_multi.set_defaults(func=cmd_multi)

    return parser


def main():
    # 日志配置
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        level="INFO",
    )

    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
