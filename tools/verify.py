#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""su-multi-geo M3 — 배포 후 검증. "고쳤다"를 크롤러의 눈으로 증명한다.

사용:
    python tools/verify.py deploy out/<host>/audit.json [--deploy out/<host>/deploy]
    python tools/verify.py diff   before/audit.json after/audit.json

출력:
    <out>/verify.json (스키마: su-multi-geo/verify/1) + VERIFY.md + 콘솔 요약
    exit code: fail이 하나라도 있으면 1

원칙
  · 라이브 사이트에서 받은 것만 근거다. 패키지에 있다는 것은 근거가 아니다.
  · 진단 대상 호스트 외에는 요청하지 않는다. 리다이렉트 목적지도 다시 검사한다.
  · 파서·정책 판정·정규화는 crawl.py 것을 그대로 쓴다 (복제 금지).
  · 표준 라이브러리만 쓴다 (pip 의존 0).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.parse
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from xml.etree import ElementTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import crawl  # noqa: E402   (fetch·PageParser·robots 정책·normalize를 재사용)
import generate  # noqa: E402  (slug_of — 패키지 파일명 ↔ URL 역매핑)

SCHEMA = "su-multi-geo/verify/1"
AUDIT_SCHEMA_PREFIX = "su-multi-geo/audit/"

ORDER = {"fail": 0, "warn": 1, "pass": 2, "skip": 3}
MARK = {"fail": "❌", "warn": "⚠️", "pass": "✅", "skip": "—"}

# 실패했을 때 사람이 다음에 할 일 — VERIFY.md에 한 줄씩 붙는다
NEXT = {
    "noindex": "noindex를 먼저 걷어내라. 이게 남아 있으면 나머지 최적화는 전부 무효다.",
    "robots.status": "robots.txt가 200으로 서빙되는지 확인하라 (CDN·SEO 플러그인이 가로채는 경우가 많다).",
    "robots.preserved": "기존 robots.txt 원문이 지워졌다. 백업본을 되돌리고 추가 블록만 다시 얹어라.",
    "robots.policy": "추가한 UA 블록이 실제로 서빙되지 않는다. 배포 파일과 서버 파일을 대조하라.",
    "robots.sitemap": "robots.txt에 `Sitemap:` 줄을 넣어라.",
    "sitemap.reachable": "사이트맵이 200으로 응답하고 XML로 파싱되는지 확인하라.",
    "sitemap.locs": "사이트맵에 실린 URL이 200이 아니다 — 죽은 URL을 빼거나 페이지를 되살려라.",
    "sitemap.noindex": "noindex 페이지가 사이트맵에 들어 있다 — 둘 중 하나를 고쳐라.",
    "sitemap.canonical": "사이트맵 URL과 canonical이 어긋난다 — 사이트맵에 canonical URL을 실어라.",
    "llms.status": "llms.txt를 웹루트에 올려라.",
    "llms.todo": "llms.txt에 `<<TODO` 표식이 남아 있다 — 미완성 배포다. 채우고 다시 올려라.",
    "jsonld.present": "해당 페이지 `<head>`에 LD 스니펫이 들어가지 않았다.",
    "jsonld.type": "LD가 들어갔지만 @type이 다르다 — 스니펫을 다시 붙여라.",
    "jsonld.visible": "LD가 화면에 없는 말을 한다 — 스팸으로 분류될 수 있다. "
                      "본문에 그 문구를 노출하거나 LD에서 빼라.",
    "jsonld.org_id": "Organization @id가 페이지마다 다르다 — 엔티티가 쪼개진다. 전역 1개로 통일하라.",
    "meta.applied": "meta 초안이 반영되지 않았다 — meta-draft.csv를 검토해 적용하라.",
    "meta.duplicate": "중복 title이 남아 있다 — 페이지 고유 문구를 사람이 붙여야 한다.",
    "diff.new": "새로 생긴 findings다 — 배포가 만든 회귀인지 먼저 확인하라.",
    "diff.persisting": "critical이 그대로 남았다 — 다음 사이클 최우선 과제다.",
    "diff.scorecard": "레인 점수가 나빠졌다 — 무엇이 바뀌었는지 findings를 대조하라.",
    "diff.pages": "이전 크롤에 있던 URL이 사라졌다 — 404인지 리다이렉트인지 확인하라.",
}


# ─────────────────────────────────────────────────────────── 체크 목록

def chk(checks, cid, status, message, evidence=None):
    checks.append({"id": cid, "status": status, "message": message,
                   "evidence": evidence or {}})


def summarize(checks) -> dict:
    counts = Counter(c["status"] for c in checks)
    return {k: counts.get(k, 0) for k in ("pass", "fail", "warn", "skip")}


