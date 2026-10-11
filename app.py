"""
app.py — Interfaz Streamlit para procesamiento de censos vehiculares.

Ejecutar:
    streamlit run app.py
"""

import io
import re
from pathlib import Path

import pandas as pd
import streamlit as st

# Importar el motor existente
import procesar_censo3 as motor

#importar generador de croquis
import croquis as crq


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


# ─────────────────────────────────────────────────────────────
# 2) Lectura inicial (para poblar checkboxes)
# ─────────────────────────────────────────────────────────────
# Streamlit necesita un path o buffer. Pasamos un buffer de bytes al motor.
@st.cache_data(show_spinner=False)
def cargar_estructura(contenido: bytes):
    """Lee el Excel y devuelve metadata para poblar la UI."""
    buffer = io.BytesIO(contenido)

    # Leer hojas directamente
    xls = pd.ExcelFile(buffer)

    if "DATOS" not in xls.sheet_names:
        raise ValueError("El archivo no tiene una hoja 'DATOS'.")

    # Leer CONFIG si existe
    buffer.seek(0)
    try:
        df_cfg = pd.read_excel(buffer, sheet_name="CONFIG", dtype=str)
        df_cfg.columns = [str(c).strip().lower() for c in df_cfg.columns]
        cfg = {}
        for _, row in df_cfg.iterrows():
            cfg[str(row["clave"]).strip().lower()] = (
                str(row["valor"]).strip() if pd.notna(row["valor"]) else ""
            )
    except Exception:
        cfg = {}

    # Leer DATOS para sacar tipos
    buffer.seek(0)
    df_datos = pd.read_excel(buffer, sheet_name="DATOS", dtype=str)
    df_datos.columns = [str(c).strip() for c in df_datos.columns]

    tipos = sorted(
        df_datos["tipo_vehiculo"].dropna().astype(str).str.strip().unique().tolist()
    ) if "tipo_vehiculo" in df_datos.columns else []

    return cfg, tipos


try:
    cfg_inicial, tipos_detectados = cargar_estructura(archivo.getvalue())
except Exception as e:
    st.error(f"❌ Error al leer el archivo: {e}")
    st.stop()


# ─────────────────────────────────────────────────────────────
# 3) Controles de configuración
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("⚙️ Configuración")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Tipos a excluir** (no suman en hora pico ni totales)")
    excluidos_default = [t.strip() for t in cfg_inicial.get("tipos_excluidos", "").split(",") if t.strip()]
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
        value=cfg_inicial.get("nombre_fila_total", motor.NOMBRE_FILA_TOTAL_DEFAULT),
        label_visibility="collapsed",
    )

st.markdown("**Tipos pesados** (para el cálculo del % de pesados)")
calcular_pesados = st.checkbox(
    "Calcular % de vehículos pesados",
    value=cfg_inicial.get("calcular_pct_pesados", "NO").strip().upper() == "SI",
)

tipos_pesados_default = [t.strip() for t in cfg_inicial.get("tipos_pesados", "").split(",") if t.strip()]
tipos_pesados = st.multiselect(
    "Tipos que cuentan como pesados",
    options=[t for t in tipos_detectados if t not in excluidos],
    default=[t for t in tipos_pesados_default if t in tipos_detectados and t not in excluidos],
    disabled=not calcular_pesados,
)

st.markdown("**Personalización de gráficos** (opcional, se puede dejar vacío)")
col_t1, col_t2 = st.columns(2)

with col_t1:
    titulo_personalizado = st.text_input(
        "Título de los gráficos",
        value="",
        placeholder="Ej: VOLUMEN TRÁNSITO",
        help="Si lo dejás vacío, se usa 'VOLUMEN TRÁNSITO <calle>'",
    )

with col_t2:
    subtitulo_personalizado = st.text_input(
        "Subtítulo de los gráficos",
        value="",
        placeholder="Ej: DOMINGO 26 DE JULIO DE 2026",
        help="Si lo dejás vacío, se usa la fecha del CONFIG",
    )


# ─────────────────────────────────────────────────────────────
# 4) Procesamiento
# ─────────────────────────────────────────────────────────────
if not st.button("▶️ Procesar censo", type="primary"):
    st.stop()

