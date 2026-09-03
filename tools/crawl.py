#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""su-multi-geo Phase 0 — 사이트 전수 진단 (크롤러의 눈).

사용:
    python tools/crawl.py <도메인|URL> [--max-pages 300] [--delay 0.5] [--out out/]

출력:
    <out>/<host>/audit.json   (스키마: su-multi-geo/audit/1)
    콘솔 요약 (audit.sh와 같은 톤)

원칙
  · 자바스크립트 없이 받은 HTML만 본다. "코드에 있다"는 근거가 아니다.
  · 창작하지 않는다. 측정한 값만 audit.json에 담는다.
  · robots.txt의 Disallow는 크롤할 때 존중한다.
  · 표준 라이브러리만 쓴다 (pip 의존 0).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, deque
from datetime import datetime, timezone
from html.parser import HTMLParser

UA = "su-multi-geo-audit/2.0"
SCHEMA = "su-multi-geo/audit/1"
TIMEOUT = 15

# GEO 레인 — 생성 엔진 크롤러. Google-Extended는 UA가 아니라 robots 토큰이다.
AI_UAS = [
    "GPTBot", "OAI-SearchBot", "ChatGPT-User",
    "ClaudeBot", "Claude-SearchBot", "Claude-User",
    "PerplexityBot", "Perplexity-User", "Google-Extended",
]
# NEO 레인 — 한국 검색 크롤러.
NEO_UAS = ["Yeti", "Daumoa"]
ALL_UAS = AI_UAS + NEO_UAS

ASSET_EXT = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg", ".ico", ".bmp",
    ".css", ".js", ".mjs", ".map", ".json", ".xml", ".txt", ".pdf", ".zip",
    ".mp4", ".webm", ".mp3", ".wav", ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".rss", ".atom", ".csv", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
)

HANGUL = re.compile(r"[가-힣]")
WS = re.compile(r"\s+")

# 한글은 검색결과에서 영문의 약 두 배 폭을 먹는다 — 그래서 권장 길이가 다르다.
LEN_TITLE = {"ko": (25, 30), "en": (50, 60)}
LEN_DESC = {"ko": (70, 80), "en": (150, 160)}


# ─────────────────────────────────────────────────────────── robots.txt

def parse_robots(raw: str):
    """robots.txt를 (agents, rules) 그룹 목록으로 쪼갠다.

    audit.sh의 awk POLICY와 같은 그룹핑 규칙: 규칙이 나온 뒤 User-agent 줄이
    다시 나오면 새 그룹으로 본다. 주석은 제거하지 않는다(awk판과 동일).
    """
    groups = []
    agents: list[str] = []
    rules: list[tuple[str, bool]] = []
    saw_rule = False
    for raw_line in (raw or "").split("\n"):
        line = raw_line.rstrip("\r").lower().lstrip()
        if line.startswith("user-agent:"):
            if saw_rule:
                groups.append((agents, rules))
                agents, rules, saw_rule = [], [], False
            agents.append(line[len("user-agent:"):].strip())
        elif re.match(r"^(dis)?allow:", line):
            saw_rule = True
            is_allow = line.startswith("allow:")
            path = re.sub(r"^(dis)?allow:\s*", "", line).strip()
            rules.append((path, is_allow))
    if agents or rules:
        groups.append((agents, rules))
    return groups


def robots_policy(raw: str, ua: str) -> str:
    """UA의 실효 정책 판정.

    반환: explicit-allow|explicit-block|explicit-partial
          |star-allow|star-block|star-partial|none
    """
    target = ua.lower()
    verdict: dict[str, str] = {}
    for agents, rules in parse_robots(raw):
        for path, is_allow in rules:
            for agent in agents:
                key = "e" if agent == target else ("s" if agent == "*" else "")
                if not key or key in verdict:
                    continue
                if is_allow:
                    verdict[key] = "allow" if path in ("/", "") else "partial"
                else:
                    verdict[key] = "block" if path == "/" else ("allow" if path == "" else "partial")
    if "e" in verdict:
        return "explicit-" + verdict["e"]
    if "s" in verdict:
        return "star-" + verdict["s"]
    return "none"


def crawl_rules(raw: str, ua: str):
    """우리 UA에 적용되는 Disallow/Allow 규칙 (없으면 User-agent:* 규칙)."""
    target = ua.lower()
    exact: list[tuple[str, bool]] = []
    star: list[tuple[str, bool]] = []
    for agents, rules in parse_robots(raw):
        if target in agents:
            exact.extend(rules)
        if "*" in agents:
            star.extend(rules)
    return exact or star


