"""Cazador deterministico v1: extrae datos estructurados de una pagina web
gastando 0 peticiones del modelo en el camino feliz.

Flujo: navegar -> volcar texto -> regex (0 req) -> OCR si hace falta (0 req)
-> solo si todo falla, 1 llamada al modelo para leer/sintetizar.

Uso:
  cazar.py "tarea" --url URL --extraer precio,stock [--ocr] [--tab N]

El modo agente completo (agent_free.py) queda para tareas multi-paso.
"""
import base64
import json
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, "/home/hatch/workspace/browspark")
sys.path.insert(0, "/home/hatch/workspace/openrouter-free")
from browspark import call as bs_call
from extraer import extraer, mejor
from modelos import leer_cuota
from agent_free import tab_inicial, esperar_contenido, verificar

MCP = "http://127.0.0.1:9223/mcp"
SID_FILE = "/tmp/browspark-sid.txt"


def screenshot_a_archivo(tab, destino="/tmp/caza.png"):
    """Screenshot via MCP crudo; guarda el PNG y devuelve su ruta."""
    with open(SID_FILE) as f:
        sid = f.read().strip().split("=", 1)[-1]
    payload = {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
               "params": {"name": "browser_screenshot",
                          "arguments": {"tabId": tab, "format": "png"}}}
    req = urllib.request.Request(
        MCP, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "Mcp-Session-Id": sid}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read().decode("utf-8", "ignore")
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if line.startswith("{"):
            d = json.loads(line)
            for c in d.get("result", {}).get("content", []):
                if c.get("type") == "image" and c.get("data"):
                    with open(destino, "wb") as f:
                        f.write(base64.b64decode(c["data"]))
                    return destino
    return None


def ocr(ruta):
    try:
        out = subprocess.run(
            ["tesseract", ruta, "stdout", "-l", "spa+eng"],
            capture_output=True, text=True, timeout=120)
        return out.stdout
    except Exception as e:
        return f"(OCR no disponible: {e})"


def main():
    if len(sys.argv) < 2 or "--url" not in sys.argv:
        print(__doc__)
        sys.exit(1)
    tarea = sys.argv[1]
    url = sys.argv[sys.argv.index("--url") + 1]
    tipos = []
    if "--extraer" in sys.argv:
        tipos = sys.argv[sys.argv.index("--extraer") + 1].split(",")
    usar_ocr = "--ocr" in sys.argv
    tab = None
    if "--tab" in sys.argv:
        tab = int(sys.argv[sys.argv.index("--tab") + 1])

    sin_cuota = False
    try:
        usadas, limite = leer_cuota()
        restantes = limite - usadas
        print(f"cuota free: {usadas}/{limite} (restan {restantes})", flush=True)
        if restantes < 1:
            # El camino feliz cuesta 0 peticiones; solo se pierde el escalado.
            print("SIN CUOTA: solo extracción determinística, "
                  "sin escalado al modelo.", flush=True)
            sin_cuota = True
    except Exception as e:
        print(f"no se pudo leer la cuota ({e}), sigo", flush=True)

    tab = tab or tab_inicial()
    if not tab:
        print("ERROR: no hay pestaña usable")
        sys.exit(1)
    print(f"navegando a {url} ...", flush=True)
    bs_call("browser_navigate", {"tabId": tab, "url": url})
    texto = esperar_contenido(tab)
    print(f"texto volcado: {len(texto)} chars", flush=True)

    datos = extraer(texto, tipos) if tipos else {}
    hallados = {k: v for k, v in datos.items() if v}
    if not hallados and usar_ocr:
        print("regex sin hallazgos, probando OCR...", flush=True)
        ruta = screenshot_a_archivo(tab)
        if ruta:
            texto_ocr = ocr(ruta)
            print(f"OCR: {len(texto_ocr)} chars", flush=True)
            datos = extraer(texto_ocr, tipos)
            hallados = {k: v for k, v in datos.items() if v}
            if hallados:
                texto = texto_ocr

    if hallados:
        print("EXTRACCIÓN DETERMINÍSTICA (0 peticiones al modelo):")
        for t, vals in hallados.items():
            print(f"  {t}: {mejor(texto, t, vals)}  (candidatos: {vals[:5]})")
        veredicto, motivo = verificar(
            tarea, " ".join(f"{k}={v}" for k, v in hallados.items()))
        print(f"verificador: {veredicto} ({motivo})")
        return

    # Escalado: 1 llamada al modelo con el texto ya volcado
    if sin_cuota:
        print("sin cuota: no se escala al modelo. Fin.", flush=True)
        return
    print("extracción sin hallazgos, escalando al modelo (1 petición)...",
          flush=True)
    sys.path.insert(0, "/home/hatch/workspace/openrouter-free")
    from preguntar import preguntar
    prompt = (f"Tarea: {tarea}\nDatos a extraer: {', '.join(tipos)}\n\n"
              f"Texto de la página:\n{texto[:8000]}")
    modelo, resp = preguntar(prompt, 800, tipo="texto")
    print(f"[modelo: {modelo}]")
    print(resp)
    veredicto, motivo = verificar(tarea, resp)
    print(f"verificador: {veredicto} ({motivo})", flush=True)


if __name__ == "__main__":
    main()
