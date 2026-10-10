#!/usr/bin/env python3
"""Record listing-image provenance. Run straight after rendering listing images FROM the pack's print file.
  python3 tools/register_renders.py packs/<SKU> --renderer "pipeline/bl_listing.py" [--composed 05_spec.png]
Refuses unless the print file's sha256 equals product.json manufacture.print_file.sha256.
--composed marks images built from other registered renders (spec/infographic sheets)."""
import sys, os, json, hashlib, datetime, argparse
ap = argparse.ArgumentParser(); ap.add_argument('pack'); ap.add_argument('--renderer', required=True); ap.add_argument('--composed', nargs='*', default=[])
a = ap.parse_args(); pack = os.path.abspath(a.pack)
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
P = json.load(open(f'{pack}/product.json')); pf = P['manufacture']['print_file']
pp = os.path.join(pack, pf['path']); s = sha(pp)
if s != pf['sha256']: sys.exit(f'REFUSED: print file sha {s[:12]} != product.json {str(pf["sha256"])[:12]}')
imgs = {}
for i in P['listing']['images']:
    p = f'{pack}/listing/{i["file"]}'
    if not os.path.isfile(p): sys.exit(f'REFUSED: {i["file"]} missing')
    imgs[i['file']] = dict(sha256=sha(p), source='composed' if i['file'] in a.composed else 'render-of-print-file')
json.dump(dict(print_file=pf['path'], print_sha256=s, renderer=a.renderer, registered_at=datetime.datetime.now().isoformat(timespec='seconds'), images=imgs),
          open(f'{pack}/listing/renders.json', 'w'), indent=1)
print('registered', len(imgs), 'images against', s[:12])