def crawl_allowed(rules, path: str) -> bool:
    """접두사 최장일치. 같은 길이면 Allow가 이긴다.

    ponytail: robots의 `*`·`$` 와일드카드는 무시하고 리터럴 접두사만 본다 —
    와일드카드가 필요하면 fnmatch 변환으로 올린다.
    """
    best = None  # (len, is_allow)
    for rule_path, is_allow in rules:
        if not rule_path or not path.startswith(rule_path):
            continue
        n = len(rule_path)
        if best is None or n > best[0] or (n == best[0] and is_allow):
            best = (n, is_allow)
    return best[1] if best else True


# ─────────────────────────────────────────────────────────── HTTP

class _CountingRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str, method: str = "GET"):
    """한 번 받아온다. 예외를 던지지 않고 dict로 돌려준다."""
    out = {
        "status": None, "final_url": url, "headers": {}, "body": "",
        "ms": 0, "redirects": 0, "error": None, "content_type": "",
    }
    redirector = _CountingRedirect()
    opener = urllib.request.build_opener(redirector)
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko,en;q=0.8",
    })
    started = time.monotonic()
    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            body = resp.read(4_000_000)
            out["status"] = resp.status
            out["final_url"] = resp.geturl()
            out["headers"] = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read(1_000_000)
        except Exception:
            pass
        out["status"] = exc.code
        out["final_url"] = exc.url or url
        out["headers"] = {k.lower(): v for k, v in (exc.headers or {}).items()}
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as exc:
        out["ms"] = int((time.monotonic() - started) * 1000)
        out["error"] = _classify_error(exc)
        return out
    out["ms"] = int((time.monotonic() - started) * 1000)
    out["redirects"] = redirector.count
    out["content_type"] = out["headers"].get("content-type", "")
    out["body"] = _decode(body, out["content_type"])
    return out


def _classify_error(exc) -> str:
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ssl.SSLError) or isinstance(exc, ssl.SSLError):
        return "tls_fail"
    if isinstance(reason, socket.gaierror):
        return "dns_fail"
    if isinstance(reason, socket.timeout) or isinstance(exc, socket.timeout):
        return "timeout"
    return "error: %s" % (reason,)


def _decode(body: bytes, content_type: str) -> str:
    charset = ""
    match = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if match:
        charset = match.group(1)
    if not charset:
        match = re.search(rb'charset=["\']?([\w-]+)', body[:4096], re.I)
        if match:
            charset = match.group(1).decode("ascii", "replace")
    try:
        return body.decode(charset or "utf-8", errors="replace")
    except (LookupError, UnicodeDecodeError):
        return body.decode("utf-8", errors="replace")


# ─────────────────────────────────────────────────────────── HTML 파싱

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = None
        self.meta_description = None
        self.meta_robots = None
        self.canonical = None
        self.lang = None
        self.naver_site_verification = False
        self.og = {}
        self.h1 = []
        self.jsonld_raw = []
        self.links = []
        self._title_buf = []
        self._h1_buf = []
        self._ld_buf = []
        self._in_title = False
        self._in_h1 = 0
        self._in_ld = False
        self._skip = 0
        self._text = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and not self.lang:
            self.lang = a.get("lang") or None
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            self._meta(a)
        elif tag == "link":
            rel = a.get("rel", "").lower()
            if "canonical" in rel and not self.canonical:
                self.canonical = a.get("href") or None
        elif tag == "a":
            href = a.get("href")
            if href:
                self.links.append(href)
        elif tag == "h1":
            self._in_h1 += 1
            self._h1_buf = []
        elif tag == "script":
            if "ld+json" in a.get("type", "").lower():
                self._in_ld = True
                self._ld_buf = []
            else:
                self._skip += 1
        elif tag in ("style", "noscript", "template"):
            self._skip += 1

    def _meta(self, a):
        name = (a.get("name") or a.get("property") or a.get("http-equiv") or "").lower()
        content = a.get("content") or ""
        if name == "description" and self.meta_description is None:
            self.meta_description = content
        elif name == "robots" and self.meta_robots is None:
            self.meta_robots = content
        elif name == "naver-site-verification":
            self.naver_site_verification = True
        elif name.startswith("og:"):
            key = name[3:]
            if key in ("title", "description", "image", "url") and key not in self.og:
                self.og[key] = content

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in ("script", "style", "noscript", "template"):
            self._skip = max(0, self._skip - 1)
            self._in_ld = False

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
            self.title = WS.sub(" ", "".join(self._title_buf)).strip() or None
        elif tag == "h1" and self._in_h1:
            self._in_h1 -= 1
            text = WS.sub(" ", "".join(self._h1_buf)).strip()
            self.h1.append(text)
            self._h1_buf = []
        elif tag == "script":
            if self._in_ld:
                self._in_ld = False
                self.jsonld_raw.append("".join(self._ld_buf))
            else:
                self._skip = max(0, self._skip - 1)
        elif tag in ("style", "noscript", "template"):
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if self._in_ld:
            self._ld_buf.append(data)
            return
        if self._in_title:
            self._title_buf.append(data)
        if self._skip:
            return
        if self._in_h1:
            self._h1_buf.append(data)
        self._text.append(data)

    @property
    def text_chars(self) -> int:
        return len(WS.sub(" ", "".join(self._text)).strip())


