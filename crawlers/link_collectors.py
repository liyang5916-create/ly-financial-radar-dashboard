"""新闻链接采集器。"""

from __future__ import annotations

import re
import ssl
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from typing import Dict, List, Optional
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DETAIL_RE = re.compile(r"/article/detail/\d+\.html")
KR36_ARTICLE_RE = re.compile(r"36kr\.com/(?:p|newsflashes)/\d+")
HUXIU_ARTICLE_RE = re.compile(r"huxiu\.com/article/\d+\.html")


class CrawlSourceError(RuntimeError):
    """Raised when a source cannot return any usable article."""


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def repair_mojibake(value: str) -> str:
    if not value or not any(marker in value for marker in ("Ã", "Â", "æ", "å", "è")):
        return value
    try:
        repaired = value.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    return repaired if len(repaired) >= len(value) * 0.5 else value


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def feed_entries(root: ET.Element) -> List[ET.Element]:
    return [node for node in root.iter() if xml_local_name(node.tag) in {"item", "entry"}]


def feed_text(entry: ET.Element, *names: str) -> str:
    wanted = set(names)
    for child in entry.iter():
        if xml_local_name(child.tag) in wanted and child.text:
            return clean_text(child.text)
    return ""


def feed_link(entry: ET.Element) -> str:
    text_link = feed_text(entry, "link")
    if text_link:
        return text_link
    for child in entry.iter():
        if xml_local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href", "")
        rel = child.attrib.get("rel", "alternate")
        if href and rel in {"alternate", ""}:
            return clean_text(href)
    return ""


def short_error(exc: Exception) -> str:
    return clean_text(str(exc)) or exc.__class__.__name__


def fetch_url(url: str, headers: Dict[str, str], timeout: int = 12) -> str:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            return decode_response(response)
    except ssl.SSLError:
        # Company networks sometimes install TLS inspection certificates.
        with urlopen(request, timeout=timeout, context=ssl._create_unverified_context()) as response:
            return decode_response(response)


def decode_response(response) -> str:
    raw = response.read()
    charset = response.headers.get_content_charset()
    for encoding in [charset, "utf-8", "gb18030", "gbk"]:
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def parse_xml_feed(text: str, source_url: str) -> ET.Element:
    snippet = text.lstrip()[:120].lower()
    if snippet.startswith("<!doctype html") or snippet.startswith("<html"):
        raise ValueError(f"{source_url} 返回 HTML 页面，不是 RSS/XML")
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"{source_url} XML 解析失败: {exc}") from exc


def format_empty_message(source_name: str, attempts: List[str], errors: List[str]) -> str:
    tried = "；".join(attempts[-8:]) if attempts else "无"
    detail = "；".join(errors[-5:]) if errors else "接口可访问但没有解析到文章条目"
    return f"{source_name} 未抓到文章。已尝试：{tried}。原因：{detail}"


class ArticleLinkParser(HTMLParser):
    def __init__(self, base_url: str, url_pattern: re.Pattern):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.url_pattern = url_pattern
        self.items: List[Dict] = []
        self._active_url = ""
        self._active_title_parts: List[str] = []
        self._seen = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attr = {key: value or "" for key, value in attrs}
        href = attr.get("href", "")
        if not href:
            return
        url = urljoin(self.base_url, href)
        if not self.url_pattern.search(url) or url in self._seen:
            return
        self._active_url = url
        self._active_title_parts = [attr.get("title", ""), attr.get("aria-label", "")]

    def handle_data(self, data):
        if self._active_url:
            self._active_title_parts.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or not self._active_url:
            return
        title = repair_mojibake(clean_text(" ".join(self._active_title_parts)))
        if title:
            self.items.append({"title": title, "url": self._active_url, "summary": ""})
            self._seen.add(self._active_url)
        self._active_url = ""
        self._active_title_parts = []


def extract_article_links(html: str, base_url: str, url_pattern: re.Pattern, limit: int) -> List[Dict]:
    parser = ArticleLinkParser(base_url, url_pattern)
    parser.feed(html)
    results = parser.items[:limit]
    seen = {item["url"] for item in results}

    for match in re.finditer(r"""(?P<url>https?://[^"'<>\s]+|/[^"'<>\s]+)""", html):
        if len(results) >= limit:
            break
        raw_url = match.group("url")
        url = urljoin(base_url, raw_url)
        if url in seen or not url_pattern.search(url):
            continue
        title = title_near(html, match.start(), match.end())
        if not title:
            continue
        seen.add(url)
        results.append({"title": title, "url": url, "summary": ""})
    return results


