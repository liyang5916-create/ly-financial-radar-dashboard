"""Fetch AI assistant for collection planning."""

from __future__ import annotations

from typing import Dict, List

from processors.ai_clients import get_fetch_ai_client


DEFAULT_SOURCES = [
    "中国证券报",
    "上海证券报",
    "证券时报",
    "证券日报",
    "财联社",
    "界面新闻",
    "晚点 LatePost",
    "第一财经",
    "36氪",
    "21财经",
    "财新网",
    "华尔街见闻",
    "交易所公告",
    "监管机构",
    "国家统计局最新发布",
    "国家统计局数据解读",
]

DEFAULT_TRACKS = [
    "AI应用 / AI Agent",
    "半导体 / PCB",
    "具身智能与机器人",
    "IPO / A股科技",
    "港股科技",
    "全球市场与宏观变量",
]


class FetchAIAssistant:
    def __init__(self):
        self.client = get_fetch_ai_client()

    def status(self) -> Dict:
        return {
            "configured": self.client.configured,
            "base_url": self.client.config.base_url,
            "model": self.client.config.model,
            "key": self.client.masked_key(),
            "role": "fetch",
        }

    def build_search_plan(self, sources: List[str] = None, tracks: List[str] = None) -> Dict:
        sources = sources or DEFAULT_SOURCES
        tracks = tracks or DEFAULT_TRACKS
        fallback = self._fallback_plan(sources, tracks)
        if not self.client.configured:
            fallback["mode"] = "fallback"
            fallback["note"] = "抓取AI未配置，使用本地关键词计划。"
            return fallback

        prompt = f"""
你是财经科技日报的抓取规划助手。请基于以下信息源和重点赛道，生成用于过去24小时与盘前信息抓取的搜索计划。

信息源：{", ".join(sources)}
重点赛道：{", ".join(tracks)}

请严格输出 JSON，不要输出 Markdown。格式：
{{
  "queries": [
    {{
      "track": "赛道",
      "query": "搜索词",
      "priority": "high/medium/low",
      "source_hint": ["建议优先检索的信息源"],
      "verify_with": ["建议交叉核验的信息源"]
    }}
  ],
  "quality_rules": ["抓取和核验规则"],
  "market_data": ["需要抓取的市场指标"]
}}
"""
        try:
            plan = self.client.chat_json(
                [
                    {"role": "system", "content": "你只输出可解析 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            plan.setdefault("mode", "fetch_ai")
            return plan
        except Exception as exc:
            fallback["mode"] = "fallback"
            fallback["note"] = f"抓取AI调用失败，使用本地关键词计划: {exc}"
            return fallback

    def _fallback_plan(self, sources: List[str], tracks: List[str]) -> Dict:
        query_map = {
            "AI": ["AI Agent 融资", "大模型 应用 发布", "AI 应用 企业客户"],
            "半导体": ["PCB 订单 AI服务器", "半导体 设备 评级", "芯片 产业链 公告"],
            "机器人": ["具身智能 机器人 订单", "人形机器人 零部件", "机器人 战略合作"],
            "IPO": ["IPO 审核 科技 企业", "A股 科技 政策 监管", "交易所 科创板 公告"],
            "港股": ["港股科技 资金流", "恒生科技 美股映射", "港股 科技 财报"],
            "全球": ["国家统计局 CPI PPI", "美元指数 美股科技", "黄金 原油 人民币汇率"],
        }
        queries = []
        for track in tracks:
            words = query_map["全球"]
            for key, value in query_map.items():
                if key in track:
                    words = value
                    break
            for query in words:
                queries.append({
                    "track": track,
                    "query": query,
                    "priority": "high" if len(queries) < 8 else "medium",
                    "source_hint": sources[:5],
                    "verify_with": ["原始公告", "四大法披媒体", "国家统计局"],
                })
        return {
            "queries": queries,
            "quality_rules": [
                "优先原始公告、交易所文件、监管文件和官方数据源。",
                "同一事件至少保留一个原始来源或权威来源。",
                "单一来源且无法核验的信息标注待核验。",
                "正式总表标题必须沿用原文标题，并附原文链接。",
            ],
            "market_data": ["上证指数", "深证成指", "创业板指", "科创50", "沪深300", "北向资金", "CPI/PPI/PMI", "美元指数", "人民币汇率", "黄金", "原油", "美股主要指数", "港股科技指数"],
        }
