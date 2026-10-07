"""Person Capsule builder (research-2026-10-07): the top-level object.

A view over existing stores — subjects, photos/meshes, voice consents,
profiles, taste/order history — assembled as identity/voice/behaviour/
spatial/knowledge/provenance. Input to every template; raw capture video
stays a first-class reference, never thrown away after stills.
"""
from __future__ import annotations

import sqlite3


def build(c: sqlite3.Connection, owner: str, subject_id: str) -> dict:
    from backend import subjects as _sub
    sub = _sub.get_subject(c, owner, subject_id)
    if not sub:
        return {}
    prof = _sub.profile_for(c, owner, subject_id).get("profile", {})
    photos = [dict(r) for r in c.execute(
        "SELECT p.id,p.sha256,p.width,p.height FROM photos p"
        " JOIN photo_subjects ps ON ps.photo_id=p.id"
        " WHERE p.owner=? AND ps.subject_id=? AND ps.confirmed=1",
        (owner, subject_id))]
    meshes = [dict(r) for r in c.execute(
        "SELECT m.id,m.status FROM meshes m JOIN mesh_subjects ms ON ms.mesh_id=m.id"
        " WHERE ms.subject_id=?", (subject_id,))]
    voices = []
    try:
        voices = [dict(r) for r in c.execute(
            "SELECT id,audio_sha,created_at FROM voice_consents WHERE owner=? AND subject_id=?",
            (owner, subject_id))]
    except sqlite3.Error:
        pass
    return {
        "subject_id": subject_id,
        "identity": {"name": sub.get("name"), "kind": sub.get("kind"),
                     "face_refs": [p["id"] for p in photos[:6]]},
        "voice": {"references": [v["audio_sha"] for v in voices],
                  "enrolled": bool(voices)},
        "behaviour": {"mannerisms": prof.get("mannerisms", []),
                      "gestures": prof.get("gestures", []),
                      "expressions": prof.get("expressions", []),
                      "skills": prof.get("skills", [])},
        "spatial": {"meshes": [m["id"] for m in meshes]},
        "knowledge": {"interests": prof.get("interests", []),
                      "relationships": prof.get("relationships", []),
                      "memories": prof.get("memories", [])[:10],
                      "humour": prof.get("humour", {})},
        "provenance": prof.get("provenance", {"default": "supplied"}),
    }