with st.spinner("Procesando..."):

    # Reconstruimos el Excel con la config actualizada del usuario
    # (para que el motor lo lea como si fuera un archivo normal)
    buffer = io.BytesIO(archivo.getvalue())

    # Reescribimos CONFIG con los valores de la UI
    xls = pd.ExcelFile(buffer)
    hojas = {nombre: pd.read_excel(buffer, sheet_name=nombre, dtype=str)
             for nombre in xls.sheet_names}
    hojas["CONFIG"] = pd.DataFrame({
        "clave": [
            "tipos_excluidos",
            "nombre_fila_total",
            "calcular_pct_pesados",
            "tipos_pesados",
        ],
        "valor": [
            ", ".join(excluidos),
            nombre_fila_total,
            "SI" if calcular_pesados else "NO",
            ", ".join(tipos_pesados),
        ],
    })

    # Guardamos en un archivo temporal en memoria
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as w:
        for nombre, df in hojas.items():
            df.to_excel(w, sheet_name=nombre, index=False)
    excel_buffer.seek(0)

    # Guardamos a un archivo temporal en disco (el motor lee por path)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(excel_buffer.getvalue())
        ruta_tmp = Path(tmp.name)

    # ── Ejecutamos el motor paso a paso (sin CLI) ──
    try:
        cfg = motor.leer_config(str(ruta_tmp))
        mapa = motor.leer_mapa(str(ruta_tmp))
        df, movs = motor.leer_datos(str(ruta_tmp))

#para comprobacion luego comentar
        st.write("**DEBUG — tipos en df:**", sorted(df["tipo_vehiculo"].unique()))
        st.write("**DEBUG — shape df:**", df.shape)
        st.write("**DEBUG — suma por tipo:**",
                df.groupby("tipo_vehiculo")[movs].sum().sum(axis=1).to_dict())

        excluidos_final = excluidos if excluidos else motor.TIPOS_EXCLUIDOS_DEFAULT

        totales = motor.totales_15min(df, movs, excluidos_final)
        pico = motor.detectar_hora_pico(totales, motor.VENTANA_PICO)
        fhp_data = motor.calcular_fhp(totales, pico[0], pico[1], motor.VENTANA_PICO)

        resumen_plano = motor.resumen_plano_hora_pico(
            df, movs, excluidos_final, pico[0], pico[1]
        )

        resumen_agr = None
        if mapa is not None and len(mapa) > 0:
            resumen_agr = motor.resumen_agrupado(
                df, movs, excluidos_final, mapa, pico[0], pico[1],
                nombre_fila_total,
            )

        pesados_hp = None
        pesados_total = None
        if calcular_pesados and tipos_pesados:
            df_hp = df[(df["hora_inicio"] >= pico[0]) & (df["hora_fin"] <= pico[1])]
            pesados_hp = motor.tabla_pesados(
                df_hp, movs, tipos_pesados, excluidos_final, nombre_fila_total
            )
            pesados_total = motor.tabla_pesados(
                df, movs, tipos_pesados, excluidos_final, nombre_fila_total
            )

    finally:
        ruta_tmp.unlink(missing_ok=True)

    # Guardamos también el Excel de salida en memoria para descarga
    salida_buffer = io.BytesIO()
    with pd.ExcelWriter(salida_buffer, engine="openpyxl") as w:
        pd.DataFrame([
            ("Hora pico inicio",   fhp_data["hora_pico_inicio"]),
            ("Hora pico fin",      fhp_data["hora_pico_fin"]),
            ("Volumen HP",         fhp_data["volumen_hp"]),
            ("Bloque máx inicio",  fhp_data["bloque_max_inicio"]),
            ("Bloque máx fin",     fhp_data["bloque_max_fin"]),
            ("Volumen máx 15 min", fhp_data["volumen_max_15min"]),
            ("FHP",                fhp_data["fhp"]),
        ], columns=["concepto", "valor"]).to_excel(w, sheet_name="FHP", index=False)

        if resumen_agr is not None:
            resumen_agr.to_excel(w, sheet_name="Resumen_Hora_Pico")
        resumen_plano.to_excel(w, sheet_name="Resumen_Hora_Pico_Plano")
        if pesados_hp is not None:
            pesados_hp.to_excel(w, sheet_name="Pesados_Hora_Pico")
        if pesados_total is not None:
            pesados_total.to_excel(w, sheet_name="Pesados_Total")
        totales.to_excel(w, sheet_name="Totales_15min", index=False)
        df.to_excel(w, sheet_name="Datos_Originales", index=False)

    salida_buffer.seek(0)


