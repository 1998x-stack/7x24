# SKILL: sina-7x24

## 描述
新浪财经 7×24 小时资讯流完整数据接口技能。
包含 API 深度分析、Python 完整客户端、使用示例。

## 触发条件
当用户提及以下需求时激活:
- 新浪财经 7x24 / sina 7*24资讯 / 财经快讯爬虫
- 抓取/获取实时资讯流（zhibo_id=152）
- 实时财经监控、资讯推送
- tag_id / zhibo_id 接口分析

---

## 接口基础

GET https://zhibo.sina.com.cn/api/zhibo/feed

### 核心参数（全部必填）

| 参数 | 固定/可变 | 说明 |
|------|-----------|------|
| zhibo_id | **152** | 财经7x24固定 |
| tag_id | 0/1/2/3/5/8/9/10/102/110/202 | 分类 |
| page | 1~N | 页码 |
| page_size | 20 | 每页条数 |
| pagesize | 同page_size | 冗余，必须同步 |
| dire | **f** | 正向（新→旧） |
| dpc | **1** | 固定 |
| id | 9999999起 | 游标ID |
| type | **0** | 固定 |

### tag_id 完整映射

0=全部 | 1=宏观 | 2=行业 | 3=公司 | 5=市场
8=其他 | 9=焦点 | 10=A股 | 102=国际 | 110=两会 | 202=原创

---

## 响应关键字段

```
result.data.feed.list[]         # 条目数组
result.data.feed.page_info      # 分页信息
result.data.feed.max_id         # 本批最大ID
result.data.feed.min_id         # 本批最小ID（翻页游标）
```

### 条目字段
- id: 全局递增，可作去重key
- type: 0=纯文字, 1=图文
- rich_text: 正文（需HTML实体解码）
- create_time: "YYYY-MM-DD HH:MM:SS"（北京时间）
- tag: [{id, name}] 标签数组
- is_delete: 1=已删，需过滤
- ext: **JSON字符串**，需二次 json.loads
  - stocks: [{market, symbol, key}]
  - docurl, docid
- multimedia.img_url: 图片列表（type=1时有值）

### market 类型
cn=A股 | us=美股 | hk=港股 | fund=基金
worldIndex=全球指数 | foreign=外汇/加密货币
commodity=大宗商品 | global=全球期货

---

## 游标分页逻辑

```
首次：id=9999999, page=1
同批翻页：id不变, page递增 → 直到 page == totalPage
跨批翻页：id = 上批min_id, page = 1 重新开始
终止：min_id == 0 或 min_id >= cursor_id 或 list为空
```

---

## 快速示例

### 最简版（20行）
```python
import re, json, requests

def get_sina_7x24(tag_id=0, count=20):
    url = "https://zhibo.sina.com.cn/api/zhibo/feed"
    params = dict(page=1, page_size=count, pagesize=count,
                  zhibo_id=152, tag_id=tag_id, dire="f",
                  dpc=1, id=9999999, type=0)
    r = requests.get(url, params=params,
                     headers={"Referer":"https://finance.sina.com.cn/"})
    text = re.sub(r"^[^(]+\(|\);\s*$", "", r.text.strip())
    return json.loads(text)["result"]["data"]["feed"]["list"]

# A股最新20条
items = get_sina_7x24(tag_id=10)
for item in items:
    print(item["create_time"], item["rich_text"][:80])
```

### 命令行用法
```bash
# 获取50条A股资讯
python sina_7x24.py --tag A股 --count 50

# 获取最近2小时全部资讯（SQLite）
python sina_7x24.py --hours 2 --format sqlite --output news.db

# 实时监控（每30秒）
python sina_7x24.py --tag 国际 --monitor --interval 30

# 保存CSV
python sina_7x24.py --tag 宏观 --count 100 --format csv
```

### 完整客户端用法
```python
from sina_7x24 import Sina7x24Client, DataExporter, fetch_since_hours

client = Sina7x24Client()

# 多分类批量获取
all_data = client.get_all_tags(["A股","国际","宏观"], count_per_tag=30)

# 增量（最近1小时）
items = fetch_since_hours(tag="全部", hours=1)

# 实时监控+回调
def on_news(item):
    print(f"[{item.id}] {item.text[:100]}")
client.monitor(tag="A股", interval=30, callback=on_news)

# 导出
DataExporter().to_json(items, "news.json")
DataExporter().to_csv(items, "news.csv")
DataExporter().to_sqlite(items, "news.db")
```

---

## 注意事项

1. 请求间隔 ≥ 0.5 秒，避免被封 IP
2. 不传 `callback` 参数可直接获取纯 JSON（推荐）
3. `is_delete=1` 的条目必须过滤
4. `ext` 是 JSON 字符串，需二次 `json.loads`
5. 所有时间为北京时间 UTC+8
6. `id` 字段全局递增，可安全用作去重 key

---

## 文件清单

| 文件 | 说明 |
|------|------|
| sina_7x24.py | 完整 Python 客户端 |
| SKILL.md | 本 Skill 描述文件 |