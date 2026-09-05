# -*- coding: utf-8 -*-
"""측정 v2 신뢰성 계약. 네트워크/API 호출은 사용하지 않는다."""

import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import drift  # noqa: E402
import measure  # noqa: E402


Q = [{"id": "Q1", "text": "가격 비교", "type": "nonbrand", "note": ""}]
HOST = "example.com"
BASE = "https://example.com"


def mrow(day, run, cited, mode="manual", **kw):
    return measure.make_row(day, "Q1", "chatgpt", run, mode,
                            True if mode == "manual" else None, cited, [], cited, [],
                            query_fingerprint_value=measure.query_fingerprint(Q[0]), **kw)


def v2_summary(cited, runs, *, qset="same", errors=0, unmeasured=0,
               surface="chatgpt_web_ui", model="", campaign="campaign-a", query_runs=None,
               scope="latest"):
    blank = {"cited": 0, "runs": 0, "rate": None, "errors": 0}
    rate = round(cited / runs, 4) if runs else None
    return {"schema": measure.SCHEMA_SUMMARY,
            "query_set": {"fingerprint": qset},
            "window": {"scope": scope},
            "conditions": {"surfaces": [surface], "modes": ["manual"], "locales": ["ko-KR"],
                           "login_states": ["signed_out"], "search_enabled": ["True"]},
            "quality": {"errors": errors, "unmeasured": unmeasured, "incompatible_rows": 0,
                        "regression_eligible": errors == 0 and unmeasured == 0},
            "engines": [{"engine": "chatgpt", "label": "ChatGPT 웹 UI",
                         "brand": dict(blank),
                         "nonbrand": {"cited": cited, "runs": runs, "rate": rate,
                                      "errors": errors}}],
            "cohorts": [{"engine": "chatgpt", "mode": "manual", "surface": surface,
                         "locale": "ko-KR", "login_state": "signed_out", "search_enabled": True,
                         "model": model, "campaign_id": campaign,
                         "queries": [{"id": qid, "fingerprint": "fp-" + qid,
                                      "observed": count, "attempts": count}
                                     for qid, count in (query_runs or [("Q1", runs)])]}],
            "urls": {"ours": [], "competitors": []}}


class MeasureV2(unittest.TestCase):
    def test_manual_and_api_slots_do_not_overwrite(self):
        rows = [mrow("2026-09-05", 1, True, surface="chatgpt_web_ui"),
                mrow("2026-09-05", 1, False, mode="api", surface="api", model="gpt-test")]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.jsonl")
            measure.append_rows(path, rows)
            self.assertEqual(len(measure.load_log(path)), 2)

    def test_api_error_is_not_citation_denominator(self):
        rows = [mrow("2026-09-05", 1, True, surface="api"),
                mrow("2026-09-05", 2, None, mode="api", outcome="error",
                     error="http_429", surface="api")]
        result = measure.aggregate(rows, Q, HOST, BASE)
        slot = result["engines"][0]["nonbrand"]
        self.assertEqual((slot["attempts"], slot["runs"], slot["cited"], slot["errors"]),
                         (2, 1, 1, 1))
        self.assertEqual(slot["rate"], 1.0)
        self.assertFalse(result["quality"]["regression_eligible"])

    def test_latest_default_and_explicit_cumulative(self):
        rows = [mrow("2026-09-01", 1, False), mrow("2026-09-15", 1, True)]
        latest = measure.aggregate(rows, Q, HOST, BASE, cumulative=False)
        total = measure.aggregate(rows, Q, HOST, BASE, cumulative=True)
        self.assertEqual(latest["engines"][0]["nonbrand"]["rate"], 1.0)
        self.assertEqual(total["engines"][0]["nonbrand"]["rate"], 0.5)
        self.assertEqual([x["date"] for x in latest["trend"]], ["2026-09-01", "2026-09-15"])

    def test_changed_query_fingerprint_is_excluded(self):
        bad = mrow("2026-09-05", 1, True)
        bad["query_fingerprint"] = measure.query_fingerprint(
            {"text": "다른 질문", "type": "nonbrand"})
        result = measure.aggregate([bad], Q, HOST, BASE)
        self.assertEqual(result["rows"], 0)
        self.assertEqual(result["quality"]["incompatible_rows"], 1)


