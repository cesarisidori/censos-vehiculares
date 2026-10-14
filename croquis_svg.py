"""
croquis_svg.py
--------------
Renderiza croquis SVG con valores dinámicos.

El SVG tiene <text id="..."> con valores placeholder (0, M1, etc.).
Esta función reemplaza el contenido de esos textos con valores reales.
"""

import re


# Tabla de destinos (misma lógica que croquis.py)
DESTINO = {
    ("N", "FTE"): "S", ("N", "IZQ"): "O", ("N", "DER"): "E",
    ("S", "FTE"): "N", ("S", "IZQ"): "O", ("S", "DER"): "E",
    ("E", "FTE"): "O", ("E", "IZQ"): "N", ("E", "DER"): "S",
    ("O", "FTE"): "E", ("O", "IZQ"): "N", ("O", "DER"): "S",
}


def _reemplazar_texto(svg: str, id_: str, nuevo_valor: str) -> str:
    """Reemplaza el contenido de un <text id="...">...</text>."""
    patron = (
        rf'(<text\b[^>]*\bid="{re.escape(id_)}"[^>]*>)'
        rf'(.*?)'
        rf'(</text>)'
    )
    return re.sub(
        patron,
        lambda m: m.group(1) + nuevo_valor + m.group(3),
        svg,
        count=1,
        flags=re.DOTALL,
    )


def calcular_entradas_salidas(volumenes, mapeo):
    """
    Calcula entradas y salidas por rama a partir de los volúmenes
    y el mapeo.
    Devuelve (entradas, salidas) — dict {rama: int}.
    """
    datos = {
        "N": {"IZQ": 0, "FTE": 0, "DER": 0},
        "S": {"IZQ": 0, "FTE": 0, "DER": 0},
        "E": {"IZQ": 0, "FTE": 0, "DER": 0},
        "O": {"IZQ": 0, "FTE": 0, "DER": 0},
    }
    for mov, pos in mapeo.items():
        if "_" not in pos:
            continue
        rama, dir_ = pos.split("_", 1)
        if rama in datos and dir_ in datos[rama]:
            datos[rama][dir_] = volumenes.get(mov, 0)

    entradas = {r: sum(datos[r].values()) for r in datos}

    salidas = {r: 0 for r in datos}
    for rama, dirs in datos.items():
        for d, val in dirs.items():
            salidas[DESTINO[(rama, d)]] += val

    return entradas, salidas


def renderizar_svg_cruz(volumenes, mapeo, nombres_ramas,
                        ruta_svg="assets/croquis_cruz.svg"):
    """
    Lee el SVG de la cruz y reemplaza los valores dinámicos.
    Calcula automáticamente las entradas/salidas.
    """
    with open(ruta_svg, "r", encoding="utf-8") as f:
        svg = f.read()

    # Calcular entradas/salidas
    entradas, salidas = calcular_entradas_salidas(volumenes, mapeo)

    # Reemplazar nombre y volumen de cada movimiento
    for mov, pos in mapeo.items():
        if "_" not in pos:
            continue
        rama, dir_ = pos.split("_", 1)
        val = volumenes.get(mov, 0)

        svg = _reemplazar_texto(svg, f"{rama}_{dir_}_nombre", mov)
        svg = _reemplazar_texto(svg, f"{rama}_{dir_}_volumen", str(val))

    # Reemplazar nombre de calle, entrada y salida por rama
    for rama in ("N", "S", "E", "O"):
        svg = _reemplazar_texto(
            svg, f"{rama}_calle_nombre",
            nombres_ramas.get(rama, "")
        )
        svg = _reemplazar_texto(
            svg, f"{rama}_entrada",
            f"Entrada: {entradas.get(rama, 0)}"
        )
        svg = _reemplazar_texto(
            svg, f"{rama}_salida",
            f"Salida: {salidas.get(rama, 0)}"
        )

    return svg
