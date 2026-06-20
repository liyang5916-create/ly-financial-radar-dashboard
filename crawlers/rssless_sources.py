"""Collectors for public news pages that do not provide RSS feeds.

The collectors in this module only read publicly available list pages and
normalize article links into the same dictionary shape used by RSS collectors.
They do not bypass login, paywalls, CAPTCHAs, or copy full article bodies.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlsplit, urlunsplit

try:
    from .link_collectors import (
        CrawlSourceError,
        clean_text,
        extract_article_links,
        fetch_url,
        short_error,
    )
except ImportError:
    from link_collectors import CrawlSourceError, clean_text, extract_article_links, fetch_url, short_error


CN_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class RsslessSourceSpec:
    source_id: str
    source_name: str
    source_type: str
    homepage: str
    list_urls: List[str]
    article_pattern: re.Pattern
    source_note: str
    default_limit: int = 20
    max_age_hours: int = 48
    require_item_time: bool = False


RSSLESS_SOURCE_SPECS = [
    RsslessSourceSpec(
        source_id="cls",
        source_name="\u8d22\u8054\u793e",
        source_type="\u8d22\u7ecf\u5feb\u8baf",
        homepage="https://www.cls.cn/",
        list_urls=[
            "https://www.cls.cn/telegraph",
            "https://www.cls.cn/depth",
            "https://www.cls.cn/",
        ],
        article_pattern=re.compile(r"cls\.cn/(?:detail|telegraph)/\d+|cls\.cn/nodeapi/[^\s\"'<>]+"),
        source_note="\u8d22\u8054\u793e\u516c\u5f00\u9875\u9762\u94fe\u63a5\u91c7\u96c6",
        default_limit=12,
    ),
    RsslessSourceSpec(
        source_id="yicai",
        source_name="\u7b2c\u4e00\u8d22\u7ecf",
        source_type="\u7efc\u5408\u8d22\u7ecf",
        homepage="https://www.yicai.com/",
        list_urls=[
            "https://www.yicai.com/news/",
            "https://www.yicai.com/brief/",
            "https://www.yicai.com/",
        ],
        article_pattern=re.compile(r"yicai\.com/(?:news|brief)/\d+\.html"),
        source_note="\u7b2c\u4e00\u8d22\u7ecf\u516c\u5f00\u9875\u9762\u94fe\u63a5\u91c7\u96c6",
        default_limit=12,
        require_item_time=True,
    ),
    RsslessSourceSpec(
        source_id="jiemian",
        source_name="\u754c\u9762\u65b0\u95fb",
        source_type="\u8d22\u7ecf\u5a92\u4f53",
        homepage="https://www.jiemian.com/",
        list_urls=[
            "https://www.jiemian.com/lists/20.html",
            "https://www.jiemian.com/lists/7.html",
            "https://www.jiemian.com/",
        ],
        article_pattern=re.compile(r"jiemian\.com/article/\d+\.html"),
        source_note="\u754c\u9762\u65b0\u95fb\u516c\u5f00\u9875\u9762\u94fe\u63a5\u91c7\u96c6",
        default_limit=10,
        require_item_time=True,
    ),
    RsslessSourceSpec(
        source_id="latepost",
        source_name="\u665a\u70b9 LatePost",
        source_type="\u79d1\u6280\u4ea7\u4e1a",
        homepage="https://www.latepost.com/",
        list_urls=[
            "https://www.latepost.com/news/dj",
            "https://www.latepost.com/",
        ],
        article_pattern=re.compile(r"latepost\.com/news/[^\s\"'<>]*?(?:id=|/)\d+"),
        source_note="\u665a\u70b9 LatePost \u516c\u5f00\u9875\u9762\u94fe\u63a5\u91c7\u96c6",
        default_limit=8,
        max_age_hours=72,
    ),
    RsslessSourceSpec(
        source_id="wallstreetcn",
        source_name="\u534e\u5c14\u8857\u89c1\u95fb",
        source_type="\u5e02\u573a\u5feb\u8baf",
        homepage="https://wallstreetcn.com/",
        list_urls=[
            "https://wallstreetcn.com/live/global",
            "https://wallstreetcn.com/news/global",
            "https://wallstreetcn.com/",
        ],
        article_pattern=re.compile(r"wallstreetcn\.com/(?:articles|live)/\d+"),
        source_note="\u534e\u5c14\u8857\u89c1\u95fb\u516c\u5f00\u9875\u9762\u94fe\u63a5\u91c7\u96c6",
        default_limit=8,
    ),
    RsslessSourceSpec(
        source_id="caixin",
        source_name="\u8d22\u65b0\u7f51",
        source_type="\u6df1\u5ea6\u8d22\u7ecf",
        homepage="https://www.caixin.com/",
        list_urls=[
            "https://www.caixin.com/",
            "https://companies.caixin.com/",
            "https://economy.caixin.com/",
        ],
        article_pattern=re.compile(r"caixin\.com/\d{4}-\d{2}-\d{2}/\d+\.html"),
        source_note="\u8d22\u65b0\u7f51\u516c\u5f00\u9875\u9762\u94fe\u63a5\u91c7\u96c6",
        default_limit=10,
        require_item_time=True,
    ),
    RsslessSourceSpec(
        source_id="21jingji",
        source_name="21\u8d22\u7ecf",
        source_type="\u8d22\u7ecf\u5a92\u4f53",
        homepage="https://www.21jingji.com/",
        list_urls=[
            "https://www.21jingji.com/",
            "https://www.21jingji.com/list/\u79d1\u6280",
        ],
        article_pattern=re.compile(r"21jingji\.com/article/\d+\.html"),
        source_note="21\u8d22\u7ecf\u516c\u5f00\u9875\u9762\u94fe\u63a5\u91c7\u96c6",
        default_limit=10,
    ),
    RsslessSourceSpec(
        source_id="tmtpost",
        source_name="\u949b\u5a92\u4f53",
        source_type="\u79d1\u6280\u5a92\u4f53",
        homepage="https://www.tmtpost.com/",
        list_urls=[
            "https://www.tmtpost.com/",
            "https://www.tmtpost.com/nictation",
        ],
        article_pattern=re.compile(r"tmtpost\.com/\d+\.html"),
        source_note="\u949b\u5a92\u4f53\u516c\u5f00\u9875\u9762\u94fe\u63a5\u91c7\u96c6",
        default_limit=10,
        max_age_hours=72,
    ),
]


RSSLESS_SOURCE_IDS = {spec.source_id for spec in RSSLESS_SOURCE_SPECS}

POSITIVE_TERMS = [
    # AI硬件核心
    "AI", "大模型", "Agent", "算力", "GPU", "芯片", "半导体", "PCB", "光模块", "HBM",
    "英伟达", "NVIDIA", "AMD", "寒武纪", "昇腾", "华为", "浪潮", "服务器", "智算中心",
    "AI服务器", "训练芯片", "推理芯片", "DGX", "A100", "H100", "CoWoS", "先进封装",
    # 科技产业
    "机器人", "具身智能", "自动驾驶", "传感器", "激光雷达", "控制器", "减速器",
    # 资本市场
    "IPO", "上市", "科创板", "港股", "A股", "北交所", "创业板", "新股",
    "财报", "业绩", "营收", "净利润", "毛利率", "现金流",
    # 投融资
    "融资", "并购", "收购", "重组", "回购", "增发", "定增", "战略投资", "Pre-IPO",
    "A轮", "B轮", "C轮", "估值", "退出",
    # 政策监管
    "政策", "监管", "交易所", "证监会", "央行", "金融", "利率", "汇率", "美联储",
    "出口管制", "关税", "制裁", "合规", "许可证",
    # 宏观数据
    "CPI", "PPI", "PMI", "社融", "M2", "黄金", "原油", "美元", "美债", "人民币",
    # 产业链
    "订单", "量产", "产能", "涨价", "供应链", "产业链", "交付", "出货量",
    # 投资相关
    "基金", "ETF", "离岸金融", "外资", "北向资金", "南向资金", "机构", "私募",
]

NEGATIVE_TERMS = [
    "足球", "篮球", "世界杯", "球迷", "俱乐部", "运动", "明星", "艺人", "电影",
    "电视剧", "综艺", "影院", "演出", "酒店", "旅游", "美食", "红酒", "入狱",
    "服刑", "校园", "教育", "书店", "情怀", "抢劫", "食安", "食品安全",
]


def selected_specs(selected_source_ids: Optional[Iterable[str]] = None) -> List[RsslessSourceSpec]:
    selected = set(selected_source_ids or [])
    if not selected:
        return list(RSSLESS_SOURCE_SPECS)
    return [spec for spec in RSSLESS_SOURCE_SPECS if spec.source_id in selected]


def strip_tracking(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def valid_title(title: str) -> bool:
    title = clean_text(title)
    if len(title) < 4 or len(title) > 180:
        return False
    if title.startswith(("http://", "https://")):
        return False
    if "<" in title or ">" in title:
        return False
    return True


def parse_loose_time(value: str) -> Optional[datetime]:
    value = clean_text(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(value).replace(tzinfo=None)
    except Exception:
        return None


def parse_relative_time(value: str, now: Optional[datetime] = None) -> Optional[datetime]:
    value = clean_text(value)
    now = now or datetime.now()
    match = re.search(r"(\d+)\s*(?:分钟|分鐘|min|minute)s?\s*(?:前|ago)", value, re.IGNORECASE)
    if match:
        return now - timedelta(minutes=int(match.group(1)))
    match = re.search(r"(\d+)\s*(?:小时|小時|hour|hr)s?\s*(?:前|ago)", value, re.IGNORECASE)
    if match:
        return now - timedelta(hours=int(match.group(1)))
    if "刚刚" in value or "刚才" in value:
        return now
    if "昨天" in value:
        hm = re.search(r"(\d{1,2}):(\d{2})", value)
        base = now - timedelta(days=1)
        if hm:
            return base.replace(hour=int(hm.group(1)), minute=int(hm.group(2)), second=0, microsecond=0)
        return base
    return None


def parse_any_time(value: str, now: Optional[datetime] = None) -> Optional[datetime]:
    return parse_loose_time(value) or parse_relative_time(value, now)


def find_page_times(html: str) -> List[datetime]:
    patterns = [
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?",
        r"[A-Z][a-z]{2},\s+\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+[+-]\d{4}",
    ]
    found: List[datetime] = []
    for pattern in patterns:
        for match in re.finditer(pattern, html):
            parsed = parse_any_time(match.group(0))
            if parsed:
                found.append(parsed)
    return found


def title_near_position(html: str, url: str) -> int:
    if not url:
        return -1
    full = html.find(url)
    if full >= 0:
        return full
    parts = urlsplit(url)
    candidates = [parts.path]
    if parts.query:
        candidates.append(f"{parts.path}?{parts.query}")
    for candidate in candidates:
        if not candidate:
            continue
        pos = html.find(candidate)
        if pos >= 0:
            return pos
    return -1


def find_item_time(html: str, url: str, now: Optional[datetime] = None) -> Optional[datetime]:
    pos = title_near_position(html, url)
    if pos < 0:
        return None
    window = html[max(0, pos - 700): min(len(html), pos + 1200)]
    patterns = [
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?",
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        r"\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}",
        r"\d+\s*(?:分钟|分鐘|min|minute)s?\s*(?:前|ago)",
        r"\d+\s*(?:小时|小時|hour|hr)s?\s*(?:前|ago)",
        r"昨天\s*\d{0,2}:?\d{0,2}",
        r"刚刚|刚才",
    ]
    parsed_times: List[datetime] = []
    for pattern in patterns:
        for match in re.finditer(pattern, window, re.IGNORECASE):
            parsed = parse_any_time(normalize_partial_date(match.group(0), now), now)
            if parsed:
                parsed_times.append(parsed)
    if not parsed_times:
        return None
    now = now or datetime.now()
    parsed_times.sort(key=lambda item: abs((now - item).total_seconds()))
    return parsed_times[0]


def normalize_partial_date(value: str, now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    if re.fullmatch(r"\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}", value.strip()):
        return f"{now.year}-{value.strip()}"
    return value


def is_recent_enough(published: datetime, max_age_hours: int, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    if published > now + timedelta(hours=6):
        return False
    return published >= now - timedelta(hours=max_age_hours)


def is_relevant_text(title: str, summary: str = "") -> bool:
    text = f"{title} {summary}"
    positive = sum(1 for word in POSITIVE_TERMS if word.lower() in text.lower())
    negative = sum(1 for word in NEGATIVE_TERMS if word.lower() in text.lower())
    if negative and positive == 0:
        return False
    if negative >= 2 and positive <= 1:
        return False
    return positive > 0


class RsslessMediaCollector:
    source_name = "No-RSS media"
    source_ids = [spec.source_id for spec in RSSLESS_SOURCE_SPECS]

    def __init__(self, selected_source_ids: Optional[Iterable[str]] = None, timeout: int = 12, specs: Optional[List[RsslessSourceSpec]] = None):
        self.timeout = timeout
        self.specs = specs if specs is not None else selected_specs(selected_source_ids)
        self.headers = {
            "User-Agent": "Mozilla/5.0 FinanceRadar/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def crawl(self, limit: int = 80) -> List[Dict]:
        results: List[Dict] = []
        errors: List[str] = []
        if not self.specs:
            return []

        per_source_limit = max(1, min(limit, max(spec.default_limit for spec in self.specs)))
        for spec in self.specs:
            try:
                results.extend(self._crawl_spec(spec, per_source_limit))
            except Exception as exc:
                errors.append(f"{spec.source_id}: {short_error(exc)}")
                print(f"[{spec.source_name}] public page crawl failed: {exc}")

        unique = self._deduplicate(results)
        print(f"[{self.source_name}] public page collection finished {len(unique)} items")
        if not unique and errors:
            raise CrawlSourceError(f"No-RSS media did not return articles. Reasons: {'; '.join(errors[-5:])}")
        return unique[:limit]

    def _crawl_spec(self, spec: RsslessSourceSpec, limit: int) -> List[Dict]:
        results: List[Dict] = []
        seen_urls = set()
        now = datetime.now()
        for list_url in spec.list_urls:
            if len(results) >= limit:
                break
            html = self._fetch(list_url)
            page_times = find_page_times(html)
            for item in extract_article_links(html, list_url, spec.article_pattern, limit - len(results)):
                url = strip_tracking(item.get("url", ""))
                title = clean_text(item.get("title", ""))
                if not url or url in seen_urls or not valid_title(title):
                    continue
                summary = clean_text(item.get("summary", ""))
                item_time = find_item_time(html, url, now)
                if item_time is None and spec.require_item_time:
                    continue
                item_time_verified = item_time is not None
                publish_time = item_time or self._safe_page_time(page_times, spec, now)
                if publish_time is None or not is_recent_enough(publish_time, spec.max_age_hours, now):
                    continue
                if not is_relevant_text(title, summary):
                    continue
                seen_urls.add(url)
                results.append(self._normalize_article(spec, title, url, summary, publish_time, item_time_verified))
        return results

    def _safe_page_time(self, page_times: List[datetime], spec: RsslessSourceSpec, now: datetime) -> Optional[datetime]:
        if spec.require_item_time:
            return None
        for candidate in page_times:
            if is_recent_enough(candidate, spec.max_age_hours, now):
                return candidate
        return now

    def _normalize_article(self, spec: RsslessSourceSpec, title: str, url: str, summary: str, publish_time: datetime, item_time_verified: bool) -> Dict:
        return {
            "title": title,
            "original_title": title,
            "url": url,
            "original_url": url,
            "canonical_url": url,
            "url_status": "ok",
            "publish_time": publish_time,
            "content": clean_text(summary),
            "source": spec.source_name,
            "source_id": spec.source_id,
            "source_type": spec.source_type,
            "collect_method": "html_list",
            "source_note": spec.source_note,
            "item_time_verified": item_time_verified,
            "rssless_quality_version": 2,
        }

    def _deduplicate(self, articles: List[Dict]) -> List[Dict]:
        unique: List[Dict] = []
        seen = set()
        for article in articles:
            key = article.get("canonical_url") or article.get("url") or article.get("title")
            if key in seen:
                continue
            seen.add(key)
            unique.append(article)
        return unique

    def _fetch(self, url: str) -> str:
        return fetch_url(url, self.headers, self.timeout)


def articles_to_rss(articles: List[Dict], title: str = "Finance Radar Generated Feed", link: str = "http://127.0.0.1:5000/") -> str:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "link").text = link
    ET.SubElement(channel, "description").text = "Generated from public article list pages by Finance Radar."

    for article in articles:
        item = ET.SubElement(channel, "item")
        url = article.get("url") or article.get("original_url") or article.get("canonical_url") or ""
        ET.SubElement(item, "title").text = article.get("title", "")
        ET.SubElement(item, "link").text = url
        ET.SubElement(item, "description").text = article.get("content", "")
        ET.SubElement(item, "guid").text = url or article.get("title", "")
        published = article.get("publish_time")
        if isinstance(published, datetime):
            dt = published if published.tzinfo else published.replace(tzinfo=CN_TZ)
            ET.SubElement(item, "pubDate").text = format_datetime(dt)
        elif published:
            ET.SubElement(item, "pubDate").text = str(published)

    return ET.tostring(rss, encoding="unicode", xml_declaration=True)
