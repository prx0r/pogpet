"""Sub-agent finding validator — verify before main agent processes.

Validates that sub-agent findings are trustworthy before the main agent
makes decisions based on them.
"""
from __future__ import annotations

import json
import os
import re
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def validate_finding(finding: dict, source: str = "sub-agent") -> dict:
    """Validate a sub-agent finding for trustworthiness."""
    issues = []
    
    # Check 1: Finding has required fields
    required = ["tool", "data"]
    for field in required:
        if field not in finding:
            issues.append(f"missing_field:{field}")
    
    # Check 2: Data is not empty
    data = finding.get("data", {})
    if not data:
        issues.append("empty_data")
    
    # Check 3: Tool name is valid
    valid_tools = {"whale_feed", "eth_check", "sol_check", "wallet_github",
                   "clone_scan", "env_scan", "git_history", "classify",
                   "drain_classify", "probe", "try-creds", "read-file", 
                   "sqli", "submit"}
    tool = finding.get("tool", "")
    if tool and tool not in valid_tools:
        issues.append(f"unknown_tool:{tool}")
    
    # Check 4: No suspicious patterns in data
    data_str = json.dumps(data)
    suspicious_patterns = [
        r"rm\s+-rf",  # destructive commands
        r"curl.*\|.*sh",  # pipe to shell
        r"wget.*\|.*sh",  # pipe to shell
        r"eval\(",  # eval execution
        r"exec\(",  # exec execution
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, data_str):
            issues.append(f"suspicious_pattern:{pattern}")
    
    # Check 5: Finding size is reasonable
    if len(data_str) > 100000:
        issues.append("oversized_finding")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "source": source,
        "timestamp": int(time.time()),
    }


def validate_findings(findings: list[dict], source: str = "sub-agent") -> dict:
    """Validate multiple findings."""
    results = [validate_finding(f, source) for f in findings]
    valid_count = sum(1 for r in results if r["valid"])
    
    return {
        "total": len(results),
        "valid": valid_count,
        "invalid": len(results) - valid_count,
        "results": results,
    }