class DriftReliability(unittest.TestCase):
    def test_identical_detailed_cohort_is_comparable(self):
        result = drift.compare_measure(v2_summary(8, 10), v2_summary(2, 10))
        self.assertEqual(result["comparison"]["status"], "comparable")

    def test_different_cohort_is_inconclusive(self):
        result = drift.compare_measure(v2_summary(8, 10, qset="a"),
                                       v2_summary(1, 10, qset="b"))
        self.assertEqual(result["comparison"]["status"], "inconclusive")

    def test_error_round_is_inconclusive(self):
        result = drift.compare_measure(v2_summary(8, 10), v2_summary(1, 10, errors=1))
        self.assertEqual(result["comparison"]["status"], "inconclusive")

    def test_model_campaign_and_query_run_mix_are_comparison_conditions(self):
        base = v2_summary(5, 10, model="m1", campaign="c1", query_runs=[("Q1", 5), ("Q2", 5)])
        variants = [
            v2_summary(5, 10, model="m2", campaign="c1", query_runs=[("Q1", 5), ("Q2", 5)]),
            v2_summary(5, 10, model="m1", campaign="c2", query_runs=[("Q1", 5), ("Q2", 5)]),
            v2_summary(5, 10, model="m1", campaign="c1", query_runs=[("Q1", 8), ("Q2", 2)]),
        ]
        for after in variants:
            with self.subTest(after=after["cohorts"][0]):
                self.assertEqual(drift.compare_measure(base, after)["comparison"]["status"],
                                 "inconclusive")

    def test_unmeasured_and_cumulative_are_inconclusive(self):
        base = v2_summary(5, 10)
        for after in (v2_summary(5, 10, unmeasured=1),
                      v2_summary(5, 10, scope="cumulative")):
            self.assertEqual(drift.compare_measure(base, after)["comparison"]["status"],
                             "inconclusive")

    def test_v2_without_detailed_cohort_is_inconclusive(self):
        before, after = v2_summary(8, 10), v2_summary(2, 10)
        before.pop("cohorts")
        after.pop("cohorts")
        self.assertEqual(drift.compare_measure(before, after)["comparison"]["status"],
                         "inconclusive")

    def test_wilson_interval_and_small_sample_policy(self):
        self.assertEqual(drift.wilson_interval(0, 0), None)
        low, high = drift.wilson_interval(5, 10)
        self.assertLess(low, .5)
        self.assertGreater(high, .5)
        self.assertGreaterEqual(drift.MIN_MEASURE_RUNS, 5)

    def test_snapshot_prevalidation_writes_nothing(self):
        tmp = tempfile.mkdtemp(prefix="snapshot-atomic-")
        try:
            out = os.path.join(tmp, "out", HOST)
            os.makedirs(out)
            audit_path = os.path.join(out, "audit.json")
            measure_path = os.path.join(out, "bad-summary.json")
            drift.write_json(audit_path, {"schema": "su-multi-geo/audit/1",
                                          "target": {"host": HOST}, "stats": {}})
            drift.write_json(measure_path, {"schema": "wrong", "target": {"host": HOST}})
            with self.assertRaises(SystemExit):
                drift.main(["snapshot", audit_path, "--measure", measure_path,
                            "--date", "2026-09-05"])
            self.assertFalse(os.path.exists(os.path.join(out, "history", "index.json")))
            self.assertFalse(os.path.exists(os.path.join(out, "history", "audit-2026-09-05.json")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_snapshot_sha256_tamper_is_rejected(self):
        tmp = tempfile.mkdtemp(prefix="snapshot-hash-")
        try:
            out = os.path.join(tmp, "out", HOST)
            os.makedirs(out)
            audit_path = os.path.join(out, "audit.json")
            payload = {"schema": "su-multi-geo/audit/1", "target": {"host": HOST},
                       "stats": {}}
            drift.write_json(audit_path, payload)
            drift.main(["snapshot", audit_path, "--date", "2026-09-05"])
            index = drift.load_index(out, HOST)
            stored = os.path.join(out, "history", index["snapshots"][0]["file"])
            drift.write_json(stored, dict(payload, changed=True))
            with self.assertRaises(SystemExit):
                drift.snapshot_json(out, index["snapshots"][0])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
