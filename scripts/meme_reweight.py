#!/usr/bin/env python3
"""Weekly meme reweight — read the performance ledger, print the table,
snapshot the weights.

Every platform is a tester (X, TikTok, Instagram, YouTube cost nothing extra
to post to), so this aggregates all of them. Run weekly; the catalog
?rank=top ordering and the next render batch follow whatever is hot.

    python3 scripts/meme_reweight.py [--days 30]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import config
from backend.creative import performance as perf


def main(days: int = 30) -> None:
    scores = perf.family_scores(days)
    w = perf.weights(days)
    if not scores:
        print("No posts in ledger yet — weights stay 1.0 everywhere.")
        return
    print(f"family performance — last {days}d")
    print(f"{'family':24s} {'posts':>6s} {'engage':>10s} {'rate':>10s} {'weight':>7s}")
    for fam, d in sorted(scores.items(), key=lambda kv: -kv[1]["rate"]):
        print(f"{fam:24s} {d['posts']:6d} {d['engagement']:10.0f} "
              f"{d['rate']:10.1f} {w.get(fam, 1.0):7.2f}")
    snap = config.DATA / perf.WEIGHTS_NAME
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text(json.dumps({"days": days, "weights": w,
                                "families": scores}, indent=2))
    print(f"snapshot → {snap}")


if __name__ == "__main__":
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 30
    main(days)
