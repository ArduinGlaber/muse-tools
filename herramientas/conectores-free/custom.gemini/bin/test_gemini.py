"""Prueba de la API de Gemini con la clave en boveda (header x-goog-api-key)."""
import json, sys, urllib.request
sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
sys.path.insert(0, "/home/hatch/workspace/cuotas")
from dynamic_credentials import add_surrogate_to_request, read_json_response
import cuotas

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")

prompt = sys.argv[1] if len(sys.argv) > 1 else "Responde solo con la palabra: OK"

body = json.dumps({
    "contents": [{"parts": [{"text": prompt}]}],
}).encode()

request = urllib.request.Request(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
add_surrogate_to_request(request, "custom.gemini", allowed_hosts=["generativelanguage.googleapis.com"])
try:
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=90) as response:
        data = read_json_response(response)
    candidates = data.get("candidates") or [{}]
    parts = (candidates[0].get("content") or {}).get("parts") or [{}]
    um = data.get("usageMetadata") or {}
    cuotas.registrar("gemini", "gemini-2.5-flash", 200,
                     tokens_in=um.get("promptTokenCount", 0),
                     tokens_out=um.get("candidatesTokenCount", 0))
    print(json.dumps({
        "http": 200,
        "model": "gemini-2.5-flash",
        "reply": parts[0].get("text"),
        "finish_reason": candidates[0].get("finishReason"),
        "usage": data.get("usageMetadata"),
    }, ensure_ascii=False, indent=2))
except urllib.error.HTTPError as e:
    cuotas.registrar("gemini", "gemini-2.5-flash", e.code)
    print(json.dumps({"http": e.code, "body": e.read().decode("utf-8", "ignore")[:800]}, ensure_ascii=False, indent=2))
    sys.exit(1)
