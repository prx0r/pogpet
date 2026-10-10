"""Friend-sent Pog messages: permissioned performances.

A Pog appearing in YOUR room with THEIR message needs consent in
both directions. Schema only (no transport yet):
- sender grants: which Pog, what it may say/do, expiry
- recipient grants: who may send, quiet hours, auto-play vs approve
- Pog carries: sender identity proof, content hash, render manifest
- revocation is instant both sides; expired grants never execute.
"""
from __future__ import annotations


PERMISSION_SCOPES = ("send_pog", "auto_play", "use_voice", "use_likeness")


def make_grant(granter: str, grantee: str, scopes: list[str],
               expires_s: int = 86400) -> dict:
    bad = [s for s in scopes if s not in PERMISSION_SCOPES]
    if bad:
        raise ValueError(f"unknown scopes {bad}")
    if expires_s <= 0 or expires_s > 30 * 86400:
        raise ValueError("expiry must be 1s..30d")
    return {"type": "pog_grant/v1", "granter": granter, "grantee": grantee,
            "scopes": sorted(set(scopes)), "expires_s": expires_s,
            "revoked": False}


def make_message(sender: str, recipient: str, pog_id: str, text: str,
                 grant: dict, recipient_approval: str = "approve") -> dict:
    """recipient_approval: approve (hold for tap) or auto_play (if granted)."""
    if grant.get("revoked"):
        raise ValueError("grant revoked")
    if grant.get("granter") != recipient or grant.get("grantee") != sender:
        raise ValueError("no matching grant")
    if "send_pog" not in grant.get("scopes", []):
        raise ValueError("send_pog not granted")
    if recipient_approval == "auto_play" and "auto_play" not in grant.get("scopes", []):
        raise ValueError("auto_play not granted; holding for approval")
    if len(text) > 500:
        raise ValueError("message too long")
    return {"type": "pog_message/v1", "sender": sender,
            "recipient": recipient, "pog_id": pog_id, "text": text,
            "mode": recipient_approval}
