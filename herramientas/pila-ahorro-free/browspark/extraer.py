"""Extraccion deterministica de datos de texto web (0 peticiones al modelo).

Dado el texto volcado de una pagina, extrae datos estructurados por patrones.
Si el texto no trae el dato (esta en imagen), la rama OCR lo intenta.

Uso como modulo:
    from extraer import extraer
    extraer(texto, ["precio", "disponibilidad"])
    # -> {"precio": ["$24.79"], "disponibilidad": []}
"""
import re

# Cada tipo: lista de (nombre_grupo, patron). El primer grupo que capture manda.
PATRONES = {
    "precio": [
        r"\$\s?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)",
        r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s?(USD|CUP|EUR)",
    ],
    "temperatura": [
        r"(-?\d+)\s*°\s*([CF])",
        r"(-?\d+)\s*grados",
    ],
    "porcentaje": [
        r"(\d{1,3})\s*%",
    ],
    "fecha": [
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
    ],
    "hora": [
        r"(\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm|AM|PM)?)",
    ],
    "telefono": [
        r"(\+?\d[\d\s-]{6,}\d)",
    ],
    "email": [
        r"([\w.+-]+@[\w-]+\.[\w.]+)",
    ],
    "stock": [
        r"(?i)\b(en stock|in stock|disponible|available|agotado|out of stock|no disponible)\b",
    ],
}

# Palabras que acompanan al dato y ayudan a elegir el mejor candidato
CONTEXTO = {
    "precio": ["precio", "price", "total", "costo", "cost"],
    "temperatura": ["temperatura", "temperature", "temp", "sensación"],
}


def _candidatos(texto, patrones):
    vals = []
    for pat in patrones:
        for m in re.finditer(pat, texto):
            v = m.group(1).strip()
            if v and v not in vals:
                vals.append(v)
    return vals


def extraer(texto, tipos):
    """Devuelve dict {tipo: [valores]}. Vacio = no encontrado."""
    out = {}
    for t in tipos:
        pats = PATRONES.get(t)
        if not pats:
            out[t] = []
            continue
        out[t] = _candidatos(texto, pats)
    return out


def mejor(texto, tipo, candidatos):
    """Elige el candidato con mas contexto relevante cerca (ventana 120ch)."""
    if not candidatos:
        return None
    claves = CONTEXTO.get(tipo, [])
    if not claves:
        return candidatos[0]
    tl = texto.lower()
    mejor_v, mejor_n = candidatos[0], -1
    for v in candidatos:
        n = 0
        for m in re.finditer(re.escape(v.lower()), tl):
            ventana = tl[max(0, m.start() - 120):m.end() + 120]
            n += sum(1 for c in claves if c in ventana)
        if n > mejor_n:
            mejor_v, mejor_n = v, n
    return mejor_v
