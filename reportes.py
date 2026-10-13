"""
reportes.py
-----------
Generación de reportes descargables del censo:

- PDF  (reportlab)   → `generar_pdf(ctx)`
- DOCX (python-docx) → `generar_docx(ctx)` — se abre en Word y en LibreOffice

Las figuras Plotly se convierten a PNG con kaleido (`fig_a_png`) y se
embeben como imágenes (croquis incluido).

`ctx` es un dict con:
    titulo, subtitulo                 str
    fecha (date), dia                 date / str
    ubicacion, lugar, analista        str
    fhp_data                          dict (ver procesar_censo3.calcular_fhp)
    resumen_agr, resumen_plano,       DataFrames (o None)
    pesados_hp, totales
    excluidos                         list[str]
    imagenes                          list[(titulo_seccion, png_bytes | None)]

Tipografía:
- PDF  → DejaVu Sans TTF **embebida** (fonts/ del proyecto → sistema →
  Arial de Windows → fallback Helvetica con acentos vía WinAnsiEncoding).
- DOCX → Arial en todos los estilos base (portable Windows/Linux).
"""

import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage

# Emojis y símbolos decorativos: en el PDF se eliminan para que el
# texto quede siempre limpio (ninguna de las fuentes candidatas los trae).
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002190-\U000024FF\uFE0F\u200D]+"
)

# Candidatas a fuente embebida, en orden de prioridad:
# (regular, bold) — primero las del proyecto, luego sistema, luego Windows.
_FUENTES = [
    (Path(__file__).parent / "fonts" / "DejaVuSans.ttf",
     Path(__file__).parent / "fonts" / "DejaVuSans-Bold.ttf"),
    (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
     Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    (Path("C:/Windows/Fonts/arial.ttf"),
     Path("C:/Windows/Fonts/arialbd.ttf")),
]


# ─────────────────────────────────────────────────────────────
# Helpers comunes
# ─────────────────────────────────────────────────────────────
def _sin_emoji(texto):
    """Quita emojis y normaliza a str."""
    return _EMOJI.sub("", str(texto or "")).strip()


def _fmt(valor):
    """Formatea un valor de celda de forma compacta."""
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, float):
        return f"{valor:g}"
    return str(valor)


def fig_a_png(fig, ancho=None, escala=2):
    """
    Convierte una figura Plotly a PNG con kaleido.
    Devuelve bytes o None si kaleido no está disponible.
    """
    try:
        kwargs = {"format": "png", "scale": escala}
        if ancho:
            kwargs["width"] = ancho
        return fig.to_image(**kwargs)
    except Exception:
        return None


def _png_dims(png):
    """(ancho_px, alto_px) de un PNG en bytes."""
    with PILImage.open(io.BytesIO(png)) as im:
        return im.size


def _aplanar_columnas(columnas):
    """MultiIndex ('Calle | Sentido', 'M1') → 'Calle | Sentido | M1'."""
    salida = []
    for col in columnas:
        if isinstance(col, tuple):
            salida.append(" | ".join(str(p).strip() for p in col
                                     if str(p).strip()))
        else:
            salida.append(str(col).strip())
    return salida


def _df_a_tabla(df, index_nombre="Tipo", encabezados=None):
    """DataFrame → (encabezados, filas) con columnas aplanadas."""
    if encabezados is None:
        encabezados = _aplanar_columnas(df.columns)
    encabezados = [index_nombre] + list(encabezados)
    filas = [[str(idx)] + [_fmt(v) for v in fila] for idx, fila in df.iterrows()]
    return encabezados, filas


def _columnas_con_grupos(df):
    """
    Devuelve (encabezados_planos, grupos) de un df (posible MultiIndex).

    - Encabezados: ('Calle | Sentido', 'M1') → 'Calle | Sentido | M1'.
    - Grupos: id de grupo por columna (nivel 0 del MultiIndex), para
      separarlos visualmente. Si las columnas no son MultiIndex → None.
    """
    encabezados = _aplanar_columnas(df.columns)
    if getattr(df.columns, "nlevels", 1) < 2:
        return encabezados, None
    grupos = [str(col[0]).strip() if len(col) else "" for col in df.columns]
    return encabezados, grupos


