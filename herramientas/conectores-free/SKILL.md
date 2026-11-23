# Conectores de APIs gratuitas

Siete conectores de modelos gratuitos que alimentan `pila-ahorro-free`:
Groq, Gemini, Cloudflare, Zhipu, FreeAI, OpenRouter y Nvidia. Cada uno
vive en `custom.<proveedor>/` con su `CONNECTOR.md`, su `connector.yaml`
y sus helpers en `bin/`. Las claves viven en la bóveda de Muse; los
helpers las piden vía `dynamic_credentials` y nunca las ven en claro.

## Cuándo usarlo

- Para llamar a un modelo free concreto desde un script o para probar
  el acceso a un proveedor antes de usarlo en `preguntar.py`.
- Para registrar el uso: cada helper anota su petición en
  `~/workspace/cuotas/uso-AAAA-MM-DD.jsonl` vía `cuotas.py`.
- No uses estos helpers para razonar o verificar nada delicado: son la
  vía barata; lo que sale a un cliente o cuesta dinero si sale mal va
  por tu cuota.

## Requisito previo (una vez por proveedor)

- Lee el `CONNECTOR.md` del proveedor y registra la conexión con
  `credentials.request_api_access` usando sus datos exactos (provider,
  auth_scheme, placement, api_hosts).
- Antes del primer cambio en una conversación, prueba el acceso con su
  `test_*.py` y un prompt inofensivo (`Responde solo con la palabra: OK`).
- Nunca pongas una clave, token o ID de cuenta en un archivo, en código,
  en un argumento o en el chat. Cloudflare: el Account ID va en la
  variable `CLOUDFLARE_ACCOUNT_ID` o en `~/.config/cloudflare-account`.

## Llamadas

- Cada helper es `python3 bin/test_<proveedor>.py "prompt" [modelo]
  [cuenta_cloudflare]` e imprime un JSON (`http`, `model`, `reply`,
  `finish_reason`, `usage`). `http` 200 con `reply` no vacío = éxito.
- Modelos por defecto: Groq `openai/gpt-oss-120b` (código) y
  `openai/gpt-oss-20b` (el 20B no es fiable en código); Gemini
  `gemini-2.5-flash`; Cloudflare
  `@cf/meta/llama-3.3-70b-instruct-fp8-fast`; Zhipu `glm-4.7-flash`;
  FreeAI `qwen7b`; Nvidia `z-ai/glm-5.3-flash`.
- Cloudflare envía `max_tokens` 4096: sin él la API corta a ~256 tokens.
- No reintentes un helper que devuelve 429 o 5xx en bucle: anota el
  error y pasa al siguiente proveedor de la cadena.

## Estado conocido (2026-11-23)

- **Nvidia caído**: las sondas con timeout hasta 300 s nunca responden.
  La cadena (`preguntar.py`) ya lo salta; no lo uses hasta verificar
  que vuelve.
- **Gemini**: `gemini-2.5-flash`. El 3.8-flash daba 503 y los 2.0/1.5
  están retirados (404).
- **Cloudflare**: el auto-descubrimiento del Account ID vía
  GET /accounts no funciona con token de alcance limitado (lista vacía).

## Cuotas

- Revisa el uso con `python3 ~/workspace/cuotas/cuotas.py` antes y
  después de una tanda. Los límites están en `cuotas/limites.json`
  (verificados 2026-10-18/19; re-verificar cada pocos meses).
- OpenRouter free: ~50 peticiones/día (el muro real cae en ~53/50).
- Si un proveedor devuelve 429, avisa al usuario indicando en qué
  número de petición cayó según tu cuenta y según la oficial.

## Available connectors

- Use `muse.connector_search` to find other connectors and
  `muse.skill_search` to find related skills.
