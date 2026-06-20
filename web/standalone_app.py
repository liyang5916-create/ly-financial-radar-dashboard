"""Standalone Finance Radar web service.

This version uses only the Python standard library so run_web.ps1/run_web.bat
can start the dashboard without Flask.
"""

from __future__ import annotations

import csv
import io
import json
import re
import ssl
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.cn_sources import crawl_all_chinese_sources_with_status
from crawlers.rssless_sources import articles_to_rss
from config.ai_runtime import update_ai_models
from processors.ai_clients import get_analysis_ai_status, get_available_ai_models
from processors.fetch_ai import FetchAIAssistant
from processors.pr_analysis import build_pr_action_advice


INDEX_PATH = PROJECT_ROOT / "web" / "templates" / "index.html"
STORE_PATH = PROJECT_ROOT / "data" / "local_store.json"
REPORT_DIR = PROJECT_ROOT / "data" / "reports"

SOURCE_OPTIONS = [
    {"id": "cnstock_news", "name": "中国证券报", "type": "法披", "group": "四大法披媒体", "enabled": True},
    {"id": "shzqb", "name": "上海证券报", "type": "法披", "group": "四大法披媒体", "enabled": True},
    {"id": "stcn", "name": "证券时报", "type": "法披", "group": "四大法披媒体", "enabled": True},
    {"id": "zqrb", "name": "证券日报", "type": "法披", "group": "四大法披媒体", "enabled": True},
    {"id": "cls", "name": "财联社", "type": "快讯", "group": "财经科技媒体", "enabled": True},
    {"id": "jiemian", "name": "界面新闻", "type": "财经", "group": "财经科技媒体", "enabled": True},
    {"id": "latepost", "name": "晚点 LatePost", "type": "科技", "group": "财经科技媒体", "enabled": True},
    {"id": "yicai", "name": "第一财经", "type": "财经", "group": "财经科技媒体", "enabled": True},
    {"id": "36kr", "name": "36氪", "type": "科技", "group": "财经科技媒体", "enabled": True},
    {"id": "huxiu", "name": "虎嗅", "type": "科技", "group": "财经科技媒体", "enabled": True},
    {"id": "21jingji", "name": "21财经", "type": "财经", "group": "财经科技媒体", "enabled": True},
    {"id": "caixin", "name": "财新网", "type": "深度", "group": "财经科技媒体", "enabled": True},
    {"id": "wallstreetcn", "name": "华尔街见闻", "type": "市场", "group": "财经科技媒体", "enabled": True},
    {"id": "exchange_ann", "name": "交易所公告", "type": "原始", "group": "官方信息", "enabled": True},
    {"id": "regulator", "name": "监管机构", "type": "原始", "group": "官方信息", "enabled": True},
    {"id": "stats_latest", "name": "国家统计局最新发布", "type": "数据", "group": "官方信息", "enabled": True},
    {"id": "stats_interpretation", "name": "国家统计局数据解读", "type": "解读", "group": "官方信息", "enabled": True},
    {"id": "northbound", "name": "北向资金", "type": "资金", "group": "市场数据", "enabled": True},
    {"id": "a_share_index", "name": "A股指数", "type": "行情", "group": "市场数据", "enabled": True},
    {"id": "global_market", "name": "全球市场", "type": "行情", "group": "市场数据", "enabled": False},
]

SOURCE_GROUP_ORDER = ["四大法披媒体", "财经科技媒体", "官方信息", "市场数据"]

KEYWORDS = {
    "AI应用 / AI Agent": ["AI", "大模型", "Agent", "AGI", "推理", "训练", "算力"],
    "半导体 / PCB": ["芯片", "晶圆", "光刻", "EDA", "PCB", "封装", "服务器"],
    "具身智能与机器人": ["机器人", "具身智能", "人形机器人", "工业机器人", "控制器", "减速器"],
    "IPO / A股科技": ["IPO", "上市", "过会", "挂牌", "科创板", "交易所", "A股"],
    "港股科技": ["港股", "恒生科技", "南向资金", "平台公司", "AH映射"],
    "全球市场与宏观变量": ["统计局", "CPI", "PPI", "PMI", "美元", "人民币", "黄金", "原油", "美股", "港股"],
}