def title_near(html: str, start: int, end: int) -> str:
    window = html[max(0, start - 900): min(len(html), end + 900)]
    patterns = [
        r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"',
        r'"webTitle"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"',
        r'title=["\']([^"\']{4,160})["\']',
        r'aria-label=["\']([^"\']{4,160})["\']',
    ]
    for pattern in patterns:
        found = re.search(pattern, window)
        if found:
            title = found.group(1)
            if "\\" in title:
                try:
                    title = bytes(title, "utf-8").decode("unicode_escape")
                except UnicodeDecodeError:
                    pass
            title = repair_mojibake(clean_text(title))
            if len(title) >= 4:
                return title
    return ""


class StcnListParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.items: List[Dict] = []
        self._li_depth = 0
        self._current: Optional[Dict] = None
        self._active_href = ""
        self._div_context: List[str] = []

    def handle_starttag(self, tag, attrs):
        attr = {key: value or "" for key, value in attrs}
        if tag == "li":
            if self._li_depth == 0:
                self._current = {"url": "", "title_parts": [], "summary_parts": [], "info_parts": [], "seen_detail": False}
            self._li_depth += 1
        if self._current is None:
            return
        if tag == "div":
            classes = f" {attr.get('class', '')} "
            if " tt " in classes:
                self._div_context.append("title")
            elif " text " in classes:
                self._div_context.append("summary")
            elif " info " in classes:
                self._div_context.append("info")
            else:
                self._div_context.append("")
        if tag == "a":
            href = attr.get("href", "")
            if DETAIL_RE.search(href):
                self._active_href = urljoin(self.base_url, href)
                self._current["seen_detail"] = True
                self._current["url"] = self._current["url"] or self._active_href

    def handle_data(self, data):
        if self._current is None:
            return
        text = clean_text(data)
        if not text:
            return
        context = self._div_context[-1] if self._div_context else ""
        if self._active_href and context == "title":
            self._current["title_parts"].append(text)
        elif self._active_href and context == "summary":
            self._current["summary_parts"].append(text)
        elif context == "info":
            self._current["info_parts"].append(text)

    def handle_endtag(self, tag):
        if self._current is None:
            return
        if tag == "a":
            self._active_href = ""
        elif tag == "div" and self._div_context:
            self._div_context.pop()
        elif tag == "li":
            self._li_depth -= 1
            if self._li_depth <= 0:
                self._finalize_item()
                self._li_depth = 0
                self._current = None
                self._active_href = ""
                self._div_context = []

    def _finalize_item(self):
        if not self._current or not self._current.get("seen_detail"):
            return
        title = clean_text(" ".join(self._current["title_parts"]))
        url = self._current.get("url", "")
        if title and url:
            self.items.append({"title": title, "url": url, "summary": clean_text(" ".join(self._current["summary_parts"])), "info_parts": self._current["info_parts"]})