# ─────────────────────────────────────────────────────────── 세션 (네트워크)

class Session:
    """대상 호스트에만 요청하는 캐시 세션. fetch는 주입 가능하다(테스트용)."""

    def __init__(self, host: str, fetch=None, delay: float = 0.5):
        self.host = host
        self.fetch = fetch or crawl.fetch
        self.delay = delay
        self.cache: dict = {}
        self.fetches = 0

    def get(self, url: str) -> dict:
        if url not in self.cache:
            self.cache[url] = self._load(url)
        return self.cache[url]

    def _load(self, url: str) -> dict:
        rec = {
            "url": url, "final_url": url, "status": None, "error": None,
            "off_host": False, "body": "", "text": "", "title": None,
            "meta_description": None, "meta_robots": None, "x_robots_tag": None,
            "canonical": None, "ld_objs": [], "ld_types": [], "ld_broken": 0,
            "html": False,
        }
        if not url.startswith(("http://", "https://")) or crawl.host_of(url) != self.host:
            rec["off_host"] = True
            rec["error"] = "off_host"
            return rec
        if self.fetches and self.delay:
            time.sleep(self.delay)
        self.fetches += 1
        res = self.fetch(url) or {}
        rec["status"] = res.get("status")
        rec["final_url"] = res.get("final_url") or url
        rec["error"] = res.get("error")
        headers = res.get("headers") or {}
        rec["x_robots_tag"] = headers.get("x-robots-tag")
        # 리다이렉트 목적지도 대상 호스트여야 한다 — 밖으로 나갔으면 본문을 쓰지 않는다
        if crawl.host_of(rec["final_url"]) != self.host:
            rec["off_host"] = True
            rec["error"] = rec["error"] or "off_host_redirect"
            return rec
        rec["body"] = res.get("body") or ""
        ctype = (res.get("content_type") or "").lower()
        if rec["body"] and ("html" in ctype or not ctype):
            rec["html"] = True
            self._parse(rec)
        return rec

    @staticmethod
    def _parse(rec: dict) -> None:
        parser = crawl.PageParser()
        try:
            parser.feed(rec["body"])
            parser.close()
        except Exception:  # 깨진 HTML에서도 여기까지 모은 값은 살린다
            pass
        rec["title"] = parser.title
        rec["meta_description"] = parser.meta_description
        rec["meta_robots"] = parser.meta_robots
        rec["canonical"] = parser.canonical
        rec["text"] = parser.text
        ok, types = crawl.jsonld_types(parser.jsonld_raw)
        rec["ld_types"] = sorted(set(types))
        rec["ld_broken"] = len(parser.jsonld_raw) - ok
        for block in parser.jsonld_raw:
            try:
                rec["ld_objs"].append(json.loads(block))
            except (ValueError, TypeError):
                continue


def is_noindex(rec: dict) -> bool:
    return crawl._noindex({"meta_robots": rec.get("meta_robots"),
                           "x_robots_tag": rec.get("x_robots_tag")})


