#!/usr/bin/env python3
"""Read-only deployment check: API contract and the exact installed UI assets.

Run on the deployment host after restarting Flask AND the bridge.
No uploads, anonymous-session creation, renders, payments or provider calls.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def check(base, token):
    failures = []

    def fetch(path, gated=False):
        url = base.rstrip('/') + path
        if gated:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode({'token': token})
        request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache',
            'User-Agent': 'Mozilla/5.0 (oddhobb-deploy-check)'})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, response.read(), response.headers.get('Content-Type', '')
        except urllib.error.HTTPError as error:
            return error.code, error.read(), error.headers.get('Content-Type', '')
        except Exception:
            return 0, b'', ''

    code, body, ctype = fetch('/backend/api/studio/status', True)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        data = {}
    if code != 200 or not isinstance(data, dict) or data.get('contract') != 'oddhobb.studio.v2':
        failures.append(f'Studio backend not ready (HTTP {code}, {ctype or "no response"}). Install backend/studio_library.py and its server registration; restart the Flask backend separately from the bridge. HTTP 401 means the bridge token is missing or invalid.')

    for path in ['site/js/api-client.js', 'site/js/cards-studio.js', 'site/js/studio-people.js',
                 'site/js/site-router.js', 'site/js/site-shell.js', 'site/css/site-shell.css']:
        code, body, _ = fetch('/' + path.removeprefix('site/') + '?v=studio-2')
        local = ROOT / path
        if code != 200 or not local.is_file() or hashlib.sha256(body).digest() != hashlib.sha256(local.read_bytes()).digest():
            failures.append(f'{path} is missing, stale or from another release. Install all files together and purge the stale CDN asset.')
    code, body, _ = fetch('/studio')
    if code != 200 or b'/js/api-client.js?v=studio-2' not in body or b'/js/cards-studio.js?v=studio-2' not in body:
        failures.append('Studio HTML is missing or stale. Restart the updated bridge and verify /studio serves the updated index.html.')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:' + os.environ.get('BRIDGE_PORT', '8797'))
    args = parser.parse_args()
    if urllib.parse.urlsplit(args.url).query:
        parser.error('Pass the origin without a query; set BRIDGE_TOKEN in the environment.')
    token = os.environ.get('BRIDGE_TOKEN', '')
    if not token and (ROOT / '.token').is_file():
        token = (ROOT / '.token').read_text().strip()
    failures = check(args.url, token)
    for message in failures:
        print('FAIL:', message)
    if not failures:
        print('PASS: Studio backend contract and all six frontend assets match this checkout.')
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
