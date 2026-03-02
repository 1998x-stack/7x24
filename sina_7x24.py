"""
新浪财经 7×24 小时资讯流 完整 Python 客户端
支持: 多分类/游标分页/增量拉取/实时监控/JSON/CSV/SQLite 导出
依赖: pip install requests
"""

import re, json, time, csv, sqlite3, logging
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, Generator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("sina7x24")

BASE_URL = "https://zhibo.sina.com.cn/api/zhibo/feed"
ZHIBO_ID = 152  # 财经 7x24 直播间固定值

TAGS = {
    "全部": 0,  "宏观": 1,   "行业": 2,   "公司": 3,
    "市场": 5,  "其他": 8,   "焦点": 9,   "A股":  10,
    "国际": 102, "两会": 110, "原创": 202,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    "Referer": "https://finance.sina.com.cn/",
}

# ─── 数据模型 ─────────────────────────────────────────

@dataclass
class StockRef:
    market: str   # cn/us/hk/fund/worldIndex/foreign/commodity/global
    symbol: str   # 代码，如 sh600111
    key:    str   # 显示名，如 北方稀土

@dataclass
class FeedItem:
    id: int;               create_time: str;   update_time: str
    rich_text: str;        type: int;          tags: list
    like_nums: int;        is_delete: int
    doc_url: str;          doc_id: str
    stocks: list;          images: list;       comment_total: int

    @property
    def text(self) -> str:
        """去除 HTML 标签的纯文字"""
        return re.sub(r"<[^>]+>", "", self.rich_text).strip()

    @property
    def datetime_obj(self) -> datetime:
        return datetime.strptime(self.create_time, "%Y-%m-%d %H:%M:%S")

    @property
    def tag_names(self) -> list:
        return [t["name"] for t in self.tags]

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update({"tag_names": self.tag_names, "text": self.text})
        return d

# ─── 解析工具 ─────────────────────────────────────────

def _strip_jsonp(text: str) -> str:
    """移除 JSONP 包装"""
    m = re.match(r"^[^(]+\((.+)\);\s*$", text, re.DOTALL)
    return m.group(1) if m else text

def _parse_item(raw: dict) -> FeedItem:
    ext = {}
    try:
        ext = json.loads(raw.get("ext", "{}"))
    except Exception:
        pass
    stocks = [StockRef(s.get("market",""), s.get("symbol",""), s.get("key",""))
              for s in ext.get("stocks", [])]
    mm = raw.get("multimedia") or {}
    images = mm.get("img_url", []) if isinstance(mm, dict) else []
    cl = raw.get("comment_list") or {}
    return FeedItem(
        id=raw["id"],
        create_time=raw.get("create_time", ""),
        update_time=raw.get("update_time", ""),
        rich_text=raw.get("rich_text", ""),
        type=raw.get("type", 0),
        tags=raw.get("tag", []),
        like_nums=raw.get("like_nums", 0),
        is_delete=raw.get("is_delete", 0),
        doc_url=raw.get("docurl", "") or ext.get("docurl", ""),
        doc_id=ext.get("docid", ""),
        stocks=stocks,
        images=images,
        comment_total=cl.get("total", 0),
    )

# ─── 核心客户端 ───────────────────────────────────────