def nodes(obj):
    """JSON-LD 트리의 dict 노드를 전부 훑는다 (@graph·중첩 포함)."""
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from nodes(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from nodes(item)


def norm_text(value) -> str:
    return crawl.WS.sub(" ", str(value or "")).strip()


def visible(text: str, needle) -> bool:
    """LD 값이 가시 텍스트에 글자 그대로 있는가 (공백만 정규화)."""
    needle = norm_text(needle)
    return bool(needle) and needle in text


def price_visible(text: str, price) -> bool:
    """가격은 천단위 쉼표 표기도 같은 값으로 본다."""
    raw = norm_text(price)
    if not raw:
        return False
    if raw in text:
        return True
    try:
        return format(int(float(raw)), ",") in text
    except ValueError:
        return False


# ─────────────────────────────────────────────────────────── A. deploy 검증

def load_package(deploy_dir: str) -> dict:
    """배포 패키지에서 검증할 파일만 읽는다."""
    pkg = {"dir": deploy_dir, "robots": None, "llms": None, "sitemaps": [],
           "jsonld": OrderedDict(), "meta": None}
    if not os.path.isdir(deploy_dir):
        return pkg
    robots = os.path.join(deploy_dir, "robots.txt")
    if os.path.exists(robots):
        pkg["robots"] = read_text(robots)
    llms = os.path.join(deploy_dir, "llms.txt")
    if os.path.exists(llms):
        pkg["llms"] = read_text(llms)
    for name in sorted(os.listdir(deploy_dir)):
        if name.startswith("sitemap") and name.endswith(".xml"):
            pkg["sitemaps"].append(name)
    for path in sorted(glob.glob(os.path.join(deploy_dir, "jsonld", "*.json"))):
        try:
            pkg["jsonld"][os.path.basename(path)] = json.loads(read_text(path))
        except ValueError:
            pkg["jsonld"][os.path.basename(path)] = None
    meta = os.path.join(deploy_dir, "meta-draft.json")
    if os.path.exists(meta):
        try:
            pkg["meta"] = json.loads(read_text(meta))
        except ValueError:
            pkg["meta"] = None
    return pkg


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def check_robots(checks, session: Session, base: str, audit: dict, pkg: dict) -> str:
    live = session.get("%s/robots.txt" % base)
    raw = live["body"] if live["status"] == 200 else ""
    if live["status"] != 200 or raw.lstrip().startswith("<"):
        chk(checks, "robots.status", "fail",
            "robots.txt가 정상 응답하지 않는다 (HTTP %s)" % live["status"],
            {"status": live["status"], "error": live["error"]})
        raw = ""
    else:
        chk(checks, "robots.status", "pass", "robots.txt HTTP 200", {"bytes": len(raw)})

    before = ((audit.get("site") or {}).get("robots") or {}).get("raw") or ""
    old_lines = [l.strip() for l in before.split("\n") if l.strip()]
    if len(before) >= 8000 and old_lines:
        old_lines.pop()  # audit.json의 robots 원문은 8000자에서 잘린다 — 마지막 줄은 못 믿는다
    if not old_lines:
        chk(checks, "robots.preserved", "skip",
            "배포 전 robots.txt 원문이 없어 보존 여부를 비교할 수 없다")
    else:
        live_lines = {l.strip() for l in raw.split("\n")}
        lost = [l for l in old_lines if l not in live_lines]
        if lost:
            chk(checks, "robots.preserved", "fail",
                "기존 robots.txt에서 %d줄이 사라졌다" % len(lost),
                {"lost": lost[:20], "lost_count": len(lost)})
        else:
            chk(checks, "robots.preserved", "pass",
                "기존 robots.txt %d줄이 전부 살아 있다" % len(old_lines))

    if pkg["robots"] is None:
        chk(checks, "robots.policy", "skip", "패키지에 robots.txt가 없다")
    else:
        mismatch = []
        for ua in crawl.ALL_UAS:
            want = crawl.robots_policy(pkg["robots"], ua)
            got = crawl.robots_policy(raw, ua)
            if want != got:
                mismatch.append({"ua": ua, "package": want, "live": got})
        if mismatch:
            chk(checks, "robots.policy", "fail",
                "UA %d종의 실효 정책이 배포 패키지와 다르다 — 블록이 서빙되지 않는다"
                % len(mismatch), {"mismatch": mismatch})
        else:
            chk(checks, "robots.policy", "pass",
                "UA %d종의 실효 정책이 패키지와 일치한다" % len(crawl.ALL_UAS))

    declared = [m.strip() for m in
                re.findall(r"(?im)^\s*sitemap:\s*(\S+)", raw)]
    if declared:
        chk(checks, "robots.sitemap", "pass",
            "robots.txt에 Sitemap 선언 %d건" % len(declared), {"declared": declared})
    else:
        chk(checks, "robots.sitemap", "fail", "robots.txt에 `Sitemap:` 줄이 없다")
    return raw


def sitemap_locs(session: Session, base: str, raw_robots: str, pkg: dict,
                 host: str) -> tuple:
    """선언·패키지 기준 사이트맵을 열고 <loc>을 모은다. (결과, loc 목록)"""
    declared = [m.strip() for m in
                re.findall(r"(?im)^\s*sitemap:\s*(\S+)", raw_robots)]
    candidates = []
    for url in declared + ["%s/%s" % (base, n) for n in pkg["sitemaps"]]:
        if not url.startswith(("http://", "https://")) or crawl.host_of(url) != host:
            continue
        if url not in candidates:
            candidates.append(url)
    results, locs, seen = [], [], set()
    queue = list(candidates)
    while queue and len(results) < 12:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        rec = session.get(url)
        entry = {"url": url, "status": rec["status"], "parsed": False,
                 "is_index": False, "loc_count": 0}
        if rec["status"] == 200:
            try:
                root = ElementTree.fromstring(rec["body"].strip())
                entry["parsed"] = True
            except ElementTree.ParseError as exc:
                entry["error"] = "XML 파싱 실패: %s" % exc
                root = None
            if root is not None:
                entry["is_index"] = root.tag.endswith("sitemapindex")
                found = [el.text.strip() for el in root.iter()
                         if el.tag.endswith("}loc") or el.tag == "loc"
                         if (el.text or "").strip()]
                entry["loc_count"] = len(found)
                if entry["is_index"]:
                    queue.extend(u for u in found if crawl.host_of(u) == host)
                else:
                    locs.extend(found)
        results.append(entry)
    return results, locs


def check_sitemap(checks, session: Session, base: str, raw_robots: str, pkg: dict,
                  host: str, max_urls: int) -> list:
    results, locs = sitemap_locs(session, base, raw_robots, pkg, host)
    if not results:
        chk(checks, "sitemap.reachable", "skip", "확인할 사이트맵 주소가 없다")
        return []
    broken = [r for r in results if r["status"] != 200 or not r["parsed"]]
    if broken:
        chk(checks, "sitemap.reachable", "fail",
            "사이트맵 %d개가 200이 아니거나 XML로 파싱되지 않는다" % len(broken),
            {"sitemaps": results})
    else:
        chk(checks, "sitemap.reachable", "pass",
            "사이트맵 %d개 200·XML 파싱 OK (URL %d개)"
            % (len(results), len(locs)), {"sitemaps": results})

    off_host = [u for u in locs if crawl.host_of(u) != host]
    targets = [u for u in locs if crawl.host_of(u) == host]
    capped = len(targets) > max_urls
    targets = targets[:max_urls]
    if off_host:
        chk(checks, "sitemap.host", "warn",
            "사이트맵에 다른 호스트 URL이 %d개 있다 — 확인하지 않았다" % len(off_host),
            {"urls": off_host[:20]})

    recs = [session.get(u) for u in targets]
    dead = [{"url": r["url"], "status": r["status"], "error": r["error"]}
            for r in recs if r["status"] != 200]
    if not targets:
        chk(checks, "sitemap.locs", "skip", "확인할 <loc> URL이 없다")
    elif dead:
        chk(checks, "sitemap.locs", "fail",
            "사이트맵 URL %d개 중 %d개가 200이 아니다" % (len(targets), len(dead)),
            {"dead": dead[:20], "checked": len(targets), "capped": capped})
    else:
        chk(checks, "sitemap.locs", "pass",
            "사이트맵 URL %d개 전부 200%s"
            % (len(targets), " (상한 %d로 잘림)" % max_urls if capped else ""),
            {"checked": len(targets), "capped": capped})

    noindexed = [r["url"] for r in recs if r["status"] == 200 and is_noindex(r)]
    if noindexed:
        chk(checks, "sitemap.noindex", "fail",
            "noindex 페이지 %d개가 사이트맵에 실려 있다" % len(noindexed),
            {"urls": noindexed[:20]})
    elif targets:
        chk(checks, "sitemap.noindex", "pass", "사이트맵에 noindex 페이지가 없다")

    mismatch = []
    for rec in recs:
        if rec["status"] != 200 or not rec["canonical"]:
            continue
        canonical = crawl.normalize(
            urllib.parse.urljoin(rec["final_url"], rec["canonical"]))
        if canonical != crawl.normalize(rec["url"]):
            mismatch.append({"url": rec["url"], "canonical": canonical})
    if mismatch:
        chk(checks, "sitemap.canonical", "fail",
            "사이트맵 URL %d개가 자기 자신이 아닌 canonical을 가리킨다" % len(mismatch),
            {"mismatch": mismatch[:20]})
    elif targets:
        chk(checks, "sitemap.canonical", "pass", "사이트맵 URL과 canonical이 일치한다")
    return recs


def check_llms(checks, session: Session, base: str, pkg: dict) -> None:
    if pkg["llms"] is None:
        chk(checks, "llms.status", "skip", "패키지에 llms.txt가 없다")
        return
    rec = session.get("%s/llms.txt" % base)
    if rec["status"] != 200:
        chk(checks, "llms.status", "fail",
            "llms.txt가 서빙되지 않는다 (HTTP %s)" % rec["status"],
            {"status": rec["status"]})
        return
    chk(checks, "llms.status", "pass", "llms.txt HTTP 200", {"bytes": len(rec["body"])})
    todos = [l.strip() for l in rec["body"].split("\n") if "<<TODO" in l]
    if todos:
        chk(checks, "llms.todo", "fail",
            "llms.txt에 `<<TODO` 표식이 %d줄 남아 있다 — 미완성 배포다" % len(todos),
            {"lines": todos[:20]})
    else:
        chk(checks, "llms.todo", "pass", "llms.txt에 남은 TODO 표식이 없다")


def jsonld_targets(pkg: dict, audit: dict, base: str) -> list:
    """패키지의 jsonld/*.json ↔ 대상 페이지 URL 매핑. (파일명, @type, url, kind)"""
    home = base + "/"
    by_slug = {}
    for page in audit.get("pages") or []:
        if page.get("status") == 200:
            by_slug.setdefault(generate.slug_of(page["url"]), page["url"])
    out = []
    for name, obj in pkg["jsonld"].items():
        stem = name[:-5]
        if stem in ("organization", "website"):
            kind, url = stem, home
        elif "." in stem:
            slug, kind = stem.rsplit(".", 1)
            url = by_slug.get(slug)
        else:
            kind, url = stem, None
        types = sorted({t for node in nodes(obj) for t in
                        ([node["@type"]] if isinstance(node.get("@type"), str)
                         else [x for x in (node.get("@type") or []) if isinstance(x, str)])})
        out.append({"file": "jsonld/%s" % name, "kind": kind, "url": url,
                    "obj": obj, "types": types})
    return out


def ld_visible_misses(obj, text: str) -> list:
    """LD가 화면에 없는 말을 하는지 — 빠진 문자열 목록."""
    misses = []
    for node in nodes(obj):
        t = node.get("@type")
        types = [t] if isinstance(t, str) else [x for x in (t or []) if isinstance(x, str)]
        if "Question" in types:
            if not visible(text, node.get("name")):
                misses.append(("question", norm_text(node.get("name"))[:60]))
            answer = node.get("acceptedAnswer") or {}
            if isinstance(answer, dict) and not visible(text, answer.get("text")):
                misses.append(("answer", norm_text(answer.get("text"))[:60]))
        elif "Organization" in types and node.get("name"):
            if not visible(text, node["name"]):
                misses.append(("organization name", norm_text(node["name"])[:60]))
        elif "Product" in types:
            if node.get("name") and not visible(text, node["name"]):
                misses.append(("product name", norm_text(node["name"])[:60]))
            offers = node.get("offers") or {}
            if isinstance(offers, dict) and offers.get("price") is not None:
                if not price_visible(text, offers["price"]):
                    misses.append(("price", norm_text(offers["price"])[:60]))
    return misses


def check_jsonld(checks, session: Session, base: str, audit: dict, pkg: dict) -> None:
    targets = jsonld_targets(pkg, audit, base)
    if not targets:
        chk(checks, "jsonld.present", "skip", "패키지에 JSON-LD 파일이 없다")
        return

    missing, wrong_type, invisible, unmapped = [], [], [], []
    for target in targets:
        if target["obj"] is None:
            wrong_type.append({"file": target["file"], "reason": "패키지 파일이 JSON으로 파싱되지 않는다"})
            continue
        if not target["url"]:
            unmapped.append(target["file"])
            continue
        rec = session.get(target["url"])
        if rec["status"] != 200 or not rec["html"]:
            missing.append({"file": target["file"], "url": target["url"],
                            "reason": "페이지 HTTP %s" % rec["status"]})
            continue
        if not rec["ld_objs"]:
            missing.append({"file": target["file"], "url": target["url"],
                            "reason": "페이지에 ld+json 블록이 없다"})
            continue
        if rec["ld_broken"]:
            wrong_type.append({"file": target["file"], "url": target["url"],
                               "reason": "ld+json 블록 %d개가 JSON으로 파싱되지 않는다" % rec["ld_broken"]})
        for wanted in target["types"]:
            if wanted not in rec["ld_types"]:
                wrong_type.append({"file": target["file"], "url": target["url"],
                                   "reason": "@type %s가 페이지 LD에 없다" % wanted})
                break
        else:
            misses = ld_visible_misses(target["obj"], rec["text"])
            if misses:
                invisible.append({"file": target["file"], "url": target["url"],
                                  "missing": ["%s: %s" % (k, v) for k, v in misses][:10]})

    if missing:
        chk(checks, "jsonld.present", "fail",
            "LD가 %d개 페이지에서 확인되지 않는다" % len(missing), {"pages": missing[:20]})
    else:
        chk(checks, "jsonld.present", "pass",
            "패키지 LD %d건의 대상 페이지에서 ld+json 블록을 확인했다" % len(targets))
    if unmapped:
        chk(checks, "jsonld.mapping", "warn",
            "대상 URL을 찾지 못한 LD 파일이 %d개다 (audit.json의 크롤 목록에 없다)" % len(unmapped),
            {"files": unmapped[:20]})
    if wrong_type:
        chk(checks, "jsonld.type", "fail",
            "@type이 어긋나거나 깨진 LD가 %d건이다" % len(wrong_type), {"items": wrong_type[:20]})
    elif not missing:
        chk(checks, "jsonld.type", "pass", "패키지와 라이브 페이지의 @type이 일치한다")
    if invisible:
        chk(checks, "jsonld.visible", "fail",
            "LD가 화면에 없는 말을 한다 — %d개 페이지 (스팸 리스크)" % len(invisible),
            {"pages": invisible[:20]})
    else:
        chk(checks, "jsonld.visible", "pass",
            "LD의 문답·이름·가격이 페이지 가시 텍스트에 글자 그대로 있다")

    org_ids = OrderedDict()
    for rec in session.cache.values():
        for obj in rec.get("ld_objs") or []:
            for node in nodes(obj):
                t = node.get("@type")
                types = [t] if isinstance(t, str) else [x for x in (t or []) if isinstance(x, str)]
                if "Organization" in types and node.get("@id"):
                    org_ids.setdefault(node["@id"], []).append(rec["url"])
    if len(org_ids) > 1:
        chk(checks, "jsonld.org_id", "fail",
            "Organization @id가 %d종으로 갈렸다 — 엔티티가 쪼개진다" % len(org_ids),
            {"ids": {k: v[:5] for k, v in org_ids.items()}})
    elif org_ids:
        chk(checks, "jsonld.org_id", "pass",
            "Organization @id가 전 페이지에서 하나다 (%s)" % list(org_ids)[0])


def check_meta(checks, session: Session, audit: dict, pkg: dict, max_urls: int) -> None:
    rows = pkg["meta"]
    if not rows:
        chk(checks, "meta.applied", "skip", "패키지에 meta-draft.json이 없다")
        return
    changed = unchanged = applied = desc_changed = 0
    misses = []
    live_titles = []
    for row in rows[:max_urls]:
        rec = session.get(row.get("url") or "")
        if rec["status"] != 200 or not rec["html"]:
            continue
        title = norm_text(rec["title"])
        live_titles.append(title)
        if title == norm_text(row.get("current_title")):
            unchanged += 1
            misses.append(row.get("url"))
        else:
            changed += 1
        if title and title == norm_text(row.get("draft_title")):
            applied += 1
        if norm_text(rec["meta_description"]) != norm_text(row.get("current_description")):
            desc_changed += 1
    evidence = {"rows": len(rows), "changed": changed, "unchanged": unchanged,
                "draft_applied": applied, "description_changed": desc_changed,
                "unchanged_urls": misses[:20]}
    if changed:
        chk(checks, "meta.applied", "pass",
            "title이 바뀐 페이지 %d개 · 그대로 %d개 (초안과 일치 %d개, 설명 변경 %d개)"
            % (changed, unchanged, applied, desc_changed), evidence)
    else:
        chk(checks, "meta.applied", "warn",
            "meta 초안이 아직 한 페이지도 반영되지 않았다 (%d페이지 확인)" % len(live_titles),
            evidence)

    dups = {t: n for t, n in Counter(t for t in live_titles if t).items() if n > 1}
    if dups:
        chk(checks, "meta.duplicate", "fail",
            "같은 title을 쓰는 페이지가 아직 %d개다 (%d그룹)"
            % (sum(dups.values()), len(dups)), {"titles": list(dups)[:20]})
    elif live_titles:
        chk(checks, "meta.duplicate", "pass", "중복 title이 남아 있지 않다")


def check_noindex(session: Session, audit: dict) -> dict:
    """배포로 noindex가 새로 생기지 않았는가 — 실패면 최우선."""
    before = {crawl.normalize(p["url"]) for p in (audit.get("pages") or [])
              if crawl._noindex(p)}
    now = [rec for rec in session.cache.values()
           if rec.get("html") and rec.get("status") == 200 and is_noindex(rec)]
    new = [rec["url"] for rec in now
           if crawl.normalize(rec["url"]) not in before]
    checked = sum(1 for r in session.cache.values() if r.get("html") and r.get("status") == 200)
    if new:
        return {"id": "noindex", "status": "fail",
                "message": "배포 후 새로 noindex가 걸린 페이지가 %d개다 — 다른 모든 검증보다 우선한다"
                           % len(new),
                "evidence": {"new": new[:20], "pages_checked": checked,
                             "was_noindex": len(before)}}
    return {"id": "noindex", "status": "pass",
            "message": "새로 생긴 noindex 없음 (%d페이지 확인)" % checked,
            "evidence": {"pages_checked": checked, "was_noindex": len(before)}}


def verify_deploy(audit: dict, deploy_dir: str, fetch=None, delay: float = 0.5,
                  max_urls: int = 500) -> dict:
    base = ((audit.get("target") or {}).get("base") or "").rstrip("/")
    host = (audit.get("target") or {}).get("host") or crawl.host_of(base)
    pkg = load_package(deploy_dir)
    session = Session(host, fetch=fetch, delay=delay)
    checks: list = []

    raw_robots = check_robots(checks, session, base, audit, pkg)
    check_sitemap(checks, session, base, raw_robots, pkg, host, max_urls)
    check_llms(checks, session, base, pkg)
    check_jsonld(checks, session, base, audit, pkg)
    check_meta(checks, session, audit, pkg, max_urls)
    checks.insert(0, check_noindex(session, audit))  # 최우선 — 목록 맨 앞에 둔다

    return {
        "schema": SCHEMA,
        "mode": "deploy",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": {"base": base, "host": host, "deploy": deploy_dir,
                   "audit_generated_at": audit.get("generated_at"),
                   "requests": session.fetches},
        "checks": checks,
        "summary": summarize(checks),
        "exit_code": 1 if any(c["status"] == "fail" for c in checks) else 0,
    }


