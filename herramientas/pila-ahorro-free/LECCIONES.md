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

- 2026-10-17: **Fallback Pollinations cableado** — preguntar.py ahora cae a pollinations/openai-fast cuando OpenRouter se agota o todo esta en cooldown. Verificado con 0/50: los 429 marcaron el muro y el fallback respondio.

- 2026-10-17: **Pollinations.ai como capa fallback** — Texto: solo 1 modelo anonimo (openai-fast/GPT-OSS 20B, con tools), sin clave, ~1 req/15s — muy lento para loops, sirve como overflow cuando OpenRouter esta agotado. Imagenes: Flux siempre gratis sin clave (~7s por 512px) — llena un hueco real (nuestra pila no genera imagenes). Estan migrando a sistema de clave+pollen; lo anonimo puede reducirse. Verificado 16/10.

- 2026-10-17: **primera lección real** — el registro funciona de extremo a extremo


