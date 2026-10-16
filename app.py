"""
app.py — Interfaz Streamlit para procesamiento de censos vehiculares.

Ejecutar:
    streamlit run app.py
"""

import copy
import hashlib
import io
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import graficos as grf
import procesar_censo3 as motor
import reportes as rep
import croquis_svg


# ─────────────────────────────────────────────────────────────
# Kaleido health check (evita cuelgues en Windows)
# ─────────────────────────────────────────────────────────────
def _mirage_funciona():
    """Verifica si mirage puede convertir una figura Plotly a PNG.

    Devuelve True si funciona, False si no.
    """
    try:
        import plotly.graph_objects as go
        import mirage
        
        # Crear figura simple de prueba
        fig = go.Figure(data=[go.Bar(y=[1, 3, 2])])
        
        # Convertir figura a JSON puro para evitar problemas con ndarray
        import json
        import plotly.io as pio
        fig_json = pio.to_json(fig)
        fig_serializable = go.Figure(json.loads(fig_json))
        
        # Intentar convertir a PNG
        png_bytes = mirage.to_image(fig_serializable, format='png', scale=1)
        return len(png_bytes) > 0
    except Exception:
        return False


MIRAGE_OK = _mirage_funciona()

# ─────────────────────────────────────────────────────────────
# Configuración de página
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Procesador de Censos",
    page_icon="🚦",
    layout="wide",
)

st.title("🚦 Procesador de Censos Vehiculares")
st.caption("Subí el Excel del censo. Los cálculos se hacen automáticamente.")


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
DIAS = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES",
        "SÁBADO", "DOMINGO"]
MESES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
         "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE",
         "DICIEMBRE"]


def _fecha_legible(dt) -> str:
    """date → '22 DE SEPTIEMBRE DE 2026' (sin día de la semana)."""
    if dt is None:
        return ""
    return f"{dt.day} DE {MESES[dt.month - 1]} DE {dt.year}"


def _dia_semana(dt) -> str:
    """date → 'MARTES'."""
    return DIAS[dt.weekday()] if dt else ""