# ─────────────────────────────────────────────────────────── B. diff 검증

def findings_by_code(report: dict) -> dict:
    out: dict = OrderedDict()
    for finding in report.get("findings") or []:
        code = finding.get("code")
        current = out.get(code)
        if current is None:
            out[code] = {"code": code, "lane": finding.get("lane"),
                         "severity": finding.get("severity"),
                         "message": finding.get("message"),
                         "urls": len(finding.get("urls") or [])}
        else:
            current["urls"] += len(finding.get("urls") or [])
    return out


SCORE_RANK = {"ok": 0, "warn": 1, "bad": 2, "na": -1}


def verify_diff(before: dict, after: dict) -> dict:
    checks: list = []
    b, a = findings_by_code(before), findings_by_code(after)

    resolved = [b[c] for c in b if c not in a]
    new = [a[c] for c in a if c not in b]
    persisting = [{"code": c, "lane": a[c]["lane"], "severity": a[c]["severity"],
                   "urls_before": b[c]["urls"], "urls_after": a[c]["urls"]}
                  for c in a if c in b]

    chk(checks, "diff.resolved", "pass",
        "해소된 findings %d건" % len(resolved),
        {"items": [{"code": f["code"], "lane": f["lane"], "severity": f["severity"]}
                   for f in resolved]})

    if any(f["severity"] == "critical" for f in new):
        status = "fail"
    elif new:
        status = "warn"
    else:
        status = "pass"
    chk(checks, "diff.new", status,
        "새로 생긴 findings %d건%s" % (len(new), " (critical 포함)" if status == "fail" else ""),
        {"items": [{"code": f["code"], "lane": f["lane"], "severity": f["severity"],
                    "urls": f["urls"], "message": f["message"]} for f in new]})

    worse = [p for p in persisting if p["urls_after"] > p["urls_before"]]
    crit = [p for p in persisting if p["severity"] == "critical"]
    chk(checks, "diff.persisting", "warn" if (crit or worse) else "pass",
        "그대로 남은 findings %d건 (critical %d · 영향 URL 증가 %d)"
        % (len(persisting), len(crit), len(worse)), {"items": persisting})

    lanes, dropped = OrderedDict(), []
    for lane in crawl.LANES:
        bs = ((before.get("scorecard") or {}).get(lane) or {}).get("status", "na")
        as_ = ((after.get("scorecard") or {}).get(lane) or {}).get("status", "na")
        lanes[lane] = {"before": bs, "after": as_}
        if SCORE_RANK.get(as_, -1) > SCORE_RANK.get(bs, -1):
            dropped.append("%s %s→%s" % (lane, bs, as_))
    chk(checks, "diff.scorecard", "fail" if dropped else "pass",
        "레인 점수 악화 %d건%s" % (len(dropped), (": " + ", ".join(dropped)) if dropped else ""),
        {"lanes": lanes})

    keys = sorted(set(before.get("stats") or {}) | set(after.get("stats") or {}))
    chk(checks, "diff.stats", "pass", "stats 전후 비교",
        {"stats": {k: {"before": (before.get("stats") or {}).get(k),
                       "after": (after.get("stats") or {}).get(k)} for k in keys}})

    bu = {p["url"] for p in (before.get("pages") or []) if p.get("status") == 200}
    au = {p["url"] for p in (after.get("pages") or []) if p.get("status") == 200}
    gone, fresh = sorted(bu - au), sorted(au - bu)
    chk(checks, "diff.pages", "warn" if gone else "pass",
        "사라진 URL %d개 · 새 URL %d개" % (len(gone), len(fresh)),
        {"gone": gone[:50], "new": fresh[:50]})

    return {
        "schema": SCHEMA,
        "mode": "diff",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": {"base": ((after.get("target") or {}).get("base") or ""),
                   "host": ((after.get("target") or {}).get("host") or ""),
                   "before_at": before.get("generated_at"),
                   "after_at": after.get("generated_at")},
        "checks": checks,
        "summary": summarize(checks),
        "exit_code": 1 if any(c["status"] == "fail" for c in checks) else 0,
    }


