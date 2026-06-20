"""PR topic analysis based on collected finance and tech news items."""

from __future__ import annotations

import json
from typing import Dict, List

from processors.ai_clients import get_analysis_gpt_client


def build_pr_action_advice(news: List[Dict], limit: int = 30) -> Dict:
    compact_news = [_compact_item(item) for item in news[:limit]]
    fallback = _fallback_advice(compact_news)
    client = get_analysis_gpt_client()
    if not client.configured or not compact_news:
        fallback["mode"] = "fallback"
        return fallback

    prompt = f"""
你是服务AI硬件科技公司的公关顾问。请基于以下新闻线索，为公关团队生成实操性的选题会提案。

要求：
1. 只基于给定新闻，不虚构事实。
2. 站在AI硬件公司公关实战角度，输出可直接用于选题会、媒体沟通、社媒运营的内容。
3. 重点关注：AI芯片、GPU、算力基础设施、AI服务器、智算中心等AI硬件产业链。
4. 每条建议要具体、可执行，适合放在看板卡片或选题提案中。
5. 区分媒体价值（主动pitch vs 被动响应）、时效性（今日必做 vs 本周储备）、传播渠道（媒体稿 vs 社媒 vs 高管发声）。
6. 严格输出JSON格式。

新闻线索：
{compact_news}

输出格式：
{{
  "editorial_direction": "一句话总结今日最适合科技公司公关立项的主选题方向及原因",
  "topic_opportunities": [
    {{
      "topic": "选题标题（新闻钩子）",
      "angle": "我方可讲的角度（技术/产品/客户案例/行业趋势）",
      "media_value": "high（适合主动pitch媒体）/medium（被动响应）/low（仅内部背景）",
      "urgency": "today（今日必做）/this_week（本周储备）/longterm（长期观察）",
      "channel": "media（媒体发稿）/social（社媒话题）/executive（高管发声）/internal（内部背景）"
    }}
  ],
  "pitch_angles": [
    {{
      "angle": "对外表达角度",
      "supporting_points": ["支撑论据1", "支撑论据2"],
      "differentiation": "与竞品差异化表达点"
    }}
  ],
  "proof_materials": [
    "需要补齐的证据/素材1（如：我方GPU性能数据）",
    "素材2（如：标杆客户案例）"
  ],
  "next_actions": [
    {{
      "action": "具体行动（如：联系36氪记者pitch算力中心选题）",
      "owner": "负责人角色（如：媒介经理/内容主编/高管助理）",
      "deadline": "完成时间（today/this_week）"
    }}
  ],
  "interview_questions": [
    "如果媒体采访，可以主动引导的问题1",
    "引导问题2"
  ],
  "social_topics": [
    "适合发社媒的话题角度1（如：#AI算力军备赛#我们的差异化打法）",
    "话题2"
  ],
  "watch_items": ["继续观察的趋势或竞品动向1", "事项2"],
  "risk_flags": ["不宜直接外发或需谨慎使用的风险1", "风险2"]
}}
"""
    try:
        result = client.chat_json(
            [
                {"role": "system", "content": "你是AI硬件科技公司公关选题分析助手，只输出可解析JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        # 标准化输出格式
        return {
            "mode": "analysis_ai",
            "editorial_direction": _text(result.get("editorial_direction"), fallback["editorial_direction"]),
            "topic_opportunities": result.get("topic_opportunities", fallback["topic_opportunities"]),
            "pitch_angles": result.get("pitch_angles", fallback["pitch_angles"]),
            "proof_materials": _string_list(result.get("proof_materials"), fallback["proof_materials"]),
            "next_actions": result.get("next_actions", fallback["next_actions"]),
            "interview_questions": _string_list(result.get("interview_questions"), []),
            "social_topics": _string_list(result.get("social_topics"), []),
            "watch_items": _string_list(result.get("watch_items"), fallback["watch_items"]),
            "risk_flags": _string_list(result.get("risk_flags"), fallback["risk_flags"]),
            # 保持向后兼容
            "priority_followup": _text(result.get("editorial_direction"), fallback["editorial_direction"]),
            "message_preparation": "；".join(_string_list(result.get("proof_materials"), [])[:2]),
            "communication_timing": "；".join([a.get("action", "") if isinstance(a, dict) else str(a) for a in (result.get("next_actions") or [])[:2]]),
        }
    except Exception as exc:
        fallback["mode"] = "fallback"
        fallback["error"] = str(exc)
        return fallback


def _compact_item(item: Dict) -> Dict:
    category = item.get("category", {}) or {}
    return {
        "title": item.get("title", ""),
        "source": item.get("source", ""),
        "publish_time": str(item.get("publish_time", "")),
        "event_type": category.get("event_type", ""),
        "industry": category.get("industry", ""),
        "heat_score": item.get("heat_score", 0),
        "url": item.get("url") or item.get("original_url") or item.get("canonical_url") or "",
    }


def _fallback_advice(compact_news: List[Dict]) -> Dict:
    if not compact_news:
        return {
            "editorial_direction": "暂无足够新闻线索，先完成抓取并核验原文来源。",
            "topic_opportunities": [],
            "pitch_angles": [],
            "proof_materials": ["准备基础事实表：来源、发布时间、主体、原文链接、是否涉及监管或资本市场。"],
            "next_actions": [
                {"action": "先完成一次抓取", "owner": "运营负责人", "deadline": "today"},
                {"action": "剔除旧闻和无原文链接内容", "owner": "内容审核", "deadline": "today"},
            ],
            "interview_questions": [],
            "social_topics": [],
            "watch_items": [],
            "risk_flags": ["数据不足，暂不形成对外选题判断。"],
            "priority_followup": "暂无足够新闻线索，先完成抓取并核验原文来源。",
            "message_preparation": "准备基础事实表：来源、发布时间、主体、原文链接、是否涉及监管或资本市场。",
            "communication_timing": "暂不主动外发，等待高相关或权威来源线索出现。",
        }

    top = sorted(compact_news, key=lambda item: item.get("heat_score") or 0, reverse=True)[:5]
    top_title = top[0].get("title") or "高热度线索"
    industries = [item.get("industry") for item in top if item.get("industry")]
    events = [item.get("event_type") for item in top if item.get("event_type")]
    industry = industries[0] if industries else "AI硬件"
    event = events[0] if events else "关键事件"

    return {
        "editorial_direction": f"优先把{industry}中的「{top_title}」转化为选题，先确认原文、主体、时间和是否能服务公司叙事。",
        "topic_opportunities": [
            {
                "topic": top_title,
                "angle": f"从{industry}产业变化切入，关联我方技术能力或产品优势",
                "media_value": "medium",
                "urgency": "this_week",
                "channel": "media"
            },
            {
                "topic": f"{event}类线索整理",
                "angle": "作为行业趋势背景，准备高管评论或专家解读",
                "media_value": "low",
                "urgency": "longterm",
                "channel": "internal"
            }
        ],
        "pitch_angles": [
            {
                "angle": f"从{industry}的产业变化切入",
                "supporting_points": ["技术落地案例", "供应链变化", "企业经营韧性"],
                "differentiation": "强调我方在该领域的差异化技术或客户优势"
            }
        ],
        "proof_materials": [
            "补齐原文链接、发布时间、权威来源和是否多源重复。",
            "准备公司可公开使用的数据、案例、产品进展或高管观点。",
        ],
        "next_actions": [
            {"action": "将线索分为可主动讲、需备口径、只监测三类", "owner": "公关主管", "deadline": "today"},
            {"action": "优先处理权威来源与多源重复事件，形成今日选题清单", "owner": "内容主编", "deadline": "today"},
        ],
        "interview_questions": [
            f"贵公司如何看待{industry}领域的最新变化？",
            "在这一趋势下，贵公司的技术/产品有什么独特优势？",
        ],
        "social_topics": [
            f"#{industry}产业观察# 从{top_title}看行业趋势",
        ],
        "watch_items": [item.get("title", "") for item in top[:3] if item.get("title")],
        "risk_flags": ["单源消息需二次核验。", "涉及监管、财报、资本动作的线索需保留原文证据链，谨慎对外表述。"],
        "priority_followup": f"优先把{industry}中的「{top_title}」转化为选题线索。",
        "message_preparation": "补齐原文链接、发布时间、权威来源和公司可公开使用的数据、案例、产品进展。",
        "communication_timing": "将线索分为可主动讲、需备口径、只监测三类，优先处理权威来源与多源重复事件。",
    }


def _text(value, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _string_list(value, fallback: List[str]) -> List[str]:
    if isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, dict):
                text = "；".join(f"{key}：{val}" for key, val in item.items() if val)
            else:
                text = str(item)
            text = text.strip()
            if text:
                items.append(text)
        return items or fallback
    if isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False)
        return [text] if text else fallback
    if value:
        return [str(value).strip()]
    return fallback
