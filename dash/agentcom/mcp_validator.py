"""MCP server validator — verify tool schemas before execution.

Prevents malicious MCP servers from injecting poisoned tool definitions.
"""
from __future__ import annotations

import json
import os
import re
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_FILE = os.path.join(ROOT, "runs", "mcp_audit.jsonl")


def validate_mcp_tool(tool_name: str, tool_schema: dict) -> dict:
    """Validate an MCP tool schema for suspicious patterns."""
    issues = []
    
    # Check 1: Tool name is reasonable
    if len(tool_name) > 100:
        issues.append("oversized_name")
    if not re.match(r'^[a-zA-Z0-9_-]+$', tool_name):
        issues.append("invalid_name_chars")
    
    # Check 2: Description is reasonable
    desc = tool_schema.get("description", "")
    if len(desc) > 1000:
        issues.append("oversized_description")
    
    # Check 3: Parameters schema is valid
    params = tool_schema.get("parameters", {})
    if not isinstance(params, dict):
        issues.append("invalid_parameters_schema")
    
    # Check 4: No suspicious patterns in description
    suspicious = ["exec", "eval", "system", "shell", "rm -rf", "curl.*sh"]
    for pattern in suspicious:
        if re.search(pattern, desc, re.I):
            issues.append(f"suspicious_description:{pattern}")
    
    # Check 5: Tool name doesn't shadow built-in tools
    builtins = {"read", "write", "edit", "bash", "find", "grep", "ls"}
    if tool_name in builtins:
        issues.append(f"shadows_builtin:{tool_name}")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "tool": tool_name,
        "timestamp": int(time.time()),
    }


def log_mcp_event(event_type: str, tool: str, details: dict = None):
    """Log MCP events for audit trail."""
    os.makedirs(os.path.dirname(AUDIT_FILE) or ".", exist_ok=True)
    entry = {
        "ts": int(time.time()),
        "event": event_type,
        "tool": tool,
        "details": details or {},
    }
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
