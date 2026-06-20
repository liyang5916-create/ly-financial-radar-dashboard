"""Markdown 日报生成。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from database.operations import DatabaseManager


REPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "reports"


class DailyReportGenerator:
    def generate_report(self, date=None) -> str:
        db = DatabaseManager()
        end = date or datetime.now()
        start = end - timedelta(days=7)
        news_list = db.find_news_by_date(start, end)
        db.close()
        return self._render(news_list)

    def save_report(self, report: str) -> str:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        filename = REPORT_DIR / f"财经日报_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filename.write_text(report, encoding="utf-8")
        return str(filename)

    def _render(self, news_list: List[Dict]) -> str:
        lines = [
            f"# 科技公司公关选题日报 {datetime.now().strftime('%Y-%m-%d')}",
            "",
            "## 今日选题方向",
            "- 从高频赛道和权威来源中筛选可转化为公司观点、客户案例、产品进展或行业解读的新闻钩子。",
            "- 不输出投资建议，重点服务选题会、采访提纲、社媒话题和对外口径准备。",
            "",
            "## 新闻原文清单",
            "| 序号 | 发布时间 | 来源媒体 | 新闻钩子/原文标题 | 原文链接 | 选题方向 | 是否可用于选题 | 备注 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for index, item in enumerate(news_list[:100], 1):
            category = item.get("category", {})
            lines.append(
                f"| {index} | {item.get('publish_time','')} | {item.get('source','')} | "
                f"{item.get('title','')} | {item.get('url') or '链接待补充'} | "
                f"{category.get('industry','其他')} | 是 | {item.get('source_note','')} |"
            )
        lines.extend([
            "",
            "## 素材与风险边界",
            "- 缺少原文链接、发布时间不清或疑似旧闻的内容不进入对外选题。",
            "- 单一媒体来源的信息只做观察，涉及监管、财报、资本动作时必须二次交叉核验。",
            "",
            "## 下一步行动",
            "- 将新闻池分为可主动讲、需备口径、只监测三类。",
            "- 对可主动讲的选题补齐公司可公开素材、数据、案例、专家或高管观点。",
        ])
        return "\n".join(lines)
