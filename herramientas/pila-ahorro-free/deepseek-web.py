#!/usr/bin/env python3
"""Cliente para el chat web de DeepSeek (chat.deepseek.com) sin API oficial.

Usa el userToken de la sesion web (LocalStorage -> userToken) como Bearer token.
El token se guarda en ~/.config/deepseek-usertoken (modo 600), nunca en el repo.

Uso:
    deepseek-web.py "tu pregunta" [--think] [--search] [--token TOKEN]

Si el endpoint cambia, ajustar API_URL / payload en _probar_endpoint().
"""
import json
import os
import sys
import urllib.request

TOKEN_FILE = os.path.expanduser("~/.config/deepseek-usertoken")
# Endpoint real del frontend web (extraido del JS de chat.deepseek.com)
API_URL = "https://chat.deepseek.com/api/v0/chat/completion"


def leer_token(cli_token=None):
    if cli_token:
        return cli_token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    return None


def guardar_token(token):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(token.strip())
    os.chmod(TOKEN_FILE, 0o600)


def _post(token, url, payload, pow_header=None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Origin": "https://chat.deepseek.com",
        "Referer": "https://chat.deepseek.com/",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    }
    if pow_header:
        headers["X-Ds-Pow-Response"] = pow_header
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")[:500]
    except Exception as e:
        return -1, f"ERROR: {e}"


def crear_sesion(token):
    status, body = _post(token, "https://chat.deepseek.com/api/v0/chat_session/create", {})
    if status != 200:
        return None, f"HTTP {status}: {body[:200]}"
    try:
        d = json.loads(body)
        sid = d["data"]["biz_data"]["id"]
        return sid, None
    except Exception as e:
        return None, f"respuesta inesperada: {body[:200]}"


def resolver_pow(token):
    """Obtiene y resuelve el challenge PoW. Devuelve el header X-Ds-Pow-Response."""
    import base64
    import subprocess
    status, body = _post(
        token,
        "https://chat.deepseek.com/api/v0/chat/create_pow_challenge",
        {"target_path": "/api/v0/chat/completion"},
    )
    if status != 200:
        return None, f"challenge HTTP {status}"
    try:
        ch = json.loads(body)["data"]["biz_data"]["challenge"]
    except Exception:
        return None, "challenge inesperado"
    r = subprocess.run(
        ["node", "/home/hatch/workspace/openrouter-free/deepseek-pow.mjs",
         ch["challenge"], ch["salt"], str(ch["difficulty"]), str(ch["expire_at"])],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        return None, f"solver fallo: {r.stderr[:100]}"
    answer = int(r.stdout.strip())
    header = json.dumps({
        "algorithm": ch["algorithm"],
        "challenge": ch["challenge"],
        "salt": ch["salt"],
        "signature": ch["signature"],
        "answer": answer,
        "target_path": "/api/v0/chat/completion",
    }, separators=(",", ":"))
    return base64.b64encode(header.encode()).decode(), None


def preguntar(token, prompt, think=False, search=False):
    sid, err = crear_sesion(token)
    if not sid:
        return -1, f"no se pudo crear sesion: {err}"
    pow_header, err = resolver_pow(token)
    if not pow_header:
        return -1, f"PoW fallo: {err}"
    # Payload exacto del frontend web (main.js de chat.deepseek.com)
    payload = {
        "chat_session_id": sid,
        "parent_message_id": None,
        "model_type": "default",
        "prompt": prompt,
        "ref_file_ids": [],
        "thinking_enabled": think,
        "search_enabled": search,
    }
    return _post(token, API_URL, payload, pow_header)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    cli_token = None
    for f in flags:
        if f.startswith("--token="):
            cli_token = f.split("=", 1)[1]

    if not args:
        print("Uso: deepseek-web.py \"pregunta\" [--think] [--search] [--token=...]")
        sys.exit(1)

    token = leer_token(cli_token)
    if not token:
        print("Sin token. Guardalo con: deepseek-web.py --token=TU_TOKEN \"hola\"")
        print("El token se saca de chat.deepseek.com -> F12 -> Application -> "
              "Local Storage -> userToken")
        sys.exit(2)
    if cli_token:
        guardar_token(cli_token)
        print("Token guardado en ~/.config/deepseek-usertoken", file=sys.stderr)

    status, body = preguntar(
        token, args[0],
        think="--think" in flags, search="--search" in flags,
    )
    if status == 401 or status == 403:
        print(f"HTTP {status}: token invalido o caducado. Pide un userToken nuevo.",
              file=sys.stderr)
        sys.exit(3)
    if status != 200:
        print(f"HTTP {status}: {body}", file=sys.stderr)
        sys.exit(4)
    # La respuesta web es SSE: el texto llega como parches APPEND,
    # cada evento data: {"v":"fragmento"} se acumula en orden
    textos = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            try:
                d = json.loads(line[5:])
                v = d.get("v")
                p = d.get("p", "")
                # Ignorar eventos de estado (p. ej. response/status -> FINISHED)
                if isinstance(p, str) and p and "content" not in p and "fragments" not in p:
                    continue
                if isinstance(v, str):
                    textos.append(v)
                elif isinstance(v, dict):
                    resp = v.get("response", {})
                    if isinstance(resp, dict):
                        for frag in resp.get("fragments", []):
                            c = frag.get("content") if isinstance(frag, dict) else None
                            if c:
                                textos.append(c)
                # formato OpenAI por si acaso
                for ch in d.get("choices", []):
                    t = ch.get("delta", {}).get("content") or \
                        ch.get("message", {}).get("content")
                    if t:
                        textos.append(t)
            except Exception:
                pass
    out = "".join(textos).strip()
    print(out if out else body[:2000])


if __name__ == "__main__":
    main()
