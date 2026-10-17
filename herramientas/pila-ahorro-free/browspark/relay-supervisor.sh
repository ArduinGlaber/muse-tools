#!/bin/bash
# Supervisor del relay: lo mantiene vivo.
# Solo reinicia si el proceso MUERE (crash) o sale con codigo 42 (407 del
# upstream). Ya no hay reinicio proactivo por tiempo: si el relay responde
# 200 y esta sano, se deja correr.
LOG=~/workspace/openrouter-free/vigilar.log
while true; do
    python3 /home/hatch/workspace/browspark/relay-proxy.py >> "$LOG" 2>&1
    code=$?
    echo "$(date -u '+%F %T') supervisor: relay salio con codigo $code, reiniciando" >> "$LOG"
    sleep 1
done
