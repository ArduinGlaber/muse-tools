# conectores-free

Los conectores de APIs gratuitas que usa `pila-ahorro-free` para derivar
trabajo sin gastar la cuota de Muse. Cada conector vive en su carpeta
`custom.<proveedor>/` con su `CONNECTOR.md` (setup y credenciales), su
`connector.yaml` y sus helpers en `bin/`. Las claves **nunca** van en el
repo: viven en la bóveda de Muse y los helpers las piden vía
`dynamic_credentials` (surrogate `hsurr:`), que solo se resuelve en una
petición aprobada al host registrado.

`cuotas/` es el registro propio de uso: `cuotas.py` anota cada petición
en `uso-AAAA-MM-DD.jsonl` y `limites.json` guarda los límites free
verificados (re-verificar cada pocos meses: los proveedores los cambian
sin aviso).

## Conectores

| Proveedor | Modelo usado | Helper | Estado (2026-11-23) |
|---|---|---|---|
| Groq | `openai/gpt-oss-120b` (código) / `openai/gpt-oss-20b` | `custom.groq/bin/test_groq.py` | Sano; el 20B no es fiable en código |
| Gemini | `gemini-2.5-flash` | `custom.gemini/bin/test_gemini.py` | Sano (3.8-flash daba 503) |
| Cloudflare | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | `custom.cloudflare/bin/test_cloudflare.py` | Sano; `max_tokens` 4096 (antes cortaba a ~256) |
| Zhipu | `glm-4.7-flash` | `custom.zhipu/bin/test_zhipu.py` | Sano |
| FreeAI | `qwen7b` | `custom.freeai/bin/test_freeai.py` | Sano; `bin/clonar_voz.py` clona voz |
| OpenRouter | modelos `:free` | `custom.openrouter/bin/test_free.py` | Sano; ~50 req/día en tier free |
| Nvidia | `z-ai/glm-5.3-flash` | `custom.nvidia/bin/test_nvidia.py` | **Caído** (sondas hasta 300 s sin respuesta; la cadena lo salta) |

## Instalación

```bash
# 1. Copiar los conectores y el registro de cuotas a tu workspace
cp -r herramientas/conectores-free/custom.* ~/workspace/custom-connectors/
cp -r herramientas/conectores-free/cuotas ~/workspace/cuotas/

# 2. Registrar cada conexión con su CONNECTOR.md (clave en bóveda,
#    nunca en archivos): los detalles de cada proveedor están en su
#    sección "Connect" (provider, auth_scheme, placement, api_hosts).
```

## Uso

```bash
# Prueba de acceso (lo primero antes de cambiar nada en una conversación)
python3 ~/workspace/custom-connectors/custom.groq/bin/test_groq.py "Responde solo con la palabra: OK"
python3 ~/workspace/custom-connectors/custom.gemini/bin/test_gemini.py "Responde solo con la palabra: OK"
python3 ~/workspace/custom-connectors/custom.cloudflare/bin/test_cloudflare.py "Responde solo con la palabra: OK" "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
python3 ~/workspace/custom-connectors/custom.zhipu/bin/test_zhipu.py "Responde solo con la palabra: OK" "glm-4.7-flash"
python3 ~/workspace/custom-connectors/custom.freeai/bin/test_freeai.py "Responde solo con la palabra: OK" "qwen7b"
python3 ~/workspace/custom-connectors/custom.nvidia/bin/test_nvidia.py "Responde solo con la palabra: OK" "z-ai/glm-5.3-flash"
python3 ~/workspace/custom-connectors/custom.openrouter/bin/test_free.py "Responde solo con la palabra: OK"

# Resumen de uso de hoy contra los límites
python3 ~/workspace/cuotas/cuotas.py
```

Cada helper imprime un JSON con `http`, `model`, `reply`, `finish_reason`
y `usage`, y registra la petición en `~/workspace/cuotas/` automáticamente.

## Cloudflare: el Account ID no va en el código

`test_cloudflare.py` acepta el Account ID como tercer argumento; si no
se pasa, intenta descubrirlo vía GET /accounts, pero eso **no funciona**
con un token de alcance limitado (devuelve lista vacía, verificado
2026-11-23). Ponlo en la variable `CLOUDFLARE_ACCOUNT_ID` o en
`~/.config/cloudflare-account` (modo 600). `preguntar.py` ya lo lee de
ahí (`herramientas/pila-ahorro-free/preguntar.py`).

## Rutas asumidas

`/home/hatch/workspace/...` (estándar en la VM de Muse) y `sys.path` a
`/opt/muse/skills/custom-connector-setup/bin` para `dynamic_credentials`
(lectura de la bóveda).
