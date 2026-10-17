#!/bin/bash
# Supervisor del relay: lo mantiene con token fresco.
# - Reinicio proactivo cada 25 min (la rotacion del token es ~30-45 min)
# - Reinicio inmediato si el relay sale con codigo 42 (detectó 407 = token podrido)
# Cada arranque hereda el entorno fresco de este shell -> token actual.
LOG=~/workspace/openrouter-free/vigilar.log
while true; do
    timeout 1500 python3 /home/hatch/workspace/browspark/relay-proxy.py >> "$LOG" 2>&1
    code=$?
    echo "$(date -u '+%F %T') supervisor: relay salio con codigo $code, reiniciando" >> "$LOG"
    sleep 1
done
