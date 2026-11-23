#!/usr/bin/env python3
"""Lazo agéntico ReAct sobre la pila free (prototipo).

Uso:
    python3 lazo.py "tarea a resolver" [--pasos 10] [--grupos 60]

El agente razona, usa herramientas y observa resultados hasta dar una
respuesta final o agotar los pasos. Modelos rápidos primero (groq-120b,
nvidia); los lentos quedan de respaldo. Pausa de 2.5s entre llamadas
para respetar los límites por minuto. Cada llamada registra su cuota
automáticamente vía los helpers (ver ~/workspace/cuotas/cuotas.py).
--grupos fija el default de grupos que revisa buscar_grupos en esa
ejecución (el agente puede pedir otro valor por tarea, hasta el total
de tus grupos en mis-grupos.txt, que se cuenta solo).
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import html as html_lib

sys.path.insert(0, "/home/hatch/workspace/openrouter-free")
from preguntar import (
    _preguntar_groq120b, _preguntar_nvidia, _preguntar_zhipu,
    _preguntar_freeai, _preguntar_cloudflare, _preguntar_gemini,
    _preguntar_deepseek, _preguntar_openrouter,
    preguntar_pollinations, TIPOS, MODELOS,
)

PAUSA_S = 2.5          # entre llamadas al modelo (respeta 30 RPM de Groq)
MAX_PASOS = 10
MAX_SALIDA = 4000      # caracteres máx. por observación
DEFAULT_GRUPOS = 25    # grupos por defecto en buscar_grupos (override: --grupos N)
# El tope es dinámico: _contar_grupos() lee mis-grupos.txt en cada llamada.

SYSTEM = """Eres un agente que resuelve tareas usando herramientas.
Herramientas disponibles:
- shell: ejecuta un comando del sistema. args: {"comando": "..."}
- leer: lee un archivo (primeras 200 líneas). args: {"ruta": "..."}
- escribir: crea o sobrescribe un archivo. args: {"ruta": "...", "contenido": "..."}
- subpregunta: delega una sub-pregunta a otro modelo de la pila. args: {"pregunta": "..."}
- buscar_web: busca en la web (DuckDuckGo, sin clave). args: {"consulta": "...", "n": 5}
- leer_url: extrae el texto de una página web. args: {"url": "..."}
- buscar_grupos: busca productos/anuncios en tus grupos de Facebook. args: {"consulta": "...", "keywords": "palabra1,palabra2", "limite_grupos": 25} (si omites limite_grupos usa el default de la ejecución)
- vigilancia_clientes: corre la vigilancia diaria de clientes (marca los hallazgos como vistos, igual que el cron). args: {}

