"""Package install monitor — log all pip/npm installs.

Detects supply chain attacks via malicious packages.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_FILE = os.path.join(ROOT, "runs", "package_audit.jsonl")


def log_package_install(package: str, manager: str, version: str = "",
                       source: str = "unknown"):
    """Log a package installation."""
    os.makedirs(os.path.dirname(AUDIT_FILE) or ".", exist_ok=True)
    entry = {
        "ts": int(time.time()),
        "action": "package_install",
        "package": package,
        "manager": manager,
        "version": version,
        "source": source,
    }
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def scan_pip_packages() -> list[dict]:
    """Scan installed pip packages for suspicious patterns."""
    try:
        result = subprocess.run(
            ["pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=10
        )
        packages = json.loads(result.stdout)
        
        suspicious = []
        for pkg in packages:
            name = pkg.get("name", "")
            version = pkg.get("version", "")
            
            # Check for suspicious patterns
            if any(x in name.lower() for x in ["test", "debug", "dev"]):
                suspicious.append({"name": name, "version": version, 
                                 "reason": "dev/test package in production"})
        
        return suspicious
    except:
        return []


def scan_npm_packages() -> list[dict]:
    """Scan installed npm packages for suspicious lifecycle hooks."""
    try:
        result = subprocess.run(
            ["npm", "ls", "--json", "--depth=0"],
            capture_output=True, text=True, timeout=10, cwd=ROOT
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            packages = data.get("dependencies", {})
            
            suspicious = []
            for name, info in packages.items():
                version = info.get("version", "")
                # Check for packages with lifecycle hooks
                pkg_path = os.path.join(ROOT, "node_modules", name, "package.json")
                if os.path.exists(pkg_path):
                    with open(pkg_path) as f:
                        pkg_json = json.load(f)
                    scripts = pkg_json.get("scripts", {})
                    hooks = ["preinstall", "postinstall", "install"]
                    for hook in hooks:
                        if hook in scripts:
                            suspicious.append({"name": name, "version": version,
                                             "hook": hook, "script": scripts[hook][:100]})
            
            return suspicious
    except:
        return []