def jsonld_types(blocks) -> list:
    """JSON-LD 블록에서 @type을 전부 긁는다 (@graph·중첩 포함)."""
    types = []

    def walk(node):
        if isinstance(node, dict):
            t = node.get("@type")
            if isinstance(t, str):
                types.append(t)
            elif isinstance(t, list):
                types.extend([x for x in t if isinstance(x, str)])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    ok = 0
    for block in blocks:
        try:
            walk(json.loads(block))
            ok += 1
        except (ValueError, TypeError):
            continue
    return ok, types


# ─────────────────────────────────────────────────────────── URL 정규화

def normalize(url: str) -> str:
    """쿼리스트링·프래그먼트를 떼고 스킴·호스트를 소문자로."""
    parts = urllib.parse.urlsplit(url)
    path = parts.path or "/"
    return urllib.parse.urlunsplit((
        parts.scheme.lower(), parts.netloc.lower(), path, "", "",
    ))


def is_page(url: str) -> bool:
    path = urllib.parse.urlsplit(url).path.lower()
    return not path.endswith(ASSET_EXT)


def host_of(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc.lower()


def script_of(text: str) -> str:
    """길이 기준을 정할 문자 종류: 한글 비중이 높으면 ko."""
    if not text:
        return "en"
    return "ko" if len(HANGUL.findall(text)) >= max(1, len(text) * 0.15) else "en"


# ─────────────────────────────────────────────────────────── 크롤

def crawl_site(base: str, max_pages: int, delay: float, rules) -> list:
    host = host_of(base)
    seen = {normalize(base)}
    queue = deque([normalize(base)])
    pages = []
    while queue and len(pages) < max_pages:
        url = queue.popleft()
        res = fetch(url)
        page = page_record(url, res)
        pages.append(page)
        sys.stderr.write("  · %-4s %s\n" % (page["status"] or "ERR", url))
        sys.stderr.flush()
        for href in page.pop("_links", []):
            try:
                nxt = normalize(urllib.parse.urljoin(res["final_url"] or url, href))
            except ValueError:
                continue
            if not nxt.startswith(("http://", "https://")):
                continue
            if host_of(nxt) != host or nxt in seen or not is_page(nxt):
                continue
            if not crawl_allowed(rules, urllib.parse.urlsplit(nxt).path):
                continue
            seen.add(nxt)
            if len(seen) <= max_pages * 4:
                queue.append(nxt)
        if delay:
            time.sleep(delay)
    return pages


def page_record(url: str, res: dict) -> dict:
    page = {
        "url": url,
        "status": res["status"],
        "final_url": res["final_url"],
        "title": None, "meta_description": None, "meta_robots": None,
        "x_robots_tag": res["headers"].get("x-robots-tag"),
        "canonical": None, "h1": [], "jsonld_count": 0, "jsonld_types": [],
        "text_chars": 0, "og": {}, "naver_site_verification": False,
        "lang": None, "response_ms": res["ms"], "error": res["error"],
        "_links": [],
    }
    if res["error"] or not res["body"]:
        return page
    if "html" not in (res["content_type"] or "text/html").lower():
        return page
    parser = PageParser()
    try:
        parser.feed(res["body"])
        parser.close()
    except Exception:  # 깨진 HTML에서도 여기까지 모은 값은 살린다
        pass
    count, types = jsonld_types(parser.jsonld_raw)
    page.update({
        "title": parser.title,
        "meta_description": parser.meta_description,
        "meta_robots": parser.meta_robots,
        "canonical": parser.canonical,
        "h1": parser.h1,
        "jsonld_count": count,
        "jsonld_types": sorted(set(types)),
        "text_chars": parser.text_chars,
        "og": parser.og,
        "naver_site_verification": parser.naver_site_verification,
        "lang": parser.lang,
        "_links": parser.links,
    })
    return page


# ─────────────────────────────────────────────────────────── 사이트 수준

def probe_site(base: str, robots_raw: str, robots_status, crawled: list) -> dict:
    host = host_of(base)
    declared = [
        m.strip() for m in
        re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots_raw or "")
    ]
    sitemaps, sitemap_urls = read_sitemaps(base, host, declared)

    crawl_set = {p["url"] for p in crawled if p["status"] == 200}
    sm_set = {normalize(u) for u in sitemap_urls if host_of(u) == host}
    mismatch = {
        "only_in_sitemap": sorted(sm_set - crawl_set)[:100],
        "only_in_crawl": sorted(crawl_set - sm_set)[:100] if sm_set else [],
    }

    llms = {}
    for name in ("llms.txt", "llms-full.txt"):
        llms[name] = fetch("%s/%s" % (base, name))["status"]

    home = fetch(base)
    probe = fetch("%s/__multi_geo_404_probe__" % base)
    alt_host = ("%s" % host[4:]) if host.startswith("www.") else ("www.%s" % host)
    alt = fetch("https://%s/" % alt_host)
    if alt["error"]:
        alt_result = alt["error"] if alt["error"] in ("tls_fail", "dns_fail") else "error"
    elif alt["redirects"]:
        alt_result = "redirect"
    else:
        alt_result = "ok"

    return {
        "robots": {
            "status": robots_status,
            "present": bool(robots_raw),
            "raw": (robots_raw or "")[:8000],
            "policies": {ua: robots_policy(robots_raw or "", ua) for ua in ALL_UAS},
            "sitemap_declared": declared,
        },
        "sitemaps": sitemaps,
        "sitemap_vs_crawl": mismatch,
        "llms": llms,
        "hygiene": {
            "probe_404": probe["status"],
            "redirect_hops": home["redirects"],
            "home_response_ms": home["ms"],
            "alt_host": {
                "host": alt_host,
                "result": alt_result,
                "status": alt["status"],
                "location": alt["final_url"] if alt_result == "redirect" else None,
            },
        },
    }


