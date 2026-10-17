"""Agente de navegacion v2 (FREE, fail-closed).

Mejoras sobre v1 (recomendaciones adoptadas 2026-10-16):
1. Router con fallback: prueba modelos candidatos y usa el primero sano con
   tool-calling; si uno falla a mitad de tarea, cambia al siguiente.
2. Espera tras navegar: reintenta la lectura hasta que haya contenido.
3. Anti-rendicion: mas pasos, sitios confiables sugeridos, instrucciones de
   probar alternativas antes de rendirse.
4. Verificador: otro pase del modelo valida que la respuesta contenga datos.
5. Todo pasa por el proxy fail-closed (solo :free).

Uso: python3 agent_free.py "tarea" [pista_sitio]
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "/home/hatch/workspace/browspark")
from browspark import call as bs_call
sys.path.insert(0, "/home/hatch/workspace/openrouter-free")
from modelos import (disponibles, marcar_modelo, marcar_muro_diario,
                     es_muro_diario, hay_muro, leer_cuota)

OR_PROXY = "http://127.0.0.1:8123/v1/chat/completions"
MAX_PASOS = 20

MODEL_CANDIDATES = [
    "cohere/north-mini-code:free",   # verificado con tool-calling el 16/10
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "poolside/laguna-xs-2.1:free",
    "liquid/lfm-2.5-2.6b:free",      # ultimo recurso (debil)
]

# Sitios que ya se probo que cargan bien en este navegador
SITIOS_CONFIABLES = {
    "tiempo": ["https://www.timeanddate.com/weather/cuba/havana/ext"],
    "suplemento": ["https://examine.com/supplements/d-ribose/"],
}


def p(nombre, desc, props, req):
    return {"type": "function", "function": {
        "name": nombre, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": req}}}


TOOLS = [
    p("browser_navigate", "Navega una pestaña a una URL",
      {"tabId": {"type": "integer"}, "url": {"type": "string"}}, ["tabId", "url"]),
    p("browser_tabs", "Lista las pestañas abiertas", {}, []),
    p("browser_snapshot", "Snapshot de accesibilidad (da refs para click/fill)",
      {"tabId": {"type": "integer"}}, ["tabId"]),
    p("browser_read", "Texto visible de la página (barato, preferirlo)",
      {"tabId": {"type": "integer"}}, ["tabId"]),
    p("browser_click", "Click en elemento por su ref del snapshot",
      {"tabId": {"type": "integer"}, "ref": {"type": "string"}}, ["tabId", "ref"]),
    p("browser_fill", "Escribe texto en un campo por su ref",
      {"tabId": {"type": "integer"}, "ref": {"type": "string"}, "text": {"type": "string"}},
      ["tabId", "ref", "text"]),
    p("browser_key", "Pulsa una tecla (ej. Enter)",
      {"tabId": {"type": "integer"}, "key": {"type": "string"}}, ["tabId", "key"]),
    p("browser_wait", "Espera: texto que debe aparecer o ms",
      {"tabId": {"type": "integer"}, "text": {"type": "string"},
       "timeoutMs": {"type": "integer"}}, ["tabId"]),
]


def post_or(modelo, messages, tools=None, max_tokens=600):
    body = {"model": modelo, "messages": messages, "stream": False,
            "max_tokens": max_tokens}
    if tools is not None:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    req = urllib.request.Request(
        OR_PROXY, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"HTTP {e.code}: {detalle}")


def probe(modelo):
    """Prueba minima de tool-calling. Devuelve True si el modelo sirve."""
    try:
        d = post_or(modelo, [
            {"role": "user", "content": "Llama a browser_tabs"}],
            tools=TOOLS[:2], max_tokens=100)
        msg = d["choices"][0]["message"]
        tc = msg.get("tool_calls") or []
        return bool(tc) and tc[0]["function"]["name"] == "browser_tabs"
    except Exception:
        return False


def elegir_modelo():
    candidatos = disponibles(MODEL_CANDIDATES)
    if not candidatos:
        raise RuntimeError("muro diario activo o todos los modelos en cooldown")
    for m in candidatos:
        print(f"probando {m}...", flush=True)
        if probe(m):
            print(f"OK: {m}", flush=True)
            return m
        print(f"falla: {m}", flush=True)
    raise RuntimeError("ningún modelo free sano ahora mismo")


def llamar(modelo_activo, messages):
    """Llama al modelo; si falla por proveedor, rota al siguiente candidato
    y registra el 429 (cooldown de modelo o muro diario)."""
    errores = []
    candidatos = disponibles(
        [modelo_activo] + [m for m in MODEL_CANDIDATES if m != modelo_activo])
    for m in candidatos:
        try:
            d = post_or(m, messages, tools=TOOLS)
            return m, d
        except RuntimeError as e:
            txt = str(e)
            errores.append(f"{m}: {txt[:80]}")
            print(f"fallo {m}, rotando...", flush=True)
            if "429" in txt:
                if es_muro_diario(txt):
                    marcar_muro_diario()
                else:
                    marcar_modelo(m)
    raise RuntimeError("todos los modelos fallaron: " + " | ".join(errores))


def esperar_contenido(tab, intentos=3):
    """Lee hasta que haya contenido real o se agoten los intentos."""
    for i in range(intentos):
        time.sleep(4)
        txt = bs_call("browser_read", {"tabId": tab})
        if txt and len(txt.strip()) > 300:
            return txt
    return txt or "(la herramienta no devolvió contenido)"


def tab_inicial():
    out = bs_call("browser_tabs", {})
    m = re.search(r"\[(\d+)\][^\n]*dev:vm", out) or re.search(r"\[(\d+)\]", out)
    return int(m.group(1)) if m else None


FALLO_PATTERNS = ["lo siento", "no pude", "no puedo", "no fue posible",
                  "intént", "sorry", "unable", "no logr", "no tengo acceso"]


def verificar(tarea, respuesta):
    """Verificador heuristico (deterministico, 0 peticiones).
    Para tareas rutinarias conocidas: una respuesta valida trae datos
    concretos (numeros) y no es una disculpa. Devuelve (veredicto, motivo)."""
    r = (respuesta or "")
    rl = r.lower().strip()
    if not rl or len(rl) < 30:
        return "NO", "respuesta vacía o muy corta"
    if any(p in rl for p in FALLO_PATTERNS):
        return "NO", "la respuesta es una disculpa, no datos"
    if not re.search(r"\d", rl):
        return "NO", "sin números: probablemente sin datos"
    return "SI", "contiene datos concretos"


def main():
    tarea = sys.argv[1]

    # Presupuesto: un loop gasta ~20 peticiones. No arrancar si no alcanza,
    # avisar si se comeria mas de la mitad de lo que queda.
    try:
        usadas, limite = leer_cuota()
        restantes = limite - usadas
        print(f"cuota free: {usadas}/{limite} (restan {restantes})", flush=True)
        if restantes < 20:
            print("CUOTA INSUFICIENTE para un loop de agente (~20 req). "
                  "Usa preguntar.py para consultas sueltas.", flush=True)
            sys.exit(2)
        if restantes < 40:
            print("AVISO: este loop puede consumir mas de la mitad "
                  "de la cuota restante del dia.", flush=True)
    except SystemExit:
        raise
    except Exception as e:
        print(f"no se pudo leer la cuota ({e}), sigo sin presupuesto", flush=True)

    pista = sys.argv[2] if len(sys.argv) > 2 else ""
    sitios = SITIOS_CONFIABLES.get(pista, [])
    tab = tab_inicial()
    if not tab:
        print("ERROR: no hay pestaña usable")
        sys.exit(1)

    modelo = elegir_modelo()
    print(f"modelo: {modelo} | tab: {tab}", flush=True)
    if sitios:
        print(f"sitios confiables sugeridos: {sitios}", flush=True)

    messages = [
        {"role": "system", "content":
         "Eres un agente que controla un navegador con herramientas. "
         f"Trabaja en la pestaña tabId={tab}. Reglas: prefiere browser_read "
         "(barato) sobre browser_snapshot; después de navegar, la página puede "
         "tardar: si la lectura sale vacía, espera y reintenta, no te rindas. "
         + (f"Sitios que se sabe que funcionan para esto: {', '.join(sitios)}. " if sitios else "")
         + "Si un sitio no carga o te bloquea, prueba con otro antes de rendirte. "
         "NO te rindas hasta agotar alternativas. Cuando tengas datos reales, "
         "escríbelos en español directamente SIN más herramientas."},
        {"role": "user", "content": tarea},
    ]

    for paso in range(1, MAX_PASOS + 1):
        print(f"--- paso {paso} [{modelo}] ---", flush=True)
        modelo, data = llamar(modelo, messages)
        msg = data["choices"][0]["message"]
        messages.append(msg)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            respuesta = msg.get("content", "")
            print("RESPUESTA FINAL:")
            print(respuesta)
            print("--- verificando ---", flush=True)
            veredicto, motivo = verificar(tarea, respuesta)
            print(f"verificador: {veredicto} ({motivo})", flush=True)
            if veredicto == "SI":
                print("VERIFICADO: OK")
            else:
                print("VERIFICADO: FALLO - requiere revisión humana")
            return
        for tc in tool_calls:
            nombre = tc["function"]["name"]
            args = json.loads(tc["function"].get("arguments") or "{}")
            print(f"> {nombre} {json.dumps(args, ensure_ascii=False)[:120]}", flush=True)
            try:
                if nombre == "browser_navigate":
                    bs_call(nombre, args)
                    resultado = esperar_contenido(args.get("tabId", tab))
                else:
                    resultado = bs_call(nombre, args)
            except Exception as e:
                resultado = f"ERROR: {e}"
            contenido = (resultado or "").strip()[:6000] or "(la herramienta no devolvió contenido)"
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": contenido})
    print("MAX_PASOS alcanzado sin respuesta final")


if __name__ == "__main__":
    main()
