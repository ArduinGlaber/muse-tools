# pila-ahorro-free

Deriva trabajo mecánico a modelos de IA gratuitos de OpenRouter sin gastar
la cuota de Muse. Todo pasa por un proxy fail-closed que bloquea cualquier
modelo de pago (imposible gastar por error).

## Requisito previo (una vez)

1. Crea una cuenta en https://openrouter.ai y genera una API key.
2. Guárdala en la bóveda de Muse como conector `custom.openrouter`
   (placement `bearer_header`, host `openrouter.ai`). Ver
   `custom-connectors/CONNECTOR.md`.
3. El tier gratuito da ~50 peticiones/día (verificado: el muro real cae en
   ~53/50). Con 10 créditos comprados sube a 1000/día.

## Arranque (cada día / tras reinicio de VM)

```bash
# 1. Proxy fail-closed (inyecta tu clave, solo permite :free) -> :8123
python3 proxy.py &

# 2. Relay para el navegador (auth del proxy de salida + bloquea trackers) -> :3130
python3 browspark/relay-proxy.py &

# 3. Browspark (navegador del agente) -> :9223
bash browspark/start-browspark.sh
```

## Uso diario

```bash
# Pregunta suelta a un modelo free (rota por capacidad, con cooldown;
# cae a Pollinations gratis si OpenRouter se agota)
python3 preguntar.py "tu prompt"

# Agente de navegación (tareas rutinarias; gasta ~20 req, chequea presupuesto)
python3 browspark/agent_free.py "tarea" [pista_sitio]

# Cuota: chequear antes/después de cada tarea derivada
python3 cuota.py

# Lecciones: documento vivo, se actualiza con cada aprendizaje
python3 leccion.py "título" "texto"
python3 leccion.py --ver
```

## Política de enrutamiento

- Al free: borradores, resúmenes, código simple, extraer datos, clasificar.
- A la cuota de Muse: razonar, planificar, depurar, verificar lo del free,
  todo lo que sale a un cliente o cuesta dinero si sale mal.
- Patrón: el free redacta, Muse verifica.

## Detalles

Ver `LECCIONES.md` (lecciones operativas: el muro, economía barato/caro,
cooldown de modelos, disciplina de cuota, Pollinations como fallback, etc.).

Rutas asumidas: `/home/hatch/workspace/...` (estándar en la VM de Muse) y
`sys.path` a `/opt/muse/skills/custom-connector-setup/bin` para
`dynamic_credentials` (lectura de la bóveda).
