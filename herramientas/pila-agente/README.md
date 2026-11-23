# pila-agente

Lazo agéntico ReAct (prototipo) sobre la pila free de
`pila-ahorro-free`: el modelo razona, usa herramientas y observa
resultados hasta dar una respuesta final o agotar los pasos. No gasta
cuota de Muse: cada llamada va por `preguntar.py`.

## Uso

```bash
python3 lazo.py "tarea a resolver" [--pasos 10] [--grupos 60]
```

- `--pasos N`: máximo de pasos ReAct (por defecto 10).
- `--grupos N`: default de grupos que revisa `buscar_grupos` en esa
  ejecución (por defecto 25; el tope lo lee de `mis-grupos.txt`).

## Cadena de modelos

Rápidos primero, lentos de respaldo, con pausa de 2,5 s entre llamadas
(30 RPM de Groq): Groq 120B → Nvidia → Zhipu → Cloudflare → Gemini →
DeepSeek → OpenRouter free → FreeAI. Cada llamada registra su cuota
vía los helpers (ver `herramientas/conectores-free/cuotas/`).

## Herramientas

| Herramienta | Qué hace |
|---|---|
| `shell` | Ejecuta un comando del sistema (con lista de bloqueo: `rm -rf /`, `mkfs`, `dd ... of=`, fork bomb, `shutdown`/`reboot`/`poweroff`) |
| `leer` | Lee un archivo (primeras 200 líneas) |
| `escribir` | Crea o sobrescribe un archivo |
| `subpregunta` | Delega una sub-pregunta a otro modelo de la pila |
| `buscar_web` | Busca en la web (DuckDuckGo, sin clave) |
| `leer_url` | Extrae el texto de una página web |
| `buscar_grupos` | Busca productos/anuncios en grupos de Facebook (vía `fb-watch/buscar_producto.py`) |
| `vigilancia_clientes` | Corre la vigilancia diaria de clientes (vía `fb-watch/vigilar_clientes.py`; **marca los hallazgos como vistos, igual que el cron**) |

Regla dura del sistema: si la tarea pide datos actuales, precios o
límites, el agente **debe** usar `buscar_web` (y `leer_url` si hace
falta) antes de responder. Nunca responde de memoria sobre el mundo
exterior. No repite una acción que ya falló igual.

## Requisitos

- `pila-ahorro-free` instalado y operativo (el lazo importa
  `preguntar.py` desde `~/workspace/openrouter-free`).
- `buscar_grupos` y `vigilancia_clientes` necesitan
  `~/workspace/fb-watch/` (`buscar_producto.py`,
  `vigilar_clientes.py`, `mis-grupos.txt`), que **no** va en este repo
  (depende del conector de Facebook del usuario). Sin él, el resto de
  herramientas funciona igual.
- Rutas asumidas: `/home/hatch/workspace/...` (estándar en la VM de Muse).