# ─────────────────────────────────────────────────────────── 출력

def render_md(result: dict) -> str:
    target = result["target"]
    head = "배포 검증" if result["mode"] == "deploy" else "전/후 진단 비교"
    out = ["# %s — %s" % (head, target.get("host") or target.get("base") or "?"), "",
           "생성: %s · su-multi-geo verify.py" % result["generated_at"].replace("T", " "),
           ""]
    s = result["summary"]
    out += ["| 결과 | 수 |", "|---|---|",
            "| ❌ fail | %d |" % s["fail"], "| ⚠️ warn | %d |" % s["warn"],
            "| ✅ pass | %d |" % s["pass"], "| — skip | %d |" % s["skip"], ""]

    for status, title in (("fail", "❌ 실패 — 이것부터 고친다"),
                          ("warn", "⚠️ 경고"),
                          ("pass", "✅ 통과"),
                          ("skip", "— 확인하지 않음")):
        items = [c for c in result["checks"] if c["status"] == status]
        if not items:
            continue
        out += ["## %s" % title, ""]
        for c in items:
            out.append("- **`%s`** — %s" % (c["id"], c["message"]))
            if status in ("fail", "warn") and NEXT.get(c["id"]):
                out.append("  - 다음 조치: %s" % NEXT[c["id"]])
        out.append("")

    out += ["---", "",
            "증빙 원본은 `verify.json`의 `checks[].evidence`에 있다. "
            "이 문서는 그 요약이다.", ""]
    return "\n".join(out)