def sitemap_candidates(base: str, host: str, declared: list) -> list:
    """robots.txt가 준 값을 그대로 믿지 않는다 — http(s) + 진단 대상 호스트만 남긴다(SSRF 방지)."""
    candidates = []
    for url in list(declared)[:3] + ["%s/sitemap.xml" % base, "%s/sitemap_index.xml" % base]:
        if not url.startswith(("http://", "https://")) or host_of(url) != host:
            continue
        if url not in candidates:
            candidates.append(url)
    return candidates


def read_sitemaps(base: str, host: str, declared: list):
    """선언된 사이트맵 + 표준 경로 2종을 읽는다."""
    candidates = sitemap_candidates(base, host, declared)
    results = []
    urls = []
    queue = deque(candidates)
    seen = set()
    while queue and len(results) < 12:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        res = fetch(url)
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", res["body"] or "")
        is_index = bool(re.search(r"<sitemapindex", res["body"] or "", re.I))
        results.append({
            "url": url, "status": res["status"],
            "is_index": is_index, "url_count": len(locs),
        })
        if res["status"] != 200:
            continue
        if is_index:
            for child in locs[:10]:
                if child.startswith(("http://", "https://")) and host_of(child) == host:
                    queue.append(child)
        else:
            urls.extend(locs)
    return results, urls


# ─────────────────────────────────────────────────────────── findings

def add(findings, lane, severity, code, message, urls=None, data=None):
    findings.append({
        "lane": lane, "severity": severity, "code": code, "message": message,
        "urls": (urls or [])[:20], "data": data or {},
    })


def analyze(base: str, site: dict, pages: list) -> tuple:
    findings: list = []
    ok = [p for p in pages if p["status"] == 200]
    total = max(1, len(ok))

    _check_indexability(findings, ok)
    _check_meta(findings, ok, total)
    _check_structure(findings, ok, total)
    _check_site(findings, base, site, ok)
    _check_crawler_policy(findings, site)

    stats = {
        "pages_crawled": len(pages),
        "unique_titles": len({p["title"] for p in ok if p["title"]}),
        "unique_descriptions": len({p["meta_description"] for p in ok if p["meta_description"]}),
        "pages_with_jsonld": sum(1 for p in ok if p["jsonld_count"]),
        "pages_noindex": sum(1 for p in ok if _noindex(p)),
    }
    return findings, stats, scorecard(findings)


def _noindex(page) -> bool:
    blob = "%s %s" % (page.get("meta_robots") or "", page.get("x_robots_tag") or "")
    return "noindex" in blob.lower()


def _check_indexability(findings, ok):
    noindex = [p["url"] for p in ok if _noindex(p)]
    if noindex:
        add(findings, "SEO", "critical", "NOINDEX",
            "noindex가 %d개 페이지에 걸려 있다 — 다른 모든 최적화가 무효다." % len(noindex),
            noindex, {"count": len(noindex)})


