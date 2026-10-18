# Lecciones OpenRouter free + agente free (2026-10-16)

**Documento vivo**: se actualiza con cada cosa nueva que se aprende.
`leccion.py "titulo" "texto"` agrega al Registro; `leccion.py --ver` lo
muestra; `leccion.py --todo` muestra el documento completo. Los cambios
estructurales editan las secciones numeradas.

Todo lo aprendido construyendo la pila de ahorro. Reglas operativas, no notas.

## 1. El muro diario es real pero blando
- El 429 diario dice `Rate limit exceeded: free-models-per-day`.
- Cayó en **53/50** del contador oficial (nuestra cuenta: 57, 3 con 429).
- El contador oficial **va con retraso** respecto al real.
- Los 429 **por modelo** llegan antes que el muro (liquid se saturó en 40/50).
- Regla: un 429 solo es muro si el contador oficial está ≥49; si no, es de
  modelo → rotar. Implementado en `modelos.py` + `quemar.py`.

## 2. Economía: llamadas sueltas baratas, loops caros
- **Barato (1-2 req):** `preguntar.py` — borradores, resúmenes, extracción,
  clasificación, código simple.
- **Caro (~16-20 req):** `agent_free.py` — un loop de navegación se come el
  40% del día a 50/día.
- A 50/día: free para redactar sin límite práctico; agente solo para lo que
  valga la pena. A 1000/día (10 créditos) el cálculo cambia por completo.

## 3. Política de enrutamiento (decidida por el usuario)
- Al free: borradores, resúmenes, código simple, extraer datos, clasificar.
- A mi cuota: razonar, planificar, depurar, matemática, verificar lo del
  free, todo lo que sale a un cliente o cuesta dinero si sale mal.
- Patrón: el free redacta, yo verifico. Override: "hazlo tú directo" gana.

## 4. Cooldown de modelos (`modelos.py`)
- Modelo con 429 de modelo → cooldown 60 min (`cooldown-AAAA-MM-DD.json`).
- Muro diario detectado → se bloquea todo hasta el reset (~00:00 UTC).
- `preguntar.py` y `agent_free.py` filtran con `disponibles()` antes de pedir.
- `agent_free.py` además chequea presupuesto al arrancar: si restan <20 no
  arranca; si restan <40 avisa que se comería más de la mitad.

## 5. La lista de modelos free rota
- 16 modelos el 16/10, pero cambian. Nunca asumir la lista: sondear en
  runtime (`probe()` + fallback).
- Salud variable por momento: 429s, 502s (upstream saturado), algunos fingen
  tool-calling (laguna), inkling solo sirve en harnesses agénticos.

## 6. Seguridad: fail-closed, no promesas
- El proxy (`proxy.py`) **bloquea con 403** todo modelo que no sea `:free`.
  Verificado: `anthropic/claude-opus-5` → 403, `:free` → 200.
- Clave solo en bóveda (`custom.openrouter`, bearer_header). Nunca cruda en
  chat, archivos o código.

## 7. Disciplina de cuota (pedida por el usuario)
- `cuota.py`: chequear antes/después de cada tarea derivada, informar delta.
- `uso.py`: registro propio diario (modelo, status) para auditar el contador
  oficial.
- Regla 429: avisar de inmediato por WhatsApp "se agotó el free de
  OpenRouter" indicando en qué número cayó (mi cuenta vs la oficial).

## 8. Agente free de navegación (`~/workspace/browspark/agent_free.py`)
- Los free **no obedecen "responde SI/NO"** → verificador heurístico
  determinístico (datos concretos = números presentes, no disculpas). 0 req.
- Probe+fallback de modelos; espera con reintento tras navegar;
  `SITIOS_CONFIABLES` por tipo de tarea; anti-rendición (20 pasos).
- Quirk Cohere: tool_result vacío → 400; placeholder cuando vacío.
- Relay (`relay-proxy.py`): inyecta `Proxy-Authorization` (token rota;
  reiniciar si falla auth) **y bloquea rastreadores** (lista BLOCKED) —
  sin trackers no hay spam de permisos en el teléfono, páginas más rápidas,
  menos tokens.
- Política de navegación: rutinario conocido → agente free; nuevo → mi
  navegador integrado. Avisar antes cuando una tarea toque varios sitios
  nuevos (los permisos los genera la app, no se pueden agrupar).

## 9. Pi: no adoptado (decisión 16/10)
- Instalado y configurado, pero los free no lo manejan con fiabilidad
  (no completó crear un archivo en 280s). Reevaluar con 1000/día + modelo
  validado + necesidad concreta de background.

