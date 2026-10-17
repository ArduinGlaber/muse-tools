"""Gestiona LECCIONES.md (documento vivo).

Uso:
  python3 leccion.py "titulo" "texto"  -> agrega leccion fechada al Registro
  python3 leccion.py --ver             -> muestra el Registro de lecciones
  python3 leccion.py --todo            -> muestra el documento completo
"""
import datetime
import sys

P = "/home/hatch/workspace/openrouter-free/LECCIONES.md"
MARCADOR = "## Registro de lecciones\n"


def agregar(titulo, texto):
    hoy = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    linea = f"- {hoy}: **{titulo}** — {texto}\n"
    with open(P) as f:
        src = f.read()
    if MARCADOR not in src:
        src = src.rstrip() + "\n\n" + MARCADOR + "\n"
    src = src.replace(MARCADOR, MARCADOR + "\n" + linea, 1)
    with open(P, "w") as f:
        f.write(src)
    print("lección agregada")


def ver(todo=False):
    with open(P) as f:
        src = f.read()
    if todo:
        print(src)
    else:
        i = src.find(MARCADOR)
        print(src[i:] if i >= 0 else "(sin registro aún)")


def main():
    if sys.argv[1] == "--ver":
        ver()
    elif sys.argv[1] == "--todo":
        ver(todo=True)
    else:
        agregar(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