# ─────────────────────────────────────────────────────────────
# 5) Mostrar resultados
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("📊 Resultados")

# Métricas destacadas
c1, c2, c3, c4 = st.columns(4)
c1.metric("Hora pico", f"{fhp_data['hora_pico_inicio']} – {fhp_data['hora_pico_fin']}")
c2.metric("Volumen HP", f"{fhp_data['volumen_hp']:,}")
c3.metric("Volumen máx 15 min", f"{fhp_data['volumen_max_15min']:,}",
          help=f"Bloque {fhp_data['bloque_max_inicio']} – {fhp_data['bloque_max_fin']}")
c4.metric("FHP", f"{fhp_data['fhp']:.3f}")

# Tabla agrupada (render HTML con 3 niveles de encabezado)
if resumen_agr is not None:
    st.markdown("### 📋 Resumen hora pico (agrupado)")

    # ── Preparar estructura: separar calle y sentido ──
    columnas = list(resumen_agr.columns)

    # Agrupar columnas por calle (nivel 0 del índice de columnas)
    # Cada columna es (calle_sentido, mov). Lo partimos en (calle, sentido, mov)
    columnas_split = []
    for grupo, mov in columnas:
        if grupo == "Total":
            columnas_split.append(("Total", "", ""))
        else:
            partes = [p.strip() for p in grupo.split("|")]
            calle = partes[0] if len(partes) > 0 else ""
            sentido = partes[1] if len(partes) > 1 else ""
            columnas_split.append((calle, sentido, mov))

    # ── Fila 1: calles (con colspan) ──
    fila1 = []
    i = 0
    while i < len(columnas_split):
        calle = columnas_split[i][0]
        span = 1
        while i + span < len(columnas_split) and columnas_split[i + span][0] == calle:
            span += 1
        fila1.append((calle, span))
        i += span

    # ── Fila 2: sentidos (con colspan cuando se repiten) ──
    fila2 = []
    i = 0
    while i < len(columnas_split):
        calle, sentido, _ = columnas_split[i]
        # Agrupar por (calle, sentido) consecutivos
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

    # Fila 1
    html += "<tr><th rowspan='3' style='vertical-align:middle;'>Tipo</th>"
    for calle, span in fila1:
        html += f"<th colspan='{span}'>{calle}</th>"
    html += "</tr>"

    # Fila 2
    html += "<tr>"
    for sentido, span in fila2:
        html += f"<th colspan='{span}'>{sentido}</th>"
    html += "</tr>"

    # Fila 3
    html += "<tr>"
    for mov in fila3:
        html += f"<th>{mov}</th>"
    html += "</tr></thead><tbody>"

    # Filas de datos
    for idx, row in resumen_agr.iterrows():
        html += f"<tr><td>{idx}</td>"
        for val in row:
            html += f"<td>{val}</td>"
        html += "</tr>"
    html += "</tbody></table>"

    st.markdown(html, unsafe_allow_html=True)

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
# 5b) Gráficos
# ─────────────────────────────────────────────────────────────
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.divider()
st.subheader("📈 Gráficos")


# ── Títulos editables ──
def _fecha_legible(fecha_iso: str) -> str:
    """'2026-09-22' o '22/09/2026' → 'MARTES 22 DE SEPTIEMBRE DE 2026'."""
    if not fecha_iso:
        return ""
    dt = None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(fecha_iso.strip(), fmt)
            break
        except Exception:
            continue
    if dt is None:
        return fecha_iso
    dias = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES",
            "SÁBADO", "DOMINGO"]
    meses = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
             "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
    return f"{dias[dt.weekday()]} {dt.day} DE {meses[dt.month - 1]} DE {dt.year}"


