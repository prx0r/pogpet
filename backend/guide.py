"""Guided personal-shopper sessions: person first, no search bar.

A session owns the whole journey so prompting accumulates instead of
restarting: ramble (who + why + budget) -> profile -> photos (up to 10) ->
mesh -> packs (budget-filtered, no scroll) -> refine -> checkout.

Rule-based understanding v1 (occasion/budget/name/interests via patterns);
the LLM chat stack can drive turns through the same state later. Stages:
ramble -> photos -> meshing -> ready (packs) -> refining (loop) -> done.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone

from . import config, db

MAX_PHOTOS = 10

OCCASIONS = {
    "birthday": ["birthday", "bday", "born"],
    "wedding": ["wedding", "married", "bride", "groom", "stag", "hen"],
    "christmas": ["christmas", "xmas", "santa", "stocking"],
    "fathers_day": ["father's day", "fathers day", "father day", "dad's day"],
    "mothers_day": ["mother's day", "mothers day", "mum's day", "mom's day"],
    "valentine": ["valentine"],
    "anniversary": ["anniversary"],
    "thank_you": ["thank you", "thanks"],
    "new_job": ["new job", "promotion"],
    "baby": ["baby", "shower", "newborn"],
}

NAME_PATS = [
    r"(?:for|about)\s+([A-Z][a-z]{1,19})\b",
    r"\b[Dd]ad\b", r"\b[Mm]um\b", r"\b[Mm]um\b", r"\b[Gg]randma\b", r"\b[Gg]randad\b",
]
NAME_CANON = {"dad": "Dad", "mum": "Mum", "mom": "Mum", "grandma": "Grandma",
              "grandad": "Grandad", "grandpa": "Grandad"}


def new_id() -> str:
    return "gs_" + uuid.uuid4().hex[:12]


def blank_state() -> dict:
    return {"occasion": "", "occasion_date": "", "budget_cents": 0,
            "recipient": {"name": "", "interests": [], "birthday": "", "mesh_id": ""},
            "photo_ids": [], "mesh_id": "", "mesh_status": "",
            "prefs": {"motif": "", "exclude": []}, "packs": [],
            "events": [], "log": []}


def get_session(c, sid: str, owner: str) -> dict | None:
    row = c.execute("SELECT * FROM guide_sessions WHERE id=? AND owner=?",
                    (sid, owner)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["state"] = json.loads(d.get("state") or "{}")
    except ValueError:
        d["state"] = blank_state()
    return d


def save_session(c, sid: str, owner: str, stage: str, state: dict) -> None:
    now = datetime.now(timezone.utc).timestamp()
    c.execute(
        "INSERT INTO guide_sessions (id,owner,stage,state,created_at,updated_at)"
        " VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET stage=excluded.stage,"
        " state=excluded.state, updated_at=excluded.updated_at",
        (sid, owner, stage, json.dumps(state), now, now))


def _extract_budget(text: str) -> int:
    m = re.search(r"(?:under|upto|up to|about|around|max|£|\$)\s*£?\$?\s*(\d{1,4})", text.lower())
    if not m:
        m = re.search(r"(\d{1,4})\s*(?:quid|pounds|dollars|bucks)", text.lower())
    if m:
        return max(0, min(20000, int(m.group(1)) * 100))
    return 0


def _extract_occasion(text: str) -> str:
    t = text.lower()
    for occ, keys in OCCASIONS.items():
        if any(k in t for k in keys):
            return occ
    return ""


def _extract_name(text: str) -> str:
    m = re.search(NAME_PATS[0], text)
    if m:
        return m.group(1)
    low = text.lower()
    for k, canon in NAME_CANON.items():
        if re.search(r"\b" + k + r"\b", low):
            return canon
    return ""


def _extract_interests(text: str) -> list[str]:
    t = text.lower()
    found = [k for k in config.INTEREST_MOTIFS if re.search(r"\b" + re.escape(k) + r"\b", t)]
    return found[:8]


def _extract_date(text: str) -> str:
    """Explicit dates (2026-11-14, 14 Nov, Nov 14) -> ISO. '' when absent."""
    m = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    months = {mth: i + 1 for i, mth in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
    m = re.search(r"(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*", text.lower())
    if m:
        return f"{date.today().year}-{months[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{1,2})", text.lower())
    if m:
        return f"{date.today().year}-{months[m.group(1)]:02d}-{int(m.group(2)):02d}"
    return ""


def compute_events(state: dict) -> list[dict]:
    """Birthdays/weddings/occasions as countdowns. Pure function of state."""
    today = date.today()
    events = []
    rec = state.get("recipient", {})
    bday = (rec.get("birthday") or "").strip()
    if bday:
        try:
            mm, dd = int(bday[:2]), int(bday[3:5])
            nxt = date(today.year, mm, dd)
            if nxt < today:
                nxt = date(today.year + 1, mm, dd)
            events.append({"kind": "birthday", "who": rec.get("name") or "them",
                           "date": nxt.isoformat(), "days_left": (nxt - today).days})
        except (ValueError, IndexError):
            pass
    occ = state.get("occasion", "")
    odate = state.get("occasion_date", "")
    if occ in ("wedding",) and odate:
        try:
            dt = date.fromisoformat(odate)
            if dt >= today:
                events.append({"kind": "wedding", "who": rec.get("name") or "them",
                               "date": dt.isoformat(), "days_left": (dt - today).days})
        except ValueError:
            pass
    if occ == "christmas":
        xmas = date(today.year, 12, 25)
        if xmas < today:
            xmas = date(today.year + 1, 12, 25)
        events.append({"kind": "christmas", "who": rec.get("name") or "them",
                       "date": xmas.isoformat(), "days_left": (xmas - today).days})
    for e in events:
        e["urgent"] = e["days_left"] <= 14
    return sorted(events, key=lambda e: e["days_left"])


def ramble_turn(state: dict, text: str) -> tuple[dict, str]:
    """Fold one ramble message into state. Returns (state, next_prompt)."""
    rec = state.setdefault("recipient", {"name": "", "interests": [], "birthday": "", "mesh_id": ""})
    name, occ, budget = _extract_name(text), _extract_occasion(text), _extract_budget(text)
    if name and not rec.get("name"):
        rec["name"] = name
    if occ and not state.get("occasion"):
        state["occasion"] = occ
        iso = _extract_date(text)
        if iso:
            state["occasion_date"] = iso
    if budget and not state.get("budget_cents"):
        state["budget_cents"] = budget
    for i in _extract_interests(text):
        if i not in rec.get("interests", []):
            rec.setdefault("interests", []).append(i)
    bday = re.search(r"\b(0[1-9]|1[0-2])-([0-2][0-9]|3[01])\b", text)
    if bday and not rec.get("birthday"):
        rec["birthday"] = bday.group(0)
    state["events"] = compute_events(state)
    state.setdefault("log", []).append({"turn": text[:500]})

    who = rec.get("name") or "them"
    missing = []
    if not rec.get("name"):
        missing.append("who")
    if not state.get("occasion"):
        missing.append("occasion")
    if not state.get("budget_cents"):
        missing.append("budget")
    if not missing:
        return state, (f"Got it — {who}, {state['occasion'].replace('_', ' ')}, "
                       f"under {state['budget_cents'] // 100}. "
                       f"Send me up to {MAX_PHOTOS} photos and I'll sculpt them, "
                       f"then show you gift packs. Nothing to scroll.")
    prompts = {
        "who": "Who are we shopping for?",
        "occasion": f"What's the occasion for {who} — birthday, wedding, Christmas?",
        "budget": f"And roughly what per gift — under what price?",
    }
    return state, prompts[missing[0]]