## 10. Infra Browspark (ver `~/TOOLS.md`)
- `bun x browspark-mcp@latest --http-only` (no existe `bunx`); MCP :9223.
- Chromium `/opt/meta-chromium/chrome`, headless, `--no-sandbox`,
  `--disable-dev-shm-usage`, `--ignore-certificate-errors`.
- `tabId` numérico; perfiles persistentes en `~/.browspark/profiles/`.

## Archivos
- `proxy.py` (fail-closed :8123), `cuota.py`, `uso.py`, `preguntar.py`,
  `modelos.py`, `quemar.py`, `LECCIONES.md` (este archivo)
- `~/workspace/browspark/`: `agent_free.py`, `browspark.py`,
  `relay-proxy.py`, `start-browspark.sh`
- `~/workspace/custom-connectors/custom.openrouter/CONNECTOR.md`

## Registro de lecciones

- 2026-10-17: **relay: sin reinicios proactivos** — Decision del usuario 17/10: no reiniciar el relay si responde 200 y esta sano. Se elimino el timeout 1500 del supervisor (la rotacion de token era falsa y la fuga esta corregida); el supervisor solo reinicia si el proceso muere. El guardian reinicia solo si no responde o si los hilos >50 (comportamiento anormal).

- 2026-10-17: **relay: fuga de hilos (causa real de las caidas)** — El relay moria cada ~30min NO por rotacion de token (el egress acepta cualquier auth, verificado) sino por fuga: al cerrar el cliente, un hilo quedaba bloqueado en recv() para siempre y el finally nunca cerraba el socket -> 400+ hilos/FDs y CLOSE-WAIT. Fix: cuando una direccion termina, shutdown+close de AMBOS sockets (libera al hilo gemelo) + timeout 120s de inactividad. Verificado: 50 tuneles keep-alive -> 0 fugas.

- 2026-10-17: **cazar.py: extraccion deterministica** — navegar->volcar texto->regex (0 req)->OCR Tesseract (0 req)->solo si falla, 1 llamada al modelo. Verificado: temperatura en timeanddate en 16s con 0 peticiones (vs 19min/~20req del agente). OCR rama verificada (screenshot->tesseract spa+eng->regex). Tesseract: apt install tesseract-ocr tesseract-ocr-spa.

- 2026-10-17: **lote.py: buffer de subtareas** — Acumula subtareas independientes y las dispara en 1 peticion (el free cuenta por peticion, no por tokens). Agrupa por tipo dominante para que el router elija el mejor modelo. Reutiliza preguntar.py (rotacion, cooldown, fallback Pollinations). Verificado: 2 tareas = 1 peticion.

- 2026-10-17: **Reset diario no es a las 00:00 UTC** — El 17/10 a las 09:00 UTC el contador seguia en 54/50 del dia anterior. El reseteo no ocurre a medianoche UTC; hora exacta por determinar (posible ventana movil de 24h).

- 2026-10-17: **Fallback Pollinations cableado** — preguntar.py ahora cae a pollinations/openai-fast cuando OpenRouter se agota o todo esta en cooldown. Verificado con 0/50: los 429 marcaron el muro y el fallback respondio.

- 2026-10-17: **Pollinations.ai como capa fallback** — Texto: solo 1 modelo anonimo (openai-fast/GPT-OSS 20B, con tools), sin clave, ~1 req/15s — muy lento para loops, sirve como overflow cuando OpenRouter esta agotado. Imagenes: Flux siempre gratis sin clave (~7s por 512px) — llena un hueco real (nuestra pila no genera imagenes). Estan migrando a sistema de clave+pollen; lo anonimo puede reducirse. Verificado 16/10.

- 2026-10-17: **primera lección real** — el registro funciona de extremo a extremo



## 2026-10-17: DeepSeek web como fuente free (reverse engineering completo)
- La API oficial de DeepSeek NUNCA es gratis; la web chat.deepseek.com si.
- El token esta en LocalStorage -> `userToken` (se extrae con bookmarklet en movil).
- Endpoint real: `POST /api/v0/chat/completion` (SINGULAR, no "completions").
- Payload: {chat_session_id (UUID, crear via POST /api/v0/chat_session/create con {}), parent_message_id, model_type:"default", prompt, ref_file_ids:[], thinking_enabled, search_enabled}.
- Auth: `Authorization: Bearer <userToken>`.
- BLOQUEO: requiere header `X-Ds-Pow-Response` (PoW DeepSeekHashV1, dificultad ~144000).
  - Flujo: POST /api/v0/chat/create_pow_challenge {target_path} -> challenge {algorithm, challenge, salt, signature, difficulty, expire_at}.
  - Solver: WASM sha3_wasm_bg.7b9ca65ddd.wasm, funcion wasm_solve(retptr, ch_ptr, ch_len, pf_ptr, pf_len, difficulty_f64), prefix=f"{salt}_{expire_at}_".
  - En Node.js funciona nativo; en Python el binding de memoria de wasmtime da problemas -> usar Node para el PoW.
  - Header: base64(JSON {algorithm, challenge, salt, signature, answer:int, target_path}).
