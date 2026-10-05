#!/usr/bin/env python3
"""figgsite LLM bridge — speaks the site's Cloudflare-Workers contract, backs it with pi.

The site (site/index.html) does:

    POST <base>/api/ai/cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast
        body  { messages:[{role,content}...], max_tokens, temperature }
        resp  { success:true, result:{ response:"..." } }

    POST <base>/api/ai/cf/@cf/openai/whisper   (multipart: file, model)
        resp  { success:true, result:{ text:"..." } }

We keep that exact shape so index.html needs only its host swapped to
`/api/ai/cf/...` (relative) — no other edit. The model name in the path is
ignored; everything routes to pi.

pi is invoked in print mode with tools and sessions disabled:
    node pi/packages/coding-agent/dist/bundle/cli.js \
         --print --no-tools --no-session --provider ... --model ... "prompt"

Stdlib only. Token-gated when BRIDGE_TOKEN is set.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent

# Load .env into THIS process (not just the pi subprocess) so _proxy can mint
# backend tokens itself — the browser should only ever hold BRIDGE_TOKEN.
_env_file = ROOT / ".env"
if _env_file.exists():
    for _ln in _env_file.read_text().splitlines():
        _ln = _ln.strip()
        if _ln and not _ln.startswith("#") and "=" in _ln:
            _k, _, _v = _ln.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())
PI_CLI = ROOT / "pi" / "packages" / "coding-agent" / "dist" / "bundle" / "cli.js"

PORT = int(os.environ.get("BRIDGE_PORT", "8797"))
TOKEN = os.environ.get("BRIDGE_TOKEN", "")
PROVIDER = os.environ.get("PI_PROVIDER", "opencode-go")
MODEL = os.environ.get("PI_MODEL", "mimo-v2.5")
TIMEOUT = int(os.environ.get("PI_TIMEOUT", "60"))


def _prompt_from_messages(messages: list) -> str:
    """Flatten chat history into one pi prompt. pi takes a single string arg."""
    sys_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
    turns = [m for m in messages if m.get("role") in ("user", "assistant")]
    lines = []
    if sys_parts:
        lines.append("INSTRUCTIONS:\n" + "\n".join(sys_parts))
    for m in turns:
        who = "Person" if m.get("role") == "user" else "You"
        lines.append(f"{who}: {m.get('content', '')}")
    lines.append("You:")
    return "\n\n".join(lines)


def verified_actor(owner: str, owner_sig: str = "", api_key: str = "") -> dict:
    """Forward only a backend-verified browser identity to the isolated Pi call."""
    from urllib.parse import urlencode
    owner=(owner or "anon").strip()[:80]
    query=urlencode({"owner":owner,"token":os.environ.get("API_TOKEN","")})
    target=f"http://127.0.0.1:{os.environ.get('BACKEND_PORT',8798)}/api/cards/templates?{query}"
    headers={}
    if owner_sig:headers["X-Owner-Sig"]=owner_sig
    if api_key:headers["X-API-Key"]=api_key
    try:
        with urllib.request.urlopen(urllib.request.Request(target,headers=headers),timeout=15) as r:
            result=json.loads(r.read())
        if not result.get("ok"):raise PermissionError("Your session could not be verified. Reload and try again.")
    except urllib.error.HTTPError:
        raise PermissionError("Your session could not be verified. Reload and try again.") from None
    return {"FIGG_OWNER":owner,"FIGG_OWNER_SIG":owner_sig,"FIGG_API_KEY":api_key}


def run_pi(messages: list, max_tokens: int, temperature: float, actor_env: dict | None = None) -> str:
    if not PI_CLI.exists():
        raise RuntimeError(f"pi CLI not built at {PI_CLI} (run `npm run build` in pi/)")

    env = dict(os.environ)
    # Pull provider keys from .env without printing them.
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip())

    if actor_env is not None:
        env.update(actor_env)

    api_key = env.get("OPENCODE_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENCODE_API_KEY missing — set it in .env")

    prompt = _prompt_from_messages(messages)
    # --api-key is mandatory: ~/.pi/agent/models.json carries a stale
    # opencode-go apiKey that otherwise wins over the env var (402).
    #
    # -e is mandatory too: project-local extension discovery (cwd/.pi/extensions)
    # does not pick anything up in this pi build — even a trivial probe file is
    # ignored — while explicit --extension paths load fine.
    #
    # --no-builtin-tools (not --no-tools) so bash/edit/write stay off but our
    # five figg_* tools remain: a site visitor gets the pipeline and nothing else.
    cmd = [
        "node", str(PI_CLI),
        "--print",
        "-e", str(ROOT / "pi" / ".pi" / "extensions" / "figgsite.ts"),
        "--no-builtin-tools",
        "--no-session",     # ephemeral, no disk state per visitor
        "--provider", PROVIDER,
        "--api-key", api_key,
        "--model", MODEL,
        "--thinking", "off",
        "--", prompt,
    ]
    env.setdefault("FIGG_API_BASE", f"http://127.0.0.1:{os.environ.get('BACKEND_PORT', 8798)}")
    env.setdefault("FIGG_UPLOAD_DIR", str(ROOT / "data" / "uploads"))
    # The backend mints its own gate token; the extension needs it too.
    env.setdefault("FIGG_API_TOKEN", env.get("API_TOKEN", ""))

    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=TIMEOUT,
        cwd=str(ROOT / "pi"), env=env,
    )
    out = (proc.stdout or "").strip()
    if proc.returncode != 0 or not out:
        err = (proc.stderr or "").strip().splitlines()
        raise RuntimeError(err[-1] if err else f"pi exited {proc.returncode}")
    return out


# Three static roots, one origin. /studio/* serves the figg. brand studio
# (the asset pack); /premesh/* serves staged uploads for Cloudflare image
# transformations (content-addressed, pruned); /img/* serves PUBLIC product
# renders for feeds and shopping agents (marketing assets only — user photos
# never land here); everything else is the site.
ROUTES = (
    ("/studio/", ROOT / "figg-studio"),
    ("/premesh/", ROOT / "data" / "premesh" / "public"),
    ("/img/", ROOT / "data" / "productimg"),
    ("/", ROOT / "site"),
)


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _sec_headers(self) -> None:
        # Minimal hardening — no CSP yet (inline token inject + SPA scripts).
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")

    def _gated(self):
        if not TOKEN:
            return True
        q = parse_qs(urlparse(self.path).query)
        if q.get("token", [""])[0] == TOKEN:
            return True
        auth = self.headers.get("Authorization", "")
        if auth.removeprefix("Bearer ") == TOKEN:
            return True
        self._json({"success": False, "error": "bad token"}, 401)
        return False

    def _mcp_proxy(self, method: str) -> None:
        """POST/GET /mcp -> the local MCP server (:8799), streaming.

        MCP streamable HTTP needs headers BOTH ways (mcp-session-id) and a
        text/event-stream that never sets Content-Length — so this proxies
        line-by-line instead of buffering. Gated by _gated() first: without
        a token the local MCP (which carries the service token inside) must
        never be reachable.
        """
        import urllib.error
        raw = urlparse(self.path)
        target = f"http://127.0.0.1:{os.environ.get('MCP_PORT', '8799')}{raw.path}"
        if raw.query:
            target += "?" + raw.query
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if (n > 0 and method == "POST") else None
        fwd = {}
        for k, v in self.headers.items():
            if k.lower() in ("host", "content-length", "connection",
                             "accept-encoding", "transfer-encoding"):
                continue
            fwd[k] = v
        req = urllib.request.Request(target, data=body, headers=fwd, method=method)
        try:
            r = urllib.request.urlopen(req, timeout=600)
        except urllib.error.HTTPError as e:
            r = e
        except Exception as e:                                  # noqa: BLE001
            self._json({"success": False, "error": f"mcp unreachable: {e}"}, 502)
            return
        self.send_response(r.status)
        for hk in ("Content-Type", "Cache-Control", "mcp-session-id",
                   "Mcp-Session-Id"):
            hv = r.headers.get(hk)
            if hv:
                self.send_header(hk, hv)
        cl = r.headers.get("Content-Length")
        if cl:
            self.send_header("Content-Length", cl)
        self.end_headers()
        try:
            if cl:
                self.wfile.write(r.read(int(cl)))
            else:
                # SSE / chunk-less: stream lines as they arrive
                while True:
                    line = r.readline()
                    if not line:
                        break
                    self.wfile.write(line)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _proxy(self, method: str, path: str | None = None) -> None:
        """/backend/* → the Flask API on 8798, so one tunnel exposes it all.

        Two things happen here so exactly one secret is ever public:
          1. the request is gated on BRIDGE_TOKEN (done by the caller), and
          2. any incoming token is stripped and replaced with API_TOKEN, which
             never leaves this process. The frontend only ever holds one token.
        """
        import urllib.error
        raw = urlparse(self.path)
        sub = raw.path[len("/backend"):] if path is None else path
        target = f"http://127.0.0.1:{os.environ.get('BACKEND_PORT', 8798)}{sub}"

        from urllib.parse import parse_qsl, urlencode
        pairs = [(k, v) for k, v in parse_qsl(raw.query, keep_blank_values=True)
                 if k != "token"]
        api_tok = os.environ.get("API_TOKEN", "")
        if api_tok:
            pairs.append(("token", api_tok))
        if pairs:
            target += "?" + urlencode(pairs)

        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n > 0 and method == "POST" else None
        headers = {}
        for h in ("Content-Type", "X-API-Token", "X-Owner-Sig", "X-API-Key"):
            if self.headers.get(h):
                headers[h] = self.headers[h]
        if body is not None and "Content-Type" not in headers:
            headers["Content-Type"] = "application/octet-stream"

        req = urllib.request.Request(target, data=body, headers=headers, method=method)
        # Upstream X-* headers ride along (X-Premesh-Ok and friends) — the
        # rest of the response is rebuilt below so nothing leaks through.
        extra: list[tuple[str, str]] = []
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                payload = r.read()
                status = r.status
                ctype = r.headers.get("Content-Type", "application/octet-stream")
                extra = [(k, v) for k, v in r.headers.items()
                         if k.lower().startswith("x-")]
        except urllib.error.HTTPError as e:
            payload = e.read()
            status = e.code
            ctype = e.headers.get("Content-Type", "application/json")
            extra = [(k, v) for k, v in e.headers.items()
                     if k.lower().startswith("x-")]
        except Exception as e:
            self._json({"success": False, "error": f"backend unreachable: {e}"}, 502)
            return
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self._sec_headers()
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        raw = urlparse(self.path).path
        if raw.startswith("/mcp"):
            if not self._gated():
                self.close_connection = True
                return
            self._mcp_proxy("GET")
            return
        if raw.startswith("/backend/api/feeds/") or raw.startswith("/backend/api/seo/"):
            # Product feeds + SEO packs for shopping/AI agents: read-only
            # catalog data + public images, safe ungated like llms.txt.
            self._proxy("GET")
            return
        if (raw.startswith("/api/seo/") or raw.startswith("/api/companygraph")
                or raw.startswith("/learn") or raw == "/sitemap.xml"):
            # Public discovery surface — GEO pages, sitemap, SEO packs.
            self._proxy("GET", path=raw)
            return
        if raw.startswith("/guides/"):
            # Crawlable companion guides (SEO document links) — public HTML.
            self._proxy("GET", path=raw)
            return
        if raw.startswith("/backend"):
            if not self._gated():
                return
            self._proxy("GET")
            return
        if raw.startswith("/api/auth/"):
            # Google round trip — proxied, ungated (state is the CSRF check)
            self._proxy("GET", path=raw)
            return
        if raw.startswith("/api/"):
            self._json({"success": False, "error": "GET not supported"}, 405)
            return
        if raw == "/products" or raw.startswith("/products/"):
            # Products tab + per-line pages live in the SPA (site/index.html);
            # boot opens the products panel from the pathname. /products.html
            # (Etsy photo gallery file) does not match and still serves below.
            raw = "/"

        root = ROOT / "site"
        rel = raw
        for prefix, r in ROUTES:
            if raw == prefix.rstrip("/") or raw.startswith(prefix):
                root = r
                rel = raw[len(prefix) - 1:] if raw != prefix.rstrip("/") else "/"
                break

        if rel in ("", "/"):
            rel = "index.html"
        target = (root / rel.lstrip("/")).resolve()
        if not str(target).startswith(str(root.resolve())) or not target.is_file():
            self._json({"success": False, "error": "not found"}, 404)
            return
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
            ".jpg": "image/jpeg",
            ".zip": "application/zip",
            ".jpg": "image/jpeg",
            ".txt": "text/plain; charset=utf-8",
            ".ico": "image/x-icon",
        }.get(target.suffix, "application/octet-stream")
        data = target.read_bytes()
        # Pages call our own /api/* routes. Rather than hardcoding a secret in
        # their source, patch window.fetch at serve time so the token rides
        # along on same-origin API calls only.
        if target.suffix == ".html" and b"/api/" in data:
            inject = (
                "<script>(function(){var T="
                + json.dumps(TOKEN)
                + ";window.__FIGG_TOKEN=T;"
                + ";var f=window.fetch.bind(window);window.fetch=function(i,o){"
                "var u=typeof i==='string'?i:i.url;"
                "if(u.indexOf('/api/')===0||u.indexOf('/backend/')===0){var j=u.indexOf('?')>=0?'&':'?';"
                "var n=u+j+'token='+encodeURIComponent(T);"
                "var sig='';try{sig=localStorage.getItem('pogpet.ownersig')||'';}catch(e){}"
                "var hdrs=(o&&o.headers)||{};"
                "try{var actor=localStorage.getItem('pogpet.owner')||'anon';var key=localStorage.getItem('pogpet.apikey')||'';"
                "if(typeof Headers==='function'&&hdrs instanceof Headers){hdrs.set('X-Figg-Owner',actor);if(key)hdrs.set('X-API-Key',key);}"
                "else{hdrs=Object.assign({},hdrs,{'X-Figg-Owner':actor});if(key)hdrs['X-API-Key']=key;}}catch(e){}"
                "if(sig){try{if(typeof Headers==='function'&&hdrs instanceof Headers){if(!hdrs.has('X-Owner-Sig'))hdrs.set('X-Owner-Sig',sig);}else{hdrs=Object.assign({},hdrs);hdrs['X-Owner-Sig']=sig;}}catch(e){}}"
                "o=Object.assign({},o||{},{headers:hdrs});"
                "i=(typeof i==='string')?n:new Request(n,i);}return f(i,o);};})();"
                "</script>"
            ).encode()
            marker = b"</body>"
            data = (data.replace(marker, inject + marker, 1)
                    if marker in data else data + inject)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self._sec_headers()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self):
        if urlparse(self.path).path.startswith("/mcp"):
            if not self._gated():
                self.close_connection = True
                return
            self._mcp_proxy("POST")
            return
        if urlparse(self.path).path.startswith("/backend"):
            if not self._gated():
                return
            self._proxy("POST")
            return
        # Drain the body FIRST — an unread multipart on a keep-alive socket
        # makes the next parse see garbage and the connection resets.
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            n = 0
        raw = self.rfile.read(n) if n > 0 else b""

        if not self._gated():
            return
        path = urlparse(self.path).path

        if "/whisper" in path:
            # No local STT wired yet. Return the failure shape so the site
            # falls back to typing (index.html: "I didn't catch that.").
            self._json({"success": False, "error": "stt not wired; type instead"})
            return

        if "/api/ai/" not in path:
            self._json({"success": False, "error": "unknown route"}, 404)
            return

        try:
            body = json.loads(raw or b"{}")
        except Exception:
            self._json({"success": False, "error": "bad json"}, 400)
            return

        messages = body.get("messages") or []
        try:
            reply = run_pi(
                messages,
                int(body.get("max_tokens", 200)),
                float(body.get("temperature", 0.8)),
                actor_env=verified_actor(
                    str(body.get("owner") or self.headers.get("X-Figg-Owner") or "anon"),
                    self.headers.get("X-Owner-Sig", ""),
                    self.headers.get("X-API-Key", ""),
                ),
            )
        except PermissionError as e:
            self._json({"success":False,"error":str(e)},403)
            return
        except subprocess.TimeoutExpired:
            self._json({"success": False, "error": "model timeout"}, 504)
            return
        except Exception as e:
            self._json({"success": False, "error": str(e)[:300]}, 502)
            return

        self._json({"success": True, "result": {"response": reply}})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if not TOKEN:
        import secrets
        TOKEN = secrets.token_urlsafe(24)
    print(f"figgsite bridge: http://127.0.0.1:{PORT}  token={TOKEN}")
    print(f"provider={PROVIDER} model={MODEL} pi_cli={'OK' if PI_CLI.exists() else 'MISSING'}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
