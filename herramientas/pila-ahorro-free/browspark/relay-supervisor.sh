#!/bin/bash
# Supervisor del relay: lo mantiene vivo.
# Solo reinicia si el proceso MUERE (crash) o sale con codigo 42 (407 del
# upstream). Ya no hay reinicio proactivo por tiempo: si el relay responde
# 200 y esta sano, se deja correr.
#
# 2026-10-18 (anti-tormenta): si el puerto 3130 ya esta ocupado por OTRO
# relay-proxy vivo, el supervisor NO gira generando hijos muertos con
# EADDRINUSE: espera con gracia y sale. El 18/10 04:28-11:32 UTC un relay
# colgado mantuvo el puerto (rechazando TCP) y el supervisor genero 317
# hijos muertos en rafagas de ~1/s, llenando el log. Causa raiz del giro:
# reintento ciego ante cualquier codigo de salida, sin verificar el puerto.
# El vigilar.sh (cada 5 min) reintenta el arranque cuando el puerto se libere.
LOG=~/workspace/openrouter-free/vigilar.log
RELAY=/home/hatch/workspace/browspark/relay-proxy.py
PORT=3130

# 0 = puerto ocupado (acepta TCP), 1 = libre
puerto_ocupado() {
    (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null
}

# Espera con gracia a que se libere el puerto (el relay viejo puede tardar
# en morir tras el TERM del vigilar). Devuelve 0 si se libero, 1 si sigue
# ocupado tras la espera.
esperar_puerto() {
    local i
    for i in $(seq 1 15); do
        puerto_ocupado || return 0
        sleep 1
    done
    puerto_ocupado && return 1 || return 0
}

if ! esperar_puerto; then
    HOLDER=$(pgrep -f "[r]elay-proxy.py" | tr '\n' ' ')
    echo "$(date -u '+%F %T') supervisor: puerto $PORT ocupado por otro relay (pid: $HOLDER), saliendo sin duplicar" >> "$LOG"
    exit 0
fi

CONSEC=0
while true; do
    INICIO=$(date +%s)
    python3 "$RELAY" >> "$LOG" 2>&1
    code=$?
    DUR=$(($(date +%s) - INICIO))
    [ "$DUR" -lt 5 ] && CONSEC=$((CONSEC + 1)) || CONSEC=0
    if puerto_ocupado; then
        # El puerto quedo en manos de otro: reintentar no sirve, salir.
        HOLDER=$(pgrep -f "[r]elay-proxy.py" | tr '\n' ' ')
        echo "$(date -u '+%F %T') supervisor: hijo salio con codigo $code pero el puerto sigue ocupado por otro relay (pid: $HOLDER), saliendo" >> "$LOG"
        exit 0
    fi
    # Backoff en bucles de crash rapidos: evita spam de ~1/s en el log.
    ESPERA=1
    [ "$CONSEC" -ge 5 ] && ESPERA=30
    [ "$CONSEC" -ge 10 ] && ESPERA=120
    echo "$(date -u '+%F %T') supervisor: relay salio con codigo $code (vida ${DUR}s), reiniciando en ${ESPERA}s" >> "$LOG"
    sleep "$ESPERA"
done