TRACKS = [
    {"id": "ai", "name": "AI应用 / AI Agent", "hint": "融资、产品、落地"},
    {"id": "semi", "name": "半导体 / PCB", "hint": "订单、报价、材料"},
    {"id": "robot", "name": "具身智能与机器人", "hint": "产品、零部件"},
    {"id": "ipo", "name": "IPO / A股科技", "hint": "审核、政策、流动性"},
    {"id": "hk", "name": "港股科技", "hint": "估值、资金"},
    {"id": "global", "name": "全球市场与宏观变量", "hint": "美元、美债、美股"},
]

EVENT_RULES = {
    "融资并购": ["融资", "投资", "并购", "收购", "领投", "A轮", "B轮", "C轮", "战略投资"],
    "财报业绩": ["财报", "营收", "净利润", "业绩", "同比", "环比", "亏损", "盈利"],
    "政策监管": ["监管", "政策", "证监会", "交易所", "新规", "处罚", "备案", "审核"],
    "产品发布": ["发布", "新品", "上线", "推出", "量产", "模型", "芯片", "产品"],
    "市场数据": ["统计局", "CPI", "PPI", "PMI", "价格指数", "工业增加值", "社会消费品零售", "固定资产投资"],
    "市场动态": ["上涨", "下跌", "涨停", "跌停", "市场", "股价", "指数", "行情", "资金"],
}

STATS_FEEDS = [
    {
        "source_id": "stats_latest",
        "source": "国家统计局最新发布",
        "url": "https://www.stats.gov.cn/sj/zxfb/rss.xml",
        "note": "国家统计局最新发布 RSS 原文链接采集",
    },
    {
        "source_id": "stats_interpretation",
        "source": "国家统计局数据解读",
        "url": "https://www.stats.gov.cn/sj/sjjd/rss.xml",
        "note": "国家统计局数据解读 RSS 原文链接采集",
    },
]

crawl_status = {
    "running": False,
    "last_run": None,
    "total_articles": 0,
    "topics_count": 0,
    "last_error": None,
    "active_sources": [],
    "elapsed_seconds": 0,
}


def json_ready(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    return value


def load_store():
    if not STORE_PATH.exists():
        return {"news": [], "topics": []}
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        data = {"news": [], "topics": []}
    data.setdefault("news", [])
    data.setdefault("topics", [])
    return data


def save_store(data):
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(json_ready(data), ensure_ascii=False, indent=2), encoding="utf-8")


def clean_text(value):
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def repair_mojibake(value):
    if not value or not any(marker in value for marker in ("脙", "脗", "忙", "氓", "猫")):
        return value
    try:
        repaired = value.encode("latin1").decode("utf-8")
    except Exception:
        return value
    return repaired if len(repaired) >= len(value) * 0.5 else value


def parse_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.now()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.now()


def parse_rss_time(value):
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


def fetch_text(url, timeout=12):
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 FinanceRadar/1.0",
        "Accept": "application/rss+xml,application/xml,text/html;q=0.9,*/*;q=0.8",
    })
    with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
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


def find_text(item, name):
    child = item.find(name)
    return child.text if child is not None and child.text else ""


def crawl_stats_sources(selected_source_ids=None):
    selected = set(selected_source_ids or [])
    results = []
    for feed in STATS_FEEDS:
        if selected and feed["source_id"] not in selected:
            continue
        try:
            root = ET.fromstring(fetch_text(feed["url"]))
        except Exception as exc:
            print(f"[{feed['source']}] RSS抓取失败: {exc}")
            continue
        for item in root.findall(".//item")[:15]:
            title = repair_mojibake(clean_text(find_text(item, "title")))
            url = clean_text(find_text(item, "link"))
            description = repair_mojibake(clean_text(find_text(item, "description")))
            pub_date = clean_text(find_text(item, "pubDate") or find_text(item, "pubTime"))
            if not title or not url:
                continue
            results.append(infer_article({
                "_id": url,
                "title": title,
                "original_title": title,
                "url": url,
                "original_url": url,
                "canonical_url": url,
                "url_status": "ok",
                "publish_time": parse_rss_time(pub_date),
                "content": description,
                "source": feed["source"],
                "source_id": feed["source_id"],
                "source_type": "官方数据",
                "collect_method": "rss",
                "source_note": feed["note"],
            }))
    return results


