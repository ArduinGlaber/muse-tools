"""Pregunta de un solo uso a un modelo FREE (para derivar subtareas).

Uso: python3 preguntar.py "tu prompt" [max_tokens] [tipo]
Prueba modelos por orden de capacidad y usa el primero sano.
Todo pasa por el proxy fail-closed (solo :free, costo 0).
Fallbacks: DeepSeek web (sin limite diario) -> Pollinations (lento).
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


def preguntar_deepseek(prompt, max_tokens=1500, system=None, think=False):
    """Fallback via DeepSeek web (token en ~/.config/deepseek-usertoken).
    Sin limite diario conocido; resuelve PoW con node+WASM (~3-4s/peticion).
    El system prompt se antepone al prompt (la web no tiene campo system)."""
    import subprocess
    if system:
        prompt = f"Instrucciones: {system}\n\n{prompt}"
    cmd = [sys.executable, os.path.join(DIR, "deepseek-web.py"), prompt]
    if think:
        cmd.append("--think")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"deepseek-web: {r.stderr.strip()[:200]}")
    texto = r.stdout.strip()
    if not texto:
        raise RuntimeError("deepseek-web: respuesta vacía")
    return texto


def _preguntar_openrouter(prompt, max_tokens, messages, base, errores):
    """Intenta los modelos OpenRouter free en orden. Devuelve (modelo, texto)
    o None si ninguno responde. Registra errores en la lista errores."""
    modelos = [] if hay_muro() else disponibles(base)
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
    return None


def _preguntar_deepseek(prompt, max_tokens, system, tipo, errores):
    """Intenta DeepSeek web. Devuelve ("deepseek/web", texto) o None."""
    try:
        texto = preguntar_deepseek(prompt, max_tokens, system,
                                   think=(tipo == "razonar"))
        if texto:
            return "deepseek/web", texto
        errores.append("deepseek: respuesta vacía")
    except Exception as e:
        errores.append(f"deepseek: {e}")
    return None


def preguntar(prompt, max_tokens=1500, system=None, tipo=None):
    """Router con politica 2026-10-18 (acordada con el usuario):
    - razonar/texto (o sin tipo): DeepSeek primero (ilimitado, mejor razonando),
      OpenRouter free despues, Pollinations al final.
    - codigo: OpenRouter primero (north-mini-code con tool-calling),
      DeepSeek despues, Pollinations al final.
    """
    base = TIPOS.get(tipo, MODELOS)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    errores = []

    deepseek_primero = tipo in ("razonar", "texto", None)

    if deepseek_primero:
        r = _preguntar_deepseek(prompt, max_tokens, system, tipo, errores)
        if r:
            return r
        r = _preguntar_openrouter(prompt, max_tokens, messages, base, errores)
        if r:
            return r
    else:
        r = _preguntar_openrouter(prompt, max_tokens, messages, base, errores)
        if r:
            return r
        r = _preguntar_deepseek(prompt, max_tokens, system, tipo, errores)
        if r:
            return r
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
