"""竞品动态追踪与分析。"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Dict, List

from config.competitors import COMPETITOR_EVENT_TYPES, get_competitor_aliases
from processors.ai_clients import get_analysis_gpt_client


def extract_competitor_news(news_list: List[Dict], enabled_competitors: List[str] = None) -> Dict:
    """从新闻列表中提取竞品相关信息。"""
    aliases_map = get_competitor_aliases()
    competitor_news = defaultdict(list)

    for news_item in news_list:
        title = news_item.get("title", "")
        content = news_item.get("content", "")
        text = f"{title} {content}"

        # 检测是否包含竞品名称
        for alias, company_name in aliases_map.items():
            # 如果指定了追踪列表，只追踪列表中的竞品
            if enabled_competitors and company_name not in enabled_competitors:
                continue

            if alias in text:
                # 判断事件类型
                event_type = "其他动态"
                for event_name, keywords in COMPETITOR_EVENT_TYPES.items():
                    if any(keyword in text for keyword in keywords):
                        event_type = event_name
                        break

                competitor_news[company_name].append({
                    "title": title,
                    "source": news_item.get("source", ""),
                    "publish_time": str(news_item.get("publish_time", "")),
                    "url": news_item.get("url") or news_item.get("original_url") or "",
                    "event_type": event_type,
                    "heat_score": news_item.get("heat_score", 0),
                    "matched_alias": alias,
                })
                break  # 避免同一条新闻被重复匹配

    # 按热度排序
    for company in competitor_news:
        competitor_news[company].sort(key=lambda x: x.get("heat_score", 0), reverse=True)

    return dict(competitor_news)


def analyze_competitor_dynamics(competitor_news: Dict, limit: int = 5) -> Dict:
    """使用AI分析竞品动态。"""
    if not competitor_news:
        return {
            "summary": "暂无竞品动态信息。",
            "key_events": [],
            "competitive_insights": [],
            "response_suggestions": [],
        }

    # 准备精简的竞品新闻数据
    compact_data = {}
    for company, news_list in list(competitor_news.items())[:10]:  # 最多分析10家竞品
        compact_data[company] = [
            {
                "title": item["title"],
                "event_type": item["event_type"],
                "source": item["source"],
            }
            for item in news_list[:limit]
        ]

    client = get_analysis_gpt_client()
    if not client.configured:
        return _fallback_competitor_analysis(competitor_news)

    prompt = f"""
你是科技公司公关顾问，专注AI硬件领域竞品分析。请基于以下竞品动态，生成公关导向的竞争分析。

竞品新闻：
{json.dumps(compact_data, ensure_ascii=False, indent=2)}

要求：
1. 站在AI硬件公司公关视角，不是投资分析师或行业研究员。
2. 关注可用于对外传播、媒体问答、选题策划的竞争情报。
3. 识别需要主动回应的竞品动作、可借势的行业趋势、需要预备口径的风险点。
4. 输出要实操、具体，适合放在选题会或传播看板。
5. 严格输出JSON格式。

输出格式：
{{
  "summary": "一句话总结本周期竞品动态重点（从公关响应角度）",
  "key_events": [
    {{
      "competitor": "竞品名称",
      "event": "关键事件描述",
      "pr_impact": "对我方公关工作的影响（需主动回应/可借势传播/需备口径/仅观察）",
      "urgency": "high/medium/low"
    }}
  ],
  "competitive_insights": [
    "竞争洞察1：某竞品在产品/市场/品牌层面的动作，我方可对标或差异化表达的点",
    "竞争洞察2"
  ],
  "response_suggestions": [
    {{
      "scenario": "场景：如媒体问及英伟达新品",
      "talking_points": ["口径要点1", "口径要点2"],
      "materials_needed": ["需要准备的素材或数据"]
    }}
  ]
}}
"""

    try:
        result = client.chat_json(
            [
                {"role": "system", "content": "你是AI硬件行业公关竞品分析助手，只输出JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return result
    except Exception:
        return _fallback_competitor_analysis(competitor_news)


def _fallback_competitor_analysis(competitor_news: Dict) -> Dict:
    """竞品分析降级逻辑。"""
    key_events = []
    for company, news_list in list(competitor_news.items())[:5]:
        if news_list:
            top_news = news_list[0]
            key_events.append({
                "competitor": company,
                "event": top_news["title"],
                "pr_impact": "需跟进评估",
                "urgency": "medium" if top_news.get("heat_score", 0) > 70 else "low",
            })

    return {
        "summary": f"本期监测到 {len(competitor_news)} 家竞品动态，建议重点关注产品发布和财报业绩类信息。",
        "key_events": key_events,
        "competitive_insights": [
            "竞品动态已采集，建议结合业务团队判断是否需要主动响应或预备口径。",
        ],
        "response_suggestions": [
            {
                "scenario": "竞品产品发布被媒体问及",
                "talking_points": ["确认我方产品差异化优势", "强调客户实际应用场景"],
                "materials_needed": ["我方产品技术参数对比", "客户案例或标杆项目"],
            }
        ],
    }


def generate_competitor_report(competitor_news: Dict, analysis: Dict) -> str:
    """生成竞品追踪报告文本。"""
    lines = [
        "## 竞品动态追踪",
        "",
        f"**本期概览**：{analysis.get('summary', '暂无竞品动态')}",
        "",
    ]

    if analysis.get("key_events"):
        lines.append("### 关键事件")
        for event in analysis["key_events"]:
            urgency_label = {"high": "🔴 高", "medium": "🟡 中", "low": "⚪ 低"}.get(event.get("urgency", "low"), "")
            lines.append(f"- **{event['competitor']}**：{event['event']}")
            lines.append(f"  - 公关影响：{event['pr_impact']}")
            lines.append(f"  - 优先级：{urgency_label}")
        lines.append("")

    if analysis.get("competitive_insights"):
        lines.append("### 竞争洞察")
        for insight in analysis["competitive_insights"]:
            lines.append(f"- {insight}")
        lines.append("")

    if analysis.get("response_suggestions"):
        lines.append("### 响应建议")
        for suggestion in analysis["response_suggestions"]:
            lines.append(f"**{suggestion['scenario']}**")
            if suggestion.get("talking_points"):
                lines.append("口径要点：")
                for point in suggestion["talking_points"]:
                    lines.append(f"  - {point}")
            if suggestion.get("materials_needed"):
                lines.append("需要准备：")
                for material in suggestion["materials_needed"]:
                    lines.append(f"  - {material}")
            lines.append("")

    # 附上详细新闻列表
    if competitor_news:
        lines.append("### 详细新闻")
        for company, news_list in list(competitor_news.items())[:10]:
            lines.append(f"**{company}**")
            for news in news_list[:3]:
                lines.append(f"- [{news['event_type']}] {news['title']} ({news['source']})")
                if news.get('url'):
                    lines.append(f"  链接：{news['url']}")
            lines.append("")

    return "\n".join(lines)
