"""Estado diario de modelos free: cooldown por 429 y lectura de cuota.

- Un modelo que da 429 de MODELO entra en cooldown 60 min.
- Si se detecta el muro DIARIO ("free-models-per-day"), se bloquea todo
  hasta el reset (~00:00 UTC).
- Los scripts filtran sus listas con disponibles() antes de pedir.
"""
import json
import os
import sys
import time
import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
COOLDOWN_MINUTOS = 60


def _hoy():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _path():
    return os.path.join(DIR, f"cooldown-{_hoy()}.json")


def _cargar():
    p = _path()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"modelos": {}, "muro_diario": None}


def _guardar(d):
    with open(_path(), "w") as f:
        json.dump(d, f)


def marcar_modelo(modelo):
    d = _cargar()
    d["modelos"][modelo] = time.time() + COOLDOWN_MINUTOS * 60
    _guardar(d)


def marcar_muro_diario():
    d = _cargar()
    d["muro_diario"] = time.time()
    _guardar(d)


def hay_muro():
    return bool(_cargar().get("muro_diario"))


def disponibles(modelos):
    """Devuelve la lista sin los modelos en cooldown. Vacía si hay muro."""
    if hay_muro():
        return []
    d = _cargar()
    ahora = time.time()
    return [m for m in modelos if d["modelos"].get(m, 0) < ahora]


def es_muro_diario(cuerpo):
    return "free-models-per-day" in (cuerpo or "")


def leer_cuota():
    """(usadas, limite) del contador oficial."""
    import urllib.request as ur
    sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
    from dynamic_credentials import add_surrogate_to_request, read_json_response
    req = ur.Request("https://openrouter.ai/api/v1/key")
    add_surrogate_to_request(req, "custom.openrouter", allowed_hosts=["openrouter.ai"])
    with ur.urlopen(req, timeout=30) as r:
        d = read_json_response(r)["data"]["free_model_daily_requests"]
    return d["used"], d["limit"]
