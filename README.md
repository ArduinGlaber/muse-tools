# muse-tools

Colección comunitaria de herramientas creadas por usuarios de Muse.
Cada herramienta vive en `herramientas/<nombre>/` con su propio README y su
`SKILL.md`: cualquier Muse la instala copiando la carpeta a
`~/workspace/custom-skills/<nombre>/` y puede operarla siguiendo el skill.

## Herramientas

| Herramienta | Qué hace | Autor |
|---|---|---|
| [pila-ahorro-free](herramientas/pila-ahorro-free/) | Deriva trabajo mecánico a modelos free de OpenRouter (proxy fail-closed, agente de navegación, disciplina de cuota) | [@ArduinGlaber](https://github.com/ArduinGlaber) |
| [conectores-free](herramientas/conectores-free/) | Conectores de APIs gratuitas (Groq, Gemini, Cloudflare, Zhipu, FreeAI, OpenRouter, Nvidia) con claves en la bóveda y registro propio de cuotas | [@ArduinGlaber](https://github.com/ArduinGlaber) |
| [pila-agente](herramientas/pila-agente/) | Lazo agéntico ReAct (prototipo) sobre la pila free: razona y usa herramientas sin gastar la cuota de Muse | [@ArduinGlaber](https://github.com/ArduinGlaber) |

## Agregar tu herramienta

Lee [CONTRIBUTING.md](CONTRIBUTING.md). En resumen: crea
`herramientas/<tu-herramienta>/` con un `README.md` (qué hace, requisitos,
uso) y sin secretos en el código (claves y tokens van en la bóveda de Muse,
nunca en el repo). Agrega tu fila a la tabla de arriba.
