"""
croquis_svg.py
--------------
Renderiza croquis SVG con valores dinámicos.

El SVG tiene <text id="..."> con valores placeholder (0, M1, etc.).
Esta función reemplaza el contenido de esos textos con valores reales.

Hay 4 variantes de croquis, cada una con su SVG en assets/:
  - Cruz     → assets/croquis_cruz.svg       (4 ramas: N, S, E, O)
  - T(sur)   → assets/croquis_T.svg          (3 ramas: S, O, E — sin Norte)
  - T(norte) → assets/croquis_T_norte.svg    (3 ramas: N, O, E — sin Sur)
  - Ruta     → assets/croquis_ruta.svg       (2 extremos, ida y vuelta)
"""

import re
import streamlit.components.v1 as components


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

# Tabla de destinos de la T(norte) (no existe rama Sur).
DESTINO_T_NORTE = {
    ("N", "IZQ"): "E", ("N", "FTE"): None, ("N", "DER"): "O",
    ("O", "IZQ"): "N", ("O", "FTE"): "E", ("O", "DER"): None,
    ("E", "IZQ"): None, ("E", "FTE"): "O", ("E", "DER"): "N",
}

RAMAS_T_NORTE = ("N", "O", "E")

# Slots que no existen como movimiento en la T. El SVG corregido ya NO los
# dibuja (no hay textos con esos ids). Se mantiene la constante porque la
# usan app.py (excluir opciones del selector de mapeo) y croquis_svg.py
# (filtrado en cálculo y render).
SLOTS_INVALIDOS_T = {"S_FTE", "O_IZQ", "E_DER"}
SLOTS_INVALIDOS_T_NORTE = {"N_FTE", "O_DER", "E_IZQ"}

# Posiciones válidas para mapear movimientos en cada tipo de croquis.
POSICIONES_T = ["S_IZQ", "S_DER", "O_FTE", "O_DER", "E_IZQ", "E_FTE"]
POSICIONES_T_NORTE = ["N_IZQ", "N_DER", "O_FTE", "O_IZQ",
                      "E_FTE", "E_DER"]
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


def _calcular_altura(svg: str, ancho_default: int = 900) -> int:
    """Calcula la altura apropiada para un SVG basada en su viewBox."""
    match = re.search(r'viewBox="[^"]*\s+([\d.]+)\s+([\d.]+)"', svg)
    if match:
        vb_ancho = float(match.group(1))
        vb_alto = float(match.group(2))
        return int(ancho_default * (vb_alto / vb_ancho))
    return 600  # Default height if parsing fails


def _reemplazar_texto(svg: str, id_: str, nuevo_valor: str) -> str:
    """Reemplaza el contenido de un <text id="...">...</text>."""
    # Si el id no existe en el SVG (p. ej. los slots eliminados de la T),
    # no hacemos nada: chequeo explícito en lugar del silencio de re.sub.
    if f'id="{id_}"' not in svg:
        return svg
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


def extraer_svg(html: str) -> str:
    """
    Devuelve solo el bloque <svg>…</svg> del HTML que arman las
    funciones renderizar_svg_* (que envuelven el SVG para
    components.html). Necesario para rasterizar el croquis a PNG
    (resvg no entiende el wrapper <html><body>).
    """
    m = re.search(r"<svg\b.*?</svg>", html, flags=re.DOTALL)
    return m.group(0) if m else html


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


def _calcular_entradas_salidas_T(volumenes, mapeo, ramas,
                                 slots_invalidos, destino):
    """Cálculo común de entradas/salidas para las variantes de la T."""
    datos = {r: {"IZQ": 0, "FTE": 0, "DER": 0} for r in ramas}
    for mov, pos in mapeo.items():
        if "_" not in pos or pos in slots_invalidos:
            continue
        rama, dir_ = pos.split("_", 1)
        if rama in datos and dir_ in datos[rama]:
            datos[rama][dir_] = volumenes.get(mov, 0)

    entradas = {r: sum(datos[r].values()) for r in datos}

    salidas = {r: 0 for r in datos}
    for rama, dirs in datos.items():
        for d, val in dirs.items():
            destino_rama = destino[(rama, d)]
            if destino_rama is not None:
                salidas[destino_rama] += val

    return entradas, salidas


