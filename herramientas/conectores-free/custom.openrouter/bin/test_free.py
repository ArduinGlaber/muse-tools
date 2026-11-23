"""Variante A: prueba del router openrouter/free con la clave en boveda."""
import json, os, sys, urllib.request
sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
sys.path.insert(0, "/home/hatch/workspace/openrouter-free")
from dynamic_credentials import add_surrogate_to_request, read_json_response
import uso

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")

body = json.dumps({
    "model": "openrouter/free",
    "messages": [{"role": "user", "content": "Responde solo con la palabra: OK"}],
}).encode()

request = urllib.request.Request(
    "https://openrouter.ai/api/v1/chat/completions",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
add_surrogate_to_request(request, "custom.openrouter", allowed_hosts=["openrouter.ai"])
try:
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=90) as response:
        data = read_json_response(response)
    uso.registrar("openrouter/free", 200)
    print(json.dumps({
        "http": 200,
        "model": data.get("model"),
        "reply": (data.get("choices") or [{}])[0].get("message", {}).get("content"),
        "finish_reason": (data.get("choices") or [{}])[0].get("finish_reason"),
        "usage": data.get("usage"),
    }, ensure_ascii=False, indent=2))
except urllib.error.HTTPError as e:
    uso.registrar("openrouter/free", e.code)
    print(json.dumps({"http": e.code, "body": e.read().decode("utf-8", "ignore")[:500]}, ensure_ascii=False, indent=2))
    sys.exit(1)