def _check_meta(findings, ok, total):
    titles = Counter(p["title"] for p in ok if p["title"])
    dup_titles = {t: n for t, n in titles.items() if n > 1}
    if dup_titles:
        affected = sum(dup_titles.values())
        urls = [p["url"] for p in ok if p["title"] in dup_titles]
        add(findings, "SEO", "warn", "TITLE_DUPLICATE",
            "같은 title을 쓰는 페이지가 %d개다 (%d%%) — 중복 콘텐츠로 묶인다."
            % (affected, round(affected * 100 / total)),
            urls, {"groups": len(dup_titles), "pages": affected,
                   "ratio": round(affected / total, 3)})

    missing_title = [p["url"] for p in ok if not p["title"]]
    if missing_title:
        add(findings, "SEO", "critical", "TITLE_MISSING",
            "title이 없는 페이지가 %d개다." % len(missing_title), missing_title,
            {"count": len(missing_title)})

    long_title, short_title = [], []
    for page in ok:
        if not page["title"]:
            continue
        lo, hi = LEN_TITLE[script_of(page["title"])]
        n = len(page["title"])
        if n > hi:
            long_title.append(page["url"])
        elif n < lo * 0.4:
            short_title.append(page["url"])
    if long_title:
        add(findings, "SEO", "info", "TITLE_TOO_LONG",
            "권장 길이(한글 25~30 · 영문 50~60)를 넘는 title이 %d개다 — 검색결과에서 잘린다."
            % len(long_title), long_title, {"count": len(long_title)})
    if short_title:
        add(findings, "SEO", "warn", "TITLE_TOO_SHORT",
            "title이 지나치게 짧은 페이지가 %d개다." % len(short_title), short_title,
            {"count": len(short_title)})

    descs = Counter(p["meta_description"] for p in ok if p["meta_description"])
    dup_desc = {d: n for d, n in descs.items() if n > 1}
    if dup_desc:
        affected = sum(dup_desc.values())
        urls = [p["url"] for p in ok if p["meta_description"] in dup_desc]
        add(findings, "SEO", "warn", "DESC_DUPLICATE",
            "같은 meta description을 쓰는 페이지가 %d개다 (%d%%) — 템플릿 하나로 찍은 흔적이다."
            % (affected, round(affected * 100 / total)),
            urls, {"groups": len(dup_desc), "pages": affected,
                   "ratio": round(affected / total, 3)})

    missing_desc = [p["url"] for p in ok if not p["meta_description"]]
    if missing_desc:
        add(findings, "SEO", "warn", "DESC_MISSING",
            "meta description이 없는 페이지가 %d개다 (%d%%)."
            % (len(missing_desc), round(len(missing_desc) * 100 / total)),
            missing_desc, {"count": len(missing_desc)})

    long_desc, short_desc = [], []
    for page in ok:
        text = page["meta_description"]
        if not text:
            continue
        lo, hi = LEN_DESC[script_of(text)]
        n = len(text)
        if n > hi:
            long_desc.append(page["url"])
        elif n < lo * 0.5:
            short_desc.append(page["url"])
    if long_desc:
        add(findings, "SEO", "info", "DESC_TOO_LONG",
            "권장 길이(한글 70~80 · 영문 150~160)를 넘는 설명이 %d개다." % len(long_desc),
            long_desc, {"count": len(long_desc)})
    if short_desc:
        add(findings, "SEO", "info", "DESC_TOO_SHORT",
            "설명이 지나치게 짧은 페이지가 %d개다." % len(short_desc), short_desc,
            {"count": len(short_desc)})


def _check_structure(findings, ok, total):
    no_ld = [p["url"] for p in ok if not p["jsonld_count"]]
    if no_ld:
        ratio = len(no_ld) / total
        add(findings, "AEO", "critical" if ratio > 0.8 else "warn", "JSONLD_MISSING",
            "JSON-LD가 한 건도 없는 페이지가 %d개다 (%d%%)."
            % (len(no_ld), round(ratio * 100)), no_ld,
            {"count": len(no_ld), "ratio": round(ratio, 3)})

    all_types = Counter()
    for page in ok:
        all_types.update(page["jsonld_types"])
    if not any(t in all_types for t in ("FAQPage", "QAPage")):
        add(findings, "AEO", "warn", "FAQ_MISSING",
            "FAQPage/QAPage JSON-LD가 한 건도 없다 — 답변 박스에 뽑힐 표면이 없다.",
            [], {"types_found": dict(all_types)})

    org_pages = [p["url"] for p in ok
                 if any(t in ("Organization", "LocalBusiness", "Corporation")
                        for t in p["jsonld_types"])]
    if not org_pages:
        add(findings, "LLMO", "warn", "ORG_JSONLD_MISSING",
            "Organization/LocalBusiness JSON-LD가 없다 — 엔티티를 붙잡을 앵커가 없다.",
            [], {})
    elif len(org_pages) > 1:
        add(findings, "LLMO", "info", "ORG_JSONLD_SCATTERED",
            "Organization을 %d개 페이지가 각자 선언한다 — 전역 @id 하나로 모아야 엔티티가 안 쪼개진다."
            % len(org_pages), org_pages, {"count": len(org_pages)})

    no_canon = [p["url"] for p in ok if not p["canonical"]]
    if no_canon:
        add(findings, "SEO", "warn", "CANONICAL_MISSING",
            "canonical이 없는 페이지가 %d개다 (%d%%)."
            % (len(no_canon), round(len(no_canon) * 100 / total)), no_canon,
            {"count": len(no_canon)})

    not_self = []
    for page in ok:
        if not page["canonical"]:
            continue
        try:
            resolved = normalize(urllib.parse.urljoin(page["url"], page["canonical"]))
        except ValueError:
            continue
        if resolved.rstrip("/") != page["url"].rstrip("/"):
            not_self.append(page["url"])
    if not_self:
        add(findings, "SEO", "info", "CANONICAL_NOT_SELF",
            "canonical이 자기 자신을 가리키지 않는 페이지가 %d개다 — 의도한 통합인지 확인하라."
            % len(not_self), not_self, {"count": len(not_self)})

    no_h1 = [p["url"] for p in ok if not p["h1"]]
    if no_h1:
        add(findings, "SEO", "warn", "H1_MISSING",
            "h1이 없는 페이지가 %d개다." % len(no_h1), no_h1, {"count": len(no_h1)})
    many_h1 = [p["url"] for p in ok if len(p["h1"]) > 1]
    if many_h1:
        add(findings, "SEO", "info", "H1_MULTIPLE",
            "h1이 여러 개인 페이지가 %d개다." % len(many_h1), many_h1,
            {"count": len(many_h1)})

    thin = [p["url"] for p in ok if p["text_chars"] < 300]
    if thin:
        add(findings, "SEO", "critical" if len(thin) / total > 0.5 else "warn", "THIN_TEXT",
            "본문 텍스트가 300자 미만인 페이지가 %d개다 — CSR(클라이언트 렌더) 의심."
            % len(thin), thin, {"count": len(thin)})


