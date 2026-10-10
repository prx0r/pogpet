"""Pogtown experiment science — probes, gold runs, comment evidence.

Implements vision/endgame-pogtown-mvp.md §§6,20-28,32-40 as pure logic:
no rendering, no publishing, no spend. Runtimes (Freaktown, Influence,
FinalBuilds2) feed these evaluators; pogpet never grows experiment
infrastructure beyond them. Everything appends to JSONL under data/.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from backend import config

PROBE_REQUIRED = ("probe_id", "experiment_id", "hypothesis_id", "arm",
                  "primary_factor", "controls", "creative", "preregistered")
ARMS = ("control", "treatment")
FINDING_STATES = ("provisional", "replicated", "robust",
                  "contradicted", "retired")

# §22 comment taxonomy (keyword v0 classifier; LLM labels upgrade later).
COMMENT_LABELS = (
    "GENERIC_POSITIVE", "CHARACTER_POSITIVE", "RETURN_REQUEST", "QUOTE",
    "JOKE_MECHANISM", "PERFORMANCE", "VISUAL", "VOICE", "TOPIC",
    "NEGATIVE_CHARACTER", "NEGATIVE_WRITING", "CONFUSION", "AI_ARTIFACT",
    "PACKAGING_MISMATCH",
)
_LABEL_PATTERNS: dict[str, list[str]] = {
    "RETURN_REQUEST": [r"bring .* back", r"more .*episodes?", r"need .*season",
                       r"when.?s the next"],
    "QUOTE": [r"^\"|“.*”", r"stealing", r"my new motto", r"gonna (say|use)"],
    "JOKE_MECHANISM": [r"the way (he|she|they|it) .*", r"thinking .* finished me",
                       r"lost it when", r"the fact .* killed me"],
    "PERFORMANCE": [r"\bpause\b", r"timing", r"delivery", r"deadpan", r"stare"],
    "VISUAL": [r"\bhat\b", r"looks? like", r"tiny .*", r"animation", r"face"],
    "VOICE": [r"\bvoice\b", r"sound(s|ing)? like", r"accent"],
    "TOPIC": [r"too real", r"literally me", r"this airport", r"my job"],
    "NEGATIVE_CHARACTER": [r"hate (this|him|her|it)", r"annoying", r"unfunny guy"],
    "NEGATIVE_WRITING": [r"same joke", r"repetitive", r"lazy writing", r"try-hard"],
    "CONFUSION": [r"don.?t get", r"what happened", r"confused", r"makes no sense"],
    "AI_ARTIFACT": [r"\barm\b.*melt", r"fingers", r"glitch", r"ai (slop|looking)"],
    "PACKAGING_MISMATCH": [r"thumbnail.*nothing", r"clickbait", r"not in the video"],
    "CHARACTER_POSITIVE": [r"killing me", r"love (him|her|them|this (guy|dog|character))",
                           r"my favorite", r"icon"],
    "GENERIC_POSITIVE": [r"\blol\b", r"haha", r"funny", r"😂", r"lmao"],
}
_OUTCOME_KEYS = ("reach", "click", "hook", "retention", "rewatch", "share",
                 "generic_positive", "specific_positive", "character_positive",
                 "return_request", "quote_adoption", "negative_specific",
                 "subscriber_effect", "returning_audience")


def probe_hash(manifest: dict) -> str:
    canon = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def validate_probe(manifest: dict) -> list[str]:
    """A probe without one primary factor + falsifiable claim is rejected."""
    gaps = []
    if not isinstance(manifest, dict):
        return ["probe must be an object"]
    for k in PROBE_REQUIRED:
        if k not in manifest:
            gaps.append(f"missing {k}")
    if manifest.get("arm") not in ARMS:
        gaps.append(f"arm must be one of {ARMS}")
    pf = manifest.get("primary_factor") or {}
    if not pf.get("name"):
        gaps.append("primary_factor.name required (one manipulated factor)")
    pre = manifest.get("preregistered") or {}
    if not pre.get("primary_metric"):
        gaps.append("preregistered.primary_metric required")
    if not pre.get("expected_direction"):
        gaps.append("preregistered.expected_direction required")
    return gaps


def freeze_probe(manifest: dict) -> dict:
    """Validate + stamp immutable hash. No edits after this point."""
    gaps = validate_probe(manifest)
    if gaps:
        raise ValueError("; ".join(gaps))
    frozen = dict(manifest)
    frozen["manifest_hash"] = probe_hash(manifest)
    frozen["frozen_at"] = time.time()
    return frozen


def retention_features(points: list[tuple[float, float]]) -> dict:
    """Raw (elapsed_ratio, watch_ratio) curve -> interpretable features.
    Beat alignment happens upstream via StageTimeline; here be numbers."""
    pts = sorted((float(t), float(r)) for t, r in points)
    if len(pts) < 3:
        return {"ok": False, "error": "need >=3 retention points"}

    def at(x: float) -> float:
        for i in range(len(pts) - 1):
            (t0, r0), (t1, r1) = pts[i], pts[i + 1]
            if t0 <= x <= t1 and t1 > t0:
                f = (x - t0) / (t1 - t0)
                return r0 + f * (r1 - r0)
        return pts[-1][1] if x >= pts[-1][0] else pts[0][1]

    feats = {f"R_{int(x * 100):02d}": round(at(x), 4)
             for x in (0.05, 0.10, 0.25, 0.50, 0.75, 0.95)}
    auc = 0.0
    for i in range(len(pts) - 1):
        (t0, r0), (t1, r1) = pts[i], pts[i + 1]
        auc += (t1 - t0) * (r0 + r1) / 2
    feats["retention_auc"] = round(auc, 4)
    drops = [(pts[i][1] - pts[i + 1][1], pts[i + 1][0])
             for i in range(len(pts) - 1)]
    feats["largest_drop"] = round(max(drops)[0], 4) if drops else 0.0
    feats["closer_retention"] = round(at(0.95), 4)
    feats["hook_retention"] = round(at(0.05), 4)
    return {"ok": True, **feats}


def classify_comment(text: str) -> dict:
    """Keyword v0: ordered taxonomy, first strong match wins; specificity =
    word count of the matched span proxy. LLM classifier upgrades later."""
    t = (text or "").lower()
    words = len(t.split())
    for label in COMMENT_LABELS:
        for pat in _LABEL_PATTERNS.get(label, []):
            m = re.search(pat, t)
            if m:
                return {"label": label, "confidence": round(min(0.9, 0.4 + 0.05 * words), 2),
                        "span": m.group(0)[:120], "specific": words >= 6}
    return {"label": "GENERIC_POSITIVE" if words else "CONFUSION",
            "confidence": 0.3, "span": text[:120], "specific": False}


def gold_rates(metrics: dict) -> dict:
    """Per-1k-engaged-view explanatory rates (§23). Raw counts in, rates out."""
    engaged = max(1, int(metrics.get("engaged_views") or 0))
    per_k = lambda n: round(1000.0 * int(n or 0) / engaged, 3)
    return {
        "specific_positive_per_k": per_k(metrics.get("specific_positive")),
        "character_positive_per_k": per_k(metrics.get("character_positive")),
        "return_requests_per_k": per_k(metrics.get("return_requests")),
        "quote_adoption_per_k": per_k(metrics.get("quote_adoption")),
        "specific_negative_per_k": per_k(metrics.get("specific_negative")),
    }


def is_gold_candidate(snapshot: dict, channel_medians: dict | None = None) -> tuple[bool, dict]:
    """Gold bar: completion ≥ median AND (shares OR comments) top-decile-ish.
    Without channel baselines, require explicit thresholds passed in."""
    med = channel_medians or {}
    reasons, need = {}, snapshot.get("metrics") or {}
    comp = float(need.get("completion") or 0)
    if comp >= float(med.get("completion", 0.35)):
        reasons["completion"] = comp
    for k in ("share_rate", "specific_positive_rate"):
        v = float(need.get(k) or 0)
        if v >= float(med.get(k, 0.02)):
            reasons[k] = v
    ok = "completion" in reasons and len(reasons) >= 2
    return ok, reasons


def explanation_plan(gold_run: dict) -> dict:
    """E1-E7 diagnostic follow-ups (§48): vary exactly one lane each."""
    base = {"gold_run_id": gold_run.get("gold_run_id", ""),
            "episode_id": gold_run.get("episode_id", "")}
    lanes = ["replication", "character_swap", "jokeblock_swap", "topic_swap",
             "performance_swap", "visual_swap", "packaging_test"]
    return {"gold_run_id": base["gold_run_id"],
            "plans": [{**base, "probe_kind": f"E{i + 1}_{lane}",
                       "varies": lane,
                       "holds": [l for l in lanes if l != lane]}
                      for i, lane in enumerate(lanes)]}


def make_finding(claim: dict, evidence: dict,
                 status: str = "provisional") -> dict:
    """Finding object (§40): claim triple + evidence refs + lifecycle."""
    if status not in FINDING_STATES:
        raise ValueError(f"status must be one of {FINDING_STATES}")
    for k in ("subject", "predicate", "object"):
        if not (claim or {}).get(k):
            raise ValueError(f"claim.{k} required")
    return {"finding_id": "",
            "claim": dict(claim),
            "scope": dict((evidence or {}).get("scope", {})),
            "evidence": {"experiments": list((evidence or {}).get("experiments", [])),
                         "n_probes": int((evidence or {}).get("n_probes", 0)),
                         "comment_refs": list((evidence or {}).get("comment_refs", []))},
            "status": status,
            "posterior": {"direction_probability": float(
                (evidence or {}).get("direction_probability", 0.5))},
            "created_at": time.time()}


def novelty_decay(appearances: list[dict]) -> dict:
    """Track per-appearance outcomes to separate mechanism from novelty (§28).
    appearances: [{n, views, completion}...] in order. Returns decay slope
    sign + whether the effect survives past debut."""
    if len(appearances) < 2:
        return {"ok": False, "error": "need >=2 appearances"}
    first = float(appearances[0].get("completion") or 0)
    rest = [float(a.get("completion") or 0) for a in appearances[1:]]
    avg_rest = sum(rest) / len(rest)
    return {"ok": True, "debut": first, "mean_later": round(avg_rest, 4),
            "survives_debut": avg_rest >= 0.8 * first}
