"""中文数据源爬虫统一入口。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

try:
    from .link_collectors import CrawlSourceError, HuxiuRssCollector, Kr36NewsflashLinkCollector, StatsGovRssCollector, StcnLinkCollector
    from .rssless_sources import RsslessMediaCollector
except ImportError:
    from link_collectors import CrawlSourceError, HuxiuRssCollector, Kr36NewsflashLinkCollector, StatsGovRssCollector, StcnLinkCollector
    from rssless_sources import RsslessMediaCollector


class Kr36Crawler:
    source_name = "36氪"
    source_id = "36kr"
    source_type = "创投科技"

    def crawl(self) -> List[Dict]:
        # 36氪主 feed 依赖 feedparser；当前恢复版保留快讯 RSS 即可。
        return []


class XueqiuCrawler:
    source_name = "雪球"
    source_id = "xueqiu"
    source_type = "社区讨论"

    def crawl(self) -> List[Dict]:
        return []


def crawl_all_chinese_sources(selected_source_ids: List[str] = None) -> List[Dict]:
    return crawl_all_chinese_sources_with_status(selected_source_ids)["articles"]


def crawl_all_chinese_sources_with_status(selected_source_ids: List[str] = None) -> Dict:
    all_results = []
    status = []
    selected = set(selected_source_ids or [])
    crawlers = [
        StcnLinkCollector(),
        Kr36NewsflashLinkCollector(),
        HuxiuRssCollector(),
        StatsGovRssCollector(),
        RsslessMediaCollector(selected),
    ]

    for crawler in crawlers:
        if selected and not _crawler_enabled(crawler, selected):
            continue
        name = getattr(crawler, "source_name", crawler.__class__.__name__)
        try:
            results = crawler.crawl()
            if selected:
                results = [item for item in results if _article_enabled(item, crawler, selected)]
            all_results.extend(results)
            status.append({"source": name, "count": len(results), "ok": len(results) > 0, "error": "" if results else f"{name} 没有返回文章"})
        except CrawlSourceError as exc:
            message = str(exc)
            status.append({"source": name, "count": 0, "ok": False, "error": message})
            print(f"爬虫 {name} 未抓到结果: {message}")
        except Exception as exc:
            message = str(exc)
            status.append({"source": name, "count": 0, "ok": False, "error": message})
            print(f"爬虫 {name} 执行失败: {message}")
    return {"articles": all_results, "status": status}


def _crawler_enabled(crawler, selected: set) -> bool:
    source_ids = set()
    source_id = getattr(crawler, "source_id", "")
    if source_id:
        source_ids.add(source_id)
    source_ids.update(getattr(crawler, "source_ids", []) or [])
    source_ids.update(feed.get("source_id", "") for feed in getattr(crawler, "FEEDS", []) if feed.get("source_id"))
    if isinstance(crawler, Kr36NewsflashLinkCollector):
        source_ids.add("36kr")
    return bool(source_ids & selected)


def _article_enabled(article: Dict, crawler, selected: set) -> bool:
    article_source_id = article.get("source_id")
    if article_source_id in selected:
        return True
    if article_source_id == "36kr_newsflash" and "36kr" in selected:
        return True
    crawler_source_id = getattr(crawler, "source_id", "")
    if crawler_source_id and crawler_source_id in selected:
        return True
    if isinstance(crawler, Kr36NewsflashLinkCollector) and "36kr" in selected:
        return True
    return False