def infer_article(article):
    title = repair_mojibake(article.get("title", ""))
    content = repair_mojibake(article.get("content", ""))
    article["title"] = title
    article["content"] = content
    text = f"{title} {content}"

    event_type = "市场动态"
    for candidate, words in EVENT_RULES.items():
        if any(word.lower() in text.lower() for word in words):
            event_type = candidate
            break
    if article.get("source_id") in {"stats_latest", "stats_interpretation"}:
        event_type = "市场数据"

    industry = "其他"
    matched_tags = []
    if article.get("source_id") in {"stats_latest", "stats_interpretation"}:
        industry = "全球市场与宏观变量"
        matched_tags.extend(["宏观数据", "国家统计局"])
    for candidate, words in KEYWORDS.items():
        if candidate in text or any(word.lower() in text.lower() for word in words):
            industry = candidate
            matched_tags.append(candidate)
            matched_tags.extend([word for word in words if word.lower() in text.lower()][:3])

    market = "产业资讯"
    if event_type == "融资并购":
        market = "一级市场"
    elif event_type == "政策监管":
        market = "政策驱动"
    elif event_type == "市场数据" or article.get("source_type") == "官方数据":
        market = "宏观数据"

    companies = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9·]{2,20}(?:公司|集团|科技|股份|证券|银行|基金|能源|汽车|电子|半导体)", text)
    article["category"] = {"event_type": event_type, "industry": industry, "market": market}
    article["entities"] = {"companies": list(dict.fromkeys(companies))[:5], "people": [], "amount": ""}
    article["sentiment"] = "neutral"
    article["tags"] = list(dict.fromkeys(matched_tags + [event_type, industry]))[:7]
    article["heat_score"] = calculate_heat_score(article)
    article["url"] = article.get("url") or article.get("original_url") or article.get("canonical_url") or ""
    return article


