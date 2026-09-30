"""CLI: python3 -m premesh INPUT [-o OUT] [--recipe meshy] [--json]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import normalize
from .recipes import RECIPES


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="premesh",
        description="Normalise an image for the next stage (Meshy, cards, thumbs).",
    )
    ap.add_argument("input", help="image file, or an http(s) URL")
    ap.add_argument("-o", "--out", default=".", help="output directory (default: .)")
    ap.add_argument("-r", "--recipe", default="meshy", choices=sorted(RECIPES))
    ap.add_argument("--zone", default=None, help="zone base URL (default: PUBLIC_BASE)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--no-save", action="store_true", help="report only, write nothing")
    args = ap.parse_args(argv)

    try:
        out = normalize(args.input, args.recipe, zone=args.zone)
    except Exception as e:                                    # noqa: BLE001
        if args.json:
            print(json.dumps({"ok": False, "error": str(e)}))
        else:
            print(f"error: {e}", file=sys.stderr)
        return 2

    ext = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(out.report.fmt, ".bin")
    if not args.no_save:
        dest_dir = Path(args.out)
        dest_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(args.input).stem if not args.input.startswith("http") else "remote"
        dest = dest_dir / f"{stem}.{args.recipe}{ext}"
        dest.write_bytes(out.data)

    if args.json:
        print(json.dumps(out.as_dict(), indent=2))
    else:
        r = out.report
        print(f"{'OK  ' if r.ok else 'FAIL'} {out.recipe}: "
              f"{r.width}x{r.height} {r.mode} alpha={r.has_alpha} "
              f"coverage={r.coverage:.1%}")
        print(f"     url {out.url}")
        for issue in r.issues:
            print(f"     ! {issue}")
        if not args.no_save:
            print(f"     -> {dest}")
    return 0 if out.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
