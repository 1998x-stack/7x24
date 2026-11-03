"""Source category mapping; unknown categories must not silently map to all."""

CATEGORIES: dict[str, int] = {
    "all": 0, "全部": 0,
    "macro": 1, "宏观": 1,
    "industry": 2, "行业": 2,
    "company": 3, "公司": 3,
    "market": 5, "市场": 5,
    "other": 8, "其他": 8,
    "focus": 9, "焦点": 9,
    "a_share": 10, "A股": 10,
    "international": 102, "国际": 102,
}

def category_id(name: str) -> int:
    try:
        return CATEGORIES[name]
    except KeyError as exc:
        raise ValueError(f"unknown category: {name}") from exc
