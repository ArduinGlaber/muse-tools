"""Pregunta de un solo uso a un modelo FREE (para derivar subtareas).

Uso: python3 preguntar.py "tu prompt" [max_tokens]
Prueba modelos por orden de capacidad y usa el primero sano.
Todo pasa por el proxy fail-closed (solo :free, costo 0).
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "/home/hatch/workspace/openrouter-free")
from modelos import (disponibles, marcar_modelo, marcar_muro_diario,
                     es_muro_diario, hay_muro)

OR_PROXY = "http://127.0.0.1:8123/v1/chat/completions"
# Fallback sin clave cuando OpenRouter se agota (lento: ~1 req/15s anonimo)
POLLINATIONS_URL = "https://text.pollinations.ai/openai"
POLL_MIN_INTERVALO = 15  # segundos entre peticiones (limite anonimo)
DIR = os.path.dirname(os.path.abspath(__file__))
POLL_TS = os.path.join(DIR, "pollinations-ultima.json")


def _poll_log(status, ms, chars=0):
    hoy = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    p = os.path.join(DIR, f"pollinations-uso-{hoy}.jsonl")
    with open(p, "a") as f:
        f.write(json.dumps({
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": status, "ms": int(ms), "chars": chars}) + "\n")


def _respetar_intervalo():
    """Espera lo necesario para no pasar de 1 peticion cada 15s."""
    ahora = time.time()
    ultimo = 0
    if os.path.exists(POLL_TS):
        try:
            with open(POLL_TS) as f:
                ultimo = json.load(f).get("ts", 0)
        except Exception:
            pass
    espera = POLL_MIN_INTERVALO - (ahora - ultimo)
    if espera > 0:
        print(f"[pollinations] esperando {espera:.0f}s (limite 1/15s)...",
              flush=True)
        time.sleep(espera)
    with open(POLL_TS, "w") as f:
        json.dump({"ts": time.time()}, f)

# Orden: mas capaz primero (se filtra por cooldown antes de usar)
MODELOS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "thinkingmachines/inkling:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "cohere/north-mini-code:free",
    "poolside/laguna-xs-2.1:free",
    "liquid/lfm-2.5-2.6b:free",
]

# Router por tipo de tarea: el mas capaz PARA ESE TIPO primero.
# (El free cuenta por peticion, no por tokens: siempre el mas potente.)
TIPOS = {
    "codigo": [
        "cohere/north-mini-code:free",      # tool-calling verificado
        "nvidia/nemotron-3-super-120b-a12b:free",
        "poolside/laguna-xs-2.1:free",      # especializado en codigo
        "google/gemma-4-31b-it:free",
        "liquid/lfm-2.5-2.6b:free",
    ],
    "texto": [
        "nvidia/nemotron-3-super-120b-a12b:free",
        "google/gemma-4-31b-it:free",
        "thinkingmachines/inkling:free",
        "cohere/north-mini-code:free",
        "liquid/lfm-2.5-2.6b:free",
    ],
    "razonar": [
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "google/gemma-4-31b-it:free",
        "thinkingmachines/inkling:free",
        "liquid/lfm-2.5-2.6b:free",
    ],
}


def _clasificar_429(modelo, cuerpo):
    if es_muro_diario(cuerpo):
        marcar_muro_diario()
    else:
        marcar_modelo(modelo)


def preguntar_pollinations(prompt, max_tokens=1500, system=None):
    """Fallback sin clave (Pollinations, modelo openai-fast).
    Respeta el limite anonimo de 1 peticion/15s y registra uso."""
    _respetar_intervalo()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({"model": "openai-fast", "messages": messages,
                       "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(
        POLLINATIONS_URL, data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
        texto = d["choices"][0]["message"].get("content", "").strip()
        _poll_log("ok", (time.time() - t0) * 1000, len(texto))
        return texto
    except Exception as e:
        _poll_log(f"error: {e}", (time.time() - t0) * 1000)
        raise


def preguntar(prompt, max_tokens=1500, system=None, tipo=None):
    base = TIPOS.get(tipo, MODELOS)
    modelos = [] if hay_muro() else disponibles(base)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    errores = []
    for m in modelos:
        try:
            body = json.dumps({"model": m, "messages": messages,
                               "stream": False, "max_tokens": max_tokens}).encode()
            req = urllib.request.Request(
                OR_PROXY, data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.load(r)
            msg = d["choices"][0]["message"]
            texto = msg.get("content") or msg.get("reasoning") or ""
            if texto.strip():
                return m, texto.strip()
            errores.append(f"{m}: respuesta vacía")
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode("utf-8", "ignore")
            if e.code == 429:
                _clasificar_429(m, cuerpo)
            errores.append(f"{m}: HTTP {e.code}")
        except Exception as e:
            errores.append(f"{m}: {e}")
    # Fallback final: Pollinations (gratis sin clave, lento pero sin cuota)
    try:
        texto = preguntar_pollinations(prompt, max_tokens, system)
        if texto:
            return "pollinations/openai-fast", texto
        errores.append("pollinations: respuesta vacía")
    except Exception as e:
        errores.append(f"pollinations: {e}")
    raise RuntimeError("ningún modelo respondió: " + " | ".join(errores[:3]))


if __name__ == "__main__":
    if sys.argv[1] == "--ver-fallback":
        hoy = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        p = os.path.join(DIR, f"pollinations-uso-{hoy}.jsonl")
        print(open(p).read().strip() if os.path.exists(p)
              else "(fallback sin uso hoy)")
    else:
        prompt = sys.argv[1]
        max_tokens = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
        tipo = sys.argv[3] if len(sys.argv) > 3 else None
        modelo, texto = preguntar(prompt, max_tokens, tipo=tipo)
        print(f"[modelo: {modelo}]")
        print(texto)
