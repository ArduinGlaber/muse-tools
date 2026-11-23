# Lazo agéntico ReAct sobre la pila free

Resuelve una tarea con un lazo ReAct que solo usa modelos gratuitos:
el modelo razona, usa una herramienta por turno y observa el resultado
hasta dar la respuesta final o agotar los pasos. No gasta cuota de Muse.

## Cuándo usarlo

- Tareas de varios pasos que se resuelven con búsqueda web, lectura de
  archivos y comandos, donde un solo `preguntar.py` no basta.
- Nunca para nada que salga a un cliente, cueste dinero si sale mal o
  necesite juicio fino: ahí va tu cuota, con verificación.
- `vigilancia_clientes` marca los hallazgos como vistos (igual que el
  cron diario): úsala solo cuando quieras ese efecto.

## Uso

- Ejecuta `python3 lazo.py "tarea" [--pasos 10] [--grupos 60]`.
  `--pasos` es el máximo de pasos ReAct (10 por defecto); `--grupos`
  es el default de grupos en `buscar_grupos` (25 por defecto).
- El agente responde con un bloque `accion` por turno
  (`{"herramienta": "...", "argumentos": {...}}`) o con la respuesta
  final sin bloque. Cada observación se trunca a 4000 caracteres.
- La cadena de modelos es: Groq 120B → Nvidia → Zhipu → Cloudflare →
  Gemini → DeepSeek → OpenRouter free → FreeAI, con pausa de 2,5 s
  entre llamadas. Estado conocido (2026-11-23): **Nvidia caído**, la
  cadena lo salta.

## Herramientas

- `shell` (con bloqueo de comandos destructivos), `leer` (200 líneas),
  `escribir`, `subpregunta`, `buscar_web` (DuckDuckGo, sin clave),
  `leer_url`, `buscar_grupos` y `vigilancia_clientes`.
- `buscar_grupos` y `vigilancia_clientes` dependen de
  `~/workspace/fb-watch/` (no incluido en el repo): sin él, devuelven
  error y el agente sigue con el resto.

## Límites

- Prototipo: sin memoria entre ejecuciones, sin reintento de pasos
  fallidos (la regla es no repetir una acción que falló igual) y con
  tope de 10 pasos.
- Los modelos free se equivocan: verifica el resultado antes de actuar
  sobre él, igual que con `preguntar.py`.
