"""信息抽取模块。"""

from __future__ import annotations

import json
from typing import Dict, List

from config.settings import ANALYSIS_AI_API_KEY, ANALYSIS_AI_BASE_URL, ANALYSIS_AI_MODEL

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class InfoExtractor:
    def __init__(self):
        kwargs = {"api_key": ANALYSIS_AI_API_KEY}
        if ANALYSIS_AI_BASE_URL:
            kwargs["base_url"] = ANALYSIS_AI_BASE_URL
        self.client = OpenAI(**kwargs) if OpenAI and ANALYSIS_AI_API_KEY else None

    def extract_from_article(self, title: str, content: str) -> Dict:
        prompt = f"""
请从以下财经新闻中提取关键信息，以JSON格式返回：

标题：{title}
内容：{content[:500]}

要求提取：
1. event_type（事件类型）：融资并购/产品发布/财报业绩/政策监管/人事变动/市场数据/市场动态
2. industry（行业）：半导体/AI应用/新能源/生物医药/消费电子/全球市场/其他
3. market（市场层级）：一级市场/二级市场/政策驱动/宏观数据
4. companies（相关公司）：列表
5. people（相关人物）：列表
6. amount（涉及金额）：如果有融资、交易金额，提取出来
7. sentiment（情感倾向）：positive/neutral/negative
8. tags（关键词标签）：3-5个关键词

返回JSON格式。
"""
        try:
            if not self.client:
                raise RuntimeError("分析AI Key 未配置，跳过 LLM 抽取")
            response = self.client.chat.completions.create(
                model=ANALYSIS_AI_MODEL,
                messages=[{"role": "system", "content": "你是专业财经新闻分析助手"}, {"role": "user", "content": prompt}],
                temperature=0.3,
            )
            result_text = response.choices[0].message.content
            if "```json" in result_text:
                result_text = result_text.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in result_text:
                result_text = result_text.split("```", 1)[1].split("```", 1)[0]
            return json.loads(result_text.strip())
        except Exception as exc:
            print(f"信息抽取失败: {exc}")
            return {
                "category": {"event_type": "未分类", "industry": "其他", "market": "未知"},
                "entities": {"companies": [], "people": [], "amount": ""},
                "sentiment": "neutral",
                "tags": [],
            }

    def batch_extract(self, articles: List[Dict]) -> List[Dict]:
        results = []
        for article in articles:
            extracted = self.extract_from_article(article.get("title", ""), article.get("content", ""))
            article.update({
                "category": extracted.get("category", {}),
                "entities": extracted.get("entities", {}),
                "sentiment": extracted.get("sentiment", "neutral"),
                "tags": extracted.get("tags", []),
            })
            results.append(article)
        return results
