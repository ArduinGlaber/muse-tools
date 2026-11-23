#!/usr/bin/env python3
"""Cliente para el chat web de DeepSeek (chat.deepseek.com) sin API oficial.

Usa el userToken de la sesion web (LocalStorage -> userToken) como Bearer token.
El token se guarda en ~/.config/deepseek-usertoken (modo 600), nunca en el repo.

Uso:
    deepseek-web.py "tu pregunta" [--think] [--search] [--seguir|--nuevo] [--sesion=NOMBRE] [--cerrar] [--token TOKEN]

--seguir continua en el chat guardado (el ultimo, o el de --sesion).
Sin --seguir cada pregunta abre un chat nuevo y pasa a ser el guardado.
--sesion=NOMBRE guarda un chat por tema (deepseek-sesion-<nombre>.json).
Limites: maximo 10 temas guardados; un tema sin uso 7 dias se cierra
solo (la limpieza corre en cada llamada). --cerrar cierra la sesion
(con --sesion, ese tema) y sale.

Si el endpoint cambia, ajustar API_URL / payload en _probar_endpoint().
"""
import json
import os
import re
import sys
import time
import urllib.request

# Limites de temas (2026-11-23, acordado con el usuario):
# maximo 10 chats guardados; un tema sin uso 7 dias se cierra solo.
# La limpieza es perezosa: corre en cada llamada, sin cron.
MAX_TEMAS = 10
VENCIMIENTO_DIAS = 7

# 2026-11-05: el egress cierra conexiones de forma intermitente
# ("Remote end closed connection without response", IncompleteRead).
# Son fallos de transporte transitorios, en rafagas de ~15-30 s.
# 2026-11-09: CloudFront tambien devuelve a veces un HTTP 307 sin
# Location seguible (pagina generica de error de CloudFront): urllib
# no lo puede seguir y lo devuelve como HTTPError. Es el mismo
# transitorio de transporte/CDN, no un cambio de endpoint ni del
# token: la misma peticion repetida llega a la API (200 + 40003 con
# el token caducado). Por eso el 307 tambien se reintenta a nivel de
# flujo completo, igual que el -1.
# Reintento a nivel de flujo completo (sesion + PoW nuevos por
# intento, backoff 5/10 s): el PoW es de un solo uso y reintentar el
# completion con el mismo PoW da {"code":40301,"msg":
# "INVALID_POW_RESPONSE"} (200 con JSON de error, no SSE). Solo se
# reintenta el error de transporte (status -1) o ese 40301; un
# HTTPError (401/403/429/5xx) se devuelve tal cual, sin reintento.

_DIR = os.path.dirname(os.path.abspath(__file__))
SESION_FILE = os.path.join(_DIR, "deepseek-sesion.json")
TOKEN_FILE = os.path.expanduser("~/.config/deepseek-usertoken")


def slug_tema(nombre):
    """Nombre de tema -> slug seguro para el archivo de sesion."""
    slug = re.sub(r"[^a-z0-9_-]", "-", (nombre or "").lower()).strip("-")
    return (slug[:40] or None)


def archivo_sesion(nombre=None):
    """Archivo de sesion: por defecto deepseek-sesion.json; con tema,
    deepseek-sesion-<slug>.json. None si el nombre no da un slug."""
    if nombre:
        slug = slug_tema(nombre)
        if not slug:
            return None
        return os.path.join(_DIR, f"deepseek-sesion-{slug}.json")
    return SESION_FILE
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


def cargar_sesion(archivo=None):
    """Chat guardado: {chat_session_id, parent_message_id, ultimo_uso}."""
    archivo = archivo or SESION_FILE
    try:
        with open(archivo) as f:
            d = json.load(f)
        if d.get("chat_session_id") and d.get("parent_message_id") is not None:
            return d
    except Exception:
        pass
    return None


def guardar_sesion(sid, parent_id, archivo=None, tema=None):
    archivo = archivo or SESION_FILE
    try:
        with open(archivo, "w") as f:
            json.dump({"chat_session_id": sid,
                       "parent_message_id": parent_id,
                       "ultimo_uso": time.time(),
                       "tema": tema}, f)
    except Exception as e:
        print(f"aviso: no se pudo guardar la sesion: {e}", file=sys.stderr)


