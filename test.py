from crawlers.cn_sources import crawl_all_chinese_sources


if __name__ == "__main__":
    items = crawl_all_chinese_sources(selected_source_ids=["stats_latest", "stats_interpretation"])
    print(f"抓取 {len(items)} 条")
    for item in items[:5]:
        print(item.get("source_id"), item.get("title"), item.get("url"))
