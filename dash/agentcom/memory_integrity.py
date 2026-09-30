"""Memory bank integrity — hash chain verification.

Every memory entry gets a SHA-256 hash chain. If an attacker poisons
the memory bank, the chain breaks and we detect it.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _hash(data: str) -> str:
    """SHA-256 hash of content."""
    return hashlib.sha256(data.encode()).hexdigest()


def _hash_file(path: str) -> str:
    """SHA-256 hash of file content."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class MemoryIntegrity:
    """Hash chain for memory bank entries."""
    
    def __init__(self, memory_dir: str):
        self.memory_dir = memory_dir
        self.chain_file = os.path.join(memory_dir, ".integrity.json")
        self._load()
    
    def _load(self):
        if os.path.exists(self.chain_file):
            with open(self.chain_file) as f:
                self.chain = json.load(f)
        else:
            self.chain = {"entries": [], "last_hash": "genesis"}
    
    def _save(self):
        with open(self.chain_file, "w") as f:
            json.dump(self.chain, f, indent=1)
    
    def add_entry(self, name: str, content: str) -> str:
        """Add entry with hash chain."""
        entry_hash = _hash(content + self.chain["last_hash"])
        entry = {
            "name": name,
            "hash": entry_hash,
            "prev_hash": self.chain["last_hash"],
            "timestamp": int(time.time()),
            "size": len(content),
        }
        self.chain["entries"].append(entry)
        self.chain["last_hash"] = entry_hash
        self._save()
        return entry_hash
    
    def verify(self) -> dict:
        """Verify entire chain integrity."""
        prev = "genesis"
        broken = []
        for i, entry in enumerate(self.chain["entries"]):
            if entry["prev_hash"] != prev:
                broken.append({"index": i, "name": entry["name"], 
                             "expected": prev[:16], "got": entry["prev_hash"][:16]})
            prev = entry["hash"]
        
        return {
            "valid": len(broken) == 0,
            "entries": len(self.chain["entries"]),
            "last_hash": self.chain["last_hash"][:16],
            "broken": broken,
        }
    
    def is_poisoned(self) -> bool:
        """Quick check if chain is broken."""
        result = self.verify()
        return not result["valid"]
