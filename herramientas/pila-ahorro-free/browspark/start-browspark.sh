#!/bin/bash
# Arranca la pila Browspark en la VM: relay-proxy (inyecta auth del proxy de
# egress, token rotativo -> se lee del entorno al arrancar) + companion MCP.
# El companion expone MCP en http://127.0.0.1:9223/mcp (45 herramientas).
set -e
export PATH="/opt/hatch-image/bin:$PATH"
DIR="$(cd "$(dirname "$0")" && pwd)"

# Relay 127.0.0.1:3130 (si no corre ya)
if ! curl -s -m 3 -x http://127.0.0.1:3130 https://example.com -o /dev/null; then
  nohup python3 "$DIR/relay-proxy.py" > "$DIR/relay-proxy.log" 2>&1 &
  sleep 1
fi

# Companion (si no corre ya)
if ! curl -s -m 3 http://127.0.0.1:9223/mcp -o /dev/null -w "%{http_code}" | grep -q "200"; then
  nohup bun x browspark-mcp@latest --http-only > "$DIR/companion.log" 2>&1 &
  for i in $(seq 1 30); do
    sleep 2
    if grep -q "browspark: ready" "$DIR/companion.log" 2>/dev/null; then break; fi
  done
fi

echo "relay :3130 + companion :9223/mcp"
echo "Lanzar navegador:"
echo "  python3 $DIR/browspark.py browser_session '{\"action\":\"launch\",\"browser\":\"chromium\",\"browserPath\":\"/opt/meta-chromium/chrome\",\"headless\":true,\"args\":[\"--no-sandbox\",\"--disable-dev-shm-usage\",\"--ignore-certificate-errors\"],\"proxy\":\"http://127.0.0.1:3130\",\"context\":\"vm\"}'"
