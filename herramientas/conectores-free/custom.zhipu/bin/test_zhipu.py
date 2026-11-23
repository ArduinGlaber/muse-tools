"""Prueba de la API de Zhipu AI (z.ai) con la clave en bóveda (Bearer header, formato OpenAI)."""
import json, sys, urllib.request
sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
sys.path.insert(0, "/home/hatch/workspace/cuotas")
from dynamic_credentials import add_surrogate_to_request, read_json_response
import cuotas

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")

prompt = sys.argv[1] if len(sys.argv) > 1 else "Responde solo con la palabra: OK"
model = sys.argv[2] if len(sys.argv) > 2 else "glm-4.7-flash"

body = json.dumps({
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
}).encode()

request = urllib.request.Request(
    "https://api.z.ai/api/paas/v4/chat/completions",
    data=body,
    headers={"Content-Type": "application/json",
             "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
    method="POST",
)
add_surrogate_to_request(request, "custom.zhipu", allowed_hosts=["api.z.ai"])
try:
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
        data = read_json_response(response)
    u = data.get("usage") or {}
    cuotas.registrar("zhipu", model, 200,
                     tokens_in=u.get("prompt_tokens", 0),
                     tokens_out=u.get("completion_tokens", 0))
    print(json.dumps({
        "http": 200,
        "model": data.get("model"),
        "reply": (data.get("choices") or [{}])[0].get("message", {}).get("content"),
        "finish_reason": (data.get("choices") or [{}])[0].get("finish_reason"),
        "usage": data.get("usage"),
    }, ensure_ascii=False, indent=2))
except urllib.error.HTTPError as e:
    cuotas.registrar("zhipu", model, e.code)
    print(json.dumps({"http": e.code, "body": e.read().decode("utf-8", "ignore")[:800]}, ensure_ascii=False, indent=2))
    sys.exit(1)
