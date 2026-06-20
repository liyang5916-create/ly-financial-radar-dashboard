"""新闻去重。"""

from __future__ import annotations

from typing import Dict, List


class Deduplicator:
    def __init__(self, use_redis=False):
        self.use_redis = use_redis

    def deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        seen = set()
        unique = []
        for article in articles:
            key = article.get("canonical_url") or article.get("url") or f"{article.get('source','')}|{article.get('title','')}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(article)
        return unique