def _rangos_grupos(grupos):
    """Lista de grupos → [(col_ini, col_fin), ...] (columnas 1..n)."""
    rangos = []
    actual, inicio = None, None
    for j, g in enumerate(grupos, start=1):
        if g != actual:
            if actual is not None:
                rangos.append((inicio, j - 1))
            actual, inicio = g, j
    if inicio is not None:
        rangos.append((inicio, len(grupos)))
    return rangos


def _anchos_proporcionales(encabezados, filas, ancho_util, familia="Helvetica",
                           fuente=7, minima_cm=0.6):
    """
    Anchos de columna según el contenido real (métricas de la fuente),
    normalizados para sumar `ancho_util` exacto.

    Cada columna pide: ancho de la palabra más larga del encabezado
    (negrita) o del dato más largo (regular) + padding de celda (2+2 pt)
    + 2 pt de seguridad. Así ninguna etiqueta se corta a mitad de palabra
    ni se pisan los encabezados. Si sobra página, el excedente se reparte
    en proporción; si falta, se escala (último recurso).
    """
    from reportlab.lib.units import cm
    from reportlab.pdfbase.pdfmetrics import stringWidth

    negrita = "Helvetica-Bold" if familia == "Helvetica" else "DejaVu-Bold"
    extra = 6  # 2 pt × 2 lados de padding + 2 pt de seguridad

    n = len(encabezados)
    if n <= 1:
        return [ancho_util]

    deseado = []
    for j in range(n):
        palabras = [p for parte in str(encabezados[j]).split("|")
                    for p in parte.split()]
        ancho_enc = max((stringWidth(p, negrita, fuente) for p in palabras),
                        default=0)
        ancho_datos = 0
        for fila in filas:
            if j < len(fila):
                ancho_datos = max(ancho_datos,
                                  stringWidth(str(fila[j]), familia, fuente))
        deseado.append(max(ancho_enc, ancho_datos) + extra)

    deseado = [max(d, minima_cm * cm) for d in deseado]

    total = sum(deseado)
    if total <= ancho_util:
        # Sobra página: repartir el excedente en proporción al contenido
        excedente = ancho_util - total
        return [d + excedente * d / total for d in deseado]
    # No entra: escalar (los encabezados más largos pueden envolver más)
    factor = ancho_util / total
    return [d * factor for d in deseado]


def _ficha(ctx):
    """Pares (etiqueta, valor) de los datos manuales del reporte."""
    fecha = ctx.get("fecha")
    if hasattr(fecha, "strftime"):
        fecha_txt = fecha.strftime("%d/%m/%Y")
    else:
        fecha_txt = str(fecha or "")
    return [
        ("Fecha", fecha_txt),
        ("Día", ctx.get("dia", "")),
        ("Ubicación", ctx.get("ubicacion", "")),
        ("Lugar", ctx.get("lugar", "")),
        ("Analista", ctx.get("analista", "")),
    ]


def _metricas_fhp(fhp):
    """Pares (etiqueta, valor) del bloque de hora pico / FHP."""
    return [
        ("Hora pico", f"{fhp['hora_pico_inicio']} – {fhp['hora_pico_fin']}"),
        ("Volumen hora pico", _fmt(fhp["volumen_hp"])),
        ("Bloque máximo de 15 min",
         f"{fhp['bloque_max_inicio']} – {fhp['bloque_max_fin']}"),
        ("Volumen máx. 15 min", _fmt(fhp["volumen_max_15min"])),
        ("FHP", f"{fhp['fhp']:.3f}"),
    ]


