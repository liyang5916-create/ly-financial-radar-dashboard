"""Clean low-value or stale no-RSS media items from local_store.json."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.rssless_sources import RSSLESS_SOURCE_IDS, is_relevant_text

STORE_PATH = PROJECT_ROOT / "data" / "local_store.json"


def parse_dt(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def keep_item(item, now):
    source_id = item.get("source_id")
    if source_id not in RSSLESS_SOURCE_IDS:
        return True
    if item.get("rssless_quality_version") != 2:
        return False
    published = parse_dt(item.get("publish_time"))
    if not published or published < now - timedelta(hours=48) or published > now + timedelta(hours=6):
        return False
    return is_relevant_text(item.get("title", ""), item.get("content", ""))


def main():
    data = json.loads(STORE_PATH.read_text(encoding="utf-8-sig")) if STORE_PATH.exists() else {"news": [], "topics": []}
    now = datetime.now()
    before = len(data.get("news", []))
    data["news"] = [item for item in data.get("news", []) if keep_item(item, now)]
    removed = before - len(data["news"])
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Removed {removed} stale/low-relevance no-RSS items. Kept {len(data['news'])} news items.")


if __name__ == "__main__":
    main()
