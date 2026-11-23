"""Prueba de la API de Free.ai con la clave en bóveda (Bearer header).

Free.ai: https://api.free.ai/v1 — 30.000 tokens/día (free pool),
1.000 peticiones API/mes, 60 req/min en el plan Free.

Uso:
  python3 test_freeai.py                      # lista modelos (GET /v1/models)
  python3 test_freeai.py "tu prompt"          # chat con modelo free
  python3 test_freeai.py "tu prompt" "qwen7b"
"""
import json, sys, urllib.request
sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
sys.path.insert(0, "/home/hatch/workspace/cuotas")
from dynamic_credentials import add_surrogate_to_request, read_json_response
import cuotas

BASE = "https://api.free.ai"
HOSTS = ["api.free.ai"]

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")

def _get(path):
    req = urllib.request.Request(
        BASE + path,
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
        method="GET",
    )
    add_surrogate_to_request(req, "custom.freeai", allowed_hosts=HOSTS)
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as r:
        return r.status, read_json_response(r)

def _post_chat(prompt, model):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        BASE + "/v1/chat/",
        data=body,
        headers={"Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
        method="POST",
    )
    add_surrogate_to_request(req, "custom.freeai", allowed_hosts=HOSTS)
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=90) as r:
        return r.status, read_json_response(r)

if len(sys.argv) == 1:
    try:
        status, data = _get("/v1/models")
        print(json.dumps({"http": status, "data": data}, ensure_ascii=False, indent=2)[:3000])
    except urllib.error.HTTPError as e:
        print(json.dumps({"http": e.code, "body": e.read().decode("utf-8", "ignore")[:800]}, ensure_ascii=False, indent=2))
        sys.exit(1)
else:
    prompt = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "qwen7b"
    try:
        status, data = _post_chat(prompt, model)
        u = data.get("usage") or {}
        cuotas.registrar("freeai", model, status,
                         tokens_in=u.get("prompt_tokens", u.get("input_tokens", 0)),
                         tokens_out=u.get("completion_tokens", u.get("output_tokens", 0)))
        # la respuesta puede venir en varios formatos
        reply = (data.get("choices") or [{}])[0].get("message", {}).get("content") \
            or data.get("reply") or data.get("response") or data.get("text")
        print(json.dumps({"http": status, "model": model, "reply": reply,
                          "usage": data.get("usage")},
                         ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as e:
        cuotas.registrar("freeai", model, e.code)
        print(json.dumps({"http": e.code, "body": e.read().decode("utf-8", "ignore")[:800]}, ensure_ascii=False, indent=2))
        sys.exit(1)