# ─────────────────────────────────────────────────────────────
# PDF (reportlab)
# ─────────────────────────────────────────────────────────────
def _registrar_fuentes_pdf():
    """
    Registra DejaVu Sans (embebida en el PDF). Fallback: Helvetica.
    Devuelve el nombre de la familia a usar.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "DejaVu" in pdfmetrics.getRegisteredFontNames():
        return "DejaVu"

    for ttf, ttf_bold in _FUENTES:
        if ttf.exists() and ttf_bold.exists():
            try:
                pdfmetrics.registerFont(TTFont("DejaVu", str(ttf)))
                pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(ttf_bold)))
                pdfmetrics.registerFontFamily(
                    "DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                    italic="DejaVu", boldItalic="DejaVu-Bold",
                )
                return "DejaVu"
            except Exception:
                continue
    return "Helvetica"


def _tabla_pdf(datos, col_widths=None, fuente=8, familia="Helvetica",
               encabezado=False, grupos=None):
    """
    Tabla de reportlab con estilos acordes al reporte.

    - Si `encabezado`, la primera fila se convierte en Paragraph para que
      los títulos largos se envuelvan en vez de pisarse entre columnas.
    - Si se pasa `grupos` (id por columna), aplica banding alternado por
      grupo y un borde vertical más marcado al cierre de cada grupo.
    """
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Table, TableStyle

    datos = [list(fila) for fila in datos]
    if encabezado:
        estilo_enc = ParagraphStyle(
            "EncTabla",
            fontName=("Helvetica-Bold" if familia == "Helvetica"
                      else "DejaVu-Bold"),
            fontSize=fuente,
            leading=fuente + 1.5,
            alignment=1,  # centrado
        )
        datos[0] = [Paragraph(escape(str(c)), estilo_enc) for c in datos[0]]

    tabla = Table(datos, colWidths=col_widths,
                  repeatRows=1 if encabezado else 0)
    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), familia),
        ("FONTSIZE", (0, 0), (-1, -1), fuente),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c0c0c0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if encabezado:
        estilo += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f5f7fa")),
        ]
    else:
        estilo += [
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f7fa")),
        ]

    # Banding por grupos (filas de datos; el encabezado ya tiene su color)
    if grupos:
        fila_ini = 1 if encabezado else 0
        for k, (j0, j1) in enumerate(_rangos_grupos(grupos)):
            if k % 2 == 1:
                estilo.append(("BACKGROUND", (j0, fila_ini), (j1, -1),
                               colors.HexColor("#eef3fa")))
            estilo.append(("LINEAFTER", (j1, 0), (j1, -1),
                           1.0, colors.HexColor("#8a9bb5")))

    tabla.setStyle(TableStyle(estilo))
    return tabla


def generar_pdf(ctx):
    """Genera el reporte PDF y devuelve bytes."""
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

    familia = _registrar_fuentes_pdf()
    negrita = "DejaVu-Bold" if familia == "DejaVu" else "Helvetica-Bold"

    estilos = getSampleStyleSheet()
    h1 = ParagraphStyle("RepH1", parent=estilos["Title"], fontName=negrita,
                        fontSize=17, spaceAfter=2)
    sub_st = ParagraphStyle("RepSub", parent=estilos["Normal"],
                            fontName=familia, fontSize=11, alignment=TA_CENTER)
    h2 = ParagraphStyle("RepH2", parent=estilos["Heading2"], fontName=negrita,
                        fontSize=12, spaceBefore=12, spaceAfter=4)
    h3 = ParagraphStyle("RepH3", parent=estilos["Heading3"], fontName=negrita,
                        fontSize=10, spaceBefore=8, spaceAfter=2)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=str(ctx.get("titulo") or "Reporte de censo"),
    )
    ancho_util = doc.width
    story = []

    # ── Encabezado ──
    story.append(Paragraph(
        escape(_sin_emoji(ctx.get("titulo") or "Reporte de censo")), h1))
    subtitulo = _sin_emoji(ctx.get("subtitulo"))
    if subtitulo:
        story.append(Paragraph(escape(subtitulo), sub_st))
    story.append(Spacer(1, 10))

    # ── Datos del censo ──
    story.append(Paragraph("Datos del censo", h2))
    ficha = [[escape(k), escape(str(v or "—"))] for k, v in _ficha(ctx)]
    story.append(_tabla_pdf(ficha, col_widths=[3.5 * cm, 12 * cm],
                            fuente=9, familia=familia))

    # ── FHP ──
    story.append(Paragraph("Factor de hora pico (FHP)", h2))
    fhp = [[escape(k), escape(v)] for k, v in _metricas_fhp(ctx["fhp_data"])]
    story.append(_tabla_pdf(fhp, col_widths=[5 * cm, 8 * cm],
                            fuente=9, familia=familia))

    # ── Resumen agrupado (si hay MAPA) ──
    resumen_agr = ctx.get("resumen_agr")
    if resumen_agr is not None:
        story.append(Paragraph("Resumen hora pico (agrupado)", h2))
        enc_planos, grupos = _columnas_con_grupos(resumen_agr)
        enc, filas = _df_a_tabla(resumen_agr, encabezados=enc_planos)
        fuente_res = 6.5 if len(enc) <= 14 else 5.0
        story.append(_tabla_pdf(
            [enc] + filas,
            col_widths=_anchos_proporcionales(enc, filas, ancho_util,
                                              familia=familia,
                                              fuente=fuente_res),
            fuente=fuente_res,
            familia=familia, encabezado=True, grupos=grupos,
        ))

    # ── % pesados (si aplica) ──
    pesados_hp = ctx.get("pesados_hp")
    if pesados_hp is not None:
        story.append(Paragraph("% de vehículos pesados — hora pico", h2))
        enc, filas = _df_a_tabla(pesados_hp, index_nombre="tipo_vehiculo")
        story.append(_tabla_pdf(
            [enc] + filas,
            col_widths=_anchos_proporcionales(enc, filas, ancho_util,
                                              familia=familia, fuente=6.5),
            fuente=6.5, familia=familia, encabezado=True,
        ))

    # ── Totales 15 min ──
    totales = ctx.get("totales")
    if totales is not None:
        story.append(Paragraph("Totales por bloque de 15 min", h2))
        enc, filas = _df_a_tabla(totales, index_nombre="#")
        fuente_tot = 7 if len(enc) <= 16 else 6
        story.append(_tabla_pdf(
            [enc] + filas,
            col_widths=_anchos_proporcionales(enc, filas, ancho_util,
                                              familia=familia,
                                              fuente=fuente_tot),
            fuente=fuente_tot,
            familia=familia, encabezado=True,
        ))

    # ── Gráficos ──
    con_imagenes = [(t, png) for t, png in ctx.get("imagenes", []) if png]
    if con_imagenes:
        story.append(Paragraph("Gráficos", h2))
    alto_max = 15 * cm
    for titulo, png in con_imagenes:
        story.append(Paragraph(escape(_sin_emoji(titulo)), h3))
        w_px, h_px = _png_dims(png)
        escala = min(ancho_util / w_px, alto_max / h_px)
        story.append(Image(io.BytesIO(png),
                           width=w_px * escala, height=h_px * escala))
        story.append(Spacer(1, 6))

    doc.build(story)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────
# DOCX (python-docx)
# ─────────────────────────────────────────────────────────────
def _sombrear_celda(celda, color_hex):
    """Fondo de celda (w:shd); python-docx no tiene API nativa para esto."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    tc_pr = celda._tc.get_or_add_tcPr()
    sombra = OxmlElement("w:shd")
    sombra.set(qn("w:val"), "clear")
    sombra.set(qn("w:color"), "auto")
    sombra.set(qn("w:fill"), color_hex.lstrip("#"))
    tc_pr.append(sombra)