def calculate_heat_score(article):
    base = 62
    text = f"{article.get('title', '')} {article.get('content', '')}"
    if article.get("source_type") == "官方数据":
        base += 12
    if any(word in text for word in ["融资", "并购", "财报", "监管", "统计局", "CPI", "PPI", "芯片", "AI", "大模型"]):
        base += 10
    if article.get("content"):
        base += min(len(article["content"]) // 160, 10)
    return min(base, 100)


def get_recent_news(hours=48, event_type=None, industry=None):
    since = datetime.now() - timedelta(hours=hours)
    news = []
    for raw_item in load_store().get("news", []):
        if raw_item.get("is_demo"):
            continue
        item = infer_article(dict(raw_item))
        published = parse_datetime(item.get("publish_time"))
        if published < since:
            continue
        category = item.get("category", {})
        if event_type and category.get("event_type") != event_type:
            continue
        if industry and category.get("industry") != industry:
            continue
        news.append(item)
    news.sort(key=lambda item: parse_datetime(item.get("publish_time")), reverse=True)
    return news


def generate_topics(news):
    buckets = {}
    for item in news:
        tags = item.get("tags") or [item.get("category", {}).get("industry", "其他")]
        for tag in tags:
            if not tag:
                continue
            bucket = buckets.setdefault(tag, {"items": [], "companies": []})
            bucket["items"].append(item)
            bucket["companies"].extend(item.get("entities", {}).get("companies", []))
    topics = []
    for tag, bucket in buckets.items():
        topics.append({
            "_id": f"topic_{tag}",
            "topic_name": tag,
            "keywords": [tag],
            "related_news_ids": [item.get("_id") or item.get("url", "") for item in bucket["items"]],
            "news_count": len(bucket["items"]),
            "heat_trend": "上行" if len(bucket["items"]) >= 2 else "观察",
            "related_companies": list(dict.fromkeys(bucket["companies"]))[:6],
            "create_time": datetime.now(),
        })
    topics.sort(key=lambda item: item["news_count"], reverse=True)
    return topics[:30]


def build_daily_summary(news, topics):
    if not news:
        return {
            "headline": "今日暂无可用线索",
            "bullets": ["先选择左侧来源并执行采集。", "抓取结果会优先展示原文标题与原文链接。", "明细表出现新闻后，点击公关选题分析卡片里的开始分析。"],
            "risks": ["数据不足，暂不形成对外选题判断。"],
            "follow_up": ["完成一次采集", "点击开始分析", "按可主动讲、需备口径、只监测三类分层"],
        }

    event_counts = {}
    industry_counts = {}
    for item in news:
        category = item.get("category", {})
        event_counts[category.get("event_type", "未分类")] = event_counts.get(category.get("event_type", "未分类"), 0) + 1
        industry_counts[category.get("industry", "其他")] = industry_counts.get(category.get("industry", "其他"), 0) + 1

    top_event = max(event_counts, key=event_counts.get)
    top_industry = max(industry_counts, key=industry_counts.get)
    high_value = [item for item in news if item.get("heat_score", 0) >= 74][:3]
    return {
        "headline": f"今日优先从{top_industry}中寻找科技公司可借势表达的选题，{top_event}是主要新闻钩子。",
        "bullets": [
            f"共归集 {len(news)} 条线索，覆盖 {len({item.get('source') for item in news})} 个来源，可作为今日选题会的新闻池。",
            f"最高频方向为 {top_industry}，优先筛选能承接公司观点、客户案例、产品进展或行业解读的线索。",
            f"热点标签：{', '.join([topic['topic_name'] for topic in topics[:4]]) or '暂无'}，可作为标题、采访提纲或社媒话题备选。",
        ],
        "risks": [
            "缺少原文链接、发布时间不清或疑似旧闻的内容不进入对外选题。",
            "单一媒体来源的信息只做观察，涉及监管、财报、资本动作时必须二次交叉核验。",
        ],
        "follow_up": [f"评估是否立项：{item.get('title', '')}" for item in high_value] or ["等待高热度线索出现"],
    }


def dashboard_payload():
    news = get_recent_news()
    topics = generate_topics(news)
    platform_counts = {}
    event_counts = {}
    industry_counts = {}
    valid_links = 0
    for item in news:
        platform_counts[item.get("source", "未知")] = platform_counts.get(item.get("source", "未知"), 0) + 1
        category = item.get("category", {})
        event_counts[category.get("event_type", "未分类")] = event_counts.get(category.get("event_type", "未分类"), 0) + 1
        industry_counts[category.get("industry", "其他")] = industry_counts.get(category.get("industry", "其他"), 0) + 1
        if item.get("url") and not item.get("is_demo"):
            valid_links += 1
    avg_heat = round(sum(item.get("heat_score", 0) for item in news) / len(news)) if news else 0
    return {
        "total_news": len(news),
        "recent_24h": len(get_recent_news(hours=24)),
        "topics_count": len(topics),
        "valid_links": valid_links,
        "pending_verify": max(len(news) - valid_links, 0),
        "hot_topics": topics[:10],
        "event_distribution": event_counts,
        "summary": {
            "total": len(news),
            "platform_counts": platform_counts,
            "event_counts": event_counts,
            "industry_counts": industry_counts,
            "avg_heat": avg_heat,
            "top_topic": topics[0]["topic_name"] if topics else "暂无",
        },
        "daily_summary": build_daily_summary(news, topics),
        "storage": {"mode": "local_json", "path": str(STORE_PATH)},
        "last_update": crawl_status.get("last_run"),
    }


def format_dt(value):
    return parse_datetime(value).strftime("%Y-%m-%d %H:%M")


def generate_report():
    news = get_recent_news()
    topics = generate_topics(news)
    summary = build_daily_summary(news, topics)
    lines = [
        f"# 科技公司公关选题日报 {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## 今日选题方向",
        f"- {summary['headline']}",
        *[f"- {item}" for item in summary["bullets"]],
        "",
        "## 素材与风险边界",
        *[f"- {item}" for item in summary["risks"]],
        "",
        "## 下一步行动",
        *[f"- {item}" for item in summary["follow_up"]],
        "",
        "## 新闻原文清单",
        "| 序号 | 发布时间 | 来源媒体 | 新闻钩子/原文标题 | 原文链接 | 选题方向 | 是否可用于选题 | 备注 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, item in enumerate(news[:100], 1):
        category = item.get("category", {})
        url = item.get("url") or item.get("original_url") or "链接待补充"
        title = str(item.get("title", "")).replace("|", " ")
        note = str(item.get("source_note", "")).replace("|", " ")
        lines.append(
            f"| {index} | {format_dt(item.get('publish_time'))} | {item.get('source','')} | "
            f"{title} | {url} | {category.get('industry','其他')} | 是 | {note} |"
        )
    return "\n".join(lines)


def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["title", "source", "publish_time", "event_type", "industry", "heat_score", "original_url"])
    for item in get_recent_news():
        category = item.get("category", {})
        writer.writerow([
            item.get("title", ""),
            item.get("source", ""),
            item.get("publish_time", ""),
            category.get("event_type", ""),
            category.get("industry", ""),
            item.get("heat_score", ""),
            item.get("url", ""),
        ])
    return output.getvalue().encode("utf-8-sig")


class RadarHandler(BaseHTTPRequestHandler):
    server_version = "FinanceRadar/1.3"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            return self.send_file(INDEX_PATH, "text/html; charset=utf-8")
        if path == "/api/config":
            fetch_ai = FetchAIAssistant()
            return self.send_json({"success": True, "data": {
                "monitor_topics": [{"name": key, "keywords": value, "enabled": True} for key, value in KEYWORDS.items()],
                "tracks": TRACKS,
                "sources": SOURCE_OPTIONS,
                "source_group_order": SOURCE_GROUP_ORDER,
                "event_types": list(EVENT_RULES.keys()),
                "default_keywords": sorted({word for words in KEYWORDS.values() for word in words}),
                "fetch_ai": fetch_ai.status(),
                "analysis_ai": get_analysis_ai_status(),
                "ai_models": get_available_ai_models(),
            }})
        if path == "/api/ai-models":
            return self.send_json({"success": True, "data": get_available_ai_models()})
        if path == "/api/news":
            news = get_recent_news(
                event_type=query.get("event_type", [""])[0] or None,
                industry=query.get("industry", [""])[0] or None,
            )
            per_page = int(query.get("per_page", ["100"])[0] or 100)
            page = int(query.get("page", ["1"])[0] or 1)
            start = (page - 1) * per_page
            return self.send_json({"success": True, "data": {
                "news": news[start:start + per_page],
                "total": len(news),
                "page": page,
                "per_page": per_page,
                "storage": {"mode": "local_json", "path": str(STORE_PATH)},
            }})
        if path == "/api/dashboard":
            return self.send_json({"success": True, "data": dashboard_payload()})
        if path == "/api/topics":
            return self.send_json({"success": True, "data": generate_topics(get_recent_news())})
        if path == "/api/analysis/pr":
            return self.send_json({"success": True, "data": build_pr_action_advice(get_recent_news(hours=48))})
        if path == "/api/crawl/status":
            return self.send_json({"success": True, "data": crawl_status})
        if path == "/api/search/status":
            return self.send_json({"success": True, "data": {
                "running": crawl_status["running"],
                "storage": {"mode": "local_json", "path": str(STORE_PATH)},
                "pipeline": [
                    {"name": "来源选择", "state": "ready"},
                    {"name": "抓取AI规划", "state": "ready"},
                    {"name": "RSS抓取", "state": "running" if crawl_status["running"] else "ready"},
                    {"name": "规则分类", "state": "ready"},
                    {"name": "报告生成", "state": "ready"},
                ],
            }})
        if path == "/api/export":
            export_type = query.get("type", ["csv"])[0]
            if export_type == "report":
                return self.send_download(generate_report().encode("utf-8"), "finance-report.md", "text/markdown; charset=utf-8")
            return self.send_download(export_csv(), "finance-news.csv", "text/csv; charset=utf-8")
        if path.startswith("/feeds/"):
            source_id = path.rsplit("/", 1)[-1].replace(".xml", "")
            news = [item for item in get_recent_news(hours=48) if source_id == "all" or item.get("source_id") == source_id]
            feed = articles_to_rss(news[:80], title=f"Finance Radar - {source_id}")
            return self.send_bytes(feed.encode("utf-8"), "application/rss+xml; charset=utf-8")

        return self.send_json({"success": False, "error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/crawl/start":
            return self.handle_crawl()
        if parsed.path == "/api/report/generate":
            report = generate_report()
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            filename = REPORT_DIR / f"财经日报_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            filename.write_text(report, encoding="utf-8")
            return self.send_json({"success": True, "data": {"report": report, "filename": str(filename)}})
        if parsed.path == "/api/fetch-ai/plan":
            payload = self.read_json_body()
            plan = FetchAIAssistant().build_search_plan(
                sources=payload.get("sources"),
                tracks=payload.get("tracks"),
            )
            return self.send_json({"success": True, "data": plan})
        if parsed.path == "/api/config/ai-models":
            payload = self.read_json_body()
            try:
                update_ai_models(
                    fetch_model=payload.get("fetch_model"),
                    analysis_model=payload.get("analysis_model"),
                )
                return self.send_json({"success": True, "data": {
                    "fetch_ai": FetchAIAssistant().status(),
                    "analysis_ai": get_analysis_ai_status(),
                }})
            except ValueError as exc:
                return self.send_json({"success": False, "error": str(exc)}, status=400)
        return self.send_json({"success": False, "error": "Not found"}, status=404)

    def handle_crawl(self):
        started_at = datetime.now()
        payload = self.read_json_body()
        selected_source_ids = payload.get("source_ids") or []
        crawl_status.update({"running": True, "last_error": None})
        try:
            crawl_result = crawl_all_chinese_sources_with_status(selected_source_ids or None)
            source_status = crawl_result.get("status", [])
            articles = [infer_article(item) for item in crawl_result.get("articles", [])]
            data = load_store()
            existing = [item for item in data.get("news", []) if not item.get("is_demo")]
            by_id = {item.get("_id") or item.get("url") or item.get("title"): item for item in existing}
            for item in articles:
                item["crawl_time"] = datetime.now()
                by_id[item.get("_id") or item.get("url") or item.get("title")] = item
            data["news"] = list(by_id.values())
            data["topics"] = generate_topics(data["news"])
            save_store(data)
            crawl_status.update({
                "running": False,
                "last_run": datetime.now().isoformat(),
                "total_articles": len(articles),
                "topics_count": len(data["topics"]),
                "active_sources": sorted({item.get("source", "未知") for item in articles}),
                "elapsed_seconds": round((datetime.now() - started_at).total_seconds(), 2),
            })
            return self.send_json({"success": True, "data": {
                "articles_count": len(articles),
                "topics_count": len(data["topics"]),
                "source_status": source_status,
                "storage": {"mode": "local_json", "path": str(STORE_PATH)},
            }})
        except Exception as exc:
            crawl_status.update({"running": False, "last_error": str(exc)})
            return self.send_json({"success": False, "error": str(exc)}, status=500)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def send_file(self, path, content_type):
        body = Path(path).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_no_cache_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload, status=200):
        body = json.dumps(json_ready(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_no_cache_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_download(self, body, filename, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f"attachment; filename={filename}")
        self.send_no_cache_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_no_cache_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_no_cache_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("X-Finance-Radar-Version", "1.3")


def run(host="127.0.0.1", port=5000):
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fetch_status = FetchAIAssistant().status()
    analysis_status = get_analysis_ai_status()
    gpt_status = analysis_status.get("providers", {}).get("gpt", {})
    server = ThreadingHTTPServer((host, port), RadarHandler)
    print("=" * 60)
    print("财经日报雷达 - Web 服务启动")
    print("=" * 60)
    print(f"访问地址: http://{host}:{port}")
    print(f"抓取AI: {'已配置' if fetch_status.get('configured') else '未配置'} ({fetch_status.get('model') or '-'})")
    print(f"分析AI: {'已配置' if gpt_status.get('configured') else '未配置'} ({gpt_status.get('model') or '-'})")
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    server.serve_forever()


if __name__ == "__main__":
    run()
