"""Quema peticiones hasta el 429 para verificar el limite diario real.

Pausa 4s entre peticiones (evita el limite de 20/min). Si un modelo da 429
con el contador oficial <45, es limite de modelo -> rota al siguiente.
"""
import json
import sys
import time
import urllib.error
import urllib.request

OR_PROXY = "http://127.0.0.1:8123/v1/chat/completions"
MODELOS = [
    "liquid/lfm-2.5-2.6b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "cohere/north-mini-code:free",
]


def pedir(modelo):
    body = json.dumps({"model": modelo, "messages":
                       [{"role": "user", "content": "Di OK"}],
                       "stream": False, "max_tokens": 5}).encode()
    req = urllib.request.Request(
        OR_PROXY, data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def contador_oficial():
    """Lee usadas/limite del contador oficial."""
    import urllib.request as ur
    sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
    from dynamic_credentials import add_surrogate_to_request, read_json_response
    req = ur.Request("https://openrouter.ai/api/v1/key")
    add_surrogate_to_request(req, "custom.openrouter", allowed_hosts=["openrouter.ai"])
    with ur.urlopen(req, timeout=30) as r:
        d = read_json_response(r)["data"]["free_model_daily_requests"]
    return d["used"], d["limit"]


def main():
    n = 0
    for modelo in MODELOS:
        while True:
            n += 1
            try:
                pedir(modelo)
                print(f"#{n} {modelo} OK", flush=True)
            except urllib.error.HTTPError as e:
                cuerpo = e.read().decode("utf-8", "ignore")[:200]
                print(f"#{n} {modelo} HTTP {e.code}: {cuerpo[:100]}", flush=True)
                if e.code == 429:
                    usadas, limite = contador_oficial()
                    print(f"contador oficial: {usadas}/{limite}", flush=True)
                    if usadas >= limite - 1:
                        print(f"MURO DIARIO en peticion #{n} ({usadas}/{limite})", flush=True)
                        return
                    print("429 de modelo, rotando...", flush=True)
                    break
                break  # otro error: probar siguiente modelo
            except Exception as e:
                print(f"#{n} {modelo} ERROR {e}", flush=True)
                break
            time.sleep(4)


if __name__ == "__main__":
    main()