def _tabla_docx(doc, encabezados, filas, fuente_pt=8, grupos=None):
    """
    Agrega una tabla estilo 'Table Grid' con fuente Arial controlada.

    Si se pasa `grupos` (id por columna), aplica banding alternado por
    grupo igual que en el PDF.
    """
    from docx.shared import Pt

    tabla = doc.add_table(rows=1, cols=len(encabezados))
    tabla.style = "Table Grid"
    for j, txt in enumerate(encabezados):
        tabla.rows[0].cells[j].text = str(txt)
    for fila in filas:
        celdas = tabla.add_row().cells
        for j, txt in enumerate(fila):
            celdas[j].text = str(txt)

    for i, fila in enumerate(tabla.rows):
        for celda in fila.cells:
            for parrafo in celda.paragraphs:
                parrafo.paragraph_format.space_before = Pt(0)
                parrafo.paragraph_format.space_after = Pt(0)
                for run in parrafo.runs:
                    run.font.size = Pt(fuente_pt)
                    run.font.name = "Arial"
                    if i == 0:
                        run.bold = True

    # Encabezado con el mismo fondo que el PDF
    for celda in tabla.rows[0].cells:
        _sombrear_celda(celda, "#e8eef7")

    # Banding por grupos (columnas 1..n; la 0 es el índice)
    if grupos:
        for k, (j0, j1) in enumerate(_rangos_grupos(grupos)):
            if k % 2 == 1:
                for fila in tabla.rows[1:]:
                    for j in range(j0, min(j1 + 1, len(fila.cells))):
                        _sombrear_celda(fila.cells[j], "#eef3fa")
    return tabla