def limpiar_sesiones(max_guardados=MAX_TEMAS):
    """Cierra sesiones vencidas (>VENCIMIENTO_DIAS sin uso) y, si
    siguen siendo mas de max_guardados, las menos usadas. Devuelve
    los nombres de archivo cerrados. Sin red, sin cron: corre en
    cada llamada. El cierre aqui es dejar de reusar el chat; el
    historial queda en la cuenta de DeepSeek."""
    ahora = time.time()
    archivos = []
    try:
        nombres = os.listdir(_DIR)
    except OSError:
        return []
    for nombre in nombres:
        if nombre.startswith("deepseek-sesion") and nombre.endswith(".json"):
            ruta = os.path.join(_DIR, nombre)
            try:
                with open(ruta) as f:
                    d = json.load(f)
                uso = d.get("ultimo_uso") or os.path.getmtime(ruta)
            except Exception:
                uso = os.path.getmtime(ruta)
            archivos.append((ruta, uso))
    cerrados = []
    for ruta, uso in archivos:
        if ahora - uso > VENCIMIENTO_DIAS * 86400:
            try:
                os.remove(ruta)
                cerrados.append(os.path.basename(ruta))
            except OSError:
                pass
    archivos = [(r, u) for (r, u) in archivos if os.path.exists(r)]
    archivos.sort(key=lambda x: x[1])
    while len(archivos) > max_guardados:
        ruta, _ = archivos.pop(0)
        try:
            os.remove(ruta)
            cerrados.append(os.path.basename(ruta))
        except OSError:
            pass
    return cerrados


def extraer_id_respuesta(body):
    """Id del mensaje de respuesta: viene en el evento `ready`
    (response_message_id) o en v.response.message_id. Es el padre
    de la proxima pregunta del mismo chat."""
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        try:
            d = json.loads(line[5:])
        except Exception:
            continue
        if isinstance(d, dict) and d.get("response_message_id") is not None:
            return d["response_message_id"]
        v = d.get("v") if isinstance(d, dict) else None
        if isinstance(v, dict):
            resp = v.get("response", {})
            if isinstance(resp, dict) and resp.get("message_id") is not None:
                return resp["message_id"]
    return None


def _post(token, url, payload, pow_header=None, reintentar=True):
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
    intentos = 4 if reintentar else 1
    for intento in range(1, intentos + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "ignore")[:500]
        except Exception as e:
            if intento < intentos:
                time.sleep(5 * intento)
                continue
            return -1, f"ERROR: {e}"
    return -1, "ERROR: sin respuesta"


def crear_sesion(token):
    status, body = _post(token, "https://chat.deepseek.com/api/v0/chat_session/create", {})
    if status != 200:
        return None, f"HTTP {status}: {body[:200]}"
    try:
        d = json.loads(body)
        biz = d["data"]["biz_data"]
        # Desde 2026-10-20 la API envuelve la sesion en "chat_session";
        # antes el id venia directo en biz_data.
        sid = biz.get("chat_session", {}).get("id") or biz["id"]
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


