# Cómo contribuir

## Agregar una herramienta

1. Crea la carpeta `herramientas/<nombre-de-tu-herramienta>/` (minúsculas,
   guiones, sin espacios).
2. Pon ahí tu código y un `README.md` con, como mínimo:
   - **Qué hace** (1-2 párrafos)
   - **Requisitos** (cuentas, claves, software)
   - **Uso** (comandos de ejemplo que funcionen)
3. Agrega un `SKILL.md` + `skill.yaml` en formato skill de Muse, escrito
   para que otro Muse lo instale y lo opere sin ayuda humana: qué hace, cuándo
   usarlo, comandos exactos, qué verificar y dónde están los límites.
   Instalación: copiar la carpeta a `~/workspace/custom-skills/<nombre>/`.
4. Agrega tu herramienta a la tabla del `README.md` principal.
5. Abre un PR con una descripción breve de qué aporta.

## Reglas (no negociables)

- **Cero secretos en el código.** Nada de API keys, tokens, contraseñas ni
  credenciales en ningún archivo del repo — ni siquiera de ejemplo con
  formato real. Las credenciales viven en la bóveda de Muse; el README
  explica cómo configurarlas, no las contiene.
- **Rutas portables.** La VM de Muse usa `/home/hatch/workspace/...`;
  evita rutas de tu máquina local fuera de ese esquema o documenta cómo
  adaptarlas.
- **Un README que funcione.** Si un tercero no puede ponerla a andar
  siguiendo tu README, el PR no se acepta.
- **Licencia.** Todo lo aquí publicado se considera MIT salvo que la
  herramienta indique otra licencia en su carpeta.

## Sugerencias

- Scripts pequeños y enfocados ganan sobre frameworks grandes.
- Si tu herramienta aprende con el uso (límites, quirks), incluye un
  documento de lecciones como `LECCIONES.md`.
