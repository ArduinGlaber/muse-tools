"""Buffer de subtareas para el free tier (uso interno de Muse).

Acumula subtareas independientes y las dispara en UNA sola peticion,
agrupadas por tipo para que el router elija el mejor modelo.
El free cuenta por peticion, no por tokens: N tareas = 1 peticion.

Uso:
  lote.py agregar "prompt" [tipo]  (tipo: codigo|texto|razonar, defecto texto)
  lote.py ver
  lote.py enviar
  lote.py limpiar
"""
import json
import os
import re
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
from preguntar import preguntar  # noqa: E402

BUFFER = os.path.join(DIR, "lote-buffer.json")
MAX_CHARS = 800_000  # ~200K tokens, margen bajo los 262K de contexto


def _cargar():
    if os.path.exists(BUFFER):
        with open(BUFFER) as f:
            return json.load(f)
    return []


def _guardar(items):
    with open(BUFFER, "w") as f:
        json.dump(items, f, ensure_ascii=False)


def agregar(prompt, tipo="texto"):
    items = _cargar()
    items.append({"prompt": prompt, "tipo": tipo})
    _guardar(items)
    print(f"en buffer: {len(items)} tarea(s)")


def ver():
    items = _cargar()
    if not items:
        print("(buffer vacío)")
        return
    for i, it in enumerate(items, 1):
        print(f"{i}. [{it['tipo']}] {it['prompt'][:80]}")


def limpiar():
    _guardar([])
    print("buffer limpiado")


def enviar():
    items = _cargar()
    if not items:
        print("(buffer vacío, nada que enviar)")
        return
    total = sum(len(it["prompt"]) for it in items)
    if total > MAX_CHARS:
        print(f"lote muy grande ({total} chars > {MAX_CHARS}), "
              "parte en dos envíos")
        return
    # Tipo dominante -> router elige el mejor modelo para ese tipo
    tipos = [it["tipo"] for it in items]
    dominante = max(set(tipos), key=tipos.count)

    partes = ["Responde CADA punto de forma numerada e independiente, "
              "sin mezclarlos. Sé conciso en cada uno.\n"]
    for i, it in enumerate(items, 1):
        partes.append(f"\nPUNTO {i} [{it['tipo']}]:\n{it['prompt']}\n")
    mega = "".join(partes)
    max_tokens = min(8000, 1200 * len(items))

    modelo, texto = preguntar(mega, max_tokens, tipo=dominante)
    print(f"[modelo: {modelo}] [tareas: {len(items)}] [tipo: {dominante}]")
    # Partir por "PUNTO N" o lista numerada "N."
    trozos = re.split(r"(?m)^PUNTO (\d+).*?$", texto)
    if len(trozos) <= 2:
        trozos = re.split(r"(?m)^(\d+)[\.\)]\s+", texto)
    if len(trozos) > 2:
        for n, cuerpo in zip(trozos[1::2], trozos[2::2]):
            print(f"\n--- respuesta {n} ---")
            print(cuerpo.strip()[:2000])
    else:
        print(texto)
    _guardar([])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "agregar":
        agregar(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "texto")
    elif cmd == "ver":
        ver()
    elif cmd == "enviar":
        enviar()
    elif cmd == "limpiar":
        limpiar()
    else:
        print("uso: lote.py agregar|ver|enviar|limpiar")
