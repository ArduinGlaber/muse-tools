#!/bin/bash
# Guardian de la pila free: verifica proxy :8123, relay :3130 y companion :9223.
# Reinicia lo que este caido. Pensado para correr cada 5 min via cron.
# Lock: evita ejecuciones concurrentes (el chequeo puede tardar >5 min).
LOCK=/tmp/vigilar-pila-free.lock
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date -u '+%F %T') otra instancia en curso, saliendo" >> ~/workspace/openrouter-free/vigilar.log
    exit 0
fi
LOG=~/workspace/openrouter-free/vigilar.log
ok=1

# Lanzamientos de demonios: sub-shell que cierra el fd 9 del lock antes del
# exec + disown con job control (set -m). Sin esto el script quedaba colgado
# en do_wait al terminar: setsid(1) falla con EPERM cuando el subshell del &
# ya es lider de grupo de procesos (no desacopla nada, el demonio queda como
# hijo directo) y ademas el lock quedaba retenido por el fd 9 heredado por
# los demonios. Con set -m, disown si funciona.
set -m
if ! curl -s -m 5 http://127.0.0.1:8123/v1/models -o /dev/null; then
    echo "$(date -u '+%F %T') proxy caido, reiniciando" >> "$LOG"
    ( exec 9>&-; cd ~/workspace/openrouter-free && exec setsid nohup python3 proxy.py >> "$LOG" 2>&1 < /dev/null ) &
    disown
    ok=0
fi
FALLOS=~/workspace/openrouter-free/relay-fallos.count
[ -f "$FALLOS" ] || echo 0 > "$FALLOS"

# NOTA 2026-10-18: se ELIMINO la deteccion de "token roto" por comparacion.
# Cada proceso recibe un token DIFERENTE del egress (es por-proceso, no rota
# en el tiempo), y el egress acepta CUALQUIER auth. Comparar tokens entre
# procesos siempre da diferente -> bucle de reinicios. El token es irrelevante.

relay_ok=0
CURL_DIAG=""
# -f: los errores HTTP (502 del relay cuando el egress esta lento) cuentan como fallo
if curl -sf -m 10 -x http://127.0.0.1:3130 https://example.com -o /dev/null -w "%{http_code} %{time_total}s" > /tmp/relay-check-1.txt 2>&1; then
    relay_ok=1
else
    C1=$(cat /tmp/relay-check-1.txt 2>/dev/null); EC1=$?
    sleep 5
    if curl -sf -m 10 -x http://127.0.0.1:3130 https://example.com -o /dev/null -w "%{http_code} %{time_total}s" > /tmp/relay-check-2.txt 2>&1; then
        relay_ok=1
    else
        C2=$(cat /tmp/relay-check-2.txt 2>/dev/null)
        CURL_DIAG="curl1[$C1] curl2[$C2]"
    fi
fi

if [ "$relay_ok" = 1 ]; then
    echo 0 > "$FALLOS"
else
    # El relay no responde al chequeo completo. ¿Proceso muerto o transitorio?
    if (echo > /dev/tcp/127.0.0.1/3130) 2>/dev/null; then
        # Acepta TCP: el proceso vive. ¿Es el egress?
        EGRESS="${https_proxy:-$http_proxy}"
        if [ -n "$EGRESS" ] && ! curl -s -m 10 -x "$EGRESS" https://example.com -o /dev/null; then
            echo "$(date -u '+%F %T') egress lento, relay sin reiniciar" >> "$LOG"
            echo 0 > "$FALLOS"
        else
            # Transitorio probable: solo se reinicia si falla 2 ciclos seguidos
            N=$(($(cat "$FALLOS") + 1))
            echo "$N" > "$FALLOS"
            if [ "$N" -ge 2 ]; then
                RPID=$(pgrep -f "[r]elay-proxy.py" | head -1)
                HILOS=$(ls /proc/$RPID/task 2>/dev/null | wc -l)
                MEM=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
                echo "$(date -u '+%F %T') relay sin responder 2 ciclos (egress OK), reiniciando supervisor [diag: pid=$RPID hilos=$HILOS mem_kb=$MEM $CURL_DIAG]" >> "$LOG"
                pkill -f "[r]elay-supervisor.sh" 2>/dev/null
                pkill -f "[r]elay-proxy.py" 2>/dev/null
                for i in $(seq 1 10); do
                    (echo > /dev/tcp/127.0.0.1/3130) 2>/dev/null || break
                    sleep 1
                done
                if (echo > /dev/tcp/127.0.0.1/3130) 2>/dev/null; then
                    echo "$(date -u '+%F %T') relay no murio con TERM, aplicando KILL" >> "$LOG"
                    pkill -9 -f "[r]elay-proxy.py" 2>/dev/null; sleep 1
                fi
                ( exec 9>&-; exec setsid nohup bash /home/hatch/workspace/browspark/relay-supervisor.sh >> "$LOG" 2>&1 < /dev/null ) &
                disown
                echo 0 > "$FALLOS"
            else
                echo "$(date -u '+%F %T') relay transitorio (fallo $N/2), sin reinicio [$CURL_DIAG]" >> "$LOG"
            fi
        fi
    else
        # No acepta TCP: proceso muerto -> reinicio inmediato
        echo "$(date -u '+%F %T') relay no acepta TCP (muerto), reiniciando supervisor" >> "$LOG"
        pkill -f "[r]elay-supervisor.sh" 2>/dev/null
        pkill -f "[r]elay-proxy.py" 2>/dev/null
        for i in $(seq 1 10); do
            (echo > /dev/tcp/127.0.0.1/3130) 2>/dev/null || break
            sleep 1
        done
        if (echo > /dev/tcp/127.0.0.1/3130) 2>/dev/null; then
            echo "$(date -u '+%F %T') relay no murio con TERM, aplicando KILL" >> "$LOG"
            pkill -9 -f "[r]elay-proxy.py" 2>/dev/null; sleep 1
        fi
        ( exec 9>&-; exec setsid nohup bash /home/hatch/workspace/browspark/relay-supervisor.sh >> "$LOG" 2>&1 < /dev/null ) &
        disown
        echo 0 > "$FALLOS"
    fi
    ok=0
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
        if (echo > /dev/tcp/127.0.0.1/3130) 2>/dev/null; then
            echo "$(date -u '+%F %T') relay no murio con TERM, aplicando KILL" >> "$LOG"
            pkill -9 -f "[r]elay-proxy.py" 2>/dev/null; sleep 1
        fi
        ( exec 9>&-; exec setsid nohup bash /home/hatch/workspace/browspark/relay-supervisor.sh >> "$LOG" 2>&1 < /dev/null ) &
        disown
        ok=0
    fi
fi
if ! curl -s -m 5 http://127.0.0.1:9223/mcp -o /dev/null; then
    echo "$(date -u '+%F %T') companion caido, reiniciando" >> "$LOG"
    ( exec 9>&-; exec timeout 120 bash ~/workspace/browspark/start-browspark.sh >> "$LOG" 2>&1 )
    ok=0
fi
[ $ok -eq 1 ] || echo "$(date -u '+%F %T') restauracion intentada" >> "$LOG"
