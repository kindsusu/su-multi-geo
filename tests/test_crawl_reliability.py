# -*- coding: utf-8 -*-
"""크롤 범위·robots·색인 판정의 거짓 정상 회귀 테스트."""

import os
import gzip
import sys
import unittest
import urllib.request
from unittest.mock import patch
from tempfile import TemporaryDirectory

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import crawl  # noqa: E402


def response(url, status=200, body="", content_type="text/html", final_url=None, error=None):
    return {"status": status, "final_url": final_url or url, "headers": {}, "body": body,
            "ms": 1, "redirects": 0, "error": error, "content_type": content_type}


class RobotsReliabilityTests(unittest.TestCase):
    def test_exact_empty_group_does_not_inherit_wildcard_rules(self):
        raw = "User-agent: *\nDisallow: /\n\nUser-agent: testbot\n"
        self.assertEqual(crawl.crawl_rules(raw, "testbot"), [])
        self.assertTrue(crawl.crawl_allowed(crawl.crawl_rules(raw, "testbot"), "/"))

    def test_comments_case_groups_wildcard_end_and_query(self):
        raw = """User-agent: *
Disallow: /private # comment
User-agent: TestBot
Disallow: /*?preview=*
Allow: /public?preview=yes$

User-agent: testbot
Disallow: /tmp$
"""
        rules = crawl.crawl_rules(raw, "TESTBOT")
        self.assertFalse(crawl.crawl_allowed(rules, "/x?preview=no"))
        self.assertTrue(crawl.crawl_allowed(rules, "/public?preview=yes"))
        self.assertFalse(crawl.crawl_allowed(rules, "/tmp"))
        self.assertTrue(crawl.crawl_allowed(rules, "/tmp/more"))
        # exact 그룹이 있으면 star 그룹은 합치지 않는다.
        self.assertTrue(crawl.crawl_allowed(rules, "/private"))

    def test_multiple_matching_exact_groups_are_merged(self):
        raw = "User-agent: bot\nDisallow: /a\n\nUser-agent: BOT\nDisallow: /b\n"
        rules = crawl.crawl_rules(raw, "Bot")
        self.assertFalse(crawl.crawl_allowed(rules, "/a"))
        self.assertFalse(crawl.crawl_allowed(rules, "/b"))


