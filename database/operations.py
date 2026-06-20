"""数据库兼容层。

优先使用本地 JSON，保留与旧 Flask 代码相同的方法名。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STORE_PATH = PROJECT_ROOT / "data" / "local_store.json"


def _json_ready(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    return value


def _parse_dt(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.min


class _CollectionCompat:
    def __init__(self, db, key):
        self.db = db
        self.key = key

    def insert_one(self, item):
        data = self.db._load()
        data.setdefault(self.key, [])
        data[self.key].append(item)
        self.db._save(data)


class DatabaseManager:
    def __init__(self):
        self.topics_collection = _CollectionCompat(self, "topics")

    def _load(self):
        if not STORE_PATH.exists():
            return {"news": [], "topics": []}
        try:
            data = json.loads(STORE_PATH.read_text(encoding="utf-8-sig"))
        except Exception:
            data = {"news": [], "topics": []}
        data.setdefault("news", [])
        data.setdefault("topics", [])
        return data

    def _save(self, data):
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STORE_PATH.write_text(json.dumps(_json_ready(data), ensure_ascii=False, indent=2), encoding="utf-8")

    def insert_news(self, article: Dict):
        data = self._load()
        key = article.get("_id") or article.get("url") or article.get("title")
        existing = data.get("news", [])
        if article.get("url") or article.get("original_url") or article.get("canonical_url"):
            existing = [item for item in existing if not item.get("is_demo")]
        by_id = {item.get("_id") or item.get("url") or item.get("title"): item for item in existing}
        by_id[key] = article
        data["news"] = list(by_id.values())
        self._save(data)

    def find_news_by_date(self, start: datetime, end: datetime) -> List[Dict]:
        data = self._load()
        items = []
        for item in data.get("news", []):
            if item.get("is_demo"):
                continue
            published = _parse_dt(item.get("publish_time"))
            if start <= published <= end:
                items.append(item)
        items.sort(key=lambda item: _parse_dt(item.get("publish_time")), reverse=True)
        return items

    def find_news_by_category(self, event_type=None, industry=None) -> List[Dict]:
        data = self._load()
        items = []
        for item in data.get("news", []):
            if item.get("is_demo"):
                continue
            category = item.get("category", {})
            if event_type and category.get("event_type") != event_type:
                continue
            if industry and category.get("industry") != industry:
                continue
            items.append(item)
        items.sort(key=lambda item: _parse_dt(item.get("publish_time")), reverse=True)
        return items

    def get_hot_topics(self, limit=50) -> List[Dict]:
        data = self._load()
        topics = data.get("topics", [])
        topics.sort(key=lambda item: item.get("news_count", 0), reverse=True)
        return topics[:limit]

    def get_storage_info(self):
        return {"mode": "local_json", "path": str(STORE_PATH)}

    def close(self):
        return None
