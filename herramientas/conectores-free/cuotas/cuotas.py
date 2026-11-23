"""Seguimiento propio de cuotas free de Gemini, Groq, Cloudflare, Nvidia, Zhipu y Free.ai.

Cada peticion que sale hacia estos proveedores se registra en un JSONL diario:
~/workspace/cuotas/uso-AAAA-MM-DD.jsonl
con {ts, proveedor, modelo, status, in, out, neurons}.

Los limites free estan en limites.json (verificados 2026-10-18/19).

Uso:
    import cuotas
    cuotas.registrar("groq", "openai/gpt-oss-20b", 200, tokens_in=79, tokens_out=25)

    python3 cuotas.py   # muestra el resumen de hoy vs limites
"""
import json
import os
from datetime import datetime, timezone

DIR = os.path.dirname(os.path.abspath(__file__))
LIMITES_PATH = os.path.join(DIR, "limites.json")


def _ruta_hoy():
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(DIR, f"uso-{hoy}.jsonl")


def registrar(proveedor, modelo, status, tokens_in=0, tokens_out=0, neurons=0.0):
    """Registra una peticion. status: codigo HTTP (o 'error')."""
    with open(_ruta_hoy(), "a") as f:
        f.write(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "proveedor": proveedor,
            "modelo": modelo,
            "status": status,
            "in": tokens_in,
            "out": tokens_out,
            "neurons": neurons,
        }) + "\n")


def _leer_hoy():
    ruta = _ruta_hoy()
    eventos = []
    if os.path.exists(ruta):
        with open(ruta) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    eventos.append(json.loads(line))
                except Exception:
                    continue
    return eventos


def resumen():
    """Devuelve dict proveedor -> {peticiones, ok, e429, in, out, neurons} de hoy."""
    ag = {}
    for e in _leer_hoy():
        p = e.get("proveedor", "?")
        a = ag.setdefault(p, {"peticiones": 0, "ok": 0, "e429": 0,
                              "in": 0, "out": 0, "neurons": 0.0})
        a["peticiones"] += 1
        if e.get("status") == 200:
            a["ok"] += 1
        if e.get("status") == 429:
            a["e429"] += 1
        a["in"] += e.get("in", 0) or 0
        a["out"] += e.get("out", 0) or 0
        a["neurons"] += e.get("neurons", 0) or 0
    return ag


def _cargar_limites():
    try:
        with open(LIMITES_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def mostrar():
    lim = _cargar_limites()
    ag = resumen()
    print("Cuotas free hoy (UTC) vs limites:")
    print("-" * 60)
    for prov in ("gemini", "groq", "cloudflare", "nvidia", "zhipu", "freeai"):
        a = ag.get(prov, {"peticiones": 0, "ok": 0, "e429": 0,
                          "in": 0, "out": 0, "neurons": 0.0})
        L = lim.get(prov, {})
        if prov == "cloudflare":
            usado = a["neurons"]
            tope = L.get("neuronas_dia", "?")
            print(f"  {prov:10s} {a['peticiones']:4d} pet | "
                  f"{usado:8.1f}/{tope} neurons "
                  f"({a['e429']} x 429)")
        else:
            usado = a["peticiones"]
            tope = L.get("rpd", "?")
            print(f"  {prov:10s} {usado:4d}/{tope} pet/dia | "
                  f"tokens in={a['in']} out={a['out']} "
                  f"({a['e429']} x 429)")
    print("-" * 60)
    print("Nota: esto cuenta solo lo que sale de nuestros helpers. "
          "Si usas la misma clave en otro lado, el proveedor ve mas.")


if __name__ == "__main__":
    mostrar()