def calcular_entradas_salidas_T(volumenes, mapeo):
    """
    Igual que calcular_entradas_salidas pero para la T(sur): solo ramas
    S, O, E; los movimientos en slots inválidos se ignoran y los giros
    con destino None (DESTINO_T) no suman salida.
    Devuelve (entradas, salidas) — dict {rama: int}.
    """
    return _calcular_entradas_salidas_T(
        volumenes, mapeo, RAMAS_T, SLOTS_INVALIDOS_T, DESTINO_T)


def calcular_entradas_salidas_T_norte(volumenes, mapeo):
    """
    Igual que calcular_entradas_salidas_T pero para la T(norte): solo
    ramas N, O, E; los giros imposibles (DESTINO_T_NORTE) no suman salida.
    Devuelve (entradas, salidas) — dict {rama: int}.
    """
    return _calcular_entradas_salidas_T(
        volumenes, mapeo, RAMAS_T_NORTE, SLOTS_INVALIDOS_T_NORTE,
        DESTINO_T_NORTE)


RAMAS_OD = {
    "Cruz": ("N", "S", "E", "O"),
    "T": RAMAS_T,
    "T_norte": RAMAS_T_NORTE,
    "Ruta": ("O", "E"),
}

NOMBRES_RAMA = {"N": "Norte", "S": "Sur", "E": "Este", "O": "Oeste"}


def calcular_matriz_od(volumenes, mapeo, tipo):
    """
    Matriz origen-destino a partir de los volúmenes y el mapeo.

    Devuelve (ramas, matriz): `matriz[i][j]` es el volumen que va de
    `ramas[i]` a `ramas[j]`, o None si ese movimiento no existe en el
    croquis (diagonal / giro en U, o giro imposible de la T).

    Para Ruta se asume O_IZQ = Oeste→Este (ida) y O_FTE = Este→Oeste
    (vuelta), que es la orientación de las flechas del SVG.
    """
    ramas = RAMAS_OD.get(tipo, RAMAS_OD["Cruz"])
    idx = {r: i for i, r in enumerate(ramas)}
    matriz = [[None] * len(ramas) for _ in ramas]

    # Volumen por slot: misma lógica que entradas/salidas (un slot, un mov).
    slots = {pos: volumenes.get(mov, 0) for mov, pos in mapeo.items()}

    if tipo == "Ruta":
        matriz[idx["O"]][idx["E"]] = slots.get("O_IZQ", 0)
        matriz[idx["E"]][idx["O"]] = slots.get("O_FTE", 0)
        return ramas, matriz

    destinos_t = {"T": DESTINO_T, "T_norte": DESTINO_T_NORTE}
    destino = destinos_t.get(tipo, DESTINO)
    for (rama, dir_), dest in destino.items():
        if rama not in idx or dest is None or dest not in idx:
            continue
        matriz[idx[rama]][idx[dest]] = slots.get(f"{rama}_{dir_}", 0)
    return ramas, matriz