- Respuesta: SSE con parches JSON: eventos `data: {"v":"texto"}` se acumulan; ignorar eventos con "p" que no sea content/fragments (ej. FINISHED).
- Scripts: deepseek-web.py (cliente), deepseek-pow.mjs (solver), sha3_wasm_bg.7b9ca65ddd.wasm.
- Token en ~/.config/deepseek-usertoken (600), NO en el repo.

## 2026-10-17 (noche): DeepSeek integrado a preguntar.py
- preguntar_deepseek() añadido como fallback 1 (despues de OpenRouter free, antes de Pollinations).
- Orden: OpenRouter free (legitimo, 50/dia) -> DeepSeek web (sin limite conocido, token propio) -> Pollinations (ultimo recurso).
- Para tipo="razonar" usa --think (modo DeepThink de la web).

## 2026-10-17 (noche): causa raiz de los timeouts del relay
- El slow-log mostro que el egress acepta TCP al instante pero no responde al CONNECT.
- Causa: el SUPERVISOR tenia un token viejo en su entorno (3d0d9627 vs dd6d8811 actual).
  Al reiniciar el relay, heredaba el entorno podrido. El egress no devuelve 407 con
  token podrido: simplemente no responde al CONNECT (cuelgue silencioso).
- Fix 1: al matar el relay, matar tambien el SUPERVISOR para que renazca con env fresco.
- Fix 2: relay-proxy.py ahora falla rapido (502 en 8s) si el egress no responde al CONNECT,
  en vez de colgar 15s. El peek bajo de 15s a 8s para que el 502 salga antes del timeout
  del cliente (10s).
- Fix 3: vigilar.sh usa curl -f para que un 502 cuente como fallo (antes pasaba como OK).
- Leccion: los reinicios manuales del relay deben matar el supervisor tambien, o el token
  podrido persiste. El guardian (cron) ya lo hace bien porque cada pasada tiene env fresco.

## 2026-10-18 (madrugada): token rota frecuentemente - deteccion proactiva
- El token del egress rota cada ~30-60 min. El relay lo cachea al arrancar; con token
  viejo el egress cuelga el CONNECT en silencio.
- Fix: vigilar.sh compara el token del proceso relay (/proc/PID/environ) con el actual.
  Si difieren, reinicia supervisor+relay INMEDIATAMENTE (sin esperar 2 fallos).
- Esto elimina el downtime entre rotacion y deteccion reactiva.

## 2026-10-18: el token es por-proceso, NO rota - eliminada deteccion
- Cada proceso nuevo recibe un token DIFERENTE del egress. No es rotacion temporal.
- El egress acepta CUALQUIER auth (verificado). El token es irrelevante.
- La "deteccion proactiva de token roto" comparaba tokens entre procesos -> siempre
  diferentes -> bucle de reinicios cada 5 min. ELIMINADA.
- Leccion: no asumir que un valor que cambia entre procesos es "rotacion".

## 2026-10-18: fix DeepSeek aplicado al relay (causa raiz)
- DIAGNOSTICO: la lectura de headers sin timeout dejaba hilos bloqueados por los
  preconnects de Chromium -> agotamiento de FDs -> accept() EMFILE sin try/except
  -> proceso moria -> sin SO_REUSEADDR -> "Address already in use" en bucle.
- FIX APLICADO: recv_until con deadline 10s, SO_REUSEADDR, accept() con backoff
  en EMFILE, semaforo BoundedSemaphore(200) + 503, RuntimeError en Thread.start().
- BUG PROPIO durante la aplicacion: recv_until devolvia el head CON el \r\n\r\n,
  generando lineas vacias que rompian los headers reenviados (el Proxy-Authorization
  quedaba como body). Fix: devolver head SIN el delimitador.
- La logica del tunel (peek, relay) se mantuvo intacta del original que funcionaba.
- Comparacion: DeepSeek dio diagnostico cerrado con codigo; OpenRouter (north-mini-code)
  solo brainstorming sin converger. DeepSeek gano.
