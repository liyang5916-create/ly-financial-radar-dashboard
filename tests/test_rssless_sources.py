import re
import unittest
import xml.etree.ElementTree as ET

from crawlers.rssless_sources import RsslessMediaCollector, RsslessSourceSpec, articles_to_rss


class RsslessSourceTests(unittest.TestCase):
    def test_public_page_collector_extracts_and_normalizes_links(self):
        spec = RsslessSourceSpec(
            source_id="demo",
            source_name="Demo Finance",
            source_type="finance",
            homepage="https://example.com/",
            list_urls=["https://example.com/news"],
            article_pattern=re.compile(r"example\.com/article/\d+"),
            source_note="demo public page collection",
        )
        html = """
        <html><body>
          <time>2026-06-17 09:30:00</time>
          <div><span>2026-06-17 09:30:00</span><a href="/article/1001" title="AI company files for IPO">AI company files for IPO</a></div>
          <a href="https://example.com/article/1001" title="AI company files for IPO">duplicate</a>
        </body></html>
        """
        collector = RsslessMediaCollector(specs=[spec])
        collector._fetch = lambda url: html

        results = collector.crawl(limit=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_id"], "demo")
        self.assertEqual(results[0]["collect_method"], "html_list")
        self.assertEqual(results[0]["url"], "https://example.com/article/1001")
        self.assertEqual(results[0]["publish_time"].year, 2026)

    def test_public_page_collector_skips_stale_items_when_item_time_is_required(self):
        spec = RsslessSourceSpec(
            source_id="demo",
            source_name="Demo Finance",
            source_type="finance",
            homepage="https://example.com/",
            list_urls=["https://example.com/news"],
            article_pattern=re.compile(r"example\.com/article/\d+"),
            source_note="demo public page collection",
            require_item_time=True,
        )
        html = """
        <html><body>
          <div><span>2023-05-01 08:00:00</span><a href="/article/1002" title="AI company files for IPO">AI company files for IPO</a></div>
          <div><a href="/article/1003" title="AI chip order rises">AI chip order rises</a></div>
        </body></html>
        """
        collector = RsslessMediaCollector(specs=[spec])
        collector._fetch = lambda url: html

        results = collector.crawl(limit=10)

        self.assertEqual(results, [])

    def test_public_page_collector_skips_low_relevance_titles(self):
        spec = RsslessSourceSpec(
            source_id="demo",
            source_name="Demo Finance",
            source_type="finance",
            homepage="https://example.com/",
            list_urls=["https://example.com/news"],
            article_pattern=re.compile(r"example\.com/article/\d+"),
            source_note="demo public page collection",
        )
        html = """
        <html><body>
          <div><span>2026-06-17 09:30:00</span><a href="/article/1004" title="World Cup fans watch movies in hotels">World Cup fans watch movies in hotels</a></div>
        </body></html>
        """
        collector = RsslessMediaCollector(specs=[spec])
        collector._fetch = lambda url: html

        results = collector.crawl(limit=10)

        self.assertEqual(results, [])

    def test_articles_to_rss_outputs_valid_xml(self):
        feed = articles_to_rss([
            {"title": "Market update", "url": "https://example.com/a", "content": "Summary"}
        ])

        root = ET.fromstring(feed)

        self.assertEqual(root.tag, "rss")
        self.assertEqual(root.findtext("./channel/item/title"), "Market update")
        self.assertEqual(root.findtext("./channel/item/link"), "https://example.com/a")


if __name__ == "__main__":
    unittest.main()
