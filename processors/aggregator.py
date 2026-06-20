"""话题聚合。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List


class TopicAggregator:
    def generate_topics(self, articles: List[Dict], min_articles=2) -> List[Dict]:
        buckets = {}
        for article in articles:
            tags = article.get("tags") or [article.get("category", {}).get("industry", "其他")]
            for tag in tags:
                if not tag:
                    continue
                bucket = buckets.setdefault(tag, {"items": [], "companies": []})
                bucket["items"].append(article)
                bucket["companies"].extend(article.get("entities", {}).get("companies", []))

        topics = []
        for tag, bucket in buckets.items():
            if len(bucket["items"]) < min_articles:
                continue
            topics.append({
                "_id": f"topic_{tag}",
                "topic_name": tag,
                "keywords": [tag],
                "related_news_ids": [item.get("_id") or item.get("url", "") for item in bucket["items"]],
                "news_count": len(bucket["items"]),
                "heat_trend": "↑" if len(bucket["items"]) >= 2 else "→",
                "related_companies": list(dict.fromkeys(bucket["companies"]))[:6],
                "create_time": datetime.now(),
            })
        topics.sort(key=lambda item: item["news_count"], reverse=True)
        return topics