class CrawlCoverageTests(unittest.TestCase):
    def test_main_returns_partial_for_incomplete_saved_report(self):
        report = {"target": {"host": "example.com"}, "coverage": {"complete": False},
                  "site": {}, "stats": {}, "findings": [], "scorecard": {}}
        with TemporaryDirectory() as tmp, patch.object(crawl, "build_report", return_value=report), \
                patch.object(crawl, "print_summary"):
            self.assertEqual(crawl.main(["example.com", "--out", tmp]), 2)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "example.com", "audit.json")))

    def test_main_rejects_negative_delay(self):
        with self.assertRaises(SystemExit) as caught:
            crawl.main(["example.com", "--delay", "-0.1"])
        self.assertEqual(caught.exception.code, 2)

    def test_redirect_handler_blocks_external_and_disallowed_targets(self):
        req = urllib.request.Request("https://example.com/start")
        handler = crawl._CountingRedirect("example.com", [("/private", False)])
        self.assertIsNone(handler.redirect_request(
            req, None, 302, "Found", {}, "https://evil.example/target"))
        self.assertIsNone(handler.redirect_request(
            req, None, 302, "Found", {}, "https://example.com/private/a"))

    def test_build_report_exposes_coverage_and_sitemap_urls(self):
        sitemap = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/a</loc></url></urlset>'
        html = '<html><head><title>Example page title with enough text</title></head><body><h1>Page</h1>' + ('x' * 400) + '</body></html>'

        def fake(url, method="GET", **kwargs):
            if url.endswith("/robots.txt"):
                return response(url, body="User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml", content_type="text/plain")
            if url.endswith("/sitemap.xml"):
                return response(url, body=sitemap, content_type="application/xml")
            if url.endswith("/sitemap_index.xml") or url.endswith("/llms.txt") or url.endswith("/llms-full.txt"):
                return response(url, status=404)
            if url.endswith("/__multi_geo_404_probe__"):
                return response(url, status=404)
            return response(url, body=html)

        with patch.object(crawl, "fetch", side_effect=fake):
            report = crawl.build_report("https://example.com", 10, 0)
        self.assertTrue(report["coverage"]["complete"])
        self.assertEqual(report["coverage"]["pages_fetched"], 2)
        self.assertEqual(report["site"]["sitemap_urls"], ["https://example.com/a"])
        self.assertIn("parsed", report["site"]["sitemaps"][0])

    def test_disallowed_seed_is_never_fetched(self):
        called = []
        with patch.object(crawl, "fetch", side_effect=lambda url, **kw: called.append(url) or response(url)):
            coverage = {}
            pages = crawl.crawl_site("https://example.com", 10, 0, [("/", False)],
                                     seeds=["https://example.com/secret"], coverage=coverage)
        self.assertEqual(pages, [])
        self.assertEqual(called, [])
        self.assertFalse(coverage["complete"])
        self.assertIn("seed_blocked_by_robots", coverage["reasons"])

    def test_only_successful_html_discovers_links_and_cap_is_reported(self):
        bodies = {
            "https://example.com/": (404, '<a href="/ghost">ghost</a>'),
        }
        with patch.object(crawl, "fetch", side_effect=lambda u, **kw: response(u, bodies[u][0], bodies[u][1])):
            coverage = {}
            pages = crawl.crawl_site("https://example.com", 10, 0, [], coverage=coverage)
        self.assertEqual([p["url"] for p in pages], ["https://example.com/"])
        self.assertFalse(coverage["complete"])
        self.assertIn("http_errors", coverage["reasons"])

        def linked(url, **kwargs):
            return response(url, body='<a href="/a">a</a><a href="/b">b</a>')
        with patch.object(crawl, "fetch", side_effect=linked):
            coverage = {}
            crawl.crawl_site("https://example.com", 1, 0, [], coverage=coverage)
        self.assertFalse(coverage["complete"])
        self.assertEqual(coverage["queued_remaining"], 2)

    def test_sitemap_seed_and_query_are_fetched(self):
        called = []
        with patch.object(crawl, "fetch", side_effect=lambda u, **kw: called.append(u) or response(u)):
            crawl.crawl_site("https://example.com", 5, 0, [],
                             seeds=["https://example.com/product?id=1"])
        self.assertIn("https://example.com/product?id=1", called)

    def test_discovered_private_link_counts_but_does_not_make_coverage_incomplete(self):
        with patch.object(crawl, "fetch", return_value=response(
                "https://example.com/", body='<a href="/private/a">private</a>')):
            coverage = {}
            crawl.crawl_site("https://example.com", 10, 0, [("/private/", False)],
                             coverage=coverage)
        self.assertTrue(coverage["complete"])
        self.assertEqual(coverage["blocked_count"], 1)


class SitemapReliabilityTests(unittest.TestCase):
    def test_inspection_limit_is_explicit_and_preserves_pending_urls(self):
        declared = ["https://example.com/s%d.xml" % i for i in range(102)]
        xml = "<urlset/>"
        with patch.object(crawl, "fetch", side_effect=lambda u: response(
                u, body=xml, content_type="application/xml")):
            results, _ = crawl.read_sitemaps("https://example.com", "example.com", declared)
        self.assertEqual({r["url"] for r in results}, set(declared + [
            "https://example.com/sitemap.xml", "https://example.com/sitemap_index.xml"]))
        pending = [r for r in results if r["error"] == "inspection_limit"]
        self.assertTrue(pending)
        self.assertTrue(all(r["truncated"] and not r["parsed"] for r in pending))

    def test_gzip_expansion_is_bounded(self):
        packed = gzip.compress(b"x" * (crawl.MAX_BODY + 1))
        body, truncated = crawl._bounded_gunzip(packed, crawl.MAX_BODY)
        self.assertEqual(len(body), crawl.MAX_BODY)
        self.assertTrue(truncated)

    def test_valid_xml_and_invalid_200_are_distinguished(self):
        valid = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/a</loc></url></urlset>'
        calls = {"https://example.com/sitemap.xml": response("https://example.com/sitemap.xml", body=valid, content_type="application/xml"),
                 "https://example.com/sitemap_index.xml": response("https://example.com/sitemap_index.xml", body="not xml", content_type="text/plain")}
        with patch.object(crawl, "fetch", side_effect=lambda u: calls[u]):
            results, urls = crawl.read_sitemaps("https://example.com", "example.com", [])
        self.assertEqual(urls, ["https://example.com/a"])
        self.assertTrue(results[0]["parsed"])
        self.assertFalse(results[1]["parsed"])
        self.assertTrue(results[1]["error"])


