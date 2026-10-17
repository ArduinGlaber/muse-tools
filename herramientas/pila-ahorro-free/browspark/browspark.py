"""Helper para hablar con el companion Browspark (http://127.0.0.1:9223/mcp).

Uso:
    python3 browspark.py browser_session '{"action":"launch","browser":"chromium","browserPath":"/opt/meta-chromium/chrome","headless":true,"args":["--no-sandbox","--disable-dev-shm-usage","--ignore-certificate-errors"],"proxy":"http://127.0.0.1:3130","context":"vm"}'
    python3 browspark.py browser_navigate '{"tabId":123,"url":"https://example.com"}'
    python3 browspark.py browser_read '{"tabId":123}'

Requiere: companion corriendo (start-browspark.sh) y relay-proxy.py en :3130.
"""
import json
import sys
import urllib.request

MCP = "http://127.0.0.1:9223/mcp"
SID_FILE = "/tmp/browspark-sid.txt"


def _post(payload, session=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(
        MCP, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        sid = r.headers.get("Mcp-Session-Id")
        raw = r.read().decode("utf-8", "ignore")
    return sid, raw


def _extract(raw):
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if line.startswith("{"):
            try:
                d = json.loads(line)
                r = d.get("result", d.get("error", d))
                if isinstance(r, dict) and "content" in r:
                    return "\n".join(
                        c.get("text", "") for c in r["content"] if c.get("type") == "text"
                    )
                return json.dumps(r, ensure_ascii=False)[:4000]
            except Exception:
                pass
    return raw[:500]


def get_session():
    try:
        with open(SID_FILE) as f:
            sid = f.read().strip()
            return sid.split("=", 1)[-1] if sid else None
    except OSError:
        return None


def new_session():
    sid, _ = _post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "browspark-py", "version": "1.0"}},
    })
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    with open(SID_FILE, "w") as f:
        f.write(sid)
    return sid


def call(tool, args):
    sid = get_session() or new_session()
    try:
        _, raw = _post({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        }, sid)
    except urllib.error.HTTPError:
        sid = new_session()
        _, raw = _post({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        }, sid)
    out = _extract(raw)
    if "Server not initialized" in out:
        sid = new_session()
        _, raw = _post({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        }, sid)
        out = _extract(raw)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    tool = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(call(tool, args))