def preguntar(token, prompt, think=False, search=False, sid=None,
              parent_id=None):
    # El PoW es de un solo uso: si el completion se corta a mitad de
    # stream, reintentarlo con el mismo PoW da INVALID_POW_RESPONSE.
    # Por eso el reintento es a nivel de flujo completo (sesion + PoW
    # nuevos en cada intento), no a nivel de _post para el completion.
    # Con sid dado (--seguir) se reutiliza la sesion y solo el PoW es
    # nuevo en cada intento. Devuelve (status, body, sid_usado).
    for intento in range(1, 4):
        if sid is None:
            sid, err = crear_sesion(token)
            if not sid:
                if (err.startswith("HTTP -1") or err.startswith("HTTP 307")) and intento < 3:
                    time.sleep(5 * intento)
                    continue
                return -1, f"no se pudo crear sesion: {err}", sid
        pow_header, err = resolver_pow(token)
        if not pow_header:
            if (err.startswith("challenge HTTP -1") or err.startswith("challenge HTTP 307")) and intento < 3:
                time.sleep(5 * intento)
                continue
            return -1, f"PoW fallo: {err}", sid
        # Payload exacto del frontend web (main.js de chat.deepseek.com)
        payload = {
            "chat_session_id": sid,
            "parent_message_id": parent_id,
            "model_type": "default",
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": think,
            "search_enabled": search,
        }
        status, body = _post(token, API_URL, payload, pow_header,
                             reintentar=False)
        if status == -1 and intento < 3:
            time.sleep(5 * intento)
            continue
        if status == 200 and intento < 3:
            # Un 200 con {"code":40301,"msg":"INVALID_POW_RESPONSE"} es
            # un rechazo, no una respuesta: reintentar con PoW nuevo.
            try:
                d = json.loads(body)
                if isinstance(d, dict) and d.get("code") not in (None, 0):
                    time.sleep(5 * intento)
                    continue
            except Exception:
                pass
        return status, body, sid
    return -1, "ERROR: sin respuesta", sid


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    cli_token = None
    sesion_nombre = None
    for f in flags:
        if f.startswith("--token="):
            cli_token = f.split("=", 1)[1]
        elif f.startswith("--sesion="):
            sesion_nombre = f.split("=", 1)[1]

    archivo = archivo_sesion(sesion_nombre)
    if sesion_nombre and archivo is None:
        print(f"Nombre de sesion invalido: {sesion_nombre!r}", file=sys.stderr)
        sys.exit(1)
    etiqueta = sesion_nombre or "por defecto"

    if "--cerrar" in flags:
        if archivo and os.path.exists(archivo):
            os.remove(archivo)
            print(f"Sesion '{etiqueta}' cerrada.")
        else:
            print(f"No habia sesion guardada '{etiqueta}'.")
        sys.exit(0)

    if not args:
        print("Uso: deepseek-web.py \"pregunta\" [--think] [--search] [--seguir|--nuevo] [--sesion=NOMBRE] [--cerrar] [--token=...]")
        print("  --seguir: continua en el chat guardado (ultimo, o el de --sesion)")
        print("  --nuevo: empieza un chat nuevo (es el comportamiento por defecto)")
        print("  --sesion=NOMBRE: un chat guardado por tema; maximo 10 temas,")
        print("    un tema sin uso 7 dias se cierra solo")
        print("  --cerrar: cierra la sesion (con --sesion, ese tema) y sale")
        sys.exit(1)

    # Limpieza perezosa: vencidos fuera, y hueco para el chat nuevo
    # (al seguir no se crea archivo nuevo, no hace falta hueco).
    seguir = "--seguir" in flags
    cerrados = limpiar_sesiones(MAX_TEMAS if seguir else MAX_TEMAS - 1)
    if cerrados:
        print(f"Sesiones cerradas por limite: {', '.join(cerrados)}",
              file=sys.stderr)

    sid = None
    parent_id = None
    if seguir:
        estado = cargar_sesion(archivo)
        if not estado:
            print(f"Sin chat guardado '{etiqueta}' (no existe o vencio): corre primero una pregunta sin --seguir y luego continua con --seguir.",
                  file=sys.stderr)
            sys.exit(5)
        sid = estado["chat_session_id"]
        parent_id = estado["parent_message_id"]

    token = leer_token(cli_token)
    if not token:
        print("Sin token. Guardalo con: deepseek-web.py --token=TU_TOKEN \"hola\"")
        print("El token se saca de chat.deepseek.com -> F12 -> Application -> "
              "Local Storage -> userToken")
        sys.exit(2)
    if cli_token:
        guardar_token(cli_token)
        print("Token guardado en ~/.config/deepseek-usertoken", file=sys.stderr)

    status, body, sid = preguntar(
        token, args[0],
        think="--think" in flags, search="--search" in flags,
        sid=sid, parent_id=parent_id,
    )
    if status == 401 or status == 403:
        print(f"HTTP {status}: token invalido o caducado. Pide un userToken nuevo.",
              file=sys.stderr)
        sys.exit(3)
    if status != 200:
        print(f"HTTP {status}: {body}", file=sys.stderr)
        sys.exit(4)
    # Guardar la sesion para --seguir: el id de la respuesta es el
    # padre de la proxima pregunta en el mismo chat.
    rid = extraer_id_respuesta(body)
    if rid is not None and sid is not None:
        guardar_sesion(sid, rid, archivo=archivo, tema=sesion_nombre)
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
