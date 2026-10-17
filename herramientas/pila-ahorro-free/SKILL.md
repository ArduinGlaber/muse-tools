# Ahorro de cuota con modelos free

Deriva el trabajo mecánico a modelos gratuitos de OpenRouter y Pollinations
sin gastar tu cuota de Muse. Todo pasa por un proxy fail-closed que bloquea
cualquier modelo de pago.

## Cuándo usarlo

- Deriva a los modelos free borradores, resúmenes, código simple, extracción
  de datos y clasificación. Son tareas donde un error se detecta fácil.

- Mantén en tu cuota razonar, planificar, depurar, matemática, verificar lo
  que produjo el free y todo lo que sale a un cliente o cuesta dinero si
  sale mal.

- El patrón es: el free redacta, tú verificas. Si el usuario dice "hazlo tú
  directo", usa tu cuota sin discutir.

## Requisito previo (una vez)

- El usuario crea una cuenta en OpenRouter y guarda su API key en tu bóveda
  con el conector `custom.openrouter` (placement `bearer_header`, host
  `openrouter.ai`). Lee `custom-connectors/CONNECTOR.md` para el setup.

- Nunca pongas la clave en archivos, código o chat. El proxy la inyecta
  desde la bóveda.

## Arrancar los servicios

- Ejecuta con `muse.exec` en background: `python3 proxy.py` (puerto 8123),
  `python3 browspark/relay-proxy.py` (puerto 3130) y
  `bash browspark/start-browspark.sh` (companion en 9223).

- El proxy solo permite modelos terminados en `:free` y responde 403 a todo
  lo demás. Verifícalo pidiendo un modelo de pago y esperando el 403.

- El relay inyecta la autenticación del proxy de salida y bloquea
  rastreadores de publicidad para que las páginas carguen más rápido y no
  disparen permisos en el teléfono del usuario.

## Consultas sueltas (barato: 1 a 2 peticiones)

- Ejecuta `python3 preguntar.py "tu prompt" [max_tokens]`. Prueba modelos
  por orden de capacidad y usa el primero sano.

- Si OpenRouter se agota o todo está en cooldown, cae solo a Pollinations
  gratis (`pollinations/openai-fast`), respetando su límite de 1 petición
  cada 15 segundos. La salida indica el modelo con `[modelo: ...]`.

- Revisa el uso del fallback con `python3 preguntar.py --ver-fallback`.

## Lotes (ahorro máximo: N tareas = 1 petición)

- El free cuenta por petición, no por tokens. Acumula subtareas independientes
  con `python3 lote.py agregar "prompt" [tipo]` (tipos: codigo, texto, razonar)
  y dispáralas con `python3 lote.py enviar`: una sola petición numerada.

- El router elige el mejor modelo según el tipo dominante del lote. Revisa
  con `python3 lote.py ver`, descarta con `python3 lote.py limpiar`.

- Úsalo para trabajo mecánico en volumen: secciones de informe, textos,
  extracciones. No para tareas encadenadas ni urgentes.

## Caza determinística (búsquedas web: 0 a 1 petición)

- Para extraer datos estructurados de una página conocida, usa
  `python3 browspark/cazar.py "tarea" --url URL --extraer precio,stock`.
  Navega, vuelca el texto y extrae con regex: 0 peticiones al modelo.

- Si el dato está en imagen, agrega `--ocr`: screenshot a Tesseract
  (`spa+eng`) y regex sobre el texto. Solo si todo falla escala al modelo
  con 1 petición.

- Los patrones viven en `browspark/extraer.py` (precio, temperatura,
  porcentaje, fecha, hora, teléfono, email, stock). Amplíalos con el uso.

- El agente completo `browspark/agent_free.py` queda para tareas multi-paso
  no rutinarias.

## Navegación web (agente completo)

- Ejecuta `python3 browspark/agent_free.py "tarea" [pista_sitio]`. El agente
  prueba modelos con tool-calling real y rota ante fallos.

- Úsalo solo para tareas rutinarias y conocidas. Para cosas nuevas usa tu
  navegador integrado.

- El script chequea la cuota al arrancar: no inicia si restan menos de 20
  peticiones y avisa si consumiría más de la mitad de lo restante.

- El verificador es heurístico y determinístico (datos concretos presentes,
  sin disculpas) y no gasta peticiones.

## Disciplina de cuota

- Ejecuta `python3 cuota.py` antes y después de cada tarea derivada e
  informa al usuario el delta.

- El registro propio `uso.py` audita el contador oficial de OpenRouter, que
  va con retraso.

- Si OpenRouter devuelve 429, avisa al usuario de inmediato indicando en qué
  número de petición cayó según tu cuenta y según la oficial.

- El muro diario real cae alrededor de 53/50, no exacto en 50. Los 429 por
  modelo llegan antes: rota en vez de rendirte.

## Lecciones vivas

- Agrega lo que aprendas con `python3 leccion.py "título" "texto"`. Consulta
  con `python3 leccion.py --ver` y el documento completo con `--todo`.

- Lee `LECCIONES.md` antes de operar la pila por primera vez.

## Available connectors

- [Openrouter](custom-connectors/CONNECTOR.md) for the vaulted API key that the proxy injects into every request.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
