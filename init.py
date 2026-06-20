"""初始化项目目录。"""

from pathlib import Path


for folder in ["data", "data/reports", "web/templates", "crawlers", "processors", "database", "output"]:
    Path(folder).mkdir(parents=True, exist_ok=True)

print("财经日报雷达目录已初始化")