fecha_censo = cfg.get("fecha_censo", "").strip()
subtitulo_base = subtitulo_personalizado.strip() or _fecha_legible(fecha_censo)


# ── Preparar datos de series por calle/sentido ──
# Necesitamos: para cada bloque (hora o 15 min) × calle × sentido → volumen
# Excluimos tipos excluidos.
df_validos = df[~df["tipo_vehiculo"].isin(excluidos_final)]

# Traer calle/sentido de cada movimiento
mapa_dict = {}
if mapa is not None:
    for _, row in mapa.iterrows():
        mapa_dict[row["movimiento"]] = (row["calle"], row["sentido"])

# Enriquecer df con calle/sentido
df_enriq = df_validos.copy()
df_enriq["calle"] = df_enriq.apply(
    lambda r: mapa_dict.get(r.name, (None, None))[0] if False else None, axis=1
)

# Mejor: armar tabla de agregación manualmente (más robusto)
def _volumen_por_calle_sentido(df_validos, movs, mapa_dict):
    """
    Devuelve DataFrame con columnas:
        hora_inicio, hora_fin, calle, sentido, volumen
    Agrupa por bloque × calle × sentido.
    """
    registros = []
    for _, fila in df_validos.iterrows():
        for mov in movs:
            if mov not in mapa_dict:
                continue
            calle, sentido = mapa_dict[mov]
            vol = int(fila[mov])
            if vol == 0:
                continue
            registros.append({
                "hora_inicio": fila["hora_inicio"],
                "hora_fin": fila["hora_fin"],
                "calle": calle,
                "sentido": sentido,
                "volumen": vol,
            })
    if not registros:
        return pd.DataFrame(columns=["hora_inicio", "hora_fin", "calle",
                                     "sentido", "volumen"])
    df_reg = pd.DataFrame(registros)
    agg = df_reg.groupby(
        ["hora_inicio", "hora_fin", "calle", "sentido"],
        as_index=False
    )["volumen"].sum()
    return agg


df_cs = _volumen_por_calle_sentido(df_validos, movs, mapa_dict)


# ── Función para dibujar un gráfico de barras agrupadas ──
def _grafico_barras(df_cs, calle, bloques, titulo, subtitulo,
                    etiquetas_x, eje_y_label):
    """
    df_cs      : DataFrame con columnas hora_inicio, calle, sentido, volumen
    calle      : nombre de la calle a graficar
    bloques    : lista de (hora_inicio, hora_fin, etiqueta_x)
    """
    sub = df_cs[df_cs["calle"] == calle]
    if sub.empty:
        st.info(f"Sin datos para la calle '{calle}'.")
        return

    sentidos = sorted(sub["sentido"].unique())
    # Colores: azul, rojo, verde, violeta, naranja...
    paleta = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd",
              "#ff7f0e", "#8c564b", "#e377c2"]

    fig = go.Figure()
    for i, sentido in enumerate(sentidos):
        valores = []
        for hi, hf, _ in bloques:
            v = sub[
                (sub["hora_inicio"] == hi) &
                (sub["sentido"] == sentido)
            ]["volumen"].sum()
            valores.append(int(v))
        fig.add_trace(go.Bar(
            name=sentido,
            x=etiquetas_x,
            y=valores,
            marker_color=paleta[i % len(paleta)],
        ))

    # Serie "Ambos" (suma de sentidos)
    valores_ambos = []
    for hi, hf, _ in bloques:
        v = sub[sub["hora_inicio"] == hi]["volumen"].sum()
        valores_ambos.append(int(v))
    fig.add_trace(go.Bar(
        name="Ambos",
        x=etiquetas_x,
        y=valores_ambos,
        marker_color=paleta[len(sentidos) % len(paleta)],
    ))

    fig.update_layout(
        title=dict(
            text=f"{titulo}<br><sub>{subtitulo}</sub>",
            x=0.5,
            xanchor="center",
            font=dict(size=16),
        ),
        xaxis_title="",
        yaxis_title=eje_y_label,
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.0,
                    xanchor="right", x=1.0),
        margin=dict(l=60, r=20, t=80, b=50),
        height=420,
        plot_bgcolor="white",
        yaxis=dict(gridcolor="#e0e0e0"),
    )
    st.plotly_chart(fig, use_container_width=True)


