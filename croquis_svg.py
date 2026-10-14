"""
croquis_svg.py
--------------
Renderiza croquis SVG con valores dinámicos.

El SVG tiene <text id="..."> con valores placeholder (0, M1, etc.).
Esta función reemplaza el contenido de esos textos con valores reales.

Hay 3 tipos de croquis, cada uno con su SVG en assets/:
  - Cruz → assets/croquis_cruz.svg  (4 ramas: N, S, E, O)
  - T    → assets/croquis_T.svg     (3 ramas: S, O, E — sin Norte)
  - Ruta → assets/croquis_ruta.svg  (2 extremos, ida y vuelta)
"""

import re


# Tabla de destinos de la CRUZ (misma lógica que croquis.py)
DESTINO = {
    ("N", "FTE"): "S", ("N", "IZQ"): "O", ("N", "DER"): "E",
    ("S", "FTE"): "N", ("S", "IZQ"): "O", ("S", "DER"): "E",
    ("E", "FTE"): "O", ("E", "IZQ"): "N", ("E", "DER"): "S",
    ("O", "FTE"): "E", ("O", "IZQ"): "N", ("O", "DER"): "S",
}

# Tabla de destinos de la T (no existe rama Norte; los giros imposibles
# tienen destino None y se ignoran en el cálculo de salidas).
DESTINO_T = {
    ("S", "IZQ"): "O", ("S", "FTE"): None, ("S", "DER"): "E",
    ("O", "IZQ"): None, ("O", "FTE"): "E", ("O", "DER"): "S",
    ("E", "IZQ"): "S", ("E", "FTE"): "O", ("E", "DER"): None,
}

RAMAS_T = ("S", "O", "E")

# Slots que el SVG de la T dibuja pero que no existen como movimiento
# (flechas tachadas): se muestran siempre con guión.
SLOTS_INVALIDOS_T = {"S_FTE", "O_IZQ", "E_DER"}

# Posiciones válidas para mapear movimientos en cada tipo de croquis.
POSICIONES_T = ["S_IZQ", "S_DER", "O_FTE", "O_DER", "E_IZQ", "E_FTE"]
POSICIONES_RUTA = ["O_IZQ", "O_FTE"]

# Orden canonico de las 12 posiciones de la cruz. Lo usan los selectores
# de mapeo de la app (mismo orden que croquis.py).
ORDEN_CANONICO = [
    "N_IZQ", "N_FTE", "N_DER",
    "S_IZQ", "S_FTE", "S_DER",
    "E_IZQ", "E_FTE", "E_DER",
    "O_IZQ", "O_FTE", "O_DER",
]

GUION = chr(8212)  # — (se usa en slots inválidos / vacíos)


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


def _normalizar_ancho_svg(svg: str) -> str:
    """Fuerza width=100% / height=auto en la raíz <svg> para que escale
    dentro del contenedor de Streamlit (croquis_ruta.svg trae píxeles fijos)."""
    def _fix(m):
        tag = m.group(0)
        tag = re.sub(r'width="[^"]*"', 'width="100%"', tag, count=1)
        tag = re.sub(r'height="[^"]*"', 'height="auto"', tag, count=1)
        return tag
    return re.sub(r'<svg\b[^>]*>', _fix, svg, count=1)


def _cargar_svg(ruta_svg: str) -> str:
    """Lee el SVG y normaliza su ancho para render responsivo."""
    with open(ruta_svg, "r", encoding="utf-8") as f:
        return _normalizar_ancho_svg(f.read())


def leer_svg_esquema(ruta_svg: str) -> str:
    """Lee un SVG tal cual (sin reemplazar valores) para mostrarlo como
    esquema de referencia. Normaliza el ancho."""
    return _cargar_svg(ruta_svg)


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


