"""Five rigid visual grammars — validators, no coordinates.

The AI produces semantic fields (headline, subject, panel dialogue). The
deterministic renderer owns all geometry. Occasion is a parameter, never
a template; styles are rendering choices, never templates.
"""
from __future__ import annotations

TEMPLATE_IDS = ("comic_4panel", "hero_scene", "interview_scene",
                "news_scene", "meme_2beat")

OCCASIONS = ("birthday", "christmas", "halloween", "fathers_day",
             "mothers_day", "valentines", "anniversary", "graduation",
             "retirement", "new_baby", "general")

BEATS = ("setup", "development", "turn", "payoff")
WORLDS = ("sport", "cinematic", "stage", "fantasy", "workplace",
          "holiday", "domestic_epic")
COMPOSITIONS = ("full_body", "three_quarter", "waist_up")
INTERVIEW_FORMATS = ("sports_sideline", "press_conference",
                     "late_night_couch", "red_carpet",
                     "documentary_confessional")
NEWS_FORMATS = ("breaking_news", "field_report", "special_investigation",
                "press_briefing")
MEME_GRAMMARS = ("expectation_reality", "before_after", "setup_reaction",
                 "confident_failure", "calm_chaos", "reveal")
EXPRESSIONS = ("neutral", "pleased", "confused", "concerned", "smug",
               "shocked", "exhausted", "celebrating")
STYLES = ("editorial_ink", "doomer_ink", "clean_comic", "retro_comic")


def _str(v, limit: int) -> bool:
    return isinstance(v, str) and len(v) <= limit


def _enum(v, allowed: tuple) -> bool:
    return v in allowed


def validate_comic_4panel(c: dict) -> list[str]:
    gaps = []
    if c.get("type") != "comic_4panel":
        return ["type must be comic_4panel"]
    if not isinstance(c.get("premise_id"), str) or not c["premise_id"]:
        gaps.append("premise_id required")
    if c.get("style_id") not in STYLES:
        gaps.append(f"style_id must be one of {STYLES}")
    panels = c.get("panels")
    if not isinstance(panels, list) or len(panels) != 4:
        return gaps + ["exactly 4 panels required"]
    for i, p in enumerate(panels):
        if not isinstance(p, dict):
            gaps.append(f"panel {i} must be an object")
            continue
        if p.get("beat") not in BEATS:
            gaps.append(f"panel {i} beat must be one of {BEATS}")
        if not _str(p.get("scene", ""), 240) or not p.get("scene"):
            gaps.append(f"panel {i} scene required (<=240)")
        dlg = p.get("dialogue")
        if not isinstance(dlg, list) or not dlg or len(dlg) > 2:
            gaps.append(f"panel {i} dialogue: 1-2 bubbles")
            continue
        for b in dlg:
            if not isinstance(b, dict) or not _str(b.get("speaker", ""), 32) \
                    or not b.get("speaker"):
                gaps.append(f"panel {i} bubble needs speaker (<=32)")
            if not _str(b.get("text", ""), 90) or not b.get("text"):
                gaps.append(f"panel {i} bubble needs text (<=90)")
    if c.get("bottom_caption") is not None:
        gaps.append("bottom_caption must be null (no explanatory caption)")
    return gaps


def validate_hero_scene(c: dict) -> list[str]:
    gaps = []
    if c.get("type") != "hero_scene":
        return ["type must be hero_scene"]
    if c.get("world") not in WORLDS:
        gaps.append(f"world must be one of {WORLDS}")
    if not _str(c.get("role", ""), 80) or not c.get("role"):
        gaps.append("role required (<=80)")
    if c.get("composition") not in COMPOSITIONS:
        gaps.append(f"composition must be one of {COMPOSITIONS}")
    if not _str(c.get("headline", ""), 54) or not c.get("headline"):
        gaps.append("headline required (<=54)")
    if c.get("subheadline") is not None and not _str(c["subheadline"], 100):
        gaps.append("subheadline <=100")
    props = c.get("props", [])
    if not isinstance(props, list) or len(props) > 4 or \
            any(not _str(p, 32) for p in props):
        gaps.append("props: max 4, <=32 chars each")
    if c.get("environment_notes") is not None and not _str(c["environment_notes"], 220):
        gaps.append("environment_notes <=220")
    return gaps


