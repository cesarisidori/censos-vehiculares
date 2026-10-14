"""
croquis.py
----------
OBSOLETO - modulo viejo basado en Plotly. Usar croquis_svg.py.
Se conserva como legacy mientras test_croquis.py y test_reportes.py
lo referencian. Ver migracion Plotly -> SVG.

Croquis de intersección en cruz (12 movimientos) al estilo "ingeniería vial".

Cada rama tiene:
  - Una caja con el nombre de la calle + Entrada / Salida.
  - Los 3 movimientos (izq, frente, der) con flechita y volumen.

Movimientos canónicos por rama:
  <RAMA>_IZQ, <RAMA>_FTE, <RAMA>_DER
  RAMA ∈ {N, S, E, O}

Criterio de los giros: desde el punto de vista del conductor que llega.
"""

import plotly.graph_objects as go


# ─────────────────────────────────────────────────────────────
# Estilos
# ─────────────────────────────────────────────────────────────
COLOR_FLECHA = "#333333"
COLOR_CAJA_FONDO = "#f5f5f5"
COLOR_CAJA_BORDE = "#333333"
COLOR_TEXTO = "#000000"
COLOR_ETIQUETA = "#1f3a93"
COLOR_CENTRO = "#222222"

ORDEN_CANONICO = [
    "N_IZQ", "N_FTE", "N_DER",
    "S_IZQ", "S_FTE", "S_DER",
    "E_IZQ", "E_FTE", "E_DER",
    "O_IZQ", "O_FTE", "O_DER",
]


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _flecha_giro(fig, x, y, orientacion, lado):
    """
    Dibuja una flecha de giro (quebrada, forma de L).
    orientacion: "N", "S", "E", "O"
    lado       : "IZQ" o "DER" (punto de vista del conductor)
    x, y       : punto de anclaje
    """
    L = 0.28
    G = 0.28

    if orientacion == "N":
        avance = (0, -L)
        dobla = (-G, 0) if lado == "IZQ" else (G, 0)
    elif orientacion == "S":
        avance = (0, L)
        dobla = (-G, 0) if lado == "IZQ" else (G, 0)
    elif orientacion == "E":
        avance = (-L, 0)
        dobla = (0, G) if lado == "IZQ" else (0, -G)
    elif orientacion == "O":
        avance = (L, 0)
        dobla = (0, G) if lado == "IZQ" else (0, -G)
    else:
        return

    x1 = x + avance[0]
    y1 = y + avance[1]
    x2 = x1 + dobla[0]
    y2 = y1 + dobla[1]

    fig.add_trace(go.Scatter(
        x=[x, x1, x2], y=[y, y1, y2],
        mode="lines",
        line=dict(color=COLOR_FLECHA, width=2.2),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_annotation(
        x=x2, y=y2, ax=x1, ay=y1,
        xref="x", yref="y", axref="x", ayref="y",
        showarrow=True, arrowhead=2, arrowsize=1.2,
        arrowwidth=2.2, arrowcolor=COLOR_FLECHA, text="",
    )


def _flecha_frente(fig, x, y, orientacion):
    """Flecha recta del movimiento frente."""
    L = 0.55
    if orientacion == "N":
        x2, y2 = x, y - L
    elif orientacion == "S":
        x2, y2 = x, y + L
    elif orientacion == "E":
        x2, y2 = x - L, y
    elif orientacion == "O":
        x2, y2 = x + L, y
    else:
        return

    fig.add_annotation(
        x=x2, y=y2, ax=x, ay=y,
        xref="x", yref="y", axref="x", ayref="y",
        showarrow=True, arrowhead=2, arrowsize=1.2,
        arrowwidth=2.2, arrowcolor=COLOR_FLECHA, text="",
    )


def _texto(fig, x, y, txt, size=12, color=COLOR_TEXTO, bold=False, align="center"):
    """Agrega un texto."""
    pref = "<b>" if bold else ""
    suf = "</b>" if bold else ""
    fig.add_annotation(
        x=x, y=y, text=f"{pref}{txt}{suf}",
        showarrow=False,
        font=dict(size=size, color=color, family="Arial"),
        align=align,
    )


# ─────────────────────────────────────────────────────────────
# Caja con nombre de calle + Entrada/Salida
# ─────────────────────────────────────────────────────────────
def _dibujar_caja_rama(fig, x, y, nombre_calle, entrada, salida):
    """Dibuja la caja con nombre de calle + Entrada + Salida."""
    ancho = 2.4
    alto = 0.8

    fig.add_shape(
        type="rect",
        x0=x - ancho / 2, y0=y - alto / 2,
        x1=x + ancho / 2, y1=y + alto / 2,
        fillcolor=COLOR_CAJA_FONDO,
        line=dict(color=COLOR_CAJA_BORDE, width=1.2),
    )
    # Nombre
    _texto(fig, x, y + 0.18, nombre_calle, size=12, bold=True)
    # Entrada / Salida en una sola línea
    _texto(fig, x, y - 0.16, f"Entrada: {entrada}   Salida: {salida}", size=10)


# ─────────────────────────────────────────────────────────────
# Panel de una rama
# ─────────────────────────────────────────────────────────────
def _dibujar_panel_rama(fig, x_centro, y_centro, orientacion, rama,
                        valores_rama, etiquetas_rama, nombre_calle,
                        entrada, salida,
                        mostrar_etiquetas=True):
    """
    Dibuja un panel de rama.

    x_centro, y_centro : centro del panel
    orientacion        : "N", "S", "E", "O"
    valores_rama       : {"IZQ": 127, "FTE": 45, "DER": 30}
    etiquetas_rama     : {"IZQ": "M1", "FTE": "M2", "DER": "M3"}
    nombre_calle       : texto para la caja de la rama
    entrada, salida    : totales calculados
    """
    sep = 0.65

    if orientacion in ("N", "S"):
        # Panel horizontal (3 columnas de flechas)
        y_flecha = 0.20
        y_etiqueta = -0.25

        cols = [(-sep, "IZQ"), (0, "FTE"), (sep, "DER")]
        for dx, clave in cols:
            x_col = x_centro + dx
            if clave == "FTE":
                _flecha_frente(fig, x_col, y_centro + y_flecha + 0.15, orientacion)
            else:
                _flecha_giro(fig, x_col, y_centro + y_flecha + 0.15,
                             orientacion, clave)
            if mostrar_etiquetas:
                _texto(fig, x_col, y_centro + y_etiqueta,
                       etiquetas_rama.get(clave, ""),
                       size=11, color=COLOR_ETIQUETA)
            # valor
            _texto(fig, x_col, y_centro + y_etiqueta - 0.35,
                   str(valores_rama.get(clave, 0)), size=14, bold=True)

        # Caja con Entrada/Salida
        y_caja = y_centro + (1.6 if orientacion == "N" else -1.6)
        _dibujar_caja_rama(fig, x_centro, y_caja, nombre_calle, entrada, salida)

    else:
        # Panel vertical (3 filas de flechas), para E y O
        sep_v = 0.9
        x_flecha = 0.55
        x_etiqueta = -0.7

        filas = [(sep_v, "IZQ"), (0, "FTE"), (-sep_v, "DER")]
        for dy, clave in filas:
            y_row = y_centro + dy
            if clave == "FTE":
                _flecha_frente(fig, x_centro + x_flecha, y_row, orientacion)
            else:
                _flecha_giro(fig, x_centro + x_flecha, y_row,
                             orientacion, clave)
            if mostrar_etiquetas:
                _texto(fig, x_centro + x_etiqueta, y_row + 0.08,
                       etiquetas_rama.get(clave, ""),
                       size=11, color=COLOR_ETIQUETA)
            # valor debajo de la etiqueta, separado de la flecha
            _texto(fig, x_centro + x_etiqueta, y_row - 0.18,
                   str(valores_rama.get(clave, 0)), size=14, bold=True)

        # Caja con Entrada/Salida, más alejada del panel
        x_caja = x_centro + (2.8 if orientacion == "E" else -2.8)
        _dibujar_caja_rama(fig, x_caja, y_centro, nombre_calle, entrada, salida)


# ─────────────────────────────────────────────────────────────
# Croquis principal
# ─────────────────────────────────────────────────────────────
def dibujar_croquis_cruz(volumenes: dict, mapeo: dict = None,
                         nombres_ramas: dict = None,
                         titulo: str = "",
                         mostrar_etiquetas: bool = True):
    """
    volumenes     : dict {"M1": 127, ...}
    mapeo         : dict {"M1": "N_IZQ", ...}  (si None, mapeo por defecto)
    nombres_ramas : dict {"N": "RP 18 Norte", ...}
    titulo        : título del croquis.
    mostrar_etiquetas : si True, muestra el nombre del movimiento (M1...)
    """
    if nombres_ramas is None:
        nombres_ramas = {"N": "Norte", "S": "Sur", "E": "Este", "O": "Oeste"}

    if mapeo is None:
        claves = list(volumenes.keys())
        mapeo = {claves[i]: ORDEN_CANONICO[i]
                 for i in range(min(len(claves), len(ORDEN_CANONICO)))}

    # Organizar por rama
    datos = {
        "N": {"IZQ": (0, ""), "FTE": (0, ""), "DER": (0, "")},
        "S": {"IZQ": (0, ""), "FTE": (0, ""), "DER": (0, "")},
        "E": {"IZQ": (0, ""), "FTE": (0, ""), "DER": (0, "")},
        "O": {"IZQ": (0, ""), "FTE": (0, ""), "DER": (0, "")},
    }
    for mov, pos in mapeo.items():
        if "_" not in pos:
            continue
        rama, dir_ = pos.split("_")
        if rama in datos and dir_ in datos[rama]:
            datos[rama][dir_] = (volumenes.get(mov, 0), mov)

    # Destino de cada movimiento (para calcular Salidas)
        destino = {
        # NORTE: vienen del norte (bajan)
        ("N", "FTE"): "S",   # sigue recto → sale por el sur
        ("N", "IZQ"): "O",   # flecha dibujada hacia la izq visual → sale por el oeste
        ("N", "DER"): "E",   # flecha dibujada hacia la der visual → sale por el este
        # SUR: vienen del sur (suben)
        ("S", "FTE"): "N",   # sigue recto → sale por el norte
        ("S", "IZQ"): "O",   # giro izq del conductor → sale por el oeste
        ("S", "DER"): "E",   # giro der del conductor → sale por el este
        # ESTE: vienen del este (van al oeste)
        ("E", "FTE"): "O",   # sigue recto → sale por el oeste
        ("E", "IZQ"): "N",   # flecha dibujada hacia arriba → sale por el norte
        ("E", "DER"): "S",   # flecha dibujada hacia abajo → sale por el sur
        # OESTE: vienen del oeste (van al este)
        ("O", "FTE"): "E",   # sigue recto → sale por el este
        ("O", "IZQ"): "N",   # flecha dibujada hacia arriba → sale por el norte
        ("O", "DER"): "S",   # flecha dibujada hacia abajo → sale por el sur
    }

    entradas = {}
    salidas = {r: 0 for r in datos}
    for rama, dirs in datos.items():
        entradas[rama] = sum(v[0] for v in dirs.values())
        for d, (val, _) in dirs.items():
            salidas[destino[(rama, d)]] += val

    # ── Figura ──
    fig = go.Figure()

    # Centro: cuadrito negro
    fig.add_shape(type="rect", x0=-0.35, y0=-0.35, x1=0.35, y1=0.35,
                  fillcolor=COLOR_CENTRO, line=dict(width=0))

    fig.update_layout(
        title=dict(text=titulo, x=0.5, xanchor="center", font=dict(size=16))
        if titulo else None,
        xaxis=dict(range=[-7, 7], visible=False, fixedrange=True),
        yaxis=dict(range=[-7, 7], visible=False, fixedrange=True,
                   scaleanchor="x", scaleratio=1),
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=40 if titulo else 20, b=20),
        height=850,
        showlegend=False,
    )

    # Panel NORTE (arriba)
    _dibujar_panel_rama(
        fig, x_centro=0, y_centro=2.7,
        orientacion="N", rama="N",
        valores_rama={k: v[0] for k, v in datos["N"].items()},
        etiquetas_rama={k: v[1] for k, v in datos["N"].items()},
        nombre_calle=nombres_ramas["N"],
        entrada=entradas["N"], salida=salidas["N"],
        mostrar_etiquetas=mostrar_etiquetas,
    )

    # Panel SUR (abajo)
    _dibujar_panel_rama(
        fig, x_centro=0, y_centro=-2.7,
        orientacion="S", rama="S",
        valores_rama={k: v[0] for k, v in datos["S"].items()},
        etiquetas_rama={k: v[1] for k, v in datos["S"].items()},
        nombre_calle=nombres_ramas["S"],
        entrada=entradas["S"], salida=salidas["S"],
        mostrar_etiquetas=mostrar_etiquetas,
    )

    # Panel ESTE (derecha)
    _dibujar_panel_rama(
        fig, x_centro=2.7, y_centro=0,
        orientacion="E", rama="E",
        valores_rama={k: v[0] for k, v in datos["E"].items()},
        etiquetas_rama={k: v[1] for k, v in datos["E"].items()},
        nombre_calle=nombres_ramas["E"],
        entrada=entradas["E"], salida=salidas["E"],
        mostrar_etiquetas=mostrar_etiquetas,
    )

    # Panel OESTE (izquierda)
    _dibujar_panel_rama(
        fig, x_centro=-2.7, y_centro=0,
        orientacion="O", rama="O",
        valores_rama={k: v[0] for k, v in datos["O"].items()},
        etiquetas_rama={k: v[1] for k, v in datos["O"].items()},
        nombre_calle=nombres_ramas["O"],
        entrada=entradas["O"], salida=salidas["O"],
        mostrar_etiquetas=mostrar_etiquetas,
    )

    return fig