import re
import unittest

from crawlers.link_collectors import (
    CrawlSourceError,
    HuxiuRssCollector,
    Kr36NewsflashLinkCollector,
    StcnLinkCollector,
    extract_article_links,
    feed_entries,
    feed_link,
    feed_text,
    parse_xml_feed,
)


class LinkCollectorTests(unittest.TestCase):
    def test_feed_helpers_parse_atom_link_href(self):
        root = parse_xml_feed(
            """<?xml version="1.0"?>
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>测试标题</title>
                <link href="https://example.com/a/1" rel="alternate" />
                <updated>2026-06-15T09:00:00Z</updated>
              </entry>
            </feed>""",
            "memory://atom",
        )

        entry = feed_entries(root)[0]

        self.assertEqual(feed_text(entry, "title"), "测试标题")
        self.assertEqual(feed_link(entry), "https://example.com/a/1")

    def test_36kr_rss_collector_parses_items_without_network(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss><channel>
          <item>
            <title>36氪文章标题</title>
            <link>https://36kr.com/p/123456789</link>
            <description>摘要</description>
            <pubDate>Mon, 15 Jun 2026 09:00:00 +0800</pubDate>
          </item>
        </channel></rss>"""
        collector = Kr36NewsflashLinkCollector()
        collector._fetch = lambda url: xml

        results = collector.crawl()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_id"], "36kr")
        self.assertEqual(results[0]["url"], "https://36kr.com/p/123456789")

    def test_huxiu_html_fallback_extracts_original_links(self):
        html = """<html><body>
          <a href="/article/1234567.html" title="虎嗅文章标题">虎嗅文章标题</a>
        </body></html>"""
        collector = HuxiuRssCollector()
        collector._crawl_rss = lambda url, limit: (_ for _ in ()).throw(ValueError("rss down"))
        collector._fetch = lambda url: html

        results = collector.crawl()

        self.assertEqual(results[0]["source_id"], "huxiu")
        self.assertEqual(results[0]["url"], "https://www.huxiu.com/article/1234567.html")
        self.assertEqual(results[0]["collect_method"], "html_list")

    def test_stcn_empty_source_reports_error(self):
        collector = StcnLinkCollector()
        collector.RSS_URLS = ["https://bad.example/rss.xml"]
        collector.LIST_URLS = ["https://bad.example/list.html"]
        collector._fetch = lambda url: (_ for _ in ()).throw(ValueError("network blocked"))

        with self.assertRaises(CrawlSourceError) as ctx:
            collector.crawl()

        self.assertIn("证券时报 未抓到文章", str(ctx.exception))
        self.assertIn("network blocked", str(ctx.exception))

    def test_extract_article_links_from_json_like_page(self):
        html = '{"title":"文章标题来自页面数据","url":"https://36kr.com/p/999888777"}'

        results = extract_article_links(html, "https://36kr.com/", re.compile(r"36kr\.com/p/\d+"), 5)

        self.assertEqual(results[0]["title"], "文章标题来自页面数据")
        self.assertEqual(results[0]["url"], "https://36kr.com/p/999888777")


if __name__ == "__main__":
    unittest.main()
