#!/bin/bash
# Guardian de la pila free: verifica proxy :8123, relay :3130 y companion :9223.
# Reinicia lo que este caido. Pensado para correr cada 5 min via cron.
LOG=~/workspace/openrouter-free/vigilar.log
ok=1

if ! curl -s -m 5 http://127.0.0.1:8123/v1/models -o /dev/null; then
    echo "$(date -u '+%F %T') proxy caido, reiniciando" >> "$LOG"
    cd ~/workspace/openrouter-free && nohup python3 proxy.py >> "$LOG" 2>&1 & disown
    ok=0
fi
if ! curl -s -m 10 -x http://127.0.0.1:3130 https://example.com -o /dev/null; then
    # Reintento antes de declarar caído (evita falsos positivos por lentitud)
    sleep 5
    if ! curl -s -m 10 -x http://127.0.0.1:3130 https://example.com -o /dev/null; then
        echo "$(date -u '+%F %T') relay caido, reiniciando supervisor" >> "$LOG"
        pkill -f "[r]elay-supervisor.sh" 2>/dev/null
        pkill -f "[r]elay-proxy.py" 2>/dev/null
        # Esperar a que libere el puerto antes de arrancar el nuevo
        for i in $(seq 1 10); do
            (echo > /dev/tcp/127.0.0.1/3130) 2>/dev/null || break
            sleep 1
        done
        # El supervisor arranca con el entorno fresco de este shell
        nohup bash /home/hatch/workspace/browspark/relay-supervisor.sh >> "$LOG" 2>&1 & disown
        ok=0
    fi
fi
if ! curl -s -m 5 http://127.0.0.1:9223/mcp -o /dev/null; then
    echo "$(date -u '+%F %T') companion caido, reiniciando" >> "$LOG"
    bash ~/workspace/browspark/start-browspark.sh >> "$LOG" 2>&1
    ok=0
fi
[ $ok -eq 1 ] || echo "$(date -u '+%F %T') restauracion intentada" >> "$LOG"
