"""
test_reportes.py — Genera PDF y DOCX de prueba con censo_ejemplo_cruz.xlsx.

Uso:
    python3 test_reportes.py

Salida:
    test_reporte.pdf / test_reporte.docx en la raíz del proyecto.
"""

from datetime import date
from pathlib import Path

import graficos as grf
import procesar_censo3 as motor
import reportes as rep

RUTA = Path(__file__).with_name("censo_ejemplo_cruz.xlsx")

TITULO = "VOLUMEN TRÁNSITO"
SUBTITULO = "DOMINGO 26 DE JULIO DE 2026"

# ── 1) Procesar con el mismo pipeline que usa la app ──
res = motor.procesar(str(RUTA))
print("Censo procesado - hora pico {}-{}, FHP {}".format(
      res['pico'][0], res['pico'][1], res['fhp_data']['fhp']))

# ── 2) Datos por calle/sentido (igual que la app) ──
mapa_dict = {}
if res["mapa"] is not None:
    mapa_dict = {row["movimiento"]: (row["calle"], row["sentido"])
                 for _, row in res["mapa"].iterrows()}

df_validos = res["df"][~res["df"]["tipo_vehiculo"].isin(res["excluidos"])]
df_cs = grf.volumen_por_calle_sentido(df_validos, res["movs"], mapa_dict)

figuras = []

if not df_cs.empty:
    figuras.append(("Distribución por 15 minutos — censo completo",
                    grf.fig_lineas(df_cs, TITULO, SUBTITULO)))

    agg_hora = grf.agregar_por_hora(df_cs)
    for calle in sorted(agg_hora["calle"].unique()):
        sub = agg_hora[agg_hora["calle"] == calle]
        fig = grf.fig_barras_agrupadas(
            sub, "hora_entera", sorted(sub["hora_entera"].unique()),
            f"{TITULO} {calle}", SUBTITULO, "VOLUMEN HORARIO")
        if fig:
            figuras.append((f"Volumen por hora — {calle}", fig))

    hp_ini, hp_fin = res["pico"][0], res["pico"][1]
    bloques_hp = res["totales"][
        (res["totales"]["hora_inicio"] >= hp_ini)
        & (res["totales"]["hora_fin"] <= hp_fin)]
    for calle in sorted(df_cs["calle"].unique()):
        sub = df_cs[df_cs["calle"] == calle]
        fig = grf.fig_barras_agrupadas(
            sub, "hora_inicio", bloques_hp["hora_inicio"].tolist(),
            f"{TITULO} {calle}", f"DE {hp_ini} a {hp_fin} DEL {SUBTITULO}",
            "VOLUMEN CADA 15 MINUTOS")
        if fig:
            figuras.append((f"Volumen cada 15 min (hora pico) — {calle}", fig))

# Tortas (todos los tipos, incluidos los excluidos)
serie_hp = res["df"][(res["df"]["hora_inicio"] >= res["pico"][0])
                     & (res["df"]["hora_fin"] <= res["pico"][1])]
serie_hp = serie_hp.groupby("tipo_vehiculo")[res["movs"]].sum().sum(axis=1)
serie_hp = serie_hp[serie_hp > 0].sort_values(ascending=False)
fig = grf.fig_torta(serie_hp, "Composición por tipo — hora pico", SUBTITULO)
if fig:
    figuras.append(("Composición por tipo — hora pico", fig))

# ── 3) Croquis — DESHABILITADO: el croquis no se incluye en los reportes
# mapeo_croquis = {m: p for m, p in MAPEO_EJEMPLO.items()
#                  if m in res["movs"]}
# if mapeo_croquis:
#     volumenes = {m: int(df_validos[m].sum()) for m in mapeo_croquis}
#     fig = crq.dibujar_croquis_cruz(
#         mapeo=mapeo_croquis,
#         nombres_ramas={"N": "Norte", "S": "Sur", "E": "Este", "O": "Oeste"},
#         titulo="Croquis — hora pico")
#     figuras.append(("Croquis", fig))

# ── 4) Convertir figuras a PNG ──
print("Convirtiendo figuras a PNG (mirage)...")
imgs = []
for nombre, figura in figuras:
    png = rep.fig_a_png(figura)
    if png:
        imgs.append((nombre, png))
        print(f"  - {nombre}: OK ({len(png)} bytes)")
    else:
        print(f"  - {nombre}: ERROR")

# ── 5) Generar PDF ──
print("Generando PDF...")
pdf_path = rep.gen_pdf(
    imgs=imgs,
    output_path="test_reporte.pdf",
    title=TITULO,
    subtitle=SUBTITULO,
    date=date.today(),
)
print(f"PDF: {pdf_path}")

# ── 6) Generar DOCX ──
print("Generando DOCX...")
docx_path = rep.gen_docx(
    imgs=imgs,
    output_path="test_reporte.docx",
    title=TITULO,
    subtitle=SUBTITULO,
    date=date.today(),
)
print(f"DOCX: {docx_path}")

print("\nListo: test_reporte.pdf y test_reporte.docx")
