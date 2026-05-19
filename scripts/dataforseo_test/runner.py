"""DataForSEO test runner.

Validates whether DataForSEO can supply the question / volume / PAA /
branded-search data needed by the cached market-intelligence layer.

See:
  docs/dataforseo-test-plan.md             (the manual plan this automates)
  docs/market-intelligence-architecture.md (what we're validating against)

Usage:
  1. Put DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD in api/.env
  2. cp scripts/dataforseo_test/config.example.json scripts/dataforseo_test/config.json
  3. Edit config.json with your 5 test businesses
  4. python scripts/dataforseo_test/runner.py

Output: scripts/dataforseo_test/results/{timestamp}/
  - raw/{business_slug}/{endpoint}.json   one file per API call
  - raw/toronto_comparison/{vertical}.json one file per vertical
  - SUMMARY.md                            human-readable verdict per Q1-Q6
  - manifest.json                         machine-readable summary

The script intentionally calls the live /live endpoints sequentially with a
60s timeout. ~25 calls total, ~3 minutes wall time, ~$0.70 in API credits.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

API_BASE = "https://api.dataforseo.com"
TIMEOUT = 60.0
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent

QUESTION_WORD_RE = re.compile(
    r"^(who|what|where|when|why|how|which|is|are|can|do|does|should)\b", re.I
)
QUESTION_PHRASE_RE = re.compile(r"\b(best|near me|cheap|top|emergency|24/?7|open)\b", re.I)


# DataForSEO city-level location_code lookup. DataForSEO Labs API is
# country-only (94 locations worldwide), but the Keywords Data API supports
# city-level via integer location_code. These codes come from
# /v3/keywords_data/google_ads/locations. Add cities here as new test
# businesses are added.
CITY_LOCATION_CODES: dict[str, int] = {
    "Burlington":   1002197,
    "Mississauga":  1002350,
    "Milton":       1002347,
    "Oakville":     1002371,
    "Brampton":     1002191,
    "Toronto":      1002451,
}


def normalize_domain(raw: str) -> str:
    """DataForSEO keywords_for_site expects a bare domain. Strip protocol,
    leading 'www.', and trailing slashes / paths so the config can hold the
    URL in whichever form the owner pasted."""
    s = raw.strip()
    s = re.sub(r"^https?://", "", s, flags=re.I)
    s = re.sub(r"^www\.", "", s, flags=re.I)
    s = s.split("/", 1)[0]  # drop any path
    return s.strip()


# ──────────────────────────────────────────────────────────────────────────────
# Credentials + config loading
# ──────────────────────────────────────────────────────────────────────────────

def load_credentials() -> tuple[str, str]:
    """Read DataForSEO credentials. Tries api/.env first, then root .env, then
    plain environ. Fails clearly if either is missing.
    """
    for env_path in (REPO_ROOT / "api" / ".env", REPO_ROOT / ".env"):
        if env_path.exists():
            load_dotenv(env_path, override=False)

    login = os.getenv("DATAFORSEO_LOGIN", "").strip()
    password = os.getenv("DATAFORSEO_PASSWORD", "").strip()

    if not login or not password:
        sys.exit(
            "ERROR: DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD must be set.\n"
            "Add them to api/.env or .env at the repo root, then re-run."
        )
    return login, password


def load_config() -> dict[str, Any]:
    cfg_path = SCRIPT_DIR / "config.json"
    if not cfg_path.exists():
        sys.exit(
            f"ERROR: {cfg_path} not found.\n"
            f"Copy config.example.json to config.json and fill in the 5 test businesses."
        )
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────────────────
# Thin HTTP client wrapper
# ──────────────────────────────────────────────────────────────────────────────

class DataForSEOClient:
    """Minimal sync httpx wrapper. One retry on 5xx, single-task POSTs only."""

    def __init__(self, login: str, password: str) -> None:
        self._client = httpx.Client(
            auth=(login, password),
            timeout=TIMEOUT,
            headers={"Content-Type": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def post(self, path: str, body: list[dict[str, Any]]) -> dict[str, Any]:
        for attempt in (1, 2):
            try:
                resp = self._client.post(f"{API_BASE}{path}", json=body)
            except httpx.RequestError as exc:
                if attempt == 2:
                    return {"_error": f"request_error: {exc}", "status_code": 0}
                time.sleep(2)
                continue
            if resp.status_code >= 500 and attempt == 1:
                time.sleep(2)
                continue
            try:
                payload = resp.json()
            except json.JSONDecodeError:
                payload = {"_error": "non_json_response", "body": resp.text[:500]}
            payload["_http_status"] = resp.status_code
            return payload
        return {"_error": "unreachable", "status_code": 0}

    # ── Endpoint helpers ─────────────────────────────────────────────────────

    def keyword_ideas(self, seeds: list[str], location_name: str, limit: int = 100) -> dict[str, Any]:
        """Country-level keyword discovery via Labs API. Labs doesn't support
        city-level; pass 'Canada' or similar. Kept for future country-wide
        seed discovery; not used in the city-level test path."""
        return self.post(
            "/v3/dataforseo_labs/google/keyword_ideas/live",
            [{
                "keywords": seeds,
                "location_name": location_name,
                "language_name": "English",
                "limit": limit,
                "include_serp_info": False,
            }],
        )

    def keywords_for_keywords(
        self, seeds: list[str], location_code: int, limit: int = 200
    ) -> dict[str, Any]:
        """Keyword discovery from seeds via Keywords Data API. Supports
        CITY-level location_code (e.g. 1002197 = Burlington, ON). Returns a
        flat list of {keyword, search_volume, competition, cpc, ...}.
        Primary discovery endpoint for the cached market-intelligence layer."""
        return self.post(
            "/v3/keywords_data/google_ads/keywords_for_keywords/live",
            [{
                "keywords": seeds,
                "location_code": location_code,
                "language_name": "English",
                "limit": limit,
            }],
        )

    def serp_advanced(self, keyword: str, location_name: str) -> dict[str, Any]:
        return self.post(
            "/v3/serp/google/organic/live/advanced",
            [{
                "language_code": "en",
                "location_name": location_name,
                "keyword": keyword,
                "device": "desktop",
            }],
        )

    def search_volume(
        self,
        keywords: list[str],
        location_code: int | None = None,
        location_name: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        """Per-keyword volume. Pass location_code for city-level (preferred)
        or location_name for country-level. date_from/date_to populate
        monthly_searches in each result item for trend analysis."""
        body: dict[str, Any] = {
            "keywords": keywords,
            "language_name": "English",
            "include_serp_info": False,
        }
        if location_code is not None:
            body["location_code"] = location_code
        else:
            body["location_name"] = location_name or "Canada"
        if date_from:
            body["date_from"] = date_from
        if date_to:
            body["date_to"] = date_to
        return self.post("/v3/keywords_data/google_ads/search_volume/live", [body])

    def keywords_for_site(self, target: str, location_name: str = "Canada") -> dict[str, Any]:
        return self.post(
            "/v3/dataforseo_labs/google/keywords_for_site/live",
            [{
                "target": target,
                "location_name": location_name,
                "language_name": "English",
                "limit": 50,
            }],
        )


# ──────────────────────────────────────────────────────────────────────────────
# Response parsing helpers — DataForSEO nests results 3 levels deep
# ──────────────────────────────────────────────────────────────────────────────

def get_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Returns the items array from tasks[0].result[0].items, or [].
    Used for SERP-family responses where items are nested one level deep."""
    try:
        return response["tasks"][0]["result"][0]["items"] or []
    except (KeyError, IndexError, TypeError):
        return []


