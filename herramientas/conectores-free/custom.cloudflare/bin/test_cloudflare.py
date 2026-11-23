"""Prueba de Cloudflare Workers AI con la clave en boveda (Bearer header).

Descubre el Account ID via GET /accounts y luego llama al endpoint
OpenAI-compatible de Workers AI.
"""
import json, sys, urllib.request
sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
sys.path.insert(0, "/home/hatch/workspace/cuotas")
from dynamic_credentials import add_surrogate_to_request, read_json_response
import cuotas

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")

def authed_get(url):
    req = urllib.request.Request(url, headers=dict(UA), method="GET")
    add_surrogate_to_request(req, "custom.cloudflare", allowed_hosts=["api.cloudflare.com"])
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as r:
        return read_json_response(r)

def authed_post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers=dict(UA, **{"Content-Type": "application/json"}),
                                 method="POST")
    add_surrogate_to_request(req, "custom.cloudflare", allowed_hosts=["api.cloudflare.com"])
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=120) as r:
        return read_json_response(r)

prompt = sys.argv[1] if len(sys.argv) > 1 else "Responde solo con la palabra: OK"
model = sys.argv[2] if len(sys.argv) > 2 else "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
account_id = sys.argv[3] if len(sys.argv) > 3 else None

try:
    # 1. Account ID: usar el dado o descubrirlo via /accounts
    if not account_id:
        accts = authed_get("https://api.cloudflare.com/client/v4/accounts")
        if not accts.get("success") or not accts.get("result"):
            print(json.dumps({"http": 200, "error": "sin cuentas", "body": accts}, ensure_ascii=False)[:500])
            sys.exit(1)
        account_id = accts["result"][0]["id"]

    # 2. Chat completion (formato OpenAI)
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
    data = authed_post(url, {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        # Sin max_tokens la API corta por defecto a ~256 tokens (2026-11-23:
        # un plan de ~1200 palabras quedó a la mitad de una frase).
        "max_tokens": 4096,
    })
    choice = (data.get("choices") or [{}])[0]
    u = data.get("usage") or {}
    cuotas.registrar("cloudflare", model, 200,
                     tokens_in=u.get("prompt_tokens", 0),
                     tokens_out=u.get("completion_tokens", 0),
                     neurons=u.get("neurons", 0.0))
    print(json.dumps({
        "http": 200,
        "account_id": account_id,
        "model": model,
        "reply": choice.get("message", {}).get("content"),
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage"),
    }, ensure_ascii=False, indent=2))
except urllib.error.HTTPError as e:
    cuotas.registrar("cloudflare", model, e.code)
    print(json.dumps({"http": e.code, "body": e.read().decode("utf-8", "ignore")[:800]}, ensure_ascii=False, indent=2))
    sys.exit(1)