# Definición global de título base para todos los gráficos
titulo_base = titulo_personalizado.strip() or "VOLUMEN TRÁNSITO"

# ═════════════════════════════════════════════════════════════
# GRÁFICO A — Censo completo por 15 min (líneas, todas las calles)
# ═════════════════════════════════════════════════════════════
if mapa is not None and not df_cs.empty:
    st.markdown("### 📈 Distribución por 15 minutos — censo completo")

    titulo_base = titulo_personalizado.strip() or "VOLUMEN TRÁNSITO"

    # Eje X: todos los bloques de 15 min ordenados
    bloques_15 = sorted(df_cs["hora_inicio"].unique())

    fig_lineas = go.Figure()

    # Una línea por sentido (de todas las calles)
    sentidos_unicos = sorted(df_cs["sentido"].unique())
    paleta_lineas = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd",
                     "#ff7f0e", "#8c564b", "#e377c2", "#7f7f7f"]

    for i, sentido in enumerate(sentidos_unicos):
        sub = df_cs[df_cs["sentido"] == sentido]
        valores = []
        for hi in bloques_15:
            v = sub[sub["hora_inicio"] == hi]["volumen"].sum()
            valores.append(int(v))

        fig_lineas.add_trace(go.Scatter(
            x=bloques_15,
            y=valores,
            mode="lines+markers",
            name=sentido,
            line=dict(width=2.5, color=paleta_lineas[i % len(paleta_lineas)]),
            marker=dict(size=7),
        ))

    fig_lineas.update_layout(
        title=dict(
            text=f"{titulo_base}<br><sub>{subtitulo_base}</sub>",
            x=0.5, xanchor="center", font=dict(size=16),
        ),
        xaxis_title="",
        yaxis_title="VOLUMEN",
        legend=dict(orientation="h", yanchor="bottom", y=-0.25,
                    xanchor="center", x=0.5),
        margin=dict(l=60, r=20, t=80, b=80),
        height=460,
        plot_bgcolor="white",
        xaxis=dict(gridcolor="#f0f0f0", tickangle=-45),
        yaxis=dict(gridcolor="#e0e0e0"),
    )
    st.plotly_chart(fig_lineas, use_container_width=True)


# ═════════════════════════════════════════════════════════════
# GRÁFICO B — Censo completo por hora (barras agrupadas)
# ═════════════════════════════════════════════════════════════
if mapa is not None and not df_cs.empty:
    st.markdown("### 📊 Volumen por hora — censo completo")

    # Agrupar bloques por hora entera (HH:00)
    df_cs_hora = df_cs.copy()
    df_cs_hora["hora_entera"] = df_cs_hora["hora_inicio"].str.slice(0, 2) + ":00"

    # Suma por (hora_entera, calle, sentido)
    agg_hora = df_cs_hora.groupby(
        ["hora_entera", "calle", "sentido"], as_index=False
    )["volumen"].sum()

    horas_orden = sorted(agg_hora["hora_entera"].unique())
    calles = sorted(agg_hora["calle"].unique())

    for calle in calles:
        sub_calle = agg_hora[agg_hora["calle"] == calle]
        sentidos = sorted(sub_calle["sentido"].unique())
        paleta_bar = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd",
                      "#ff7f0e", "#8c564b", "#e377c2"]

        fig_hora = go.Figure()
        for i, sentido in enumerate(sentidos):
            valores = []
            for h in horas_orden:
                v = sub_calle[
                    (sub_calle["hora_entera"] == h) &
                    (sub_calle["sentido"] == sentido)
                ]["volumen"].sum()
                valores.append(int(v))
            fig_hora.add_trace(go.Bar(
                name=sentido,
                x=horas_orden,
                y=valores,
                marker_color=paleta_bar[i % len(paleta_bar)],
            ))

        # Serie "Ambos" (suma de sentidos de esa calle por hora)
        valores_ambos = []
        for h in horas_orden:
            v = sub_calle[sub_calle["hora_entera"] == h]["volumen"].sum()
            valores_ambos.append(int(v))
        fig_hora.add_trace(go.Bar(
            name="Ambos",
            x=horas_orden,
            y=valores_ambos,
            marker_color=paleta_bar[len(sentidos) % len(paleta_bar)],
        ))

        fig_hora.update_layout(
            title=dict(
                text=f"{titulo_base} {calle}<br><sub>{subtitulo_base}</sub>",
                x=0.5, xanchor="center", font=dict(size=15),
            ),
            xaxis_title="",
            yaxis_title="VOLUMEN HORARIO",
            barmode="group",
            legend=dict(orientation="h", yanchor="bottom", y=1.0,
                        xanchor="right", x=1.0),
            margin=dict(l=60, r=20, t=80, b=50),
            height=420,
            plot_bgcolor="white",
            yaxis=dict(gridcolor="#e0e0e0"),
        )
        st.plotly_chart(fig_hora, use_container_width=True)


