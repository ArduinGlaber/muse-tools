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
        # ¿Es el relay o el egress? Si el egress directo responde, el culpable
        # es el relay; si tampoco responde, es el egress y reiniciar no ayuda.
        EGRESS="${https_proxy:-$http_proxy}"
        if [ -n "$EGRESS" ] && curl -s -m 10 -x "$EGRESS" https://example.com -o /dev/null; then
            # Diagnóstico en el momento del fallo (para saber POR QUÉ cae)
            RPID=$(pgrep -f "[r]elay-proxy.py" | head -1)
            HILOS=$(ls /proc/$RPID/task 2>/dev/null | wc -l)
            MEM=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
            TCP="no"
            (echo > /dev/tcp/127.0.0.1/3130) 2>/dev/null && TCP="si"
            echo "$(date -u '+%F %T') relay caido (egress OK), reiniciando supervisor [diag: pid=$RPID hilos=$HILOS mem_kb=$MEM tcp=$TCP]" >> "$LOG"
            pkill -f "[r]elay-supervisor.sh" 2>/dev/null
            pkill -f "[r]elay-proxy.py" 2>/dev/null
            # Esperar a que libere el puerto antes de arrancar el nuevo
            for i in $(seq 1 10); do
                (echo > /dev/tcp/127.0.0.1/3130) 2>/dev/null || break
                sleep 1
            done
            # El supervisor arranca con el entorno fresco de este shell
            nohup bash /home/hatch/workspace/browspark/relay-supervisor.sh >> "$LOG" 2>&1 & disown
        else
            echo "$(date -u '+%F %T') egress lento, relay no reiniciado (se reintenta en 5 min)" >> "$LOG"
        fi
        ok=0
    fi
fi
# Comportamiento anormal: el relay responde pero con fuga de hilos/FDs
# (firma del bug corregido; si reaparece, se reinicia)
RPID=$(pgrep -f "[r]elay-proxy.py" | head -1)
if [ -n "$RPID" ]; then
    HILOS=$(ls /proc/$RPID/task 2>/dev/null | wc -l)
    if [ "$HILOS" -gt 50 ]; then
        echo "$(date -u '+%F %T') relay con $HILOS hilos (anormal), reiniciando supervisor" >> "$LOG"
        pkill -f "[r]elay-supervisor.sh" 2>/dev/null
        pkill -f "[r]elay-proxy.py" 2>/dev/null
        for i in $(seq 1 10); do
            (echo > /dev/tcp/127.0.0.1/3130) 2>/dev/null || break
            sleep 1
        done
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