def calcular_entradas_salidas_T(volumenes, mapeo):
    """
    Igual que calcular_entradas_salidas pero para la T: solo ramas
    S, O, E; los movimientos en slots inválidos se ignoran y los giros
    con destino None (DESTINO_T) no suman salida.
    Devuelve (entradas, salidas) — dict {rama: int}.
    """
    datos = {r: {"IZQ": 0, "FTE": 0, "DER": 0} for r in RAMAS_T}
    for mov, pos in mapeo.items():
        if "_" not in pos or pos in SLOTS_INVALIDOS_T:
            continue
        rama, dir_ = pos.split("_", 1)
        if rama in datos and dir_ in datos[rama]:
            datos[rama][dir_] = volumenes.get(mov, 0)

    entradas = {r: sum(datos[r].values()) for r in datos}

    salidas = {r: 0 for r in datos}
    for rama, dirs in datos.items():
        for d, val in dirs.items():
            destino = DESTINO_T[(rama, d)]
            if destino is not None:
                salidas[destino] += val

    return entradas, salidas


def renderizar_svg_cruz(volumenes, mapeo, nombres_ramas,
                        ruta_svg="assets/croquis_cruz.svg"):
    """
    Lee el SVG de la cruz y reemplaza los valores dinámicos.
    Calcula automáticamente las entradas/salidas.
    """
    svg = _cargar_svg(ruta_svg)

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


def renderizar_svg_T(volumenes, mapeo, nombres_ramas,
                     ruta_svg="assets/croquis_T.svg"):
    """
    Lee el SVG de la T y reemplaza los valores dinámicos.
    - Slots inválidos (S_FTE, O_IZQ, E_DER) → siempre guión "—".
    - Slots válidos sin movimiento mapeado → también guión.
    - Entradas/salidas según DESTINO_T (sin rama Norte).
    """
    svg = _cargar_svg(ruta_svg)

    entradas, salidas = calcular_entradas_salidas_T(volumenes, mapeo)

    # Invertir el mapeo: slot → movimiento (solo slots válidos de la T)
    slot_a_mov = {}
    for mov, pos in mapeo.items():
        if pos in POSICIONES_T:
            slot_a_mov[pos] = mov

    for rama in RAMAS_T:
        for dir_ in ("IZQ", "FTE", "DER"):
            slot = f"{rama}_{dir_}"
            mov = slot_a_mov.get(slot)
            if slot in SLOTS_INVALIDOS_T or mov is None:
                svg = _reemplazar_texto(svg, f"{slot}_nombre", GUION)
                svg = _reemplazar_texto(svg, f"{slot}_volumen", GUION)
            else:
                svg = _reemplazar_texto(svg, f"{slot}_nombre", mov)
                svg = _reemplazar_texto(
                    svg, f"{slot}_volumen", str(volumenes.get(mov, 0))
                )

    for rama in RAMAS_T:
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


def renderizar_svg_ruta(volumenes, mapeo, nombres_extremos,
                        ruta_svg="assets/croquis_ruta.svg"):
    """
    Lee el SVG de la ruta (ida y vuelta) y reemplaza los valores.
    Solo tiene 2 slots: O_IZQ y O_FTE — qué movimiento va en cada uno
    se decide por `mapeo` (no se hardcodean nombres de movimiento).
    `nombres_extremos` = {"O": extremo oeste, "E": extremo este}.
    No calcula entradas/salidas (el SVG no tiene esos textos).
    """
    svg = _cargar_svg(ruta_svg)

    slot_a_mov = {pos: mov for mov, pos in mapeo.items()
                  if pos in POSICIONES_RUTA}

    for slot in POSICIONES_RUTA:
        mov = slot_a_mov.get(slot)
        if mov is None:
            svg = _reemplazar_texto(svg, f"{slot}_nombre", GUION)
            svg = _reemplazar_texto(svg, f"{slot}_volumen", GUION)
        else:
            svg = _reemplazar_texto(svg, f"{slot}_nombre", mov)
            svg = _reemplazar_texto(
                svg, f"{slot}_volumen", str(volumenes.get(mov, 0))
            )

    svg = _reemplazar_texto(
        svg, "O_calle_nombre", nombres_extremos.get("O", "")
    )
    svg = _reemplazar_texto(
        svg, "E_calle_nombre", nombres_extremos.get("E", "")
    )

    return svg