def print_summary(result: dict) -> None:
    s = result["summary"]
    print("")
    print("════════════════════════════════════════════")
    print(" %s — %s" % ("배포 검증" if result["mode"] == "deploy" else "전/후 비교",
                        result["target"].get("host") or result["target"].get("base")))
    print("════════════════════════════════════════════")
    for c in sorted(result["checks"], key=lambda c: ORDER[c["status"]]):
        print(" %s %-20s %s" % (MARK[c["status"]], c["id"], c["message"]))
    print("")
    print(" 결과: ❌ %d · ⚠️ %d · ✅ %d · — %d" % (s["fail"], s["warn"], s["pass"], s["skip"]))
    if s["fail"]:
        print(" 실패가 있다 — 배포는 아직 끝나지 않았다.")


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="배포 후 검증 / 전후 진단 비교")
    sub = ap.add_subparsers(dest="mode", required=True)

    d = sub.add_parser("deploy", help="배포 패키지가 실제로 서빙되는지 라이브에서 확인")
    d.add_argument("audit", help="배포 전 audit.json")
    d.add_argument("--deploy", default=None, help="배포 패키지 폴더 (기본: audit.json 옆의 deploy/)")
    d.add_argument("--delay", type=float, default=0.5, help="요청 간격(초)")
    d.add_argument("--max-urls", type=int, default=500, help="사이트맵 URL 확인 상한")
    d.add_argument("--out", default=None, help="verify.json 경로")

    f = sub.add_parser("diff", help="배포 전/후 audit.json 비교")
    f.add_argument("before")
    f.add_argument("after")
    f.add_argument("--out", default=None)

    args = ap.parse_args(argv)

    if args.mode == "deploy":
        audit = load_json(args.audit)
        if not str(audit.get("schema", "")).startswith(AUDIT_SCHEMA_PREFIX):
            sys.stderr.write("audit.json 스키마가 아니다: %s\n" % audit.get("schema"))
            return 2
        here = os.path.dirname(os.path.abspath(args.audit))
        deploy_dir = args.deploy or os.path.join(here, "deploy")
        if not os.path.isdir(deploy_dir):
            sys.stderr.write("배포 패키지 폴더가 없다: %s\n" % deploy_dir)
            return 2
        result = verify_deploy(audit, deploy_dir, delay=args.delay,
                               max_urls=args.max_urls)
        default_out = os.path.join(here, "verify.json")
    else:
        before, after = load_json(args.before), load_json(args.after)
        for name, report in (("before", before), ("after", after)):
            if not str(report.get("schema", "")).startswith(AUDIT_SCHEMA_PREFIX):
                sys.stderr.write("%s가 audit.json 스키마가 아니다: %s\n"
                                 % (name, report.get("schema")))
                return 2
        result = verify_diff(before, after)
        default_out = os.path.join(os.path.dirname(os.path.abspath(args.after)),
                                   "verify.json")

    path = args.out or default_out
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    md_path = os.path.join(os.path.dirname(os.path.abspath(path)), "VERIFY.md")
    with open(md_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_md(result))

    print_summary(result)
    print("")
    print("verify.json: %s" % path)
    print("VERIFY.md  : %s" % md_path)
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