# ═════════════════════════════════════════════════════════════
# GRÁFICO C — Hora pico por 15 min (barras agrupadas, uno por calle)
# ═════════════════════════════════════════════════════════════
if mapa is not None and not df_cs.empty:
    st.markdown("### 📊 Volumen por 15 min — hora pico")

    hp_ini, hp_fin = pico[0], pico[1]
    bloques_hp_df = totales[
        (totales["hora_inicio"] >= hp_ini) &
        (totales["hora_fin"] <= hp_fin)
    ][["hora_inicio", "hora_fin"]].reset_index(drop=True)

    bloques_hp = [
        (row["hora_inicio"], row["hora_fin"], row["hora_inicio"])
        for _, row in bloques_hp_df.iterrows()
    ]
    etiquetas_x_hp = [b[2] for b in bloques_hp]

    if subtitulo_personalizado.strip():
        subtitulo_hp = subtitulo_personalizado.strip()
    elif subtitulo_base:
        subtitulo_hp = f"DE {hp_ini} a {hp_fin} DEL {subtitulo_base}"
    else:
        subtitulo_hp = ""

    calles = sorted(df_cs["calle"].unique())
    for calle in calles:
        _grafico_barras(
            df_cs, calle, bloques_hp,
            titulo=f"{titulo_base} {calle}",
            subtitulo=subtitulo_hp,
            etiquetas_x=etiquetas_x_hp,
            eje_y_label="VOLUMEN CADA 15 MINUTOS",
        )