def validate_interview_scene(c: dict) -> list[str]:
    gaps = []
    if c.get("type") != "interview_scene":
        return ["type must be interview_scene"]
    if c.get("format") not in INTERVIEW_FORMATS:
        gaps.append(f"format must be one of {INTERVIEW_FORMATS}")
    if not _str(c.get("headline", ""), 50) or not c.get("headline"):
        gaps.append("headline required (<=50)")
    lt = c.get("lower_third")
    if not isinstance(lt, dict) or not _str(lt.get("name", ""), 28) \
            or not lt.get("name"):
        gaps.append("lower_third.name required (<=28)")
    if not isinstance(lt, dict) or not _str(lt.get("descriptor", ""), 55) \
            or not lt.get("descriptor"):
        gaps.append("lower_third.descriptor required (<=55)")
    if not _str(c.get("question", ""), 110) or not c.get("question"):
        gaps.append("question required (<=110)")
    if not _str(c.get("answer", ""), 150) or not c.get("answer"):
        gaps.append("answer required (<=150)")
    if c.get("visual_action") is not None and not _str(c["visual_action"], 160):
        gaps.append("visual_action <=160")
    return gaps


def validate_news_scene(c: dict) -> list[str]:
    gaps = []
    if c.get("type") != "news_scene":
        return ["type must be news_scene"]
    if c.get("news_format") not in NEWS_FORMATS:
        gaps.append(f"news_format must be one of {NEWS_FORMATS}")
    if not _str(c.get("headline", ""), 64) or not c.get("headline"):
        gaps.append("headline required (<=64)")
    if not _str(c.get("scene", ""), 220) or not c.get("scene"):
        gaps.append("scene required (<=220)")
    for k, lim in (("subheadline", 120), ("location_label", 30),
                   ("quote", 120), ("quote_attribution", 36)):
        if c.get(k) is not None and not _str(c[k], lim):
            gaps.append(f"{k} <={lim}")
    return gaps


def _meme_beat(b: dict, i: int) -> list[str]:
    gaps = []
    if not isinstance(b, dict):
        return [f"beat {i} must be an object"]
    if not _str(b.get("scene", ""), 200) or not b.get("scene"):
        gaps.append(f"beat {i} scene required (<=200)")
    if not _str(b.get("text", ""), 90) or not b.get("text"):
        gaps.append(f"beat {i} text required (<=90)")
    if b.get("subject_expression") is not None and \
            b["subject_expression"] not in EXPRESSIONS:
        gaps.append(f"beat {i} subject_expression must be one of {EXPRESSIONS}")
    return gaps


def validate_meme_2beat(c: dict) -> list[str]:
    gaps = []
    if c.get("type") != "meme_2beat":
        return ["type must be meme_2beat"]
    if c.get("grammar") not in MEME_GRAMMARS:
        gaps.append(f"grammar must be one of {MEME_GRAMMARS}")
    gaps += _meme_beat(c.get("beat_1") or {}, 1)
    gaps += _meme_beat(c.get("beat_2") or {}, 2)
    return gaps


VALIDATORS = {
    "comic_4panel": validate_comic_4panel,
    "hero_scene": validate_hero_scene,
    "interview_scene": validate_interview_scene,
    "news_scene": validate_news_scene,
    "meme_2beat": validate_meme_2beat,
}


def validate_creative(template_id: str, creative: dict,
                      allowed_compositions: list[str] | None = None) -> list[str]:
    """Validate one grammar payload. Composition gating: full_body is
    refused unless the resolver allowed it (no invented bodies)."""
    if template_id not in VALIDATORS:
        return [f"unknown template {template_id}"]
    gaps = VALIDATORS[template_id](creative or {})
    if template_id == "hero_scene" and allowed_compositions is not None:
        if (creative or {}).get("composition") not in allowed_compositions:
            gaps.append(f"composition not allowed (resolver allows {allowed_compositions})")
    return gaps


def validate_job(job: dict) -> list[str]:
    """Top-level card job: occasion + subjects + creative + inside."""
    gaps = []
    if job.get("schema_version") != "1.0":
        gaps.append("schema_version must be 1.0")
    if job.get("template_id") not in TEMPLATE_IDS:
        gaps.append(f"template_id must be one of {TEMPLATE_IDS}")
    occ = job.get("occasion") or {}
    if occ.get("type") not in OCCASIONS:
        gaps.append(f"occasion.type must be one of {OCCASIONS}")
    subs = job.get("subjects")
    if not isinstance(subs, list) or not 1 <= len(subs) <= 3:
        gaps.append("1-3 subjects required")
    else:
        for s in subs:
            if not isinstance(s, dict) or not s.get("subject_id") \
                    or not s.get("face_asset_id"):
                gaps.append("each subject needs subject_id + face_asset_id")
            if s.get("identity_strength", "locked") != "locked":
                gaps.append("identity_strength must be locked")
    inside = job.get("inside") or {}
    if not isinstance(inside.get("right_message"), str) \
            or len(inside.get("right_message", "")) > 400:
        gaps.append("inside.right_message required (<=400)")
    if not isinstance(inside.get("signature"), str) \
            or len(inside.get("signature", "")) > 80:
        gaps.append("inside.signature required (<=80)")
    gaps += validate_creative(job.get("template_id", ""),
                              job.get("creative") or {})
    return gaps