def _check_site(findings, base, site, ok):
    pages_all_status = site.get("_all_pages_status", [])
    broken = [u for u, s in pages_all_status if s is None or s >= 400]
    if broken:
        add(findings, "SEO", "warn", "HTTP_ERROR",
            "내부 링크를 따라간 URL 중 %d개가 오류를 냈다." % len(broken), broken,
            {"count": len(broken)})

    if not site["robots"]["present"]:
        add(findings, "SEO", "warn", "ROBOTS_MISSING",
            "robots.txt가 없거나 비정상이다 (HTTP %s)." % site["robots"]["status"],
            ["%s/robots.txt" % base], {})
    elif not site["robots"]["sitemap_declared"]:
        add(findings, "SEO", "warn", "SITEMAP_NOT_DECLARED",
            "robots.txt에 Sitemap: 선언이 없다.", ["%s/robots.txt" % base], {})

    live = [s for s in site["sitemaps"] if s["status"] == 200]
    if not live:
        add(findings, "SEO", "critical", "SITEMAP_MISSING",
            "접근 가능한 사이트맵이 없다 — 색인 대상 목록을 검색엔진에 주지 않고 있다.",
            [s["url"] for s in site["sitemaps"]], {})
    else:
        only_sm = site["sitemap_vs_crawl"]["only_in_sitemap"]
        only_cr = site["sitemap_vs_crawl"]["only_in_crawl"]
        if only_sm or only_cr:
            add(findings, "SEO", "warn", "SITEMAP_CRAWL_MISMATCH",
                "사이트맵과 실제 크롤 결과가 어긋난다 — 사이트맵에만 %d개, 크롤에만 %d개."
                % (len(only_sm), len(only_cr)), (only_cr or only_sm),
                {"only_in_sitemap": len(only_sm), "only_in_crawl": len(only_cr)})

    if site["llms"].get("llms.txt") != 200:
        add(findings, "GEO", "info", "LLMS_TXT_MISSING",
            "/llms.txt가 없다 (HTTP %s) — 모델에 줄 요약 지도를 아직 안 만들었다."
            % site["llms"].get("llms.txt"), ["%s/llms.txt" % base], {})

    hygiene = site["hygiene"]
    if hygiene["probe_404"] != 404:
        add(findings, "SEO", "warn", "SOFT_404",
            "없는 주소가 404가 아니라 HTTP %s를 낸다 — soft 404는 색인 예산을 태운다."
            % hygiene["probe_404"], [], {"status": hygiene["probe_404"]})
    if hygiene["redirect_hops"] > 1:
        add(findings, "SEO", "info", "REDIRECT_HOPS",
            "홈 접속에 리다이렉트가 %d홉이다 — 1홉으로 줄여라." % hygiene["redirect_hops"],
            [], {"hops": hygiene["redirect_hops"]})
    alt = hygiene["alt_host"]
    if alt["result"] in ("tls_fail", "dns_fail", "error"):
        add(findings, "SEO", "warn", "ALT_HOST_UNREACHABLE",
            "www↔apex 변형 주소 %s에 접속되지 않는다 (%s) — 그쪽으로 온 사용자·크롤러를 잃는다."
            % (alt["host"], alt["result"]), ["https://%s/" % alt["host"]], alt)

    if not any(p["naver_site_verification"] for p in ok):
        add(findings, "NEO", "warn", "NAVER_VERIFY_MISSING",
            "naver-site-verification 메타가 없다 — 서치어드바이저 미연결 가능성.", [], {})