class StcnLinkCollector:
    source_name = "证券时报"
    source_id = "stcn"
    source_type = "法披"

    RSS_URLS = [
        "https://app.stcn.com/rss.php?catid=1",
        "http://app.stcn.com/rss.php?catid=1",
        "https://app.stcn.com/rss.php?catid=29",
        "http://app.stcn.com/rss.php?catid=29",
        "https://app.stcn.com/rss.php?catid=340",
        "http://app.stcn.com/rss.php?catid=340",
    ]
    LIST_URLS = [
        "https://www.stcn.com/article/list/yw.html",
        "https://www.stcn.com/article/list/xw.html",
        "https://www.stcn.com/article/list/cj.html",
        "https://www.stcn.com/article/list/gs.html",
        "https://www.stcn.com/article/list/investment.html",
        "https://www.stcn.com/article/list/hq.html",
        "https://www.stcn.com/article/list/fund.html",
        "https://www.stcn.com/article/list/finance.html",
        "https://www.stcn.com/article/list/pl.html",
        "https://www.stcn.com/",
    ]

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.headers = {"User-Agent": "Mozilla/5.0 FinanceRadar/1.0", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

    def crawl(self, limit: int = 40) -> List[Dict]:
        results: List[Dict] = []
        attempts: List[str] = []
        errors: List[str] = []
        for rss_url in self.RSS_URLS:
            attempts.append(rss_url)
            try:
                results.extend(self._crawl_rss(rss_url, limit - len(results)))
            except Exception as exc:
                errors.append(f"{rss_url}: {short_error(exc)}")
                print(f"[{self.source_name}] RSS不可用 {rss_url}: {exc}")
            if len(results) >= limit:
                break
        if not results:
            results = self._crawl_list_pages(limit, attempts, errors)
        print(f"[{self.source_name}] 链接采集完成 {len(results)} 条")
        if not results:
            raise CrawlSourceError(format_empty_message(self.source_name, attempts, errors))
        return results[:limit]

    def _crawl_list_pages(self, limit: int, attempts: Optional[List[str]] = None, errors: Optional[List[str]] = None) -> List[Dict]:
        results, seen_urls = [], set()
        attempts = attempts if attempts is not None else []
        errors = errors if errors is not None else []
        for list_url in self.LIST_URLS:
            if len(results) >= limit:
                break
            attempts.append(list_url)
            try:
                parser = StcnListParser(list_url)
                parser.feed(self._fetch(list_url))
            except Exception as exc:
                errors.append(f"{list_url}: {short_error(exc)}")
                print(f"[{self.source_name}] 栏目页不可用 {list_url}: {exc}")
                continue
            for item in parser.items:
                if len(results) >= limit:
                    break
                url = item.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                results.append(self._normalize_article(item.get("title", ""), url, self._parse_publish_time(item.get("info_parts", [])), item.get("summary", ""), "html_list"))
        return results

    def _crawl_rss(self, rss_url: str, limit: int) -> List[Dict]:
        if limit <= 0:
            return []
        root = parse_xml_feed(self._fetch(rss_url), rss_url)
        results = []
        for item in feed_entries(root)[:limit]:
            title = clean_text(feed_text(item, "title"))
            url = clean_text(feed_link(item))
            description = clean_text(feed_text(item, "description", "summary", "content"))
            pub_date = clean_text(feed_text(item, "pubDate", "published", "updated"))
            if title and url:
                results.append(self._normalize_article(title, url, self._parse_rss_time(pub_date), description, "rss"))
        return results

    def _normalize_article(self, title: str, url: str, publish_time: Optional[datetime], content: str, collect_method: str) -> Dict:
        publish_time = publish_time or datetime.now()
        return {
            "title": title,
            "original_title": title,
            "url": url,
            "original_url": url,
            "canonical_url": url,
            "url_status": "ok" if url else "missing",
            "publish_time": publish_time,
            "content": content,
            "source": self.source_name,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "collect_method": collect_method,
            "source_note": "证券时报原文链接采集",
        }

    def _fetch(self, url: str) -> str:
        return fetch_url(url, self.headers, self.timeout)

    def _find_text(self, item: ET.Element, name: str) -> str:
        child = item.find(name)
        return child.text if child is not None and child.text else ""

    def _parse_rss_time(self, value: str) -> datetime:
        if not value:
            return datetime.now()
        for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=None)
            except ValueError:
                pass
        try:
            return parsedate_to_datetime(value).replace(tzinfo=None)
        except Exception:
            return datetime.now()

    def _parse_publish_time(self, parts: List[str]) -> datetime:
        text = clean_text(" ".join(parts))
        now = datetime.now()
        match = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?\s+(\d{1,2}):(\d{2})", text)
        if match:
            return datetime(*map(int, match.groups()))
        match = re.search(r"(\d{1,2})[-/月](\d{1,2})日?\s+(\d{1,2}):(\d{2})", text)
        if match:
            month, day, hour, minute = map(int, match.groups())
            return datetime(now.year, month, day, hour, minute)
        return now