def _pares_docx(doc, pares):
    """Tabla de 2 columnas (concepto, valor) a partir de pares."""
    _tabla_docx(doc, ["Concepto", "Valor"],
                [[str(k), str(v or "—")] for k, v in pares],
                fuente_pt=9)


def generar_docx(ctx):
    """Genera el reporte DOCX y devuelve bytes."""
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt

    doc = Document()

    # ── Horizontal + Arial en los estilos base ──
    seccion = doc.sections[0]
    seccion.orientation = WD_ORIENT.LANDSCAPE
    seccion.page_width, seccion.page_height = (seccion.page_height,
                                               seccion.page_width)
    for nombre in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3"):
        try:
            doc.styles[nombre].font.name = "Arial"
        except KeyError:
            pass
    doc.styles["Normal"].font.size = Pt(10)

    # ── Encabezado ──
    doc.add_heading(str(ctx.get("titulo") or "Reporte de censo"), level=0)
    subtitulo = str(ctx.get("subtitulo") or "")
    if subtitulo:
        parrafo = doc.add_paragraph(subtitulo)
        parrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # ── Datos del censo ──
    doc.add_heading("Datos del censo", level=1)
    _pares_docx(doc, _ficha(ctx))

    # ── FHP ──
    doc.add_heading("Factor de hora pico (FHP)", level=1)
    _pares_docx(doc, _metricas_fhp(ctx["fhp_data"]))

    # ── Resumen agrupado ──
    resumen_agr = ctx.get("resumen_agr")
    if resumen_agr is not None:
        doc.add_heading("Resumen hora pico (agrupado)", level=1)
        enc_planos, grupos = _columnas_con_grupos(resumen_agr)
        enc, filas = _df_a_tabla(resumen_agr, encabezados=enc_planos)
        _tabla_docx(doc, enc, filas, fuente_pt=7, grupos=grupos)

    # ── % pesados ──
    pesados_hp = ctx.get("pesados_hp")
    if pesados_hp is not None:
        doc.add_heading("% de vehículos pesados — hora pico", level=1)
        enc, filas = _df_a_tabla(pesados_hp, index_nombre="tipo_vehiculo")
        _tabla_docx(doc, enc, filas, fuente_pt=7)

    # ── Totales 15 min ──
    totales = ctx.get("totales")
    if totales is not None:
        doc.add_heading("Totales por bloque de 15 min", level=1)
        enc, filas = _df_a_tabla(totales, index_nombre="#")
        _tabla_docx(doc, enc, filas, fuente_pt=7)

    # ── Gráficos ──
    con_imagenes = [(t, png) for t, png in ctx.get("imagenes", []) if png]
    if con_imagenes:
        doc.add_heading("Gráficos", level=1)
    ancho_max_cm, alto_max_cm = 24.0, 14.5
    for titulo, png in con_imagenes:
        doc.add_heading(str(titulo), level=2)
        w_px, h_px = _png_dims(png)
        escala = min(ancho_max_cm / w_px, alto_max_cm / h_px)
        doc.add_picture(io.BytesIO(png), width=Cm(w_px * escala))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()