def _check_crawler_policy(findings, site):
    policies = site["robots"]["policies"]
    blocked = [ua for ua in AI_UAS if policies.get(ua, "none").endswith("block")]
    partial = [ua for ua in AI_UAS if policies.get(ua, "none").endswith("partial")]
    if blocked:
        add(findings, "GEO", "critical", "AI_CRAWLER_BLOCKED",
            "AI 크롤러 %d종이 차단돼 있다 (%s) — 해당 엔진 인용을 포기한 상태다."
            % (len(blocked), ", ".join(blocked)), [],
            {"blocked": blocked, "policies": {ua: policies[ua] for ua in blocked}})
    if partial:
        add(findings, "GEO", "warn", "AI_CRAWLER_PARTIAL",
            "AI 크롤러 %d종에 부분 제한이 걸려 있다 (%s) — 규칙을 직접 읽어 확인하라."
            % (len(partial), ", ".join(partial)), [], {"partial": partial})

    undeclared = [ua for ua in AI_UAS if policies.get(ua) == "none"]
    if undeclared:
        add(findings, "GEO", "info", "AI_CRAWLER_UNDECLARED",
            "AI 크롤러 %d종이 robots.txt에 명시돼 있지 않다 — 기본 허용이지만 우연에 맡긴 상태다."
            % len(undeclared), [], {"undeclared": undeclared})

    neo_blocked = [ua for ua in NEO_UAS if policies.get(ua, "none").endswith("block")]
    if neo_blocked:
        add(findings, "NEO", "critical", "NAVER_CRAWLER_BLOCKED",
            "국내 검색 크롤러가 차단돼 있다 (%s) — NEO 레인 전체가 닫힌다."
            % ", ".join(neo_blocked), [], {"blocked": neo_blocked})


LANES = ["SEO", "AEO", "GEO", "LLMO", "NEO", "reputation"]


def scorecard(findings) -> dict:
    board = {}
    for lane in LANES:
        if lane == "reputation":
            # 사이트 밖 표면이라 크롤로는 잴 수 없다. 사람이 점검한다.
            board[lane] = {"status": "na", "evidence": [],
                           "note": "사이트 밖 표면 — 점검 대상 (lanes/reputation.md)"}
            continue
        mine = [f for f in findings if f["lane"] == lane]
        if any(f["severity"] == "critical" for f in mine):
            status = "bad"
        elif any(f["severity"] == "warn" for f in mine):
            status = "warn"
        else:
            status = "ok"
        board[lane] = {"status": status, "evidence": [f["code"] for f in mine]}
    return board


# ─────────────────────────────────────────────────────────── 콘솔 요약

STATUS_MARK = {"ok": "✅", "warn": "⚠️", "bad": "❌", "na": "—"}
SEV_MARK = {"critical": "🚨", "warn": "⚠️ ", "info": "· "}