class IndexabilityReliabilityTests(unittest.TestCase):
    def page(self, **changes):
        item = {"url": "https://example.com/", "status": 200, "title": "충분히 긴 기본 페이지 제목입니다",
                "meta_description": "설명 " * 30, "meta_robots": None, "meta_googlebot": None,
                "x_robots_tag": None, "canonical": "https://example.com/", "h1": ["제목"],
                "jsonld_count": 0, "jsonld_types": [], "text_chars": 1000,
                "naver_site_verification": True}
        item.update(changes)
        return item

    def test_none_duplicate_meta_and_googlebot_snippet(self):
        p = self.page(meta_robots="index, follow, none", meta_googlebot="nosnippet")
        self.assertTrue(crawl._noindex(p))
        findings = []
        crawl._check_indexability(findings, [p])
        self.assertEqual({f["code"] for f in findings}, {"NOINDEX", "SNIPPET_RESTRICTED"})

    def test_intentional_noindex_is_not_critical(self):
        findings = []
        crawl._check_indexability(findings, [self.page(meta_robots="none", intended_indexable=False)])
        self.assertEqual([f["code"] for f in findings], ["INTENTIONAL_NOINDEX"])

    def test_x_robots_googlebot_and_max_snippet_zero(self):
        p = self.page(x_robots_tag="googlebot: max-snippet: 0")
        findings = []
        crawl._check_indexability(findings, [p])
        self.assertIn("SNIPPET_RESTRICTED", {f["code"] for f in findings})

    def test_probe_preserves_full_robots_and_excludes_intentional_nonindex_from_orphans(self):
        raw = "User-agent: *\nAllow: /\n" + ("# preserved\n" * 1000)
        pages = [self.page(url="https://example.com/a", final_url="https://example.com/a",
                           meta_robots="noindex", canonical="https://example.com/a")]
        sitemap_data = ([{"url": "https://example.com/sitemap.xml", "status": 200,
                          "is_index": False, "url_count": 0, "parsed": True,
                          "truncated": False, "error": None}], [])
        with patch.object(crawl, "fetch", return_value=response("https://example.com/", status=404)):
            site = crawl.probe_site("https://example.com", raw, 200, pages,
                                    sitemap_data=sitemap_data)
        self.assertEqual(site["robots"]["raw"], raw)
        self.assertEqual(site["sitemap_vs_crawl"]["only_in_crawl"], [])
        self.assertEqual(site["sitemap_vs_crawl"]["excluded_noindex"], ["https://example.com/a"])


class CrawlerRoleTests(unittest.TestCase):
    def test_training_block_is_information_not_search_failure(self):
        policies = {ua: "star-allow" for ua in crawl.ALL_UAS}
        policies["ClaudeBot"] = "explicit-block"
        site = {"robots": {"policies": policies}}
        findings = []
        crawl._check_crawler_policy(findings, site)
        self.assertIn("AI_TRAINING_BLOCKED", {f["code"] for f in findings})
        self.assertNotIn("AI_CRAWLER_BLOCKED", {f["code"] for f in findings})
        self.assertTrue(all(f["severity"] == "info" for f in findings))


if __name__ == "__main__":
    unittest.main()