# ═════════════════════════════════════════════════════════════
# GRÁFICO 3 y 4 — Torta de composición (con excluidos en gris)
# ═════════════════════════════════════════════════════════════
def _grafico_torta(series, titulo, subtitulo=""):
    """Torta de composición. Incluye TODOS los tipos (excluidos o no)."""
    if series is None or series.empty or series.sum() == 0:
        st.info("Sin datos para graficar.")
        return

    titulo_completo = titulo
    if subtitulo:
        titulo_completo = f"{titulo}<br><sub>{subtitulo}</sub>"

    fig = go.Figure(go.Pie(
        labels=list(series.index),
        values=list(series.values),
        hole=0.4,
        textinfo="percent+label",
        textposition="inside",
    ))
    fig.update_layout(
        title=dict(text=titulo_completo, x=0.5, xanchor="center",
                   font=dict(size=14)),
        showlegend=True,
        margin=dict(l=10, r=10, t=60, b=10),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


st.markdown("### 🥧 Composición por tipo de vehículo")

# ── Bloque 1: composición hora pico (TODOS los tipos, incluidos excluidos) ──
# Filtramos df a los 4 bloques de la hora pico, SIN excluir nada
df_hp_todos = df[
    (df["hora_inicio"] >= pico[0]) & (df["hora_fin"] <= pico[1])
]
serie_hp_todos = df_hp_todos.groupby("tipo_vehiculo")[movs].sum().sum(axis=1)
serie_hp_todos = serie_hp_todos[serie_hp_todos > 0].sort_values(ascending=False)

# ── Bloque 2: composición censo completo (TODOS los tipos) ──
serie_total_todos = df.groupby("tipo_vehiculo")[movs].sum().sum(axis=1)
serie_total_todos = serie_total_todos[serie_total_todos > 0].sort_values(ascending=False)

# ── Render ──
col_t1, col_t2 = st.columns(2)

with col_t1:
    _grafico_torta(serie_hp_todos, "Composición por tipo — hora pico",
                   subtitulo_base)

with col_t2:
    _grafico_torta(serie_total_todos, "Composición por tipo — censo completo",
                   subtitulo_base)


# ═════════════════════════════════════════════════════════════
# GRÁFICO 5 — % pesados por movimiento (si aplica)
# ═════════════════════════════════════════════════════════════
if pesados_hp is not None:
    st.markdown("### 📊 % de pesados por movimiento — hora pico")
    pct_row = pesados_hp.loc["% pesados"]
    pct_row = pct_row[[c for c in pct_row.index if c != "Total"]]
    pct_row = pct_row[pct_row > 0].sort_values(ascending=True)

    if len(pct_row) > 0:
        fig_pct = px.bar(
            x=pct_row.values,
            y=pct_row.index,
            orientation="h",
            labels={"x": "% pesados", "y": "Movimiento"},
            color=pct_row.values,
            color_continuous_scale="Reds",
        )
        fig_pct.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=max(300, len(pct_row) * 25),
            showlegend=False,
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_pct, use_container_width=True)
    else:
        st.info("No hay movimientos con pesados para graficar.")

# ─────────────────────────────────────────────────────────────
# 5c) Croquis
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("🗺️ Croquis de la intersección")


# ── Mapeo de sentido → rama de ORIGEN del croquis ──
# "Norte-Sur" = los vehículos vienen del norte  → entran por la rama N
# "Sur-Norte" = vienen del sur                  → entran por la rama S
# "Este-Oeste"= vienen del este                 → entran por la rama E
# "Oeste-Este"= vienen del oeste                → entran por la rama O
# ── Mapeo FIJO de movimientos a posiciones del croquis ──
# NORTE:  9, 8, 7  (izq a der)
# SUR:   10, 11, 12 (izq a der)
# ESTE:   4, 5, 6   (arriba a abajo)
# OESTE:  1, 2, 3   (arriba a abajo)
MAPEO_FIJO = {
    "M9":  "N_IZQ",  "M8":  "N_FTE",  "M7":  "N_DER",
    "M10": "S_IZQ",  "M11": "S_FTE",  "M12": "S_DER",
    "M4":  "E_IZQ",  "M5":  "E_FTE",  "M6":  "E_DER",
    "M1":  "O_IZQ",  "M2":  "O_FTE",  "M3":  "O_DER",
}


def _inferir_nombres_ramas(mapa_df, movs_activos):
    """
    Devuelve {"N": "Fiambalá Norte", ...} inferido del MAPA,
    mirando a qué rama del croquis va cada movimiento según MAPEO_FIJO.
    """
    nombres = {"N": "", "S": "", "E": "", "O": ""}
    if mapa_df is None:
        for k in nombres:
            nombres[k] = {"N": "Norte", "S": "Sur",
                          "E": "Este", "O": "Oeste"}[k]
        return nombres

    for _, row in mapa_df.iterrows():
        mov = str(row["movimiento"]).strip()
        if mov not in movs_activos or mov not in MAPEO_FIJO:
            continue
        rama = MAPEO_FIJO[mov].split("_")[0]
        if not nombres[rama]:
            calle = str(row["calle"]).strip()
            sufijo = {"N": "Norte", "S": "Sur",
                      "E": "Este", "O": "Oeste"}[rama]
            nombres[rama] = f"{calle} {sufijo}"

    # Fallback
    for k in nombres:
        if not nombres[k]:
            nombres[k] = {"N": "Norte", "S": "Sur",
                          "E": "Este", "O": "Oeste"}[k]
    return nombres


