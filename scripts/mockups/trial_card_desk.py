#!/usr/bin/env python3
"""Card art -> Etsy-size listing mockup (vendored automated_mockups, MIT).

Usage:
  python3 scripts/mockups/trial_card_desk.py <card-front.png> <out.png> [--tilt -4]

Builds a warm desk scene (envelope prop), places the 5:7 art with a slight
tilt, writes 2000x2000 RGB. Upstream: scripts/mockups/ (calculator auto-detect
needs scikit-image; this path uses explicit boxes only).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mockups.generator import MockupGenerator
from mockups.calculator import BoxParameters
from PIL import Image, ImageDraw

W, H = 2000, 2000


def scene(path: Path) -> None:
    img = Image.new("RGB", (W, H), (238, 232, 222))
    d = ImageDraw.Draw(img)
    for i in range(40):
        t = i / 40
        d.rectangle([0, int(H * t), W, int(H * (t + 0.03))],
                    fill=(int(238 - 14 * t), int(232 - 14 * t), int(222 - 16 * t)))
    d.polygon([(1180, 1500), (1820, 1500), (1820, 1840), (1180, 1840)],
              fill=(250, 247, 240), outline=(200, 190, 175))
    d.line([(1180, 1500), (1500, 1700), (1820, 1500)], fill=(200, 190, 175), width=6)
    img.save(path)


def main() -> int:
    art, out = sys.argv[1], sys.argv[2]
    tilt = float(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[3] == "--tilt" else -4.0
    work = Path("/tmp/mockup_card")
    work.mkdir(exist_ok=True)
    sc = work / "desk.png"
    scene(sc)
    params = {"desk.png": BoxParameters(filename="desk.png", bbox=(260, 380, 1660, 1180),
                                        width=800, height=1400, rotation=tilt, center=(780, 960))}
    r = MockupGenerator(parameters=params).generate_mockup(art, str(sc), out)
    print("mockup:", r.success, out)
    return 0 if r.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
