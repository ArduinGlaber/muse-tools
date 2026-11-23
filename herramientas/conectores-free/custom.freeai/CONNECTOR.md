# Free.ai

- `custom.freeai` conecta Muse con Free.ai (https://free.ai) a través de su API REST. Se autentica con la credencial `api_key` registrada (formato `sk-free-...`) y solo llama a `api.free.ai`.

- Los helpers están en `~/workspace/custom-connectors/custom.freeai/bin/`. `test_freeai.py` lista modelos o envía un prompt de chat y registra la llamada en `~/workspace/cuotas/cuotas.py`.

## Conexión

- La conexión se registró con `credentials.request_api_access` con estos detalles. Reutilízalos sin cambios para reconectar:

```json
{
  "provider": "freeai",
  "auth_scheme": "api_key",
  "placement": "bearer_header",
  "api_hosts": ["api.free.ai"]
}
```

- Endpoint base: `https://api.free.ai/v1` (documentación: https://free.ai/api). La clave se obtiene en free.ai tras crear la cuenta; empieza por `sk-free-`.

## Credenciales

- La conexión registrada guarda la credencial. Los helpers importan `/opt/muse/skills/custom-connector-setup/bin/dynamic_credentials.py`, que devuelve un surrogate `hsurr:` y lo coloca en el header `Authorization`. Muse sustituye la credencial real solo en peticiones aprobadas a un host registrado.

- Nunca pongas una clave, token, contraseña o cookie en este doc, un helper, un argumento, una variable de entorno o un log. Nunca pidas al usuario que pegue una en el chat.

- Mantén las redirecciones desactivadas en las peticiones autenticadas.

- Ante un 401 o 403, revisa primero la petición. Confirma que el helper adjuntó la credencial, que el host está registrado y que el placement coincide.

- Solo cuando una petición que llevaba la credencial siga siendo rechazada, llama a `credentials.request_api_access` con los detalles de arriba y `"reconnect": true`.

## Listar modelos

- Devuelve el catálogo de modelos disponibles (chat, imagen, vídeo, TTS, STT, traducción). No consume cuota de la API.

```text
python3 ~/workspace/custom-connectors/custom.freeai/bin/test_freeai.py
```

## Chat

- Envía un prompt a un modelo de chat. El endpoint es `POST /v1/chat/` (no es la ruta OpenAI `/v1/chat/completions`, aunque el cuerpo es similar).

```text
python3 ~/workspace/custom-connectors/custom.freeai/bin/test_freeai.py "tu prompt" "qwen7b"
```

- El segundo argumento (modelo) es opcional; por defecto usa `qwen7b` (Qwen 3.6 35B). Alternativa de código: `qwen-coder`. La salida JSON incluye `http`, `model`, `reply` y `usage`.

## Otros endpoints (sin probar)

- La API también ofrece: `POST /v1/image/generate/` (sdxl), `POST /v1/video/generate/`, `POST /v1/tts/` (kokoro, piper…), `POST /v1/stt/transcribe/` (whisper), `POST /v1/translate/`, `POST /v1/summarize/`. Todos comparten el free pool de tokens.

## Recuperarse de errores

- Un 401 significa clave inválida o ausente. Revisa que el helper adjuntó la credencial.

- Un 429 significa límite alcanzado (60 req/min o cuota mensual). Espera y reintenta; no lo pongas en bucle.

- Tras un fallo o timeout, no repitas la misma petición sin cambios.

## Límites

- Plan Free verificado el 2026-10-19: 30.000 tokens/día (free pool), 1.000 peticiones API/mes, 60 peticiones/minuto, 0 USD. Es un recurso escaso: en la pila va al final de la cadena, junto a OpenRouter.

- Verificación del 2026-10-19: `GET /v1/models` → 200 y `POST /v1/chat/` con `qwen7b` → 200 con respuesta correcta.

## Skills relacionadas

- Usa `muse.skill_search` para encontrar skills y `muse.connector_search` para encontrar otros conectores.