def _inferir_mapeo_default(mapa_df, movs_activos):
    """Devuelve el mapeo fijo para los movimientos que existan."""
    return {m: p for m, p in MAPEO_FIJO.items() if m in movs_activos}

# ── Inferencias ──
nombres_inferidos = _inferir_nombres_ramas(mapa, movs)
mapeo_default = _inferir_mapeo_default(mapa, movs)

# ── Nombres de ramas (editables) ──
st.markdown("**Nombres de las ramas** (editables)")

c1, c2, c3, c4 = st.columns(4)
with c1:
    nombre_N = st.text_input("Rama Norte", value=nombres_inferidos["N"],
                             key="nom_N")
with c2:
    nombre_S = st.text_input("Rama Sur", value=nombres_inferidos["S"],
                             key="nom_S")
with c3:
    nombre_E = st.text_input("Rama Este", value=nombres_inferidos["E"],
                             key="nom_E")
with c4:
    nombre_O = st.text_input("Rama Oeste", value=nombres_inferidos["O"],
                             key="nom_O")

nombres_ramas = {"N": nombre_N, "S": nombre_S, "E": nombre_E, "O": nombre_O}

# ── Mapeo movimiento → posición canónica ──
st.markdown("**Mapeo de movimientos** (a qué flecha del croquis va cada uno)")

OPCIONES_MAPEO = [
    "— (no mostrar)",
    "N_IZQ", "N_FTE", "N_DER",
    "S_IZQ", "S_FTE", "S_DER",
    "E_IZQ", "E_FTE", "E_DER",
    "O_IZQ", "O_FTE", "O_DER",
]

mapeo_final = {}
cols_mapeo = st.columns(4)
for i, mov in enumerate(movs):
    with cols_mapeo[i % 4]:
        default = mapeo_default.get(mov, "— (no mostrar)")
        idx = OPCIONES_MAPEO.index(default) if default in OPCIONES_MAPEO else 0
        seleccion = st.selectbox(
            f"{mov}", OPCIONES_MAPEO, index=idx, key=f"map_{mov}"
        )
        if seleccion != "— (no mostrar)":
            mapeo_final[mov] = seleccion


# ── Volúmenes ──
# Hora pico: desde resumen_plano (ya excluye tipos configurados)
movs_hp = [c for c in resumen_plano.columns if c != "TOTAL"]
tipos_validos = [t for t in resumen_plano.index
                 if t != "TOTAL" and t not in excluidos_final]

volumenes_hp = {}
for mov in movs_hp:
    if mov in mapeo_final:
        volumenes_hp[mov] = int(resumen_plano.loc[tipos_validos, mov].sum())

# Total del censo: desde df (excluyendo tipos configurados)
df_validos = df[~df["tipo_vehiculo"].isin(excluidos_final)]
volumenes_total = {}
for mov in movs:
    if mov in mapeo_final:
        volumenes_total[mov] = int(df_validos[mov].sum())


# ── Render de los dos croquis ──
if mapa is not None and len(mapeo_final) > 0:
    st.markdown("### 🚦 Croquis — hora pico")
    fig_hp = crq.dibujar_croquis_cruz(
        volumenes=volumenes_hp,
        mapeo=mapeo_final,
        nombres_ramas=nombres_ramas,
        titulo=f"Hora pico {pico[0]}–{pico[1]}",
    )
    st.plotly_chart(fig_hp, use_container_width=True)

    st.markdown("### 🚦 Croquis — total del censo")
    fig_total = crq.dibujar_croquis_cruz(
        volumenes=volumenes_total,
        mapeo=mapeo_final,
        nombres_ramas=nombres_ramas,
        titulo="Total del censo",
    )
    st.plotly_chart(fig_total, use_container_width=True)
else:
    st.info("Sin hoja MAPA o sin movimientos mapeados: "
            "no se puede generar el croquis.")

# ─────────────────────────────────────────────────────────────
# 6) Descarga
# ─────────────────────────────────────────────────────────────
st.divider()
nombre_salida = f"resultado_{Path(archivo.name).stem}.xlsx"
st.download_button(
    label="⬇️ Descargar Excel con todos los resultados",
    data=salida_buffer,
    file_name=nombre_salida,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)