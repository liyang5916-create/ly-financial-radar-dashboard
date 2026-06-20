"""定时任务占位。

正式部署时可接入 Windows 任务计划程序或 APScheduler，每天北京时间 09:15 调用抓取和报告生成。
"""

from __future__ import annotations

from datetime import datetime

from crawlers.cn_sources import crawl_all_chinese_sources
from output.daily_report import DailyReportGenerator


def run_daily_job():
    print(f"[{datetime.now().isoformat()}] 开始执行财经日报任务")
    articles = crawl_all_chinese_sources()
    report = DailyReportGenerator().generate_report()
    filename = DailyReportGenerator().save_report(report)
    print(f"抓取 {len(articles)} 条，报告已保存：{filename}")
