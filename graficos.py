"""
graficos.py
-----------
Construcción de las figuras Plotly de la app.

Funciones puras: reciben datos y devuelven `plotly.graph_objects.Figure`.
No dibujan en pantalla — la app decide dónde renderizarlas
(`st.plotly_chart`) y cuáles exportar a los reportes PDF/DOCX.

Todas aceptan `paleta` (lista de colores hex) para la personalización
desde la UI. La paleta por defecto es `PALETA_DEFAULT`.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Paleta por defecto (la misma que usaba la app antes de la personalización).
PALETA_DEFAULT = [
    "#1f77b4", "#d62728", "#2ca02c", "#9467bd",
    "#ff7f0e", "#8c564b", "#e377c2", "#7f7f7f",
]


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _color(paleta, indice):
    """Color de la paleta (cíclico)."""
    return paleta[indice % len(paleta)]


def _titulo(titulo, subtitulo):
    if subtitulo:
        return f"{titulo}<br><sub>{subtitulo}</sub>"
    return titulo


def _safe_int(valor):
    """Convierte a int tratando NaN/None/False como cero."""
    try:
        if valor is None:
            return 0
        if isinstance(valor, float) and pd.isna(valor):
            return 0
        if isinstance(valor, bool):
            return int(valor)
        return int(valor)
    except (TypeError, ValueError):
        return 0


# ─────────────────────────────────────────────────────────────
# Helpers de layout
# ─────────────────────────────────────────────────────────────
def _layout_barras(titulo, subtitulo, eje_y, height=210, width=500):
    return dict(
        title=dict(text=_titulo(titulo, subtitulo), x=0.5, xanchor="center",
                   font=dict(size=13)),
        xaxis_title="",
        barmode="group",
        legend=dict(orientation="h", yanchor="top", y=-0.28,
                    xanchor="center", x=0.5),
        margin=dict(l=95, r=15, t=55, b=80),
        height=height,
        width=width,
        plot_bgcolor="white",
        yaxis=dict(
            gridcolor="#e0e0e0",
            automargin=True,
            title=dict(text=eje_y, font=dict(size=10), standoff=10),
        ),
    )


# ─────────────────────────────────────────────────────────────
# Preparación de datos
# ─────────────────────────────────────────────────────────────
def volumen_por_calle_sentido(df_validos, movs, mapa_dict):
    """
    Devuelve DataFrame (hora_inicio, hora_fin, calle, sentido, volumen)
    agregando por calle/sentido los movimientos mapeados (vectorizado
    con melt, sin iterrows).
    """
    columnas = [m for m in movs if m in mapa_dict]
    columnas_vacia = ["hora_inicio", "hora_fin", "calle", "sentido", "volumen"]
    if not columnas:
        return pd.DataFrame(columns=columnas_vacia)

    largo = df_validos.melt(
        id_vars=["hora_inicio", "hora_fin"],
        value_vars=columnas,
        var_name="movimiento",
        value_name="volumen",
    )
    largo["calle"] = largo["movimiento"].map({m: v[0] for m, v in mapa_dict.items()})
    largo["sentido"] = largo["movimiento"].map({m: v[1] for m, v in mapa_dict.items()})
    largo = largo[largo["volumen"] != 0]
    return largo.groupby(
        ["hora_inicio", "hora_fin", "calle", "sentido"], as_index=False
    )["volumen"].sum()


def agregar_por_hora(df_cs):
    """Agrega los volúmenes de 15 min a bloques de hora entera (HH:00)."""
    df = df_cs.copy()
    df["hora_entera"] = df["hora_inicio"].str.slice(0, 2) + ":00"
    return df.groupby(
        ["hora_entera", "calle", "sentido"], as_index=False
    )["volumen"].sum()


# ─────────────────────────────────────────────────────────────
# Figuras
# ─────────────────────────────────────────────────────────────
def fig_barras_agrupadas(df, col_periodo, periodos, titulo, subtitulo,
                         eje_y, paleta=None, height=550, width=500):
    """
    Barras agrupadas por sentido + serie 'Ambos' (suma de sentidos).

    df       : columnas col_periodo, 'sentido', 'volumen'
    periodos : períodos en orden para el eje X
    Devuelve None si no hay datos.
    """
    paleta = paleta or PALETA_DEFAULT
    piv = df.pivot_table(index=col_periodo, columns="sentido",
                         values="volumen", aggfunc="sum")
    if piv.empty:
        return None

    fig = go.Figure()
    for i, sentido in enumerate(piv.columns):
        valores = [_safe_int(piv[sentido].get(p, 0)) for p in periodos]
        fig.add_trace(go.Bar(
            name=sentido,
            x=list(periodos),
            y=valores,
            marker_color=_color(paleta, i),
        ))

    totales = df.groupby(col_periodo)["volumen"].sum()
    fig.add_trace(go.Bar(
        name="Ambos",
        x=list(periodos),
        y=[_safe_int(totales.get(p, 0)) for p in periodos],
        marker_color=_color(paleta, len(piv.columns)),
    ))

    fig.update_layout(**_layout_barras(titulo, subtitulo, eje_y, height=height,
                                       width=width))
    return fig


def fig_lineas(df_cs, titulo, subtitulo, paleta=None, width=1000, height=600):
    """Líneas + marcadores: una por sentido (todas las calles), censo completo."""
    paleta = paleta or PALETA_DEFAULT
    bloques = sorted(df_cs["hora_inicio"].unique())
    piv = df_cs.pivot_table(index="hora_inicio", columns="sentido",
                            values="volumen", aggfunc="sum")

    fig = go.Figure()
    for i, sentido in enumerate(piv.columns):
        valores = [_safe_int(piv[sentido].get(b, 0)) for b in bloques]
        fig.add_trace(go.Scatter(
            x=bloques,
            y=valores,
            mode="lines+markers",
            name=sentido,
            line=dict(width=2.5, color=_color(paleta, i)),
            marker=dict(size=7),
        ))

    fig.update_layout(
        title=dict(text=_titulo(titulo, subtitulo), x=0.5, xanchor="center",
                   font=dict(size=14)),
        xaxis_title="",
        yaxis_title="VOLUMEN",
        legend=dict(orientation="h", yanchor="top", y=-0.32,
                    xanchor="center", x=0.5),
        margin=dict(l=70, r=20, t=75, b=95),
        width=width,
        height=height,
        plot_bgcolor="white",
        xaxis=dict(gridcolor="#f0f0f0", tickangle=-45),
        yaxis=dict(gridcolor="#e0e0e0", automargin=True,
                   title=dict(text="VOLUMEN", font=dict(size=10),
                              standoff=10)),
    )
    return fig


def fig_torta(series, titulo, subtitulo="", paleta=None):
    """Torta con hueco: composición por tipo de vehículo (todos los tipos)."""
    paleta = paleta or PALETA_DEFAULT
    if series is None or series.empty or series.sum() == 0:
        return None

    fig = go.Figure(go.Pie(
        labels=list(series.index),
        values=list(series.values),
        hole=0.4,
        textinfo="percent+label",
        textposition="inside",
        marker=dict(colors=[_color(paleta, i) for i in range(len(series))]),
    ))
    fig.update_layout(
        title=dict(text=_titulo(titulo, subtitulo), x=0.5, xanchor="center",
                   font=dict(size=13)),
        showlegend=True,
        margin=dict(l=10, r=10, t=65, b=10),
        height=400,
    )
    return fig


def fig_pesados(pesados_hp, paleta=None, width=500):
    """Barras horizontales del % de pesados por movimiento (hora pico)."""
    paleta = paleta or PALETA_DEFAULT
    pct = pesados_hp.loc["% pesados"]
    pct = pct[[c for c in pct.index if c != "Total"]]
    pct = pct[pct > 0].sort_values(ascending=True)
    if pct.empty:
        return None

    fig = px.bar(
        x=pct.values,
        y=pct.index,
        orientation="h",
        labels={"x": "% pesados", "y": "Movimiento"},
        color=pct.values,
        color_continuous_scale=[_color(paleta, 0), _color(paleta, 2)],
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=max(200, len(pct) * 25),
        width=width,
        showlegend=False,
        coloraxis_showscale=False,
    )
    return fig
