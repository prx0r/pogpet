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
    "new_baby": ["new baby"],
    "graduation": ["graduation", "graduated", "grad"],
    "retirement": ["retirement", "retired", "retiring"],
    "just_because": ["just because", "no reason", "thinking of you"],
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
            "budget_scope": "per_gift",
            "recipient": {"name": "", "interests": [], "dislikes": [],
                          "birthday": "", "mesh_id": "", "anecdotes": []},
            "delivery": {"deadline": "", "destination": ""},
            "photo_ids": [], "mesh_id": "", "mesh_status": "",
            "prefs": {"motif": "", "exclude": []}, "packs": [],
            "events": [], "log": [], "feed": [], "revision": 0,
            "last_seq": 0, "prompts": {}, "mode": "ramble"}


def _normalize_state(state: dict) -> dict:
    """Upgrade older sessions in place: every key the engine reads exists."""
    base = blank_state()
    for k, v in base.items():
        if k not in state:
            state[k] = v
    rec = state.get("recipient") or {}
    for k, v in base["recipient"].items():
        rec.setdefault(k, v)
    state["recipient"] = rec
    state.setdefault("delivery", {"deadline": "", "destination": ""})
    state["delivery"].setdefault("deadline", "")
    state["delivery"].setdefault("destination", "")
    state.setdefault("budget_scope", "per_gift")
    state.setdefault("feed", [])
    state.setdefault("revision", 0)
    state.setdefault("last_seq", 0)
    state.setdefault("prompts", {})
    state.setdefault("mode", "ramble")
    return state


