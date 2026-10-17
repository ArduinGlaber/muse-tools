"""Registro propio de usos de OpenRouter (para contrastar con el contador oficial).

Cada peticion que sale hacia openrouter.ai se registra en un JSONL diario:
~/workspace/openrouter-free/uso-AAAA-MM-DD.jsonl con {ts, modelo, status}.
"""
import json
import os
from datetime import datetime, timezone

DIR = os.path.dirname(os.path.abspath(__file__))


def _ruta_hoy():
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(DIR, f"uso-{hoy}.jsonl")


def registrar(modelo, status):
    """Registra una peticion. status: codigo HTTP devuelto (o 'error')."""
    with open(_ruta_hoy(), "a") as f:
        f.write(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "modelo": modelo,
            "status": status,
        }) + "\n")


def cuenta_hoy():
    """Devuelve (total, c429) del dia UTC actual segun nuestro registro."""
    ruta = _ruta_hoy()
    total = c429 = 0
    if os.path.exists(ruta):
        with open(ruta) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                total += 1
                if e.get("status") == 429:
                    c429 += 1
    return total, c429


if __name__ == "__main__":
    total, c429 = cuenta_hoy()
    print(f"nuestra cuenta hoy: {total} peticiones, {c429} con 429")
