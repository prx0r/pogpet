"""Build figg. asset-kit.zip from the ready-made creative studio assets.

Python 3 standard library only. Run from any working directory.
"""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'downloads/figg-asset-kit.zip'
GROUPS=['mascots','logos','patterns','templates','reference/full']
files=[ROOT/'assets/mascot-manifest.json',ROOT/'assets/design-tokens.json',ROOT/'assets/design-tokens.css',ROOT/'assets/previews/32-mascot-asset-sheet.png']
for group in GROUPS:
    files.extend(p for p in (ROOT/'assets'/group).rglob('*') if p.is_file())
OUT.parent.mkdir(exist_ok=True,parents=True)
with ZipFile(OUT,'w',ZIP_DEFLATED,compresslevel=7) as z:
    for p in sorted(set(files)):
        z.write(p,Path('figg-asset-kit')/p.relative_to(ROOT/'assets'))
    z.writestr('figg-asset-kit/START-HERE.txt', '''figg. / reusable identity & assets\n\nSVG characters: mascots/svg/\nTransparent 1024px PNGs: mascots/png/\nPrimary & print-safe outlined wordmark: logos/\nEditable social/Etsy/packaging templates: templates/\nBrand colors in JSON and CSS; 32 variant manifest in JSON.\nContact sheet: previews/32-mascot-asset-sheet.png\nCreative moodboards: reference/full/\n\nConcept images are not evidence of actual printed goods. Etsy hero image: use a photograph of a real finished sample.\nNo font files are bundled. Name/domain/trademark availability is not established.\n''')
print(f'Wrote {OUT.name}: {len(files)} assets, {OUT.stat().st_size:,} bytes')
