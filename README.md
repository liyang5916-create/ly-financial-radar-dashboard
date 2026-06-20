# 财经日报雷达

面向财经科技日报的本地 Web 看板，支持来源勾选、RSS 抓取、新闻溯源、章节分析和 Markdown 报告导出。

## 当前恢复版本包含

- 紫色渐变 Web 看板
- 左侧采集范围按媒体性质分组，卡片一行 3 个
- 国家统计局 RSS：
  - 最新发布：https://www.stats.gov.cn/sj/zxfb/rss.xml
  - 数据解读：https://www.stats.gov.cn/sj/sjjd/rss.xml
- 证券时报、36氪快讯等链接采集器框架
- GPT / Claude 分析配置状态展示接口
- 本地 JSON 存储：`data/local_store.json`

## 启动

双击 `run_web.bat`，访问：

http://127.0.0.1:5000

如果页面仍是旧版本，按 `Ctrl + F5` 强制刷新。