def get_session(c, sid: str, owner: str) -> dict | None:
    row = c.execute("SELECT * FROM guide_sessions WHERE id=? AND owner=?",
                    (sid, owner)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["state"] = _normalize_state(json.loads(d.get("state") or "{}"))
    except ValueError:
        d["state"] = blank_state()
    return d


def emit(state: dict, etype: str, data: dict | None = None) -> dict:
    """Structured UI event: profile.updated, picks.updated, prompt.shown,
    pack.quoted, render.updated. Always carries session revision."""
    state["revision"] = int(state.get("revision", 0)) + 1
    ev = {"id": f"ev_{state['revision']:06d}", "type": etype,
          "rev": state["revision"], "ts": datetime.now(timezone.utc).timestamp(),
          "data": data or {}}
    feed = state.setdefault("feed", [])
    feed.append(ev)
    del feed[:-50]
    return ev


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


NEG_RE = re.compile(
    r"(?:hates?|hating|dislikes?|doesn'?t like|don'?t like|not into|"
    r"isn'?t into|can'?t stand|boring|stupid)\s+([a-z][a-z \-]{2,24}?)(?=[,.\n]| and | but |$)",
    re.IGNORECASE)
SWITCH_RE = re.compile(
    r"(?:now |actually |instead )?(?:shopping for|buying for|gift for|it'?s for|"
    r"looking for something for)\s+([A-Z][a-z]{1,19})")
BY_RE = re.compile(
    r"(?:need(?: it|s)? by|arriv(?:e|es|ing)(?: before| by)?|deliver(?:ed|y)?(?: by)?|"
    r"in time for|before)\s+(.+?)(?=[,.\n]|$)", re.IGNORECASE)
SHIP_RE = re.compile(
    r"(?:ship|send|deliver)(?: it)? to ([A-Z][a-z]+(?: [A-Z][a-z]+)?)")
ANEC_RE = re.compile(r"[^.!?]*\b(always|never|obsessed|tells everyone|famous for|"
                      r"can'?t stop|collects)\b[^.!?]*[.!?]", re.IGNORECASE)


def _extract_dislikes(text: str) -> list[str]:
    return [m.group(1).strip().lower() for m in NEG_RE.finditer(text)]


def apply_turn(state: dict, text: str) -> list[str]:
    """Structured, validated update. Corrections override; returns change keys.

    Additions, removals and recipient switches are explicit — 'he hates golf'
    never lands in interests, and 'now shopping for Mum' retires Dad.
    """
    state = _normalize_state(state)
    rec = state["recipient"]
    changed = []

    # recipient switch first: new person retires old recipient-scoped facts
    m = SWITCH_RE.search(text)
    if m and m.group(1) != rec.get("name"):
        rec.update({"name": m.group(1), "interests": [], "dislikes": [],
                    "birthday": "", "mesh_id": "", "anecdotes": []})
        state.update({"photo_ids": [], "mesh_id": "", "mesh_status": ""})
        changed.append("recipient.switch")

    name = _extract_name(text)
    if name and not rec.get("name"):
        rec["name"] = name
        changed.append("recipient.name")
    occ = _extract_occasion(text)
    if occ and not state.get("occasion"):
        state["occasion"] = occ
        changed.append("occasion")
        iso = _extract_date(text)
        if iso:
            state["occasion_date"] = iso
    budget = _extract_budget(text)
    if budget and not state.get("budget_cents"):
        state["budget_cents"] = budget
        changed.append("budget")
    if re.search(r"\b(total|altogether|all in)\b", text.lower()):
        if state.get("budget_scope") != "total":
            state["budget_scope"] = "total"
            changed.append("budget.scope")

    for d in _extract_dislikes(text):
        hit = next((k for k in config.INTEREST_MOTIFS if k in d or d in k), d)
        if hit in rec.get("interests", []):
            rec["interests"].remove(hit)
        if hit not in rec.get("dislikes", []):
            rec.setdefault("dislikes", []).append(hit)
            changed.append(f"dislike.{hit}")
    for i in _extract_interests(text):
        if i in rec.get("dislikes", []):
            continue  # a stated dislike beats a passing mention
        if i not in rec.get("interests", []):
            rec.setdefault("interests", []).append(i)
            changed.append(f"interest.{i}")

    by = BY_RE.search(text)
    if by:
        iso = _extract_date(by.group(1)) or _extract_date(text)
        if not iso and "christmas" in by.group(1).lower():
            iso = f"{date.today().year}-12-25"
        if iso and state["delivery"]["deadline"] != iso:
            state["delivery"]["deadline"] = iso
            changed.append("delivery.deadline")
    sh = SHIP_RE.search(text)
    if sh and state["delivery"]["destination"] != sh.group(1):
        state["delivery"]["destination"] = sh.group(1)
        changed.append("delivery.destination")

    bday = re.search(r"(?<!\d-)(\b(0[1-9]|1[0-2])-([0-2][0-9]|3[01])\b)(?!-\d)", text)
    if bday and not rec.get("birthday"):
        rec["birthday"] = bday.group(1)
        changed.append("recipient.birthday")
    for m in ANEC_RE.finditer(text):
        s = m.group(0).strip()[:200]
        if s and s not in rec.get("anecdotes", []) and len(rec.get("anecdotes", [])) < 5:
            rec.setdefault("anecdotes", []).append(s)
            changed.append("recipient.anecdote")

    state["events"] = compute_events(state)
    state.setdefault("log", []).append({"turn": text[:500]})
    if changed:
        emit(state, "profile.updated", {"changed": changed,
                                        "recipient": {k: rec.get(k) for k in
                                                      ("name", "interests", "dislikes")}})
    return changed


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
    dl = (state.get("delivery") or {}).get("deadline", "")
    if dl:
        try:
            dt = date.fromisoformat(dl)
            if dt >= today:
                dest = (state.get("delivery") or {}).get("destination", "")
                events.append({"kind": "delivery", "who": rec.get("name") or "them",
                               "date": dt.isoformat(), "days_left": (dt - today).days,
                               "destination": dest or "unknown"})
        except ValueError:
            pass
    for e in events:
        e["urgent"] = e["days_left"] <= 14
    return sorted(events, key=lambda e: e["days_left"])


PROMPT_DEFS = [
    {"key": "who", "q": "Who are we shopping for?",
     "taps": [], "when": lambda s: not s["recipient"].get("name")},
    {"key": "occasion", "q": "What's the occasion — birthday, wedding, Christmas?",
     "taps": ["Birthday", "Wedding", "Christmas", "Just because"],
     "when": lambda s: bool(s["recipient"].get("name")) and not s.get("occasion")},
    {"key": "budget", "q": "And roughly what per gift?",
     "taps": ["Under £10", "Under £25", "Under £50"],
     "when": lambda s: bool(s.get("occasion")) and not s.get("budget_cents")},
    {"key": "deadline", "q": "When do you need it by?",
     "taps": [], "when": lambda s: bool(s.get("budget_cents"))
     and not (s.get("delivery") or {}).get("deadline")},
    {"key": "destination", "q": "Where's it going?",
     "taps": [], "when": lambda s: bool((s.get("delivery") or {}).get("deadline"))
     and not (s.get("delivery") or {}).get("destination")},
    {"key": "interests", "q": "What makes them laugh — golf? darts? dogs?",
     "taps": ["Golf", "Darts", "Dogs", "Reading"],
     "when": lambda s: len(s["recipient"].get("interests", [])) < 2},
    {"key": "photos", "q": "Send up to 10 photos and I'll sculpt them — then gift packs, no scrolling.",
     "taps": [], "when": lambda s: bool(s.get("budget_cents")) and not s.get("photo_ids")},
]

PROMPT_COOLDOWN = 90.0


def next_prompt(state: dict, now_ts: float | None = None,
                record: bool = True) -> dict | None:
    """One gentle prompt at a time. Answered prompts vanish; unanswered ones
    cool down before reappearing. Tap answers ride along where offered.
    record=False peeks without emitting (read-only snapshots)."""
    now_ts = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
    shown = state.setdefault("prompts", {})
    for p in PROMPT_DEFS:
        try:
            applies = bool(p["when"](state))
        except (KeyError, TypeError, AttributeError):
            applies = False
        if not applies or shown.get(p["key"], {}).get("answered"):
            continue
        last = shown.get(p["key"], {}).get("ts", 0)
        if now_ts - last < PROMPT_COOLDOWN:
            continue
        if record:
            shown[p["key"]] = {"ts": now_ts, "answered": False}
            emit(state, "prompt.shown", {"key": p["key"]})
        return {"key": p["key"], "q": p["q"], "taps": p["taps"]}
    return None


def answer_prompt(state: dict, key: str) -> None:
    state.setdefault("prompts", {}).setdefault(key, {})["answered"] = True


def ramble_turn(state: dict, text: str) -> tuple[dict, str]:
    """Fold one ramble message into state. Returns (state, next_prompt).

    Corrections override through apply_turn; the reply is the next gentle
    prompt (or the packs handoff when the basics are complete).
    """
    state = _normalize_state(state)
    apply_turn(state, text)
    rec = state["recipient"]
    who = rec.get("name") or "them"
    if not (rec.get("name") and state.get("occasion") and state.get("budget_cents")):
        if not rec.get("name"):
            return state, "Who are we shopping for?"
        if not state.get("occasion"):
            return state, f"What's the occasion for {who} — birthday, wedding, Christmas?"
        return state, "And roughly what per gift?"
    return state, (f"Got it — {who}, {state['occasion'].replace('_', ' ')}, "
                   f"under {state['budget_cents'] // 100}. "
                   f"Send me up to {MAX_PHOTOS} photos and I'll sculpt them, "
                   f"then show you gift packs. Nothing to scroll.")