class Kr36NewsflashLinkCollector:
    source_name = "36氪"
    source_id = "36kr"
    source_type = "科技产业"
    RSS_URLS = ["https://36kr.com/feed-article"]
    LIST_URLS = ["https://36kr.com/information/web_news/", "https://36kr.com/"]

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.headers = {"User-Agent": "Mozilla/5.0 FinanceRadar/1.0", "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8"}

    def crawl(self, limit: int = 20) -> List[Dict]:
        results = []
        seen_urls = set()
        attempts: List[str] = []
        errors: List[str] = []
        for rss_url in self.RSS_URLS:
            attempts.append(rss_url)
            try:
                for item in self._crawl_rss(rss_url, limit - len(results)):
                    url = item.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        results.append(item)
            except Exception as exc:
                errors.append(f"{rss_url}: {short_error(exc)}")
                print(f"[{self.source_name}] RSS不可用 {rss_url}: {exc}")
            if len(results) >= limit:
                break
        if not results:
            results = self._crawl_list_pages(limit, attempts, errors)
        print(f"[{self.source_name}] 链接采集完成 {len(results)} 条")
        if not results:
            raise CrawlSourceError(format_empty_message(self.source_name, attempts, errors))
        return results[:limit]

    def _crawl_rss(self, rss_url: str, limit: int) -> List[Dict]:
        if limit <= 0:
            return []
        root = parse_xml_feed(self._fetch(rss_url), rss_url)
        results = []
        for item in feed_entries(root)[:limit]:
            title = repair_mojibake(feed_text(item, "title"))
            url = feed_link(item)
            description = repair_mojibake(feed_text(item, "description", "summary", "content"))
            pub_date = feed_text(item, "pubDate", "published", "updated")
            source = feed_text(item, "source") or self.source_name
            if title and url:
                results.append({
                    "title": title,
                    "original_title": title,
                    "url": url,
                    "original_url": url,
                    "canonical_url": url,
                    "url_status": "ok",
                    "publish_time": self._parse_rss_time(pub_date),
                    "content": description,
                    "source": source,
                    "source_id": self.source_id,
                    "source_type": self.source_type,
                    "collect_method": "rss",
                    "source_note": "36氪 RSS 原文链接采集",
                })
        return results

    def _crawl_list_pages(self, limit: int, attempts: List[str], errors: List[str]) -> List[Dict]:
        results = []
        seen_urls = set()
        for list_url in self.LIST_URLS:
            if len(results) >= limit:
                break
            attempts.append(list_url)
            try:
                html = self._fetch(list_url)
                items = extract_article_links(html, list_url, KR36_ARTICLE_RE, limit - len(results))
            except Exception as exc:
                errors.append(f"{list_url}: {short_error(exc)}")
                print(f"[{self.source_name}] 列表页不可用 {list_url}: {exc}")
                continue
            for item in items:
                url = item.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                results.append({
                    "title": item["title"],
                    "original_title": item["title"],
                    "url": url,
                    "original_url": url,
                    "canonical_url": url,
                    "url_status": "ok",
                    "publish_time": datetime.now(),
                    "content": item.get("summary", ""),
                    "source": self.source_name,
                    "source_id": self.source_id,
                    "source_type": self.source_type,
                    "collect_method": "html_list",
                    "source_note": "36氪官网列表页原文链接采集",
                })
        return results

    def _fetch(self, url: str) -> str:
        return fetch_url(url, self.headers, self.timeout)

    def _parse_rss_time(self, value: str) -> datetime:
        try:
            return parsedate_to_datetime(value).replace(tzinfo=None) if value else datetime.now()
        except Exception:
            return datetime.now()


class HuxiuRssCollector:
    source_name = "虎嗅"
    source_id = "huxiu"
    source_type = "科技产业"
    RSS_URLS = ["https://rss.huxiu.com/"]
    LIST_URLS = ["https://www.huxiu.com/", "https://www.huxiu.com/channel/1.html"]

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.headers = {"User-Agent": "Mozilla/5.0 FinanceRadar/1.0", "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8"}

    def crawl(self, limit: int = 30) -> List[Dict]:
        results = []
        seen_urls = set()
        attempts: List[str] = []
        errors: List[str] = []
        for rss_url in self.RSS_URLS:
            attempts.append(rss_url)
            try:
                for item in self._crawl_rss(rss_url, limit - len(results)):
                    url = item.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        results.append(item)
            except Exception as exc:
                errors.append(f"{rss_url}: {short_error(exc)}")
                print(f"[{self.source_name}] RSS不可用 {rss_url}: {exc}")
            if len(results) >= limit:
                break
        if not results:
            results = self._crawl_list_pages(limit, attempts, errors)
        print(f"[{self.source_name}] 链接采集完成 {len(results)} 条")
        if not results:
            raise CrawlSourceError(format_empty_message(self.source_name, attempts, errors))
        return results[:limit]

    def _crawl_rss(self, rss_url: str, limit: int) -> List[Dict]:
        if limit <= 0:
            return []
        root = parse_xml_feed(self._fetch(rss_url), rss_url)
        results = []
        for item in feed_entries(root)[:limit]:
            title = repair_mojibake(feed_text(item, "title"))
            url = feed_link(item)
            description = repair_mojibake(feed_text(item, "description", "summary", "content"))
            pub_date = feed_text(item, "pubDate", "published", "updated")
            if title and url:
                results.append({
                    "title": title,
                    "original_title": title,
                    "url": url,
                    "original_url": url,
                    "canonical_url": url,
                    "url_status": "ok",
                    "publish_time": self._parse_rss_time(pub_date),
                    "content": description,
                    "source": self.source_name,
                    "source_id": self.source_id,
                    "source_type": self.source_type,
                    "collect_method": "rss",
                    "source_note": "虎嗅 RSS 原文链接采集",
                })
        return results

    def _crawl_list_pages(self, limit: int, attempts: List[str], errors: List[str]) -> List[Dict]:
        results = []
        seen_urls = set()
        for list_url in self.LIST_URLS:
            if len(results) >= limit:
                break
            attempts.append(list_url)
            try:
                html = self._fetch(list_url)
                items = extract_article_links(html, list_url, HUXIU_ARTICLE_RE, limit - len(results))
            except Exception as exc:
                errors.append(f"{list_url}: {short_error(exc)}")
                print(f"[{self.source_name}] 列表页不可用 {list_url}: {exc}")
                continue
            for item in items:
                url = item.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                results.append({
                    "title": item["title"],
                    "original_title": item["title"],
                    "url": url,
                    "original_url": url,
                    "canonical_url": url,
                    "url_status": "ok",
                    "publish_time": datetime.now(),
                    "content": item.get("summary", ""),
                    "source": self.source_name,
                    "source_id": self.source_id,
                    "source_type": self.source_type,
                    "collect_method": "html_list",
                    "source_note": "虎嗅官网列表页原文链接采集",
                })
        return results

    def _fetch(self, url: str) -> str:
        return fetch_url(url, self.headers, self.timeout)

    def _find_text(self, item: ET.Element, name: str) -> str:
        child = item.find(name)
        return child.text if child is not None and child.text else ""

    def _parse_rss_time(self, value: str) -> datetime:
        if not value:
            return datetime.now()
        for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=None)
            except ValueError:
                pass
        try:
            return parsedate_to_datetime(value).replace(tzinfo=None)
        except Exception:
            return datetime.now()


