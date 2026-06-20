"""Flask Web 后端。"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS

from config.ai_runtime import update_ai_models
from config.competitors import get_all_competitors
from config.settings import KEYWORDS
from crawlers.cn_sources import crawl_all_chinese_sources
from database.operations import DatabaseManager
from output.daily_report import DailyReportGenerator
from processors.aggregator import TopicAggregator
from processors.ai_clients import get_analysis_ai_status, get_available_ai_models
from processors.competitor_tracker import analyze_competitor_dynamics, extract_competitor_news, generate_competitor_report
from processors.deduplicator import Deduplicator
from processors.extractor import InfoExtractor
from processors.fetch_ai import FetchAIAssistant
from processors.pr_analysis import build_pr_action_advice

app = Flask(__name__)
CORS(app)


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Finance-Radar-Version"] = "1.3"
    return response

crawl_status = {
    "running": False,
    "last_run": None,
    "total_articles": 0,
    "topics_count": 0,
    "last_error": None,
    "active_sources": [],
    "elapsed_seconds": 0,
}

SOURCE_OPTIONS = [
    {"id": "cnstock_news", "name": "中国证券报", "type": "法披", "group": "四大法披媒体", "enabled": True},
    {"id": "shzqb", "name": "上海证券报", "type": "法披", "group": "四大法披媒体", "enabled": True},
    {"id": "stcn", "name": "证券时报", "type": "法披", "group": "四大法披媒体", "enabled": True},
    {"id": "zqrb", "name": "证券日报", "type": "法披", "group": "四大法披媒体", "enabled": True},
    {"id": "exchange_ann", "name": "交易所公告", "type": "原始公告", "group": "官方信息", "enabled": True},
    {"id": "regulator", "name": "监管机构", "type": "监管", "group": "官方信息", "enabled": True},
    {"id": "stats_latest", "name": "国家统计局最新发布", "type": "官方数据", "group": "官方信息", "enabled": True},
    {"id": "stats_interpretation", "name": "国家统计局数据解读", "type": "数据解读", "group": "官方信息", "enabled": True},
    {"id": "cls", "name": "财联社", "type": "快讯", "group": "快讯 / 市场异动", "enabled": True},
    {"id": "wallstreetcn", "name": "华尔街见闻", "type": "市场", "group": "快讯 / 市场异动", "enabled": True},
    {"id": "yicai", "name": "第一财经", "type": "综合财经", "group": "综合财经 / 深度报道", "enabled": True},
    {"id": "21jingji", "name": "21财经", "type": "财经", "group": "综合财经 / 深度报道", "enabled": True},
    {"id": "caixin", "name": "财新网", "type": "深度", "group": "综合财经 / 深度报道", "enabled": True},
    {"id": "jiemian", "name": "界面新闻", "type": "财经", "group": "综合财经 / 深度报道", "enabled": True},
    {"id": "latepost", "name": "晚点 LatePost", "type": "科技产业", "group": "科技产业 / 创投媒体", "enabled": True},
    {"id": "36kr", "name": "36氪", "type": "创投科技", "group": "科技产业 / 创投媒体", "enabled": True},
    {"id": "huxiu", "name": "虎嗅", "type": "科技产业", "group": "科技产业 / 创投媒体", "enabled": True},
    {"id": "northbound", "name": "北向资金", "type": "资金", "group": "市场数据 / 资金指标", "enabled": True},
    {"id": "a_share_index", "name": "A股指数", "type": "行情", "group": "市场数据 / 资金指标", "enabled": True},
    {"id": "global_market", "name": "全球市场", "type": "行情", "group": "市场数据 / 资金指标", "enabled": False},
]

SOURCE_GROUP_ORDER = [
    "四大法披媒体",
    "快讯 / 市场异动",
    "综合财经 / 深度报道",
    "科技产业 / 创投媒体",
    "官方信息",
    "市场数据 / 资金指标",
]

EVENT_RULES = {
    "融资并购": ["融资", "投资", "并购", "收购", "领投", "A轮", "B轮", "C轮", "战略投资"],
    "财报业绩": ["财报", "营收", "净利润", "业绩", "同比", "环比", "亏损", "盈利"],
    "政策监管": ["监管", "政策", "证监会", "交易所", "新规", "处罚", "备案", "审批"],
    "产品发布": ["发布", "新品", "上线", "推出", "量产", "模型", "芯片", "产品"],
    "人事变动": ["任命", "辞任", "离职", "CEO", "CFO", "董事长", "高管"],
    "市场数据": ["统计局", "CPI", "PPI", "PMI", "价格指数", "生产资料", "工业增加值", "社会消费品零售", "固定资产投资"],
    "市场动态": ["上涨", "下跌", "涨停", "跌停", "市场", "股价", "指数", "行情"],
}

COMPANY_PATTERN = re.compile(r"[\u4e00-\u9fa5A-Za-z0-9·]{2,20}(?:公司|集团|科技|股份|证券|银行|基金|能源|汽车|电子|半导体)")
ANALYSIS_MODE_LABELS = {"gpt": "GPT", "claude": "Claude", "compare": "GPT + Claude 对比"}


def json_ready(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    return value


def infer_article(article):
    title = article.get("title", "")
    content = article.get("content", "")
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
        industry = "全球市场"
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

    companies = list(dict.fromkeys(COMPANY_PATTERN.findall(text)))[:5]
    article.setdefault("category", {"event_type": event_type, "industry": industry, "market": market})
    article.setdefault("entities", {"companies": companies, "people": [], "amount": ""})
    article.setdefault("sentiment", "neutral")
    article.setdefault("tags", list(dict.fromkeys(matched_tags + [event_type, industry]))[:7])
    article["heat_score"] = calculate_heat_score(article)
    return article


def calculate_heat_score(article):
    base = 60
    text = f"{article.get('title', '')} {article.get('content', '')}"
    if article.get("source_type") == "官方数据":
        base += 12
    if any(word in text for word in ["融资", "并购", "财报", "监管", "统计局", "CPI", "PPI", "大模型", "芯片"]):
        base += 15
    if article.get("content"):
        base += min(len(article["content"]) // 120, 12)
    return min(base, 100)


def normalize_analysis_mode(value):
    mode = (value or "gpt").lower()
    return mode if mode in ANALYSIS_MODE_LABELS else "gpt"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/tabs")
def index_tabs():
    """多标签页看板"""
    return render_template("index_tabs.html")


@app.route("/api/config")
def config_api():
    fetch_ai = FetchAIAssistant()
    topics = [{"name": key, "keywords": value, "enabled": True} for key, value in KEYWORDS.items()]
    return jsonify({"success": True, "data": {
        "monitor_topics": topics,
        "sources": SOURCE_OPTIONS,
        "source_group_order": SOURCE_GROUP_ORDER,
        "event_types": list(EVENT_RULES.keys()),
        "default_keywords": sorted({word for words in KEYWORDS.values() for word in words}),
        "fetch_ai": fetch_ai.status(),
        "analysis_ai": get_analysis_ai_status(),
        "ai_models": get_available_ai_models(),
    }})


@app.route("/api/ai-models")
def ai_models_api():
    return jsonify({"success": True, "data": get_available_ai_models()})


@app.route("/api/dashboard")
def dashboard_api():
    db = DatabaseManager()
    start = datetime.now() - timedelta(days=7)
    news = db.find_news_by_date(start, datetime.now())
    news = [infer_article(item) for item in news]
    topics = TopicAggregator().generate_topics(news, min_articles=1)
    platform_counts, event_counts, industry_counts = {}, {}, {}
    for item in news:
        platform_counts[item.get("source", "未知")] = platform_counts.get(item.get("source", "未知"), 0) + 1
        category = item.get("category", {})
        event_counts[category.get("event_type", "未分类")] = event_counts.get(category.get("event_type", "未分类"), 0) + 1
        industry_counts[category.get("industry", "其他")] = industry_counts.get(category.get("industry", "其他"), 0) + 1
    avg_heat = round(sum(item.get("heat_score", 0) for item in news) / len(news)) if news else 0
    storage = db.get_storage_info()
    db.close()
    return jsonify({"success": True, "data": json_ready({
        "total_news": len(news),
        "recent_24h": len([item for item in news if datetime.fromisoformat(str(item.get("publish_time")).replace("Z", "+00:00")).replace(tzinfo=None) >= datetime.now() - timedelta(hours=24)]),
        "topics_count": len(topics),
        "hot_topics": topics[:10],
        "event_distribution": event_counts,
        "summary": {"total": len(news), "platform_counts": platform_counts, "event_counts": event_counts, "industry_counts": industry_counts, "avg_heat": avg_heat, "top_topic": topics[0]["topic_name"] if topics else "暂无"},
        "storage": storage,
        "last_update": crawl_status.get("last_run"),
    })})


@app.route("/api/news")
def news_api():
    event_type = request.args.get("event_type")
    industry = request.args.get("industry")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 80))
    db = DatabaseManager()
    news = db.find_news_by_category(event_type, industry) if event_type or industry else db.find_news_by_date(datetime.now() - timedelta(days=7), datetime.now())
    news = [infer_article(item) for item in news]
    total = len(news)
    start = (page - 1) * per_page
    storage = db.get_storage_info()
    db.close()
    return jsonify({"success": True, "data": {"news": json_ready(news[start:start + per_page]), "total": total, "page": page, "per_page": per_page, "storage": storage}})


@app.route("/api/topics")
def topics_api():
    db = DatabaseManager()
    topics = db.get_hot_topics(limit=50)
    db.close()
    return jsonify({"success": True, "data": json_ready(topics)})


@app.route("/api/analysis/pr")
def pr_analysis_api():
    db = DatabaseManager()
    news = db.find_news_by_date(datetime.now() - timedelta(hours=48), datetime.now())
    db.close()
    news = [infer_article(item) for item in news]
    return jsonify({"success": True, "data": build_pr_action_advice(news)})


@app.route("/api/competitors")
def competitors_api():
    """获取竞品列表配置。"""
    return jsonify({"success": True, "data": get_all_competitors()})


@app.route("/api/competitors/tracking", methods=["POST"])
def competitor_tracking_api():
    """分析竞品动态。"""
    data = request.get_json() or {}
    enabled_competitors = data.get("enabled_competitors")

    db = DatabaseManager()
    news = db.find_news_by_date(datetime.now() - timedelta(days=7), datetime.now())
    db.close()
    news = [infer_article(item) for item in news]

    competitor_news = extract_competitor_news(news, enabled_competitors)
    analysis = analyze_competitor_dynamics(competitor_news)
    report = generate_competitor_report(competitor_news, analysis)

    return jsonify({
        "success": True,
        "data": {
            "competitor_news": competitor_news,
            "analysis": analysis,
            "report": report,
        }
    })


@app.route("/api/crawl/start", methods=["POST"])
def start_crawl():
    global crawl_status
    if crawl_status["running"]:
        return jsonify({"success": False, "error": "爬取任务正在运行中"})
    started_at = datetime.now()
    crawl_status.update({"running": True, "last_error": None})
    try:
        data = request.get_json() or {}
        raw_articles = crawl_all_chinese_sources(selected_source_ids=data.get("source_ids") or None)
        unique_articles = Deduplicator(use_redis=False).deduplicate_articles(raw_articles)
        if data.get("use_llm", False):
            processed_articles = InfoExtractor().batch_extract(unique_articles)
        else:
            processed_articles = [infer_article(item) for item in unique_articles]
        topics = TopicAggregator().generate_topics(processed_articles, min_articles=1)
        db = DatabaseManager()
        for article in processed_articles:
            article["_id"] = article.get("url") or article.get("title")
            article["crawl_time"] = datetime.now()
            db.insert_news(article)
        for topic in topics:
            db.topics_collection.insert_one(topic)
        storage = db.get_storage_info()
        db.close()
        crawl_status.update({
            "running": False,
            "last_run": datetime.now().isoformat(),
            "total_articles": len(processed_articles),
            "topics_count": len(topics),
            "active_sources": sorted({item.get("source", "未知") for item in processed_articles}),
            "elapsed_seconds": round((datetime.now() - started_at).total_seconds(), 2),
        })
        return jsonify({"success": True, "data": {"articles_count": len(processed_articles), "topics_count": len(topics), "storage": storage}})
    except Exception as exc:
        crawl_status.update({"running": False, "last_error": str(exc)})
        return jsonify({"success": False, "error": str(exc)})


@app.route("/api/crawl/status")
def crawl_status_api():
    return jsonify({"success": True, "data": crawl_status})


@app.route("/api/search/status")
def search_status_api():
    return jsonify({"success": True, "data": {
        "running": crawl_status["running"],
        "storage": {"mode": "local_json", "path": str(Path(__file__).resolve().parents[1] / "data" / "local_store.json")},
        "pipeline": [
            {"name": "来源选择", "state": "ready"},
            {"name": "RSS抓取", "state": "running" if crawl_status["running"] else "ready"},
            {"name": "规则分类", "state": "ready"},
            {"name": "报告生成", "state": "ready"},
        ],
    }})


@app.route("/api/report/generate", methods=["POST"])
def generate_report_api():
    data = request.get_json() or {}
    analysis_mode = normalize_analysis_mode(data.get("analysis_mode"))
    generator = DailyReportGenerator()
    report = generator.generate_report()
    filename = generator.save_report(report)
    return jsonify({"success": True, "data": {"report": report, "filename": filename, "analysis_mode": analysis_mode, "analysis_label": ANALYSIS_MODE_LABELS[analysis_mode], "analysis_ai": get_analysis_ai_status()}})


@app.route("/api/fetch-ai/plan", methods=["POST"])
def fetch_ai_plan_api():
    data = request.get_json() or {}
    plan = FetchAIAssistant().build_search_plan(sources=data.get("sources"), tracks=data.get("tracks"))
    return jsonify({"success": True, "data": plan})


@app.route("/api/config/ai-models", methods=["POST"])
def update_ai_models_api():
    data = request.get_json() or {}
    try:
        update_ai_models(fetch_model=data.get("fetch_model"), analysis_model=data.get("analysis_model"))
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "data": {
        "fetch_ai": FetchAIAssistant().status(),
        "analysis_ai": get_analysis_ai_status(),
    }})


@app.route("/api/export")
def export_api():
    export_type = request.args.get("type", "csv")
    if export_type == "report":
        report = DailyReportGenerator().generate_report()
        return Response(report, mimetype="text/markdown", headers={"Content-Disposition": "attachment; filename=finance-report.md"})
    db = DatabaseManager()
    news = db.find_news_by_date(datetime.now() - timedelta(days=7), datetime.now())
    db.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["title", "source", "publish_time", "event_type", "industry", "heat_score", "url"])
    for item in news:
        category = item.get("category", {})
        writer.writerow([item.get("title", ""), item.get("source", ""), item.get("publish_time", ""), category.get("event_type", ""), category.get("industry", ""), item.get("heat_score", ""), item.get("url", "")])
    return Response(output.getvalue().encode("utf-8-sig"), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=finance-news.csv"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