def filas_tabla_od(volumenes, mapeo, tipo, etiquetas=None):
    """
    Filas listas para la tabla O-D del reporte:
    encabezado + una fila por origen + fila Total.
    `etiquetas` permite usar nombres de calle ({rama: texto}).
    """
    ramas, matriz = calcular_matriz_od(volumenes, mapeo, tipo)
    etiquetas = etiquetas or {}

    def _lbl(rama):
        return etiquetas.get(rama) or NOMBRES_RAMA.get(rama, rama)

    totales_col = [0] * len(ramas)
    filas = [["Origen / Destino"] + [_lbl(r) for r in ramas] + ["Total"]]
    for i, rama in enumerate(ramas):
        fila = [_lbl(rama)]
        total_fila = 0
        for j, valor in enumerate(matriz[i]):
            if valor is None:
                fila.append(GUION)
            else:
                fila.append(str(int(valor)))
                total_fila += int(valor)
                totales_col[j] += int(valor)
        fila.append(str(total_fila))
        filas.append(fila)
    filas.append(["Total"] + [str(v) for v in totales_col]
                 + [str(sum(totales_col))])
    return filas


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

    # Calcular altura y envolver en HTML para components.html
    altura = _calcular_altura(svg)
    html = f'<html><body style="margin:0;padding:0;">{svg}</body></html>'
    return html, altura


def _renderizar_svg_T(volumenes, mapeo, nombres_ramas, ruta_svg,
                      ramas, posiciones, slots_invalidos, destino):
    """Render común para las variantes de la T."""
    svg = _cargar_svg(ruta_svg)

    entradas, salidas = _calcular_entradas_salidas_T(
        volumenes, mapeo, ramas, slots_invalidos, destino)

    # Invertir el mapeo: slot → movimiento (solo slots válidos de la T)
    slot_a_mov = {}
    for mov, pos in mapeo.items():
        if pos in posiciones:
            slot_a_mov[pos] = mov

    for rama in ramas:
        for dir_ in ("IZQ", "FTE", "DER"):
            slot = f"{rama}_{dir_}"
            mov = slot_a_mov.get(slot)
            if slot in slots_invalidos or mov is None:
                svg = _reemplazar_texto(svg, f"{slot}_nombre", GUION)
                svg = _reemplazar_texto(svg, f"{slot}_volumen", GUION)
            else:
                svg = _reemplazar_texto(svg, f"{slot}_nombre", mov)
                svg = _reemplazar_texto(
                    svg, f"{slot}_volumen", str(volumenes.get(mov, 0))
                )

    for rama in ramas:
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

    # Calcular altura y envolver en HTML para components.html
    altura = _calcular_altura(svg)
    html = f'<html><body style="margin:0;padding:0;">{svg}</body></html>'
    return html, altura


def renderizar_svg_T(volumenes, mapeo, nombres_ramas,
                     ruta_svg="assets/croquis_T.svg"):
    """
    Lee el SVG de la T(sur) y reemplaza los valores dinámicos.
    - Slots inválidos (S_FTE, O_IZQ, E_DER): el SVG corregido ya no los
    dibuja; _reemplazar_texto es tolerante y no hace nada si falta el id.
    - Slots válidos sin movimiento mapeado → también guión.
    - Entradas/salidas según DESTINO_T (sin rama Norte).
    """
    return _renderizar_svg_T(
        volumenes, mapeo, nombres_ramas, ruta_svg,
        RAMAS_T, POSICIONES_T, SLOTS_INVALIDOS_T, DESTINO_T)


def renderizar_svg_T_norte(volumenes, mapeo, nombres_ramas,
                           ruta_svg="assets/croquis_T_norte.svg"):
    """
    Lee el SVG de la T(norte) y reemplaza los valores dinámicos.
    - Slots inválidos (N_FTE, O_DER, E_IZQ): no se dibujan en el SVG.
    - Slots válidos sin movimiento mapeado → guión.
    - Entradas/salidas según DESTINO_T_NORTE (sin rama Sur).
    """
    return _renderizar_svg_T(
        volumenes, mapeo, nombres_ramas, ruta_svg,
        RAMAS_T_NORTE, POSICIONES_T_NORTE, SLOTS_INVALIDOS_T_NORTE,
        DESTINO_T_NORTE)


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

    # Calcular altura y envolver en HTML para components.html
    altura = _calcular_altura(svg)
    html = f'<html><body style="margin:0;padding:0;">{svg}</body></html>'
    return html, altura
