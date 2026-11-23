# Zhipu

- `custom.zhipu` conecta Muse con Zhipu AI (plataforma internacional z.ai) a través de su API compatible con OpenAI. Se autentica con la credencial `api_key` registrada y solo llama a `api.z.ai`.

- Los helpers están en `~/workspace/custom-connectors/custom.zhipu/bin/`. `test_zhipu.py` envía un prompt a un modelo y devuelve el JSON con `http`, `reply`, `finish_reason` y `usage`; registra la llamada en `~/workspace/cuotas/cuotas.py`.

## Conexión

- La conexión se registró con `credentials.request_api_access` con estos detalles. Reutilízalos sin cambios para reconectar:

```json
{
  "provider": "zhipu",
  "auth_scheme": "api_key",
  "placement": "bearer_header",
  "api_hosts": ["api.z.ai"]
}
```

- Endpoint base: `https://api.z.ai/api/paas/v4` (documentación oficial: docs.z.ai). La clave se obtiene en `z.ai/manage-apikey/apikey-list` tras crear la cuenta en z.ai.

## Credenciales

- La conexión registrada guarda la credencial. Los helpers importan `/opt/muse/skills/custom-connector-setup/bin/dynamic_credentials.py`, que devuelve un surrogate `hsurr:` y lo coloca donde el proveedor lee la clave. Muse sustituye la credencial real solo en peticiones aprobadas a un host registrado.

- Nunca pongas una clave, token, contraseña o cookie en este doc, un helper, un argumento, una variable de entorno o un log. Nunca pidas al usuario que pegue una en el chat.

- Mantén las redirecciones desactivadas en las peticiones autenticadas.

- Ante un 401 o 403, revisa primero la petición. Confirma que el helper adjuntó la credencial, que el host está registrado y que el placement coincide.

- Solo cuando una petición que llevaba la credencial siga siendo rechazada, llama a `credentials.request_api_access` con los detalles de arriba y `"reconnect": true`.

## Chat completion

- Envía un prompt a un modelo GLM y devuelve la respuesta. Úsalo para preguntas de texto, razonamiento o código dentro de la pila free.

```text
python3 ~/workspace/custom-connectors/custom.zhipu/bin/test_zhipu.py "tu prompt" "glm-4.7-flash"
```

- El segundo argumento (modelo) es opcional; por defecto usa `glm-4.7-flash`, gratis en entrada y salida. Otros modelos gratuitos: `glm-4.6v-flash` (visión). La salida JSON incluye `http`, `model`, `reply`, `finish_reason` y `usage`.

## Recuperarse de errores

- Un 401 significa clave inválida o ausente. Revisa que el helper adjuntó la credencial y que el host `api.z.ai` está registrado.

- Un 429 con código `1305` significa que el servicio está temporalmente sobrecargado, no que hayas agotado tu cuota. No reintentes en bucle; deja que el failover de la pila pase al siguiente proveedor.

- Tras un fallo o timeout, no repitas la misma petición sin cambios.

## Límites

- La clave gratuita no necesita tarjeta. Los modelos Flash (`glm-4.7-flash`, `glm-4.6v-flash`) son gratis; el resto de modelos consumen saldo de la cuenta.

- Límite documentado: 1 petición concurrente.

- Verificación del 2026-10-19: la clave autentica correctamente (sin 401), pero el endpoint devolvió 429/1305 por sobrecarga temporal. Pendiente confirmar un 200 cuando el servicio se despeje.

## Skills relacionadas

- Usa `muse.skill_search` para encontrar skills y `muse.connector_search` para encontrar otros conectores.