def print_summary(report: dict) -> None:
    site = report["site"]
    stats = report["stats"]
    print("")
    print("════════════════════════════════════════════")
    print(" Phase 0 전수 진단 — %s" % report["target"]["base"])
    print(" %s · %d페이지" % (report["generated_at"][:16].replace("T", " "),
                             stats["pages_crawled"]))
    print("════════════════════════════════════════════")

    print("")
    print("── 0. noindex 사고 점검 (최우선) ──")
    if stats["pages_noindex"]:
        print("🚨 noindex %d개 페이지 — 다른 모든 최적화가 무효다. 이것부터 고쳐라"
              % stats["pages_noindex"])
    else:
        print("✅ noindex 없음")

    print("")
    print("── 1. 크롤 통계 ──")
    print("   크롤 페이지     : %d" % stats["pages_crawled"])
    print("   고유 title      : %d" % stats["unique_titles"])
    print("   고유 설명       : %d" % stats["unique_descriptions"])
    print("   JSON-LD 보유    : %d" % stats["pages_with_jsonld"])

    print("")
    print("── 2. robots / sitemap ──")
    print("   robots.txt      : %s (HTTP %s)"
          % ("있음" if site["robots"]["present"] else "❌ 없음/비정상",
             site["robots"]["status"]))
    print("   Sitemap 선언    : %s"
          % ("✅ %d건" % len(site["robots"]["sitemap_declared"])
             if site["robots"]["sitemap_declared"] else "❌ robots.txt에 없음"))
    for sm in site["sitemaps"]:
        tag = "인덱스 · 하위 %d" % sm["url_count"] if sm["is_index"] else "URL %d개" % sm["url_count"]
        print("   %-42s HTTP %s  (%s)" % (sm["url"], sm["status"], tag))
    mismatch = site["sitemap_vs_crawl"]
    print("   사이트맵 vs 크롤: 사이트맵에만 %d · 크롤에만 %d"
          % (len(mismatch["only_in_sitemap"]), len(mismatch["only_in_crawl"])))

    print("")
    print("── 3. AI·국내 크롤러 정책 (robots.txt 실효 판정) ──")
    for ua in ALL_UAS:
        print("   %-18s %s" % (ua, _policy_label(site["robots"]["policies"].get(ua, "none"))))
    print("   ※ Google-Extended는 UA가 아니라 robots 토큰이다 — 서버 로그에 안 잡힌다")
    print("   ※ Yeti는 네이버 검색 크롤러다 — 차단이면 NEO 레인 전체가 닫힌다")

    print("")
    print("── 4. llms.txt / 응답 위생 ──")
    for name, status in site["llms"].items():
        print("   /%-14s HTTP %s" % (name, status))
    hygiene = site["hygiene"]
    print("   404 동작        : HTTP %s  (404여야 정상)" % hygiene["probe_404"])
    print("   리다이렉트 홉   : %s" % hygiene["redirect_hops"])
    print("   홈 응답 시간    : %sms" % hygiene["home_response_ms"])
    print("   도메인 변형     : https://%s → %s"
          % (hygiene["alt_host"]["host"], hygiene["alt_host"]["result"]))

    print("")
    print("── 5. 레인 점수표 ──")
    for lane in LANES:
        cell = report["scorecard"][lane]
        codes = [f["code"] for f in report["findings"]
                 if f["lane"] == lane and f["severity"] != "info"]
        print("   %-11s %s  %s" % (lane, STATUS_MARK[cell["status"]],
                                   ", ".join(codes[:4]) or cell.get("note", "")))

    print("")
    print("── 6. findings ──")
    for f in sorted(report["findings"],
                    key=lambda x: {"critical": 0, "warn": 1, "info": 2}[x["severity"]]):
        print("   %s[%s] %s" % (SEV_MARK[f["severity"]], f["lane"], f["message"]))

    print("")
    print("════════════════════════════════════════════")
    print(" 스크립트로 안 되는 것 (사람이 확인):")
    print("  · GSC / Bing WMT / 네이버 서치어드바이저 색인 수")
    print("  · 각 엔진에 직접 질의한 AI 인용 O/X (특히 Gemini)")
    print("  · 제3자 평판 표면 (lanes/reputation.md)")
    print("════════════════════════════════════════════")


def _policy_label(policy: str) -> str:
    return {
        "explicit-allow": "✅ 명시 허용",
        "explicit-block": "🚫 명시 차단 — 이 엔진 인용을 포기한 상태다",
        "explicit-partial": "⚠️  부분 제한 (규칙 수동 확인 필요)",
        "star-allow": "허용 (User-agent:* 적용)",
        "star-block": "🚫 차단 (User-agent:* 전체 차단에 걸림)",
        "star-partial": "⚠️  부분 제한 (* 규칙 적용, 수동 확인)",
    }.get(policy, "미설정 → 기본 허용 (명시 권장)")


# ─────────────────────────────────────────────────────────── main

def build_report(target: str, max_pages: int, delay: float) -> dict:
    base = target if target.startswith(("http://", "https://")) else "https://%s" % target
    base = base.rstrip("/")
    host = host_of(base)

    robots = fetch("%s/robots.txt" % base)
    raw = robots["body"]
    # 404를 200처럼 꾸민 HTML 오류 페이지를 robots.txt로 오인하지 않는다
    if robots["status"] != 200 or raw.lstrip().startswith("<"):
        raw = ""
    rules = crawl_rules(raw, UA.split("/")[0])

    sys.stderr.write("크롤 시작: %s (최대 %d페이지, 간격 %.1fs)\n" % (base, max_pages, delay))
    pages = crawl_site(base, max_pages, delay, rules)

    site = probe_site(base, raw, robots["status"], pages)
    site["_all_pages_status"] = [(p["url"], p["status"]) for p in pages]
    findings, stats, board = analyze(base, site, pages)
    site.pop("_all_pages_status", None)

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": {"input": target, "base": base, "host": host},
        "site": site,
        "pages": pages,
        "stats": stats,
        "findings": findings,
        "scorecard": board,
    }


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="su-multi-geo 전수 진단")
    ap.add_argument("target", help="도메인 또는 URL (예: example.com)")
    ap.add_argument("--max-pages", type=int, default=300)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--out", default="out")
    args = ap.parse_args(argv)

    report = None
    try:
        report = build_report(args.target, args.max_pages, args.delay)
    except KeyboardInterrupt:
        sys.stderr.write("\n중단됨 — 여기까지의 결과를 저장한다.\n")
    except Exception as exc:  # 부분 결과라도 남긴다
        sys.stderr.write("진단 중 오류: %s\n" % exc)
    if report is None:
        return 1

    host = report["target"]["host"] or "site"
    outdir = os.path.join(args.out, host)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "audit.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print_summary(report)
    print("")
    print("audit.json 저장: %s" % path)
    print("보고서 생성    : python tools/report.py %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
