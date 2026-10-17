"""Muestra la cuota free de OpenRouter: usadas / limite / restantes (dia)."""
import json, sys, urllib.request
sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

req = urllib.request.Request("https://openrouter.ai/api/v1/key")
add_surrogate_to_request(req, "custom.openrouter", allowed_hosts=["openrouter.ai"])
with urllib.request.urlopen(req, timeout=30) as r:
    d = read_json_response(r)["data"]

f = d["free_model_daily_requests"]
print(f"OpenRouter free: usadas {f['used']} / limite {f['limit']} / restantes {f['remaining']}")
print(f"free_tier: {d['is_free_tier']}")
