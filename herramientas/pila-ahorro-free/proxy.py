"""Proxy fail-closed: solo modelos :free de OpenRouter.

Pi -> http://127.0.0.1:8123/v1 (apiKey dummy) -> este proxy inyecta la
clave real desde la boveda y reenvia a openrouter.ai. Cualquier modelo
que no termine en :free (o no sea openrouter/free) se rechaza con 403.
"""
import json
import os
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dynamic_credentials import add_surrogate_to_request
import uso

UPSTREAM = "https://openrouter.ai/api/v1"
PORT = 8123

FREE_MODELS = [
    "cohere/north-mini-code:free",
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "thinkingmachines/inkling:free",
    "openrouter/free",
]


def is_free(model_id):
    return isinstance(model_id, str) and (
        model_id == "openrouter/free" or model_id.endswith(":free")
    )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._send_json(200, {
                "object": "list",
                "data": [
                    {"id": m, "object": "model", "owned_by": "openrouter-free"}
                    for m in FREE_MODELS
                ],
            })
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw)
        except Exception:
            self._send_json(400, {"error": "invalid json"})
            return

        model = payload.get("model", "")
        # Fail-closed: solo :free
        if not is_free(model):
            self._send_json(403, {
                "error": {
                    "message": "fail-closed: solo modelos :free permitidos",
                    "model": model,
                }
            })
            return

        # Reenviar a OpenRouter con la clave de la boveda
        path = self.path
        if path.startswith("/v1/"):
            path = path[3:]
        req = urllib.request.Request(
            UPSTREAM + path,
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        add_surrogate_to_request(req, "custom.openrouter", allowed_hosts=["openrouter.ai"])
        try:
            upstream = urllib.request.build_opener(NoRedirect()).open(req, timeout=300)
        except urllib.error.HTTPError as e:
            uso.registrar(model, e.code)
            if e.code == 429:
                print("ALERTA: OpenRouter devolvio 429 (free agotado?)", flush=True)
            self._send_json(e.code, {"error": e.read().decode("utf-8", "ignore")[:500]})
            return

        uso.registrar(model, 200)

        ctype = upstream.headers.get("Content-Type", "")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        # Streaming: reenviar por chunks
        while True:
            chunk = upstream.read(8192)
            if not chunk:
                break
            try:
                self.wfile.write(chunk)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                break


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"proxy fail-closed en 127.0.0.1:{PORT}", flush=True)
    server.serve_forever()
