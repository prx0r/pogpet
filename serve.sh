#!/bin/bash
# figgsite — one process: site + pi bridge.
#   ./serve.sh            bind loopback, print token
#   ./serve.sh --tunnel   also open a Cloudflare quick tunnel
set -e
cd "$(dirname "$0")"

TOKFILE=.token
if [ ! -f "$TOKFILE" ]; then
  python3 -c "import secrets; print(secrets.token_urlsafe(24))" > "$TOKFILE"
  chmod 600 "$TOKFILE"
fi
export BRIDGE_TOKEN="${BRIDGE_TOKEN:-$(cat "$TOKFILE")}"
export BRIDGE_PORT="${BRIDGE_PORT:-8797}"

# provider key: .env if present, else opencode auth.json (NOTE: currently 402)
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi
if [ -z "$OPENCODE_API_KEY" ] && [ -f "$HOME/.local/share/opencode/auth.json" ]; then
  export OPENCODE_API_KEY="$(python3 -c "import json;print(json.load(open('$HOME/.local/share/opencode/auth.json'))['opencode-go']['key'])")"
fi

echo "figgsite token: $BRIDGE_TOKEN"
echo "open: http://127.0.0.1:$BRIDGE_PORT/?token=$BRIDGE_TOKEN"

if [ "$1" = "--tunnel" ]; then
  nohup python3 bridge/llm_bridge.py > bridge.log 2>&1 &
  echo $! > .bridge.pid
  nohup cloudflared tunnel --url "http://127.0.0.1:$BRIDGE_PORT" --no-autoupdate > tunnel.log 2>&1 &
  echo $! > .tunnel.pid
  sleep 6
  grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" tunnel.log | head -n 1 || tail -n 5 tunnel.log
else
  exec python3 bridge/llm_bridge.py
fi