def get_result(response: dict[str, Any]) -> dict[str, Any]:
    try:
        return response["tasks"][0]["result"][0] or {}
    except (KeyError, IndexError, TypeError):
        return {}


def get_keywords(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize keyword data across endpoint families.

    - keyword_ideas (Labs): result[0].items[], each with nested keyword_info.
    - keywords_for_keywords (Keywords Data): result[] is a flat list of items.
    - search_volume (Keywords Data): same flat list shape.

    Returns a uniform flat list with top-level search_volume, cpc,
    competition, and monthly_searches fields.
    """
    try:
        result = response["tasks"][0]["result"]
    except (KeyError, IndexError, TypeError):
        return []
    if not result:
        return []

    # keyword_ideas shape: result is [{items: [...]}]
    if (
        isinstance(result, list)
        and result
        and isinstance(result[0], dict)
        and "items" in result[0]
    ):
        items = result[0].get("items") or []
        out: list[dict[str, Any]] = []
        for k in items:
            info = k.get("keyword_info") or {}
            out.append({
                "keyword": k.get("keyword"),
                "search_volume": info.get("search_volume"),
                "cpc": info.get("cpc"),
                "competition": info.get("competition"),
                "monthly_searches": info.get("monthly_searches"),
            })
        return out

    # Flat list shape (keywords_for_keywords, search_volume)
    if isinstance(result, list):
        return [k for k in result if isinstance(k, dict) and "keyword" in k]
    return []


def looks_question(keyword: str) -> bool:
    """Loose heuristic: keyword starts with a question word OR contains
    high-intent phrasing. Calibrated for English; under-counts French.
    """
    return bool(QUESTION_WORD_RE.search(keyword) or QUESTION_PHRASE_RE.search(keyword))


def extract_paa_titles(serp_response: dict[str, Any]) -> list[str]:
    """SERP advanced returns mixed items; we want the people_also_ask block."""
    result = get_result(serp_response)
    for item in (result.get("items") or []):
        if item.get("type") == "people_also_ask":
            titles = []
            for paa in (item.get("items") or []):
                title = paa.get("title")
                if title:
                    titles.append(title)
            return titles
    return []


# ──────────────────────────────────────────────────────────────────────────────
# Per-question metric computation (Q1..Q6)
# ──────────────────────────────────────────────────────────────────────────────

def q1_actionability(kw_response: dict[str, Any]) -> dict[str, Any]:
    """Q1 — Are the top 30 keywords actionable?
    Pass: ≥30 keywords with non-zero volume AND ≥10 question-shaped.
    Partial: ≥20 with volume AND ≥5 question-shaped.
    """
    items = get_keywords(kw_response)
    if not items:
        return {"verdict": "FAIL", "reason": "no keywords returned", "n_total": 0,
                "n_with_volume": 0, "n_question_shaped": 0, "top10": []}

    with_volume = []
    question_shaped = []
    for k in items:
        kw = k.get("keyword") or ""
        vol = k.get("search_volume") or 0
        if vol > 0:
            with_volume.append(kw)
        if looks_question(kw):
            question_shaped.append(kw)

    n_vol = len(with_volume)
    n_q = len(question_shaped)
    if n_vol >= 30 and n_q >= 10:
        verdict = "PASS"
    elif n_vol >= 20 and n_q >= 5:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    # Top 10 by volume (treat null as 0 for sorting)
    sorted_items = sorted(items, key=lambda x: (x.get("search_volume") or 0), reverse=True)
    return {
        "verdict": verdict,
        "n_total": len(items),
        "n_with_volume": n_vol,
        "n_question_shaped": n_q,
        "top10": [{"keyword": k.get("keyword"), "search_volume": k.get("search_volume")}
                  for k in sorted_items[:10]],
    }


def q2_paa_depth(serp_response: dict[str, Any]) -> dict[str, Any]:
    """Q2 — Does PAA expansion add 4-8 questions per query in mid-cities?"""
    titles = extract_paa_titles(serp_response)
    n = len(titles)
    if n >= 4:
        verdict = "PASS"
    elif n >= 2:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"
    return {"verdict": verdict, "n": n, "questions": titles}


def q3_volume_coverage(kw_response: dict[str, Any]) -> dict[str, Any]:
    """Q3 — Is volume data populated for mid-city queries?
    Pass: ≥70% of keywords have non-zero search_volume.
    Partial: top-10 by volume have volume but overall coverage is sparse.
    """
    items = get_keywords(kw_response)
    if not items:
        return {"verdict": "FAIL", "reason": "no keywords", "pct_with_volume": 0.0,
                "n_total": 0, "n_with_volume": 0, "top10_pct_with_volume": 0.0}

    n = len(items)
    n_with = sum(1 for k in items if (k.get("search_volume") or 0) > 0)
    pct = n_with / n if n else 0.0

    sorted_items = sorted(items, key=lambda x: (x.get("search_volume") or 0), reverse=True)
    top10 = sorted_items[:10]
    top10_with = sum(1 for k in top10 if (k.get("search_volume") or 0) > 0)
    top10_pct = top10_with / len(top10) if top10 else 0.0

    if pct >= 0.70:
        verdict = "PASS"
    elif top10_pct >= 0.70:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    return {
        "verdict": verdict,
        "pct_with_volume": round(pct, 3),
        "top10_pct_with_volume": round(top10_pct, 3),
        "n_total": n,
        "n_with_volume": n_with,
    }


def q4_branded(sv_response: dict[str, Any]) -> dict[str, Any]:
    """Q4 — Does branded search return non-null volumes for actual names?
    Known caveat: Google Ads hides volumes below ~10/mo, so SMB names often
    return null. That null result is itself a meaningful architectural
    finding."""
    items = get_keywords(sv_response)
    if not items:
        return {"verdict": "FAIL", "reason": "no response items", "queries": {}, "n_with_volume": 0}

    per_query: dict[str, int | None] = {}
    for k in items:
        per_query[k.get("keyword") or ""] = k.get("search_volume")

    with_volume = sum(1 for v in per_query.values() if v is not None and v > 0)
    any_volume = any(v is not None and v > 0 for v in per_query.values())

    if with_volume == len(per_query) and len(per_query) > 0:
        verdict = "PASS"
    elif any_volume:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    return {"verdict": verdict, "queries": per_query, "n_with_volume": with_volume}


def q5_stability(sv_history_response: dict[str, Any]) -> dict[str, Any]:
    """Q5 — Is the trend data stable enough for quarterly question refresh?
    Pass: ≥70% of tracked keywords show <50% MoM swing.
    """
    items = get_keywords(sv_history_response)
    if not items:
        return {"verdict": "FAIL", "reason": "no history returned", "per_keyword": {},
                "pct_stable": 0.0, "n_stable": 0, "n_evaluated": 0}

    per_keyword: dict[str, dict[str, Any]] = {}
    n_stable = 0
    n_evaluated = 0

    for k in items:
        kw = k.get("keyword") or ""
        monthly = k.get("monthly_searches") or []
        if len(monthly) < 2:
            per_keyword[kw] = {"max_swing_pct": None, "reason": "<2 months of data"}
            continue

        volumes = [m.get("search_volumes", m.get("search_volume", 0)) or 0 for m in monthly]
        max_swing = 0.0
        for i in range(1, len(volumes)):
            prev = volumes[i - 1]
            cur = volumes[i]
            if prev == 0 and cur == 0:
                continue
            base = max(prev, 1)
            swing = abs(cur - prev) / base
            max_swing = max(max_swing, swing)

        per_keyword[kw] = {
            "max_swing_pct": round(max_swing * 100, 1),
            "monthly_volumes": volumes,
        }
        n_evaluated += 1
        if max_swing < 0.50:
            n_stable += 1

    pct_stable = (n_stable / n_evaluated) if n_evaluated else 0.0
    if pct_stable >= 0.70:
        verdict = "PASS"
    elif pct_stable >= 0.40:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    return {
        "verdict": verdict,
        "pct_stable": round(pct_stable, 3),
        "n_stable": n_stable,
        "n_evaluated": n_evaluated,
        "per_keyword": per_keyword,
    }


def q6_city_vs_toronto(
    mid_city_kw: dict[str, Any], toronto_kw: dict[str, Any]
) -> dict[str, Any]:
    """Q6 — Is mid-city data dense enough vs Toronto for the same vertical?
    Compares total keyword counts returned by keywords_for_keywords at
    city-level for both."""
    mid_items = get_keywords(mid_city_kw)
    tor_items = get_keywords(toronto_kw)
    n_mid = len(mid_items)
    n_tor = len(tor_items)
    if n_tor == 0:
        return {"verdict": "FAIL", "reason": "no Toronto data", "n_mid": n_mid, "n_toronto": 0}

    ratio = n_mid / n_tor
    if ratio >= 0.80:
        verdict = "PASS"
    elif ratio >= 0.40:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    return {
        "verdict": verdict,
        "ratio": round(ratio, 3),
        "n_mid": n_mid,
        "n_toronto": n_tor,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Orchestration
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class BusinessRun:
    slug: str
    name: str
    vertical: str
    city: str
    location_name: str
    raw: dict[str, dict[str, Any]] = field(default_factory=dict)
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)


def run_business(client: DataForSEOClient, biz: dict[str, Any], history_window: dict[str, str]) -> BusinessRun:
    location = f"{biz['city']},{biz['province']},{biz['country']}"
    location_code = CITY_LOCATION_CODES.get(biz["city"])
    run = BusinessRun(
        slug=biz["slug"],
        name=biz["name"],
        vertical=biz["vertical"],
        city=biz["city"],
        location_name=location,
    )

    print(f"\n── {biz['name']}  ({biz['vertical']} / {biz['city']}) ──")

    if location_code is None:
        msg = f"no location_code mapped for city '{biz['city']}'"
        print(f"  [A] SKIPPED ({msg})")
        run.raw["keywords_discovery"] = {"_skipped": msg}
    else:
        print(f"  [A] keywords_for_keywords (city_code={location_code})...")
        run.raw["keywords_discovery"] = client.keywords_for_keywords(
            biz["seed_keywords"], location_code, limit=200,
        )

    print(f"  [B] serp_advanced (PAA, {location})...")
    run.raw["serp_advanced"] = client.serp_advanced(biz["top_query"], location)

    print(f"  [C] branded_search_volume (city_code={location_code})...")
    run.raw["branded_search_volume"] = client.search_volume(
        biz["branded_queries"], location_code=location_code,
    )

    if biz.get("website"):
        target = normalize_domain(biz["website"])
        print(f"  [D] keywords_for_site ({target})...")
        run.raw["keywords_for_site"] = client.keywords_for_site(target)
    else:
        print("  [D] keywords_for_site SKIPPED (no website in config)")
        run.raw["keywords_for_site"] = {"_skipped": "no website in config"}

    print("  [Trend] historical search_volume on top 3 keywords...")
    discovered = get_keywords(run.raw["keywords_discovery"])
    # Pick top 3 keywords by volume (skip nulls)
    ranked = sorted(discovered, key=lambda x: (x.get("search_volume") or 0), reverse=True)
    top3_keywords = [k.get("keyword") for k in ranked[:3] if k.get("keyword") and (k.get("search_volume") or 0) > 0]
    if top3_keywords and location_code is not None:
        run.raw["trend_history"] = client.search_volume(
            top3_keywords,
            location_code=location_code,
            date_from=history_window["date_from"],
            date_to=history_window["date_to"],
        )
    else:
        run.raw["trend_history"] = {"_skipped": "no top keywords with volume"}

    return run


def compute_metrics(run: BusinessRun, toronto_kw_by_vertical: dict[str, dict[str, Any]]) -> None:
    run.metrics["Q1_actionability"] = q1_actionability(run.raw["keywords_discovery"])
    run.metrics["Q2_paa_depth"] = q2_paa_depth(run.raw["serp_advanced"])
    run.metrics["Q3_volume_coverage"] = q3_volume_coverage(run.raw["keywords_discovery"])
    run.metrics["Q4_branded_search"] = q4_branded(run.raw["branded_search_volume"])
    if not run.raw["trend_history"].get("_skipped"):
        run.metrics["Q5_stability"] = q5_stability(run.raw["trend_history"])
    else:
        run.metrics["Q5_stability"] = {
            "verdict": "FAIL", "reason": run.raw["trend_history"]["_skipped"],
            "per_keyword": {}, "n_stable": 0, "n_evaluated": 0, "pct_stable": 0.0,
        }

    tor = toronto_kw_by_vertical.get(run.vertical)
    if tor is not None:
        run.metrics["Q6_city_vs_toronto"] = q6_city_vs_toronto(run.raw["keywords_discovery"], tor)
    else:
        run.metrics["Q6_city_vs_toronto"] = {
            "verdict": "FAIL",
            "reason": f"no Toronto comparator for vertical '{run.vertical}'",
        }


def aggregate_verdict(runs: list[BusinessRun]) -> dict[str, Any]:
    """Map the per-business verdicts to the architecture-level decision."""
    counts: dict[str, dict[str, int]] = {}
    questions = ["Q1_actionability", "Q2_paa_depth", "Q3_volume_coverage",
                 "Q4_branded_search", "Q5_stability", "Q6_city_vs_toronto"]
    for q in questions:
        counts[q] = {"PASS": 0, "PARTIAL": 0, "FAIL": 0}
    for run in runs:
        for q in questions:
            v = run.metrics.get(q, {}).get("verdict", "FAIL")
            counts[q][v] = counts[q].get(v, 0) + 1

    n = len(runs)
    pass_q1234 = sum(
        1 for run in runs
        if all(run.metrics.get(q, {}).get("verdict") in ("PASS", "PARTIAL")
               for q in ["Q1_actionability", "Q2_paa_depth", "Q3_volume_coverage", "Q4_branded_search"])
        and run.metrics.get("Q1_actionability", {}).get("verdict") == "PASS"
        and run.metrics.get("Q2_paa_depth", {}).get("verdict") in ("PASS", "PARTIAL")
    )

    fail_q1_or_q2 = sum(
        1 for run in runs
        if run.metrics.get("Q1_actionability", {}).get("verdict") == "FAIL"
        or run.metrics.get("Q2_paa_depth", {}).get("verdict") == "FAIL"
    )

    if pass_q1234 >= 4:
        decision = "PROCEED"
        rationale = "≥4 of 5 businesses pass Q1+Q2+Q3+Q4. DataForSEO is the primary data source for Phase 1."
    elif fail_q1_or_q2 >= 4:
        decision = "PIVOT"
        rationale = "≥4 of 5 businesses fail Q1 or Q2. Drop DataForSEO; use SerpApi PAA + curated templates. Formula A becomes Formula B."
    elif counts["Q1_actionability"]["FAIL"] + counts["Q2_paa_depth"]["FAIL"] + counts["Q3_volume_coverage"]["FAIL"] >= 12:
        decision = "RECONSIDER"
        rationale = "Most businesses fail Q1 + Q2 + Q3. The cached intelligence layer's data foundation is too weak. Reconsider whether to ship Phase 4+ at all."
    else:
        decision = "PROCEED_WITH_CAVEATS"
        rationale = "Mixed results. Architecture doc 'Honest Caveats and Risks' needs updates before Phase 1."

    return {
        "decision": decision,
        "rationale": rationale,
        "counts_by_question": counts,
        "n_businesses": n,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Output rendering
# ──────────────────────────────────────────────────────────────────────────────

def write_raw(out_dir: Path, runs: list[BusinessRun],
              toronto_ki: dict[str, dict[str, Any]]) -> None:
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for run in runs:
        biz_dir = raw_dir / run.slug
        biz_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in run.raw.items():
            with (biz_dir / f"{name}.json").open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, default=str)
    tor_dir = raw_dir / "toronto_comparison"
    tor_dir.mkdir(parents=True, exist_ok=True)
    for vertical, payload in toronto_ki.items():
        with (tor_dir / f"{vertical}.json").open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)


def render_summary_md(out_dir: Path, runs: list[BusinessRun], agg: dict[str, Any],
                      config: dict[str, Any], started_at: str, finished_at: str) -> None:
    lines: list[str] = []
    lines.append("# DataForSEO Test — Run Summary")
    lines.append("")
    lines.append(f"- **Started:** {started_at}")
    lines.append(f"- **Finished:** {finished_at}")
    lines.append(f"- **Businesses tested:** {len(runs)}")
    lines.append(f"- **Historical window:** {config['historical_window']['date_from']} → {config['historical_window']['date_to']}")
    lines.append("")
    lines.append("## Overall verdict")
    lines.append("")
    lines.append(f"**{agg['decision']}** — {agg['rationale']}")
    lines.append("")
    lines.append("### Counts by question")
    lines.append("")
    lines.append("| Question | PASS | PARTIAL | FAIL |")
    lines.append("|---|---|---|---|")
    for q, c in agg["counts_by_question"].items():
        lines.append(f"| {q} | {c['PASS']} | {c['PARTIAL']} | {c['FAIL']} |")
    lines.append("")
    lines.append("## Per-business verdicts")
    lines.append("")
    lines.append("| Business | City | Vertical | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for run in runs:
        m = run.metrics
        row = [
            run.name,
            run.city,
            run.vertical,
            m.get("Q1_actionability", {}).get("verdict", "?"),
            m.get("Q2_paa_depth", {}).get("verdict", "?"),
            m.get("Q3_volume_coverage", {}).get("verdict", "?"),
            m.get("Q4_branded_search", {}).get("verdict", "?"),
            m.get("Q5_stability", {}).get("verdict", "?"),
            m.get("Q6_city_vs_toronto", {}).get("verdict", "?"),
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("## Per-business detail")
    lines.append("")
    for run in runs:
        lines.append(f"### {run.name}")
        lines.append("")
        lines.append(f"- Vertical: `{run.vertical}` · City: `{run.city}` · Location: `{run.location_name}`")
        lines.append("")
        m = run.metrics

        q1 = m["Q1_actionability"]
        lines.append(f"**Q1 — Actionability: `{q1['verdict']}`**")
        lines.append(f"- Total keywords returned: `{q1.get('n_total', 0)}`")
        lines.append(f"- With non-zero volume: `{q1.get('n_with_volume', 0)}`")
        lines.append(f"- Question-shaped (heuristic): `{q1.get('n_question_shaped', 0)}`")
        if q1.get("top10"):
            lines.append("- Top 10 by volume:")
            for kw in q1["top10"]:
                if isinstance(kw, dict):
                    lines.append(f"  - `{kw.get('keyword')}` — sv={kw.get('search_volume')}")
                else:
                    lines.append(f"  - {kw}")
        lines.append("")

        q2 = m["Q2_paa_depth"]
        lines.append(f"**Q2 — PAA depth: `{q2['verdict']}`**  ({q2.get('n', 0)} questions)")
        for kw in (q2.get("questions") or []):
            lines.append(f"  - {kw}")
        lines.append("")

        q3 = m["Q3_volume_coverage"]
        lines.append(f"**Q3 — Volume coverage: `{q3['verdict']}`**")
        lines.append(f"- All keywords with volume: `{int((q3.get('pct_with_volume', 0) * 100))}%` "
                     f"({q3.get('n_with_volume', 0)}/{q3.get('n_total', 0)})")
        lines.append(f"- Top-10 with volume: `{int((q3.get('top10_pct_with_volume', 0) * 100))}%`")
        lines.append("")

        q4 = m["Q4_branded_search"]
        lines.append(f"**Q4 — Branded search: `{q4['verdict']}`**")
        for q, v in (q4.get("queries") or {}).items():
            lines.append(f"  - `{q}` → `{v}`")
        lines.append("")

        q5 = m["Q5_stability"]
        lines.append(f"**Q5 — Stability: `{q5['verdict']}`**")
        if q5.get("per_keyword"):
            lines.append(f"- Stable (<50% MoM swing): `{q5.get('n_stable', 0)}/{q5.get('n_evaluated', 0)}`")
            for kw, info in (q5.get("per_keyword") or {}).items():
                swing = info.get("max_swing_pct")
                vols = info.get("monthly_volumes")
                if swing is not None:
                    lines.append(f"  - `{kw}`: max swing `{swing}%`, volumes `{vols}`")
                else:
                    lines.append(f"  - `{kw}`: {info.get('reason', 'unknown')}")
        lines.append("")

        q6 = m["Q6_city_vs_toronto"]
        lines.append(f"**Q6 — City vs Toronto: `{q6['verdict']}`**")
        if "ratio" in q6:
            lines.append(f"- Ratio: `{q6['ratio']}` ({q6.get('n_mid', 0)} mid-city vs {q6.get('n_toronto', 0)} Toronto)")
        else:
            lines.append(f"- Reason: {q6.get('reason', '')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## What to do with this report")
    lines.append("")
    lines.append("1. Read the overall verdict above.")
    lines.append("2. For any question where the result is mixed, scan the per-business detail to see WHICH business and HOW it failed.")
    lines.append("3. Cross-reference with the decision matrix in [docs/dataforseo-test-plan.md](../../../docs/dataforseo-test-plan.md#step-7--decision-criteria).")
    lines.append("4. Update [docs/market-intelligence-architecture.md](../../../docs/market-intelligence-architecture.md) per the 'After the test — what to update' section.")
    lines.append("")

    out_dir.joinpath("SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def render_manifest(out_dir: Path, runs: list[BusinessRun], agg: dict[str, Any],
                    started_at: str, finished_at: str) -> None:
    manifest = {
        "started_at": started_at,
        "finished_at": finished_at,
        "decision": agg["decision"],
        "rationale": agg["rationale"],
        "counts_by_question": agg["counts_by_question"],
        "businesses": [
            {
                "slug": r.slug, "name": r.name, "vertical": r.vertical, "city": r.city,
                "verdicts": {q: m.get("verdict") for q, m in r.metrics.items()},
            }
            for r in runs
        ],
    }
    with out_dir.joinpath("manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    # Windows default console codec is cp1252, which can't encode the box-drawing
    # characters we use for progress output. Force UTF-8 if the stdout stream
    # supports reconfigure (Python 3.7+).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    login, password = load_credentials()
    config = load_config()

    started_dt = datetime.now(timezone.utc)
    started_at = started_dt.strftime("%Y-%m-%dT%H-%M-%SZ")
    out_dir = SCRIPT_DIR / "results" / started_at
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {out_dir}")

    client = DataForSEOClient(login, password)
    runs: list[BusinessRun] = []
    toronto_ki: dict[str, dict[str, Any]] = {}

    try:
        # Per-business calls
        for biz in config["businesses"]:
            run = run_business(client, biz, config["historical_window"])
            runs.append(run)

        # Toronto comparator per vertical (city-level via Keywords Data)
        verticals = sorted({r.vertical for r in runs})
        toronto_code = CITY_LOCATION_CODES["Toronto"]
        print(f"\n── Toronto comparators ({len(verticals)} verticals, code={toronto_code}) ──")
        for vertical in verticals:
            seeds = config["toronto_comparison_seeds"].get(vertical)
            if not seeds:
                print(f"  [Toronto/{vertical}] SKIPPED (no seeds in config)")
                continue
            print(f"  [Toronto/{vertical}] keywords_for_keywords...")
            toronto_ki[vertical] = client.keywords_for_keywords(seeds, toronto_code, limit=200)

        # Compute metrics + aggregate
        for run in runs:
            compute_metrics(run, toronto_ki)

        agg = aggregate_verdict(runs)

        # Persist
        write_raw(out_dir, runs, toronto_ki)
        render_summary_md(out_dir, runs, agg, config, started_at,
                          datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"))
        render_manifest(out_dir, runs, agg, started_at,
                        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"))

    finally:
        client.close()

    print(f"\n✓ Done. Read: {out_dir / 'SUMMARY.md'}")
    print(f"  Decision: {agg['decision']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
