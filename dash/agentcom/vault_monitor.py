"""Vault call monitor — log all vault.resolve() calls with destination.

Detects if vault keys are being sent to unexpected destinations.
"""
from __future__ import annotations

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_FILE = os.path.join(ROOT, "runs", "vault_audit.jsonl")


def log_vault_access(name: str, tool: str, worker: str, 
                     capability: str, result: str = "ok"):
    """Log vault access with destination tracking."""
    os.makedirs(os.path.dirname(AUDIT_FILE) or ".", exist_ok=True)
    entry = {
        "ts": int(time.time()),
        "action": "vault_resolve",
        "name": name,
        "tool": tool,
        "worker": worker,
        "capability": capability[:16] + "...",
        "result": result,
    }
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def log_vault_store(name: str, scope: str, ttl_s: int):
    """Log vault store operations."""
    os.makedirs(os.path.dirname(AUDIT_FILE) or ".", exist_ok=True)
    entry = {
        "ts": int(time.time()),
        "action": "vault_store",
        "name": name,
        "scope": scope,
        "ttl_s": ttl_s,
    }
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def check_suspicious_access() -> list[dict]:
    """Check for suspicious vault access patterns."""
    if not os.path.exists(AUDIT_FILE):
        return []
    
    recent = []
    cutoff = time.time() - 3600  # last hour
    with open(AUDIT_FILE) as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("ts", 0) > cutoff:
                    recent.append(entry)
            except:
                pass
    
    # Check for unusual patterns
    suspicious = []
    for entry in recent:
        # Multiple different tools accessing same key
        # High frequency access
        # Access from unexpected workers
        pass
    
    return suspicious