Para usar UNA herramienta, responde con un bloque así y nada más en ese turno:
```accion
{"herramienta": "buscar_web", "argumentos": {"consulta": "precio panel solar 550W", "n": 5}}
```
Un solo bloque de acción por respuesta. Tras cada observación decide el siguiente paso.
Cuando tengas la respuesta final, escríbela SIN bloque de acción.
REGLA DURA: si la tarea pide datos actuales, precios, límites o cualquier
información externa, DEBES usar buscar_web (y leer_url si hace falta) antes
de responder. Nunca respondas de memoria a preguntas sobre el mundo exterior.
Sé eficiente: el mínimo de pasos posible. No repites una acción que ya falló igual.
"""

# Patrones que el agente nunca puede ejecutar vía shell.
BLOQUEADOS = [
    r"\brm\s+-rf\s+/(?:\s|$)", r"\brm\s+-rf\s+~(?:\s|$)",
    r"\bmkfs\b", r"\bdd\s+.*of=", r":\(\)\s*\{",
    r"\bshutdown\b", r"\breboot\b", r"\bpoweroff\b",
]


def _tool_shell(args):
    cmd = args.get("comando", "")
    for pat in BLOQUEADOS:
        if re.search(pat, cmd):
            return f"BLOQUEADO por seguridad: {cmd[:80]}"
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=60)
        out = (r.stdout + r.stderr).strip()
        return f"(exit {r.returncode})\n" + out[:MAX_SALIDA]
    except Exception as e:
        return f"Error ejecutando: {e}"


def _tool_leer(args):
    ruta = os.path.expanduser(args.get("ruta", ""))
    try:
        with open(ruta) as f:
            lineas = f.readlines()[:200]
        return "".join(lineas)[:MAX_SALIDA]
    except Exception as e:
        return f"Error leyendo: {e}"


def _tool_escribir(args):
    ruta = os.path.expanduser(args.get("ruta", ""))
    try:
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        with open(ruta, "w") as f:
            f.write(args.get("contenido", ""))
        return f"Escrito OK: {ruta}"
    except Exception as e:
        return f"Error escribiendo: {e}"


def _tool_subpregunta(args):
    # Delega a la pila completa (pregunta simple, sin lazo).
    sys.path.insert(0, "/home/hatch/workspace/openrouter-free")
    from preguntar import preguntar
    try:
        modelo, texto = preguntar(args.get("pregunta", ""), tipo="texto")
        return f"[{modelo}] {texto[:MAX_SALIDA]}"
    except Exception as e:
        return f"Error en subpregunta: {e}"


UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _tool_buscar_web(args):
    q = args.get("consulta", "").strip()
    n = max(1, min(int(args.get("n", 5)), 10))
    if not q:
        return "Falta la consulta."
    url = ("https://html.duckduckgo.com/html/?q="
           + urllib.parse.quote_plus(q))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            pagina = r.read().decode("utf-8", "ignore")
    except Exception as e:
        return f"Error buscando: {e}"
    resultados = []
    for m in re.finditer(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
            r'.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            pagina, re.S):
        link, titulo, snippet = m.groups()
        um = re.search(r"uddg=([^&]+)", link)
        if um:
            link = urllib.parse.unquote(um.group(1))
        titulo = re.sub(r"<[^>]+>", "", titulo).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet).strip()
        if link.startswith("http"):
            resultados.append((titulo, link, snippet))
        if len(resultados) >= n:
            break
    if not resultados:
        return "Sin resultados."
    return "\n\n".join(
        "%d. %s\n   %s\n   %s" % (i + 1, t, u, s[:300])
        for i, (t, u, s) in enumerate(resultados))


def _tool_leer_url(args):
    url = args.get("url", "").strip()
    if not url.startswith("http"):
        return "URL inválida."
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            ctype = r.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype:
                return "No es HTML/texto: " + ctype
            pagina = r.read(500_000).decode("utf-8", "ignore")
    except Exception as e:
        return f"Error leyendo URL: {e}"
    texto = re.sub(r"<script.*?</script>|<style.*?</style>", " ",
                   pagina, flags=re.S | re.I)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html_lib.unescape(texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto[:MAX_SALIDA] if texto else "(página sin texto extraíble)"


FBWATCH = "/home/hatch/workspace/fb-watch"


def _contar_grupos():
    """Total de grupos en mis-grupos.txt (se lee en cada llamada,
    así si entra en más grupos el tope se actualiza solo)."""
    try:
        n = 0
        with open(os.path.join(FBWATCH, "mis-grupos.txt")) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("TOTAL"):
                    n += 1
        return n or 1
    except Exception:
        return 1


def _tool_buscar_grupos(args):
    consulta = args.get("consulta", "").strip()
    keywords = args.get("keywords", "").strip()
    limite = max(1, min(int(args.get("limite_grupos", DEFAULT_GRUPOS)),
                        _contar_grupos()))
    if not consulta or not keywords:
        return "Faltan consulta y/o keywords."
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(FBWATCH, "buscar_producto.py"),
             "--query", consulta, "--keywords", keywords,
             "--limit", str(limite)],
            capture_output=True, text=True, timeout=600)
        out = (r.stdout or "").strip()
        return out[:MAX_SALIDA] if out else "(sin salida del script)"
    except subprocess.TimeoutExpired:
        return "Timeout (600s) buscando en grupos."
    except Exception as e:
        return f"Error: {e}"


def _tool_vigilancia_clientes(args):
    # OJO: marca los hallazgos como vistos, igual que el cron diario.
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(FBWATCH, "vigilar_clientes.py")],
            capture_output=True, text=True, timeout=900)
        out = (r.stdout or "").strip()
        return ((out[:MAX_SALIDA] if out else "(sin salida)") +
                "\n[nota: los hallazgos quedaron marcados como vistos]")
    except subprocess.TimeoutExpired:
        return "Timeout (900s) en vigilancia."
    except Exception as e:
        return f"Error: {e}"


HERRAMIENTAS = {
    "shell": _tool_shell,
    "leer": _tool_leer,
    "escribir": _tool_escribir,
    "subpregunta": _tool_subpregunta,
    "buscar_web": _tool_buscar_web,
    "leer_url": _tool_leer_url,
    "buscar_grupos": _tool_buscar_grupos,
    "vigilancia_clientes": _tool_vigilancia_clientes,
}


def _extraer_accion(texto):
    m = re.search(r"```accion\s*(\{.*?\})\s*```", texto, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
        if d.get("herramienta") in HERRAMIENTAS:
            return d
    except Exception:
        pass
    return None


def _llamar_modelo(prompt, errores):
    """Cadena rápida primero: groq-120b -> nvidia -> zhipu -> cloudflare ->
    gemini -> deepseek -> openrouter -> freeai -> pollinations."""
    cadena = [
        ("groq120b", lambda: _preguntar_groq120b(prompt, errores)),
        ("nvidia", lambda: _preguntar_nvidia(prompt, errores)),
        ("zhipu", lambda: _preguntar_zhipu(prompt, errores)),
        ("cloudflare", lambda: _preguntar_cloudflare(prompt, errores)),
        ("gemini", lambda: _preguntar_gemini(prompt, errores)),
        ("deepseek", lambda: _preguntar_deepseek(
            prompt, 1500, None, "razonar", errores)),
    ]
    for nombre, intento in cadena:
        r = intento()
        if r:
            return r
    base = TIPOS.get("texto", MODELOS)
    messages = [{"role": "user", "content": prompt}]
    r = _preguntar_openrouter(prompt, 1500, messages, base, errores)
    if r:
        return r
    r = _preguntar_freeai(prompt, errores)
    if r:
        return r
    try:
        texto = preguntar_pollinations(prompt, 1500)
        if texto:
            return "pollinations/openai-fast", texto
    except Exception as e:
        errores.append(f"pollinations: {e}")
    return None, None


def lazo(tarea, max_pasos=MAX_PASOS, verbose=True):
    historial = f"Tarea: {tarea}\n"
    for paso in range(1, max_pasos + 1):
        errores = []
        if paso > 1:
            time.sleep(PAUSA_S)
        nombre, resp = _llamar_modelo(SYSTEM + "\n" + historial, errores)
        if not resp:
            return f"Sin respuesta de ningún modelo: {' | '.join(errores[:3])}"
        if verbose:
            print(f"--- paso {paso} [{nombre}] ---")
            print(resp[:500])
        accion = _extraer_accion(resp)
        if not accion:
            return resp  # respuesta final
        h = accion["herramienta"]
        obs = HERRAMIENTAS[h](accion.get("argumentos", {}))
        if verbose:
            print(f"[{h}] -> {obs[:300]}")
        historial += (f"\n[Paso {paso} ({nombre})]\n{resp}\n"
                      f"[Observación de {h}]\n{obs}\n")
    return ("Pasos agotados (%d). Último estado:\n%s"
            % (max_pasos, historial[-2000:]))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]
            if not a.startswith("--pasos") and not a.startswith("--grupos")]
    mp = MAX_PASOS
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--pasos" and i + 1 < len(argv):
            mp = int(argv[i + 1])
        elif a.startswith("--pasos="):
            mp = int(a.split("=", 1)[1])
        elif a == "--grupos" and i + 1 < len(argv):
            DEFAULT_GRUPOS = max(1, min(int(argv[i + 1]), _contar_grupos()))
        elif a.startswith("--grupos="):
            DEFAULT_GRUPOS = max(1, min(int(a.split("=", 1)[1]),
                                        _contar_grupos()))
    if not args:
        print(__doc__)
        sys.exit(1)
    print(lazo(" ".join(args), max_pasos=mp))
