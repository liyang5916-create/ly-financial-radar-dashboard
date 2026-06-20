def test_imports():
    from crawlers.cn_sources import crawl_all_chinese_sources
    from web.standalone_app import SOURCE_OPTIONS

    assert callable(crawl_all_chinese_sources)
    assert any(item["id"] == "huxiu" for item in SOURCE_OPTIONS)
    assert any(item["id"] == "stats_latest" for item in SOURCE_OPTIONS)
    assert any(item["id"] == "stats_interpretation" for item in SOURCE_OPTIONS)