class Sina7x24Client:
    """
    新浪财经 7x24 完整 API 客户端

    用法:
        client = Sina7x24Client()

        # 获取最新20条A股资讯
        items = client.get_latest(tag="A股", count=20)

        # 迭代获取最多100条国际资讯（自动翻页）
        for item in client.iter_latest(tag="国际", max_items=100):
            print(item.create_time, item.text[:60])

        # 实时监控
        client.monitor(tag="全部", interval=30)
    """

    def __init__(self, delay: float = 0.5, timeout: int = 15):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.delay   = delay
        self.timeout = timeout

    def _request(self, params: dict) -> dict:
        params["_"] = int(time.time() * 1000)
        r = self.session.get(BASE_URL, params=params, timeout=self.timeout)
        r.raise_for_status()
        return json.loads(_strip_jsonp(r.text))

    def _fetch_page(self, tag_id: int, cursor_id: int,
                    page: int = 1, page_size: int = 20):
        """获取单页，返回 (items, page_info)"""
        params = dict(page=page, page_size=page_size, pagesize=page_size,
                      zhibo_id=ZHIBO_ID, tag_id=tag_id, dire="f",
                      dpc=1, id=cursor_id, type=0)
        data = self._request(params)
        result = data["result"]
        if result["status"]["code"] != 0:
            raise RuntimeError(f"API 错误: {result['status']}")
        feed      = result["data"]["feed"]
        page_info = feed.get("page_info", {})
        page_info.update({"min_id": feed.get("min_id", 0),
                          "max_id": feed.get("max_id", 0)})
        items = [_parse_item(r) for r in feed.get("list", [])
                 if not r.get("is_delete")]
        return items, page_info

    def get_latest(self, tag: str = "全部", count: int = 20) -> list:
        """获取最新 N 条资讯（单次，不翻页）"""
        items, _ = self._fetch_page(TAGS.get(tag, 0), 9_999_999,
                                    page_size=min(count, 50))
        return items[:count]

    def iter_latest(self, tag: str = "全部", max_items: int = 100,
                    since_id: Optional[int] = None,
                    since_time: Optional[datetime] = None) -> Generator:
        """迭代获取资讯，自动翻页，支持 ID / 时间过滤"""
        tag_id    = TAGS.get(tag, 0)
        cursor_id = 9_999_999
        total     = 0
        page      = 1
        while total < max_items:
            try:
                items, pi = self._fetch_page(tag_id, cursor_id, page=page)
            except Exception as e:
                logger.error(f"请求失败: {e}"); break
            if not items:
                break
            for item in items:
                if since_id   and item.id           <= since_id:   return
                if since_time and item.datetime_obj <  since_time: return
                yield item
                total += 1
                if total >= max_items: return
            if page >= pi.get("totalPage", 1):
                new_cur = pi.get("min_id", 0)
                if not new_cur or new_cur >= cursor_id: break
                cursor_id = new_cur; page = 1
            else:
                page += 1
            time.sleep(self.delay)

    def get_all_tags(self, tags: Optional[list] = None,
                     count_per_tag: int = 20) -> dict:
        """批量获取多分类资讯"""
        tags = tags or list(TAGS.keys())
        result = {}
        for tag in tags:
            logger.info(f"获取 [{tag}]...")
            try:
                result[tag] = self.get_latest(tag=tag, count=count_per_tag)
                logger.info(f"  ✓ {len(result[tag])} 条")
            except Exception as e:
                logger.error(f"  ✗ {e}"); result[tag] = []
            time.sleep(self.delay)
        return result

    def monitor(self, tag: str = "全部", interval: int = 30,
                callback=None) -> None:
        """实时监控模式（无限轮询，Ctrl+C 停止）"""
        last_id = None
        logger.info(f"监控 [{tag}] 开始，间隔 {interval}s （Ctrl+C 停止）")
        while True:
            try:
                items     = self.get_latest(tag=tag, count=20)
                new_items = [i for i in items
                             if last_id is None or i.id > last_id]
                if new_items:
                    last_id = max(i.id for i in new_items)
                    for item in reversed(new_items):
                        logger.info(f"[{item.id}] {item.create_time} "
                                    f"{item.text[:80]}")
                        if callback: callback(item)
            except KeyboardInterrupt:
                logger.info("监控停止"); return
            except Exception as e:
                logger.error(f"异常: {e}")
            time.sleep(interval)

# ─── 数据导出 ─────────────────────────────────────────