def _parse_fecha_cfg(texto):
    """'2026-09-22' | '22/09/2026' → date, o None si no se puede."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(texto).strip(), fmt).date()
        except ValueError:
            continue
    return None


@st.cache_data(show_spinner=False)
def _leer_estructura(contenido: bytes):
    """Lee CONFIG (vía motor) y los tipos de DATOS, para poblar la UI."""
    xls = pd.ExcelFile(io.BytesIO(contenido))
    if "DATOS" not in xls.sheet_names:
        raise ValueError("El archivo no tiene una hoja 'DATOS'.")

    cfg = motor.leer_config(io.BytesIO(contenido))

    df_datos = pd.read_excel(io.BytesIO(contenido), sheet_name="DATOS",
                             dtype=str)
    tipos = []
    if "tipo_vehiculo" in df_datos.columns:
        tipos = sorted(df_datos["tipo_vehiculo"].dropna().astype(str)
                       .str.strip().unique().tolist())
    return cfg, tipos


@st.cache_data(show_spinner=False)
def _leer_movimientos_mapa(contenido: bytes):
    """Lee SOLO la hoja MAPA (chica) para sugerir el tipo de croquis al subir.

    Devuelve el DataFrame o None si la hoja no existe o no tiene la columna
    'movimiento'. Rápida a propósito: no toca DATOS ni CONFIG.
    """
    try:
        df = pd.read_excel(io.BytesIO(contenido), sheet_name="MAPA", dtype=str)
    except Exception:
        return None
    if "movimiento" not in df.columns:
        return None
    return df


def _imagenes_reporte(figuras):
    """PNG de cada figura con mirage (respeta el aspect ratio original)."""
    if not MIRAGE_OK:
        st.warning(
            "Mirage no funciona en este sistema. Los reportes se generarán "
            "sin gráficos."
        )
        return [(titulo, None) for titulo, fig in figuras]
    resultados = []
    for titulo, fig in figuras:
        try:
            png = rep.fig_a_png(fig)
            resultados.append((titulo, png))
        except Exception as e:
            st.error(f"Error convirtiendo {titulo}: {e}")
            resultados.append((titulo, None))
    return resultados


def _web(fig, alto):
    """Copia de la figura con otro alto, para achicarla SOLO en pantalla.

    El `fig` original (que alimenta el reporte) queda intacto.
    """
    copia = copy.deepcopy(fig)
    copia.update_layout(height=alto)
    return copia


def _filas_dos_columnas(figs, alto_web):
    """Renderiza `figs` (título, figura) de a 2 por fila, 50% de ancho cada
    uno. No modifica las figuras originales (el reporte las usa enteras)."""
    for i in range(0, len(figs), 2):
        cols = st.columns(2)
        for col, (_, fig) in zip(cols, figs[i:i + 2]):
            with col:
                st.plotly_chart(_web(fig, alto_web), use_container_width=True)



@st.cache_data(show_spinner="📄 Generando PDF…")
def _generar_pdf(ctx):
    return rep.generar_pdf(ctx)


@st.cache_data(show_spinner="📄 Generando DOCX…")
def _generar_docx(ctx):
    return rep.generar_docx(ctx)


def _tabla_agrupada_html(resumen_agr) -> str:
    """Tabla HTML con encabezado de 3 niveles (calle / sentido / movimiento)."""
    # ── Separar calle y sentido de cada columna ──
    columnas_split = []
    for grupo, mov in resumen_agr.columns:
        if grupo == "Total":
            columnas_split.append(("Total", "", ""))
        else:
            partes = [p.strip() for p in grupo.split("|")]
            calle = partes[0] if partes else ""
            sentido = partes[1] if len(partes) > 1 else ""
            columnas_split.append((calle, sentido, mov))

    # ── Fila 1: calles (con colspan) ──
    fila1 = []
    i = 0
    while i < len(columnas_split):
        calle = columnas_split[i][0]
        span = 1
        while (i + span < len(columnas_split)
               and columnas_split[i + span][0] == calle):
            span += 1
        fila1.append((calle, span))
        i += span

    # ── Fila 2: sentidos (con colspan cuando se repiten) ──
    fila2 = []
    i = 0
    while i < len(columnas_split):
        calle, sentido, _ = columnas_split[i]
        span = 1
        while (i + span < len(columnas_split)
               and columnas_split[i + span][0] == calle
               and columnas_split[i + span][1] == sentido):
            span += 1
        fila2.append((sentido, span))
        i += span

    # ── Fila 3: movimientos (uno por columna) ──
    fila3 = [c[2] for c in columnas_split]

    # ── Construir HTML ──
    html = """
    <style>
        .tabla-censo { border-collapse: collapse; width: 100%;
                       font-family: sans-serif; font-size: 13px; }
        .tabla-censo th, .tabla-censo td {
            border: 1px solid #d0d0d0; padding: 6px 8px;
            text-align: center; white-space: nowrap;
        }
        .tabla-censo thead th { background: #e8eef7; font-weight: 600; }
        .tabla-censo thead tr:nth-child(2) th { background: #f0f4fa; font-weight: 500; }
        .tabla-censo thead tr:nth-child(3) th { background: #f7f9fc; font-weight: 400; }
        .tabla-censo tbody td:first-child {
            text-align: left; font-weight: 600; background: #fafafa;
        }
        .tabla-censo tbody tr:last-child td {
            background: #fff3cd; font-weight: 700;
        }
    </style>
    <table class="tabla-censo"><thead>
    """
    html += "<tr><th rowspan='3' style='vertical-align:middle;'>Tipo</th>"
    for calle, span in fila1:
        html += f"<th colspan='{span}'>{calle}</th>"
    html += "</tr><tr>"
    for sentido, span in fila2:
        html += f"<th colspan='{span}'>{sentido}</th>"
    html += "</tr><tr>"
    for mov in fila3:
        html += f"<th>{mov}</th>"
    html += "</tr></thead><tbody>"

    for idx, row in resumen_agr.iterrows():
        html += f"<tr><td>{idx}</td>"
        for val in row:
            html += f"<td>{val}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html


# ─────────────────────────────────────────────────────────────
# Mapeo fijo de movimientos → posiciones del croquis
# NORTE:  9, 8, 7  (izq a der) · SUR: 10, 11, 12 (izq a der)
# ESTE:   4, 5, 6  (arriba a abajo) · OESTE: 1, 2, 3 (arriba a abajo)
# ─────────────────────────────────────────────────────────────
MAPEO_FIJO = {
    "M9":  "N_IZQ",  "M8":  "N_FTE",  "M7":  "N_DER",
    "M10": "S_IZQ",  "M11": "S_FTE",  "M12": "S_DER",
    "M4":  "E_IZQ",  "M5":  "E_FTE",  "M6":  "E_DER",
    "M1":  "O_IZQ",  "M2":  "O_FTE",  "M3":  "O_DER",
}

_SUFIJOS_RAMA = {"N": "Norte", "S": "Sur", "E": "Este", "O": "Oeste"}


def _inferir_nombres_ramas(mapa_df, movs_activos):
    """
    Devuelve {"N": "Fiambalá Norte", ...} inferido del MAPA,
    mirando a qué rama del croquis va cada movimiento según MAPEO_FIJO.
    """
    nombres = {rama: "" for rama in _SUFIJOS_RAMA}

    if mapa_df is not None:
        for _, row in mapa_df.iterrows():
            mov = str(row["movimiento"]).strip()
            if mov not in movs_activos or mov not in MAPEO_FIJO:
                continue
            rama = MAPEO_FIJO[mov].split("_")[0]
            if not nombres[rama]:
                nombres[rama] = f"{str(row['calle']).strip()} {_SUFIJOS_RAMA[rama]}"

    # Fallback: "Norte", "Sur", ...
    for rama, sufijo in _SUFIJOS_RAMA.items():
        if not nombres[rama]:
            nombres[rama] = sufijo
    return nombres


def _inferir_mapeo_default(mapa_df, movs_activos):
    """Devuelve el mapeo fijo para los movimientos que existan."""
    return {m: p for m, p in MAPEO_FIJO.items() if m in movs_activos}


def _inferir_tipo_croquis(mapa_df, movs_activos):
    """
    Infere el tipo de croquis por ESTRUCTURA del MAPA: cuenta las ramas
    distintas (N/S/E/O) a las que van los movimientos activos según
    MAPEO_FIJO. 4 ramas → "Cruz", 3 → "T", ≤2 → "Ruta".
    """
    if mapa_df is None:
        return "Cruz"
    movs_mapa = {str(m).strip() for m in mapa_df["movimiento"]}
    ramas = {
        MAPEO_FIJO[m].split("_")[0]
        for m in movs_activos
        if m in movs_mapa and m in MAPEO_FIJO
    }
    if len(ramas) >= 4:
        return "Cruz"
    if len(ramas) == 3:
        return "T"
    return "Ruta"


def _inferir_tipo_croquis_temprano(mapa_df, movs_tempranos):
    """
    Sugerencia híbrida de tipo de croquis al SUBIR el archivo:
    1) Conteo de movimientos del MAPA: 12→"Cruz", 6-9→"T", 2→"Ruta".
    2) Si el conteo no encaja en ningún caso → fallback a
       _inferir_tipo_croquis (ramas vía MAPEO_FIJO).
    3) Sin MAPA / sin movimientos → "Cruz".
    """
    if mapa_df is None or not movs_tempranos:
        return "Cruz"
    n = len(movs_tempranos)
    if n == 12:
        return "Cruz"
    if 6 <= n <= 9:
        return "T"
    if n == 2:
        return "Ruta"
    return _inferir_tipo_croquis(mapa_df, movs_tempranos)


def _render_croquis(tipo, volumenes, mapeo, nombres_ramas, nombres_extremos):
    """Dispatch: renderiza el SVG correspondiente al tipo de croquis."""
    if tipo == "T":
        return croquis_svg.renderizar_svg_T(volumenes, mapeo, nombres_ramas)
    if tipo == "Ruta":
        return croquis_svg.renderizar_svg_ruta(volumenes, mapeo,
                                               nombres_extremos)
    return croquis_svg.renderizar_svg_cruz(volumenes, mapeo, nombres_ramas)


# ─────────────────────────────────────────────────────────────
# 1) Carga del archivo
# ─────────────────────────────────────────────────────────────
archivo = st.file_uploader(
    "Seleccioná el archivo Excel del censo",
    type=["xlsx", "xls"],
    help="Debe tener una hoja DATOS (obligatoria), y opcionalmente MAPA y CONFIG.",
)

if archivo is None:
    st.info("⬆️ Subí un archivo para comenzar.")
    st.stop()

contenido = archivo.getvalue()
try:
    cfg_inicial, tipos_detectados = _leer_estructura(contenido)
except Exception as e:
    st.error(f"❌ Error al leer el archivo: {e}")
    st.stop()

# Lectura temprana del MAPA (solo esa hoja, instantáneo): permite sugerir
# el tipo de croquis ANTES de procesar, sin correr el pipeline completo.
mapa_temprano = _leer_movimientos_mapa(contenido)
movs_tempranos = (
    [str(m).strip() for m in mapa_temprano["movimiento"].dropna().unique()]
    if mapa_temprano is not None else []
)
tipo_inferido = _inferir_tipo_croquis_temprano(mapa_temprano, movs_tempranos)


# ─────────────────────────────────────────────────────────────
# 2) Controles de configuración
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("⚙️ Configuración")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Tipos a excluir** (no suman en hora pico ni totales)")
    excluidos_default = [t.strip() for t in
                         cfg_inicial.get("tipos_excluidos", "").split(",")
                         if t.strip()]
    excluidos = st.multiselect(
        "Elegí los tipos a excluir",
        options=tipos_detectados,
        default=[t for t in excluidos_default if t in tipos_detectados],
        label_visibility="collapsed",
    )

with col2:
    st.markdown("**Nombre de la fila total**")
    nombre_fila_total = st.text_input(
        "Nombre de la fila total",
        value=cfg_inicial.get("nombre_fila_total",
                              motor.NOMBRE_FILA_TOTAL_DEFAULT),
        label_visibility="collapsed",
    )

st.markdown("**Tipos pesados** (para el cálculo del % de pesados)")
calcular_pesados = st.checkbox(
    "Calcular % de vehículos pesados",
    value=cfg_inicial.get("calcular_pct_pesados", "NO").strip().upper() == "SI",
)

tipos_pesados_default = [t.strip() for t in
                         cfg_inicial.get("tipos_pesados", "").split(",")
                         if t.strip()]
tipos_pesados = st.multiselect(
    "Tipos que cuentan como pesados",
    options=[t for t in tipos_detectados if t not in excluidos],
    default=[t for t in tipos_pesados_default
             if t in tipos_detectados and t not in excluidos],
    disabled=not calcular_pesados,
)


# ─────────────────────────────────────────────────────────────
# 3) Datos del reporte (carga manual)
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("📋 Datos del reporte")
st.caption("Se usan en el encabezado de los reportes PDF/DOCX y como "
           "subtítulo por defecto de los gráficos.")

fila_a = st.columns(3)
fila_b = st.columns(2)

with fila_a[0]:
    fecha_sel = st.date_input(
        "Fecha",
        value=_parse_fecha_cfg(cfg_inicial.get("fecha_censo", ""))
        or date.today(),
        key="inp_fecha",
    )

# El Día se deriva de la Fecha; el usuario puede editarlo a mano.
dia_auto = _dia_semana(fecha_sel)
if st.session_state.get("_dia_auto_previo") != dia_auto:
    st.session_state["_dia_auto_previo"] = dia_auto
    st.session_state["inp_dia"] = dia_auto

with fila_a[1]:
    dia_txt = st.text_input(
        "Día",
        key="inp_dia",
        help="Se completa automáticamente desde la Fecha. "
             "Podés editarlo a mano (se vuelve a completar si cambiás la Fecha).",
    ).strip()

with fila_a[2]:
    ubicacion_txt = st.text_input(
        "Ubicación",
        value=cfg_inicial.get("ubicacion", ""),
        key="inp_ubicacion",
        help="Precargable con la clave 'ubicacion' en la hoja CONFIG.",
    )

with fila_b[0]:
    lugar_txt = st.text_input(
        "Lugar",
        value=cfg_inicial.get("lugar", ""),
        key="inp_lugar",
        help="Precargable con la clave 'lugar' en la hoja CONFIG.",
    )

with fila_b[1]:
    analista_txt = st.text_input(
        "Analista",
        value=cfg_inicial.get("analista", ""),
        key="inp_analista",
        help="Precargable con la clave 'analista' en la hoja CONFIG.",
    )


# ─────────────────────────────────────────────────────────────
# 4) Personalización de gráficos
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("🎨 Personalización de gráficos")

col_t1, col_t2 = st.columns(2)

with col_t1:
    titulo_personalizado = st.text_input(
        "Título de los gráficos",
        value="",
        placeholder="Ej: VOLUMEN TRÁNSITO",
        help="Si lo dejás vacío, se usa 'VOLUMEN TRÁNSITO <calle>'.",
    )

with col_t2:
    subtitulo_personalizado = st.text_input(
        "Subtítulo de los gráficos",
        value="",
        placeholder="Ej: DOMINGO 26 DE JULIO DE 2026",
        help="Si lo dejás vacío, se usa el Día + la Fecha del reporte.",
    )

with st.expander("🖌️ Paleta de colores (8 series)"):
    st.caption("Se aplica a líneas, barras, tortas y % de pesados. "
               "Cambiá un color y volvé a clickear ▶️ Procesar censo.")
    cols_color = st.columns(8)
    paleta = []
    for i, col_color in enumerate(cols_color):
        with col_color:
            paleta.append(st.color_picker(
                f"Serie {i + 1}", grf.PALETA_DEFAULT[i],
                key=f"color_serie_{i}",
            ))


# ─────────────────────────────────────────────────────────────
# 4b) Tipo de croquis (elegible ANTES de procesar)
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("⚙️ Tipo de croquis")

# Al subir otro archivo, el selector vuelve al tipo inferido del archivo
# nuevo (no queda "pegado" el tipo del anterior). Se setea ANTES de
# instanciar el widget, como exige Streamlit.
huella = hashlib.sha1(contenido).hexdigest()
if st.session_state.get("_tipo_croquis_archivo") != huella:
    st.session_state["_tipo_croquis_archivo"] = huella
    st.session_state["tipo_croquis_sel"] = tipo_inferido

tipo_croquis = st.selectbox(
    "Tipo de croquis",
    ["Cruz", "T", "Ruta"],
    index=["Cruz", "T", "Ruta"].index(tipo_inferido),
    key="tipo_croquis_sel",
    label_visibility="collapsed",
    help="Sugerido según la hoja MAPA. Cambialo acá y volvé a clickear "
         "▶️ Procesar censo.",
)

if mapa_temprano is None:
    st.caption(f"Sugerencia: {tipo_inferido} (no se detectó la hoja MAPA)")
else:
    st.caption(f"Sugerencia: {tipo_inferido} "
               f"({len(movs_tempranos)} movimientos detectados)")


# ─────────────────────────────────────────────────────────────
# 5) Procesamiento
# ─────────────────────────────────────────────────────────────
st.divider()
if not st.button("▶️ Procesar censo", type="primary"):
    st.stop()

with st.spinner("Procesando..."):
    try:
        # El motor recibe el buffer directamente (sin archivo temporal)
        # y la configuración como parámetros (sin reescribir el Excel).
        res = motor.procesar(
            io.BytesIO(contenido),
            excluidos=excluidos or motor.TIPOS_EXCLUIDOS_DEFAULT,
            nombre_fila_total=nombre_fila_total,
            calcular_pesados=calcular_pesados,
            tipos_pesados=list(tipos_pesados),
        )
    except Exception as e:
        st.error(f"❌ Error al procesar el censo: {e}")
        st.stop()

    # Excel de salida en memoria, para el botón de descarga
    salida_buffer = motor.exportar_buffer(
        res["fhp_data"], res["resumen_agr"], res["resumen_plano"],
        res["pesados_hp"], res["pesados_total"], res["totales"], res["df"],
    )

df = res["df"]
movs = res["movs"]
mapa = res["mapa"]
excluidos_final = res["excluidos"]
totales = res["totales"]
pico = res["pico"]
fhp_data = res["fhp_data"]
resumen_plano = res["resumen_plano"]
resumen_agr = res["resumen_agr"]
pesados_hp = res["pesados_hp"]
pesados_total = res["pesados_total"]


# ─────────────────────────────────────────────────────────────
# 6) Mostrar resultados
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("📊 Resultados")

# Métricas destacadas
c1, c2, c3, c4 = st.columns(4)
c1.metric("Hora pico",
          f"{fhp_data['hora_pico_inicio']} – {fhp_data['hora_pico_fin']}")
c2.metric("Volumen HP", f"{fhp_data['volumen_hp']:,}")
c3.metric("Volumen máx 15 min", f"{fhp_data['volumen_max_15min']:,}",
          help=f"Bloque {fhp_data['bloque_max_inicio']} – "
               f"{fhp_data['bloque_max_fin']}")
c4.metric("FHP", f"{fhp_data['fhp']:.3f}")

# Tabla agrupada (render HTML con 3 niveles de encabezado)
if resumen_agr is not None:
    st.markdown("### 📋 Resumen hora pico (agrupado)")
    st.markdown(_tabla_agrupada_html(resumen_agr), unsafe_allow_html=True)
else:
    st.warning("El archivo no tiene hoja MAPA: se omite el resumen agrupado.")

# Pesados
if pesados_hp is not None:
    st.markdown("### 🚛 % de pesados — hora pico")
    st.dataframe(pesados_hp, use_container_width=True)

if pesados_total is not None:
    with st.expander("🚛 % de pesados — total del censo"):
        st.dataframe(pesados_total, use_container_width=True)

# Detalles
with st.expander("📄 Resumen hora pico (plano)"):
    st.dataframe(resumen_plano, use_container_width=True)

with st.expander("📄 Totales por bloque de 15 min"):
    st.dataframe(totales, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# 7) Gráficos
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("📈 Gráficos")

# Título / subtítulo base (editables en Personalización de gráficos)
titulo_base = titulo_personalizado.strip() or "VOLUMEN TRÁNSITO"
subtitulo_base = (subtitulo_personalizado.strip()
                  or f"{dia_txt} {_fecha_legible(fecha_sel)}".strip())

# Volumen por calle/sentido (vectorizado, excluye tipos configurados)
mapa_dict = {}
if mapa is not None:
    mapa_dict = {row["movimiento"]: (row["calle"], row["sentido"])
                 for _, row in mapa.iterrows()}

df_validos = df[~df["tipo_vehiculo"].isin(excluidos_final)]
df_cs = grf.volumen_por_calle_sentido(df_validos, movs, mapa_dict)

# (título de sección, figura) — se reutilizan para los reportes PDF/DOCX
figuras = []

if mapa is not None and not df_cs.empty:
    # ── Líneas: censo completo, todas las calles ──
    st.markdown("### 📈 Distribución por 15 minutos — censo completo")
    fig = grf.fig_lineas(df_cs, titulo_base, subtitulo_base, paleta)
    _, col_cen, _ = st.columns([1, 8, 1])
    with col_cen:
        st.plotly_chart(_web(fig, 480), use_container_width=True)
    figuras.append(("Distribución por 15 minutos — censo completo", fig))

    # ── Barras por hora, una por calle (de a 2 por fila) ──
    st.markdown("### 📊 Volumen por hora — censo completo")
    agg_hora = grf.agregar_por_hora(df_cs)
    figs_hora = []
    for calle in sorted(agg_hora["calle"].unique()):
        sub_calle = agg_hora[agg_hora["calle"] == calle]
        fig = grf.fig_barras_agrupadas(
            sub_calle, "hora_entera",
            sorted(sub_calle["hora_entera"].unique()),
            titulo=f"{titulo_base} {calle}",
            subtitulo=subtitulo_base,
            eje_y="VOLUMEN HORARIO",
            paleta=paleta,
            height=550,
        )
        if fig is None:
            continue
        figs_hora.append((f"Volumen por hora — {calle}", fig))
        figuras.append((f"Volumen por hora — {calle}", fig))
    _filas_dos_columnas(figs_hora, 320)

    # ── Barras de 15 min en la hora pico, una por calle (de a 2 por fila) ──
    st.markdown("### 📊 Volumen por 15 min — hora pico")
    hp_ini, hp_fin = pico[0], pico[1]
    bloques_hp = totales[(totales["hora_inicio"] >= hp_ini) & (totales["hora_fin"] <= hp_fin)]
    horas_hp = bloques_hp["hora_inicio"].tolist()

    if subtitulo_personalizado.strip():
        subtitulo_hp = subtitulo_personalizado.strip()
    elif subtitulo_base:
        subtitulo_hp = f"DE {hp_ini} a {hp_fin} DEL {subtitulo_base}"
    else:
        subtitulo_hp = ""

    figs_15 = []
    for calle in sorted(df_cs["calle"].unique()):
        sub_calle = df_cs[df_cs["calle"] == calle]
        fig = grf.fig_barras_agrupadas(
            sub_calle, "hora_inicio", horas_hp,
            titulo=f"{titulo_base} {calle}",
            subtitulo=subtitulo_hp,
            eje_y="VOLUMEN CADA 15 MINUTOS",
            paleta=paleta,
            height=550,
        )
        if fig is None:
            continue
        figs_15.append((f"Volumen cada 15 min (hora pico) — {calle}", fig))
        figuras.append((f"Volumen cada 15 min (hora pico) — {calle}", fig))
    _filas_dos_columnas(figs_15, 320)
else:
    st.info("Sin hoja MAPA o sin movimientos mapeados: "
            "se muestran solo los gráficos de composición.")

# ── Tortas: composición por tipo (incluye tipos excluidos) ──
st.markdown("### 🥧 Composición por tipo de vehículo")

serie_hp = df[(df["hora_inicio"] >= pico[0]) & (df["hora_fin"] <= pico[1])]
serie_hp = serie_hp.groupby("tipo_vehiculo")[movs].sum().sum(axis=1)
serie_hp = serie_hp[serie_hp > 0].sort_values(ascending=False)

serie_total = df.groupby("tipo_vehiculo")[movs].sum().sum(axis=1)
serie_total = serie_total[serie_total > 0].sort_values(ascending=False)

fig_t1 = grf.fig_torta(serie_hp, "Composición por tipo — hora pico",
                       subtitulo_base, paleta)
fig_t2 = grf.fig_torta(serie_total, "Composición por tipo — censo completo",
                       subtitulo_base, paleta)

col_torta1, col_torta2 = st.columns(2)
with col_torta1:
    if fig_t1 is not None:
        st.plotly_chart(fig_t1, use_container_width=True)
with col_torta2:
    if fig_t2 is not None:
        st.plotly_chart(fig_t2, use_container_width=True)

if fig_t1 is not None:
    figuras.append(("Composición por tipo — hora pico", fig_t1))
if fig_t2 is not None:
    figuras.append(("Composición por tipo — censo completo", fig_t2))

# ── % de pesados ──
if pesados_hp is not None:
    st.markdown("### 📊 % de pesados por movimiento — hora pico")
    fig_pesados = grf.fig_pesados(pesados_hp, paleta)
    if fig_pesados is not None:
        _, col_cen, _ = st.columns([1, 2, 1])
        with col_cen:
            st.plotly_chart(fig_pesados, use_container_width=True)
        figuras.append(("% de pesados por movimiento — hora pico",
                        fig_pesados))
    else:
        st.info("No hay movimientos con pesados para graficar.")


# ─────────────────────────────────────────────────────────────
# 8) Croquis
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("🗺️ Croquis de la intersección")

# ── Inferencias desde el MAPA ──
nombres_inferidos = _inferir_nombres_ramas(mapa, movs)
mapeo_default = _inferir_mapeo_default(mapa, movs)

# ── Referencia visual + nombres de ramas/extremos (editables) ──
nombres_ramas = {}
nombres_extremos = {}
with st.expander("📖 ¿Qué movimiento es cada M?"):
    st.caption("Esquemas de referencia (sin valores). El mapeo concreto "
               "se configura más abajo.")
    for titulo, ruta in [
        ("Cruz — 4 ramas (N, S, E, O)", "assets/croquis_cruz.svg"),
        ("T — 3 ramas (S, O, E; sin Norte)", "assets/croquis_T.svg"),
        ("Ruta — ida y vuelta", "assets/croquis_ruta.svg"),
    ]:
        st.markdown(f"**{titulo}**")
        st.markdown(
            f'<div style="max-width:750px; margin:0 auto;">'
            f'{croquis_svg.leer_svg_esquema(ruta)}</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    # ── Nombres de ramas / extremos (editables, según el tipo) ──
    if tipo_croquis == "Ruta":
        st.markdown("**Nombres de los extremos** (editables)")
        c1, c2 = st.columns(2)
        with c1:
            nombre_oeste = st.text_input("Extremo Oeste",
                                         value=nombres_inferidos["O"],
                                         key="nom_O")
        with c2:
            nombre_este = st.text_input("Extremo Este",
                                        value=nombres_inferidos["E"],
                                        key="nom_E")
        nombres_extremos = {"O": nombre_oeste, "E": nombre_este}
    else:
        ramas_ui = (["S", "E", "O"] if tipo_croquis == "T"
                    else ["N", "S", "E", "O"])
        st.markdown("**Nombres de las ramas** (editables)")
        cols = st.columns(len(ramas_ui))
        for col, rama in zip(cols, ramas_ui):
            with col:
                nombres_ramas[rama] = st.text_input(
                    f"Rama {nombres_inferidos[rama].title()}",
                    value=nombres_inferidos[rama],
                    key=f"nom_{rama}",
                )

# ── Mapeo movimiento → posición del croquis ──
with st.expander("🎯 Mapeo de movimientos (a qué flecha del croquis va cada uno)"):
    if tipo_croquis == "Cruz":
        opciones_mapeo = list(croquis_svg.ORDEN_CANONICO)
    elif tipo_croquis == "T":
        opciones_mapeo = [p for p in croquis_svg.ORDEN_CANONICO
                          if p not in croquis_svg.SLOTS_INVALIDOS_T
                          and not p.startswith("N_")]
    else:
        opciones_mapeo = list(croquis_svg.POSICIONES_RUTA)

    OPCIONES_MAPEO = ["— (no mostrar)"] + opciones_mapeo

    mapeo_final = {}
    cols_mapeo = st.columns(4)
    for i, mov in enumerate(movs):
        with cols_mapeo[i % 4]:
            default = mapeo_default.get(mov, "— (no mostrar)")
            idx = (OPCIONES_MAPEO.index(default)
                   if default in OPCIONES_MAPEO else 0)
            seleccion = st.selectbox(f"{mov}", OPCIONES_MAPEO, index=idx,
                                     key=f"map_{mov}")
            if seleccion != "— (no mostrar)":
                mapeo_final[mov] = seleccion

# ── Volúmenes ──
# Hora pico: desde resumen_plano (ya excluye tipos configurados)
movs_hp = [c for c in resumen_plano.columns if c != "TOTAL"]
tipos_validos = [t for t in resumen_plano.index
                 if t != "TOTAL" and t not in excluidos_final]

volumenes_hp = {mov: int(resumen_plano.loc[tipos_validos, mov].sum())
                for mov in movs_hp if mov in mapeo_final}

# Total del censo: desde df (excluyendo tipos configurados)
volumenes_total = {mov: int(df_validos[mov].sum())
                   for mov in movs if mov in mapeo_final}

# ── Render de los dos croquis ──
croquis_reporte = []  # [(título, svg)] para incluir en el reporte PDF/DOCX
if mapa is not None and len(mapeo_final) > 0:
    ancho_contenedor = "900px" if tipo_croquis == "Ruta" else "750px"

    # ── Croquis hora pico ──
    st.markdown(f"### 🚦 Croquis {tipo_croquis} — hora pico")
    svg_hp_html, altura_hp = _render_croquis(tipo_croquis, volumenes_hp, mapeo_final,
                                             nombres_ramas, nombres_extremos)
    components.html(
        f'<div style="max-width:{ancho_contenedor}; margin:0 auto;">'
        f'{svg_hp_html}</div>',
        height=altura_hp,
        scrolling=False,
    )
    croquis_reporte.append(
        (f"Croquis {tipo_croquis} — hora pico",
         croquis_svg.extraer_svg(svg_hp_html))
    )

    # ── Croquis total ──
    st.markdown(f"### 🚦 Croquis {tipo_croquis} — total del censo")
    svg_total_html, altura_total = _render_croquis(tipo_croquis, volumenes_total, mapeo_final,
                                                   nombres_ramas, nombres_extremos)
    components.html(
        f'<div style="max-width:{ancho_contenedor}; margin:0 auto;">'
        f'{svg_total_html}</div>',
        height=altura_total,
        scrolling=False,
    )
    croquis_reporte.append(
        (f"Croquis {tipo_croquis} — total del censo",
         croquis_svg.extraer_svg(svg_total_html))
    )

# ─────────────────────────────────────────────────────────────
# 9) Descargas
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("⬇️ Descargas")

nombre_base = Path(archivo.name).stem

st.download_button(
    label="⬇️ Descargar Excel con todos los resultados",
    data=salida_buffer.getvalue(),
    file_name=f"resultado_{nombre_base}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)

# ── Reportes PDF / DOCX ──
imagenes = _imagenes_reporte(figuras)

ctx_reporte = {
    "titulo": titulo_base,
    "subtitulo": subtitulo_base,
    "fecha": fecha_sel,
    "dia": dia_txt,
    "ubicacion": ubicacion_txt,
    "lugar": lugar_txt,
    "analista": analista_txt,
    "fhp_data": fhp_data,
    "resumen_agr": resumen_agr,
    "resumen_plano": resumen_plano,
    "pesados_hp": pesados_hp,
    "totales": totales,
    "excluidos": excluidos_final,
    "imagenes": imagenes,
    "croquis": croquis_reporte,
}

col_pdf, col_docx = st.columns(2)

with col_pdf:
    try:
        pdf_bytes = _generar_pdf(ctx_reporte)
        st.download_button(
            label="⬇️ Descargar reporte PDF",
            data=pdf_bytes,
            file_name=f"reporte_{nombre_base}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"❌ No se pudo generar el PDF: {e}")

with col_docx:
    try:
        docx_bytes = _generar_docx(ctx_reporte)
        st.download_button(
            label="⬇️ Descargar reporte DOCX",
            data=docx_bytes,
            file_name=f"reporte_{nombre_base}.docx",
            mime="application/vnd.openxmlformats-officedocument"
                 ".wordprocessingml.document",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"❌ No se pudo generar el DOCX: {e}")






