"""PR content sanitizer — strip instructions from external PRs.

Prevents prompt injection via malicious PR content.
"""
from __future__ import annotations

import re
import time


# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    r"(?i)ignore\s+(previous|all|above)\s+(instructions?|prompts?|rules?)",
    r"(?i)you\s+are\s+now\s+(a|an)\s+",
    r"(?i)system\s*:\s*",
    r"(?i)assistant\s*:\s*",
    r"(?i)new\s+instructions?:",
    r"(?i)override\s+(previous|all|system)",
    r"(?i)disregard\s+(previous|all|above)",
    r"(?i)forget\s+(everything|all|previous)",
    r"(?i)act\s+as\s+if",
    r"(?i)pretend\s+(you|to)\s+are",
    r"(?i)roleplay\s+as",
    r"(?i)do\s+not\s+(follow|obey|listen)",
    r"(?i)execute\s+(this|the\s+following)",
    r"(?i)run\s+(this|the\s+following)\s+(code|command|script)",
    r"(?i)curl\s+.*\|.*sh",
    r"(?i)wget\s+.*\|.*sh",
    r"(?i)eval\s*\(",
    r"(?i)exec\s*\(",
]


def sanitize_pr_content(content: str) -> dict:
    """Check PR content for prompt injection attempts."""
    injections = []
    
    for pattern in INJECTION_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            injections.append({
                "pattern": pattern,
                "matches": len(matches),
                "sample": matches[0][:50] if matches else "",
            })
    
    return {
        "safe": len(injections) == 0,
        "injections": injections,
        "content_length": len(content),
        "checked_at": int(time.time()),
    }


def is_trusted_source(source: str, trusted_sources: list[str] = None) -> bool:
    """Check if PR source is trusted."""
    if trusted_sources is None:
        trusted_sources = []  # Empty = trust no one
    
    return source in trusted_sources
