"""Global settings for Finance Radar.

The project intentionally keeps runtime secrets in a local .env file. The
loader below is tiny so the standalone web service does not depend on
python-dotenv.
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


_load_dotenv()

# Fetch AI: used for crawling plans, search terms, source expansion, and
# lightweight collection QA.
FETCH_AI_API_KEY = _env_first("FETCH_AI_API_KEY", "FETCH_GPT_API_KEY", "CRAWL_AI_API_KEY", "CRAWLER_AI_API_KEY")
FETCH_AI_BASE_URL = _env_first("FETCH_AI_BASE_URL", "FETCH_GPT_BASE_URL", "CRAWL_AI_BASE_URL", "CRAWLER_AI_BASE_URL", default="https://api.duck.cyou/v1")
FETCH_AI_MODEL = _env_first("FETCH_AI_MODEL", "FETCH_GPT_MODEL", "CRAWL_AI_MODEL", "CRAWLER_AI_MODEL", default="gpt-5.4-mini")

# Analysis AI: kept separate so GPT/Claude credentials can be supplied later.
ANALYSIS_AI_MODE = _env_first("ANALYSIS_AI_MODE", default="gpt")

ANALYSIS_GPT_API_KEY = _env_first("ANALYSIS_GPT_API_KEY", "ANALYSIS_AI_API_KEY", "OPENAI_API_KEY")
ANALYSIS_GPT_BASE_URL = _env_first("ANALYSIS_GPT_BASE_URL", "ANALYSIS_AI_BASE_URL", default="https://api.duck.cyou/v1")
ANALYSIS_GPT_MODEL = _env_first("ANALYSIS_GPT_MODEL", "ANALYSIS_AI_MODEL", default="gpt-5.5")

ANALYSIS_CLAUDE_API_KEY = _env_first("ANALYSIS_CLAUDE_API_KEY", "ANTHROPIC_API_KEY")
ANALYSIS_CLAUDE_BASE_URL = _env_first("ANALYSIS_CLAUDE_BASE_URL", default="https://api.anthropic.com")
ANALYSIS_CLAUDE_MODEL = _env_first("ANALYSIS_CLAUDE_MODEL", default="claude-3-5-sonnet-latest")

ANALYSIS_AI_API_KEY = ANALYSIS_GPT_API_KEY
ANALYSIS_AI_BASE_URL = ANALYSIS_GPT_BASE_URL
ANALYSIS_AI_MODEL = ANALYSIS_GPT_MODEL
OPENAI_API_KEY = ANALYSIS_GPT_API_KEY

MONGODB_URI = "mongodb://localhost:27017/"
MONGODB_DB = "finance_radar"

REDIS_HOST = "localhost"
REDIS_PORT = 6379

CRAWLER_SETTINGS = {
    "timeout": 10,
    "retry_times": 3,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

SOURCE_WEIGHTS = {
    "official": 1.0,
    "media": 0.8,
    "social": 0.5,
}

KEYWORDS = {
    "AI硬件 / 算力基础设施": ["GPU", "AI芯片", "算力", "训练芯片", "推理芯片", "AI服务器", "昇腾", "寒武纪", "英伟达", "NVIDIA", "AMD", "算力中心", "智算中心", "DGX", "A100", "H100", "HBM", "CoWoS"],
    "半导体 / PCB": ["芯片", "晶圆", "光刻", "EDA", "IP核", "PCB", "封装", "制程", "台积电", "中芯国际"],
    "AI应用 / AI Agent": ["AI", "大模型", "Agent", "AGI", "推理", "生成式AI", "AIGC", "ChatGPT", "文心", "通义"],
    "具身智能与机器人": ["机器人", "具身智能", "人形机器人", "工业机器人", "控制器", "减速器", "协作机器人"],
    "IPO / A股科技": ["IPO", "上市", "过会", "挂牌", "路演", "科创板", "交易所", "询价"],
    "港股科技": ["港股", "恒生科技", "南向资金", "平台公司", "AH映射", "港交所"],
    "全球市场与宏观变量": ["统计局", "CPI", "PPI", "PMI", "美元", "人民币", "黄金", "原油", "美股", "港股", "美联储"],
    "融资并购": ["A轮", "B轮", "C轮", "战略投资", "Pre-IPO", "融资", "并购", "收购", "投资"],
}

SCHEDULE_JOBS = {
    "hourly_crawl": {"interval": 3600, "sources": ["36kr", "stcn", "stats_latest", "stats_interpretation"]},
    "daily_report": {"time": "09:15", "enabled": True},
}
