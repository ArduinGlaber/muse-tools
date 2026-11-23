# DeepSeek web — token y procedimiento de refresco

Cliente: `~/workspace/openrouter-free/deepseek-web.py`
Token: `~/.config/deepseek-usertoken` (permisos 600). NUNCA mostrarlo,
imprimirlo ni registrarlo en logs o memoria.

## Cómo se obtuvo (verificado 2026-10-18)
El token es el `userToken` que chat.deepseek.com guarda en el
localStorage del navegador donde el usuario inició sesión con su
cuenta de Google. El usuario lo extrajo desde su teléfono con el
truco de `javascript:` en la barra de direcciones y lo pegó en el
chat; se guardó en el archivo y se validó con una consulta de prueba.

La extracción automática desde el navegador integrado FALLÓ el
2026-10-18 (no permite leer cookies/localStorage): no perder tiempo
reintentándola a ciegas.

## Si el token vence (síntoma: la API rechaza la autenticación al
crear la sesión; NO confundir con deriva de formato, ver LECCIONES.md
2026-10-20)
1. Avisar al usuario con estos pasos exactos:
   - Abrir chat.deepseek.com en su navegador, sesión iniciada.
   - Extraer el `userToken` del localStorage (mismo truco de la
     vez pasada) y pegarlo en el chat.
2. Al recibirlo: escribirlo en `~/.config/deepseek-usertoken`
   (sin mostrarlo), validar con:
   `python3 deepseek-web.py "Responde unicamente: OK"` y también
   una prueba con `--search`.
3. Avisar al usuario que DeepSeek quedó funcionando.

## Diagnóstico rápido de fallos
- "respuesta inesperada" con code 0 y sesión creada = deriva de
  formato de la API: revisar qué campo espera el cliente contra la
  respuesta real y corregir con fallback (precedente: 2026-10-20).
- HTTP 401/403 o mensaje de autenticación = token vencido o inválido.
- Timeout/conexión = red o egress; reintentar antes de concluir.

## Notas 2026-11-15 (refresco del token vencido el 9/11)
- Chrome 155 en Android BLOQUEA los `javascript:` por completo: ni
  el marcador con prompt() ni el de innerHTML hicieron nada al
  tocarlos. La extracción automática desde el navegador integrado
  también falló (hCaptcha imposible de resolver en 2 h).
- Opera en Android funcionó a la primera con el mismo truco.
- El marcador tiene que estar en la carpeta "Marcadores", NO en
  "Lista de lectura": en la Lista de lectura el campo URL sale
  desactivado y no se puede editar.
- El valor de localStorage "userToken" es un JSON
  `{"value":"...","__version":"0"}`: el script usa como Bearer el
  "value" crudo (64 caracteres), NO el JSON entero.