class DataExporter:
    @staticmethod
    def to_json(items: list, path: str, indent: int = 2) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump([i.to_dict() for i in items], f,
                      ensure_ascii=False, indent=indent)
        logger.info(f"JSON → {path} ({len(items)} 条)")

    @staticmethod
    def to_csv(items: list, path: str) -> None:
        if not items: return
        fields = ["id","create_time","tag_names","text",
                  "like_nums","comment_total","doc_url","stocks"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for item in items:
                w.writerow({
                    "id": item.id, "create_time": item.create_time,
                    "tag_names": "|".join(item.tag_names),
                    "text": item.text[:500],
                    "like_nums": item.like_nums,
                    "comment_total": item.comment_total,
                    "doc_url": item.doc_url,
                    "stocks": "|".join(s.symbol for s in item.stocks),
                })
        logger.info(f"CSV  → {path} ({len(items)} 条)")

    @staticmethod
    def to_sqlite(items: list, db_path: str) -> None:
        conn = sqlite3.connect(db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS feed_items (
            id INTEGER PRIMARY KEY, create_time TEXT, update_time TEXT,
            rich_text TEXT, type INTEGER, tags TEXT, like_nums INTEGER,
            is_delete INTEGER, doc_url TEXT, doc_id TEXT,
            stocks TEXT, images TEXT, comment_total INTEGER,
            inserted_at TEXT DEFAULT (datetime('now')))""")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ct ON feed_items(create_time)")
        rows = [(i.id, i.create_time, i.update_time, i.rich_text, i.type,
                 json.dumps(i.tags, ensure_ascii=False), i.like_nums,
                 i.is_delete, i.doc_url, i.doc_id,
                 json.dumps([asdict(s) for s in i.stocks], ensure_ascii=False),
                 json.dumps(i.images, ensure_ascii=False), i.comment_total)
                for i in items]
        conn.executemany(
            "INSERT OR IGNORE INTO feed_items VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))", rows)
        conn.commit(); conn.close()
        logger.info(f"SQLite → {db_path} ({len(items)} 条)")

# ─── 便捷函数 ─────────────────────────────────────────

def fetch_latest(tag: str = "全部", count: int = 20) -> list:
    return Sina7x24Client().get_latest(tag=tag, count=count)

def fetch_since_hours(tag: str = "全部", hours: float = 1) -> list:
    since = datetime.now() - timedelta(hours=hours)
    return list(Sina7x24Client().iter_latest(
        tag=tag, max_items=500, since_time=since))

# ─── 命令行 ───────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="新浪财经 7x24 资讯爬虫")
    p.add_argument("--tag",      default="全部",  choices=list(TAGS.keys()))
    p.add_argument("--count",    type=int,  default=50)
    p.add_argument("--output",   default="sina_7x24.json")
    p.add_argument("--format",   default="json", choices=["json","csv","sqlite"])
    p.add_argument("--monitor",  action="store_true",  help="实时监控模式")
    p.add_argument("--interval", type=int,  default=30, help="监控间隔（秒）")
    p.add_argument("--hours",    type=float, default=0,  help="获取最近N小时数据")
    args = p.parse_args()

    client = Sina7x24Client()

    if args.monitor:
        client.monitor(tag=args.tag, interval=args.interval)
    else:
        if args.hours > 0:
            items = fetch_since_hours(tag=args.tag, hours=args.hours)
        else:
            items = list(client.iter_latest(tag=args.tag, max_items=args.count))

        print(f"\n共获取 {len(items)} 条 [{args.tag}] 资讯\n")
        for item in items[:5]:
            print(f"  [{item.id}] {item.create_time}  {item.text[:80]}")
        if len(items) > 5:
            print(f"  ... 还有 {len(items)-5} 条")

        exp = DataExporter()
        if   args.format == "json":   exp.to_json(items, args.output)
        elif args.format == "csv":    exp.to_csv(items, args.output)
        elif args.format == "sqlite": exp.to_sqlite(items, args.output)