class StatsGovRssCollector:
    source_name = "国家统计局"
    source_type = "官方数据"
    FEEDS = [
        {"source_id": "stats_latest", "source_name": "国家统计局最新发布", "rss_url": "https://www.stats.gov.cn/sj/zxfb/rss.xml", "note": "国家统计局最新发布RSS原文链接采集"},
        {"source_id": "stats_interpretation", "source_name": "国家统计局数据解读", "rss_url": "https://www.stats.gov.cn/sj/sjjd/rss.xml", "note": "国家统计局数据解读RSS原文链接采集"},
    ]

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.headers = {"User-Agent": "Mozilla/5.0 FinanceRadar/1.0", "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8"}

    def crawl(self, limit: int = 30) -> List[Dict]:
        results = []
        per_feed_limit = max(1, limit // len(self.FEEDS))
        for feed in self.FEEDS:
            try:
                results.extend(self._crawl_feed(feed, per_feed_limit))
            except Exception as exc:
                print(f"[{feed['source_name']}] RSS抓取失败: {exc}")
        print(f"[{self.source_name}] 链接采集完成 {len(results)} 条")
        return results[:limit]

    def _crawl_feed(self, feed: Dict, limit: int) -> List[Dict]:
        root = ET.fromstring(self._fetch(feed["rss_url"]))
        results = []
        for item in root.findall(".//item")[:limit]:
            title = repair_mojibake(clean_text(self._find_text(item, "title")))
            url = clean_text(self._find_text(item, "link"))
            description = repair_mojibake(clean_text(self._find_text(item, "description")))
            pub_date = clean_text(self._find_text(item, "pubDate") or self._find_text(item, "pubTime"))
            if title and url:
                results.append({
                    "title": title,
                    "original_title": title,
                    "url": url,
                    "original_url": url,
                    "canonical_url": url,
                    "url_status": "ok",
                    "publish_time": self._parse_rss_time(pub_date),
                    "content": description,
                    "source": feed["source_name"],
                    "source_id": feed["source_id"],
                    "source_type": self.source_type,
                    "collect_method": "rss",
                    "source_note": feed["note"],
                })
        return results

    def _fetch(self, url: str) -> str:
        request = Request(url, headers=self.headers)
        with urlopen(request, timeout=self.timeout, context=ssl.create_default_context()) as response:
            raw = response.read()
            charset = response.headers.get_content_charset()
            for encoding in [charset, "utf-8", "gb18030"]:
                if not encoding:
                    continue
                try:
                    return raw.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="ignore")

    def _find_text(self, item: ET.Element, name: str) -> str:
        child = item.find(name)
        return child.text if child is not None and child.text else ""

    def _parse_rss_time(self, value: str) -> datetime:
        if not value:
            return datetime.now()
        for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=None)
            except ValueError:
                pass
        try:
            return parsedate_to_datetime(value).replace(tzinfo=None)
        except Exception:
            return datetime.now()
