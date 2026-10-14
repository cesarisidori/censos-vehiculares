"""
test_reportes.py — Genera PDF y DOCX de prueba con censo_ejemplo_cruz.xlsx.

Uso:
    python3 test_reportes.py

Salida:
    test_reporte.pdf / test_reporte.docx en la raíz del proyecto.

Además valida que todas las figuras Plotly —incluido el croquis, que
tiene shapes y annotations— se puedan exportar a PNG con kaleido.
"""

from datetime import date
from pathlib import Path

import croquis as crq
import graficos as grf
import procesar_censo3 as motor
import reportes as rep

RUTA = Path(__file__).with_name("censo_ejemplo_cruz.xlsx")

TITULO = "VOLUMEN TRÁNSITO"
SUBTITULO = "DOMINGO 26 DE JULIO DE 2026"

# ── 1) Procesar con el mismo pipeline que usa la app ──
res = motor.procesar(str(RUTA))
print(f"✅ Censo procesado — hora pico {res['pico'][0]}–{res['pico'][1]}, "
      f"FHP {res['fhp_data']['fhp']}")

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

serie_total = res["df"].groupby("tipo_vehiculo")[res["movs"]].sum().sum(axis=1)
serie_total = serie_total[serie_total > 0].sort_values(ascending=False)
fig = grf.fig_torta(serie_total, "Composición por tipo — censo completo",
                    SUBTITULO)
if fig:
    figuras.append(("Composición por tipo — censo completo", fig))

# % pesados
if res["pesados_hp"] is not None:
    fig = grf.fig_pesados(res["pesados_hp"])
    if fig:
        figuras.append(("% de pesados por movimiento — hora pico", fig))

# ── 3) Croquis — DESHABILITADO: el croquis no se incluye en los reportes
#    (se muestra solo en la app). Para re-validar kaleido con shapes +
#    annotations, descomentar el bloque siguiente.
# MAPEO_EJEMPLO = {
#     "M9": "N_IZQ", "M8": "N_FTE", "M7": "N_DER",
#     "M10": "S_IZQ", "M11": "S_FTE", "M12": "S_DER",
#     "M4": "E_IZQ", "M5": "E_FTE", "M6": "E_DER",
#     "M1": "O_IZQ", "M2": "O_FTE", "M3": "O_DER",
# }
# mapeo_croquis = {m: p for m, p in MAPEO_EJEMPLO.items()
#                  if m in res["df"].columns}
# if mapeo_croquis:
#     volumenes = {m: int(df_validos[m].sum()) for m in mapeo_croquis}
#     fig = crq.dibujar_croquis_cruz(
#         volumenes=volumenes,
#         mapeo=mapeo_croquis,
#         nombres_ramas={"N": "Norte", "S": "Sur", "E": "Este", "O": "Oeste"},
#         titulo="Croquis — hora pico",
#     )
#     figuras.append(("Croquis — hora pico", fig))

# ── 4) Figuras → PNG (kaleido) ──
imagenes = []
for titulo, fig in figuras:
    # Los croquis conservan su proporción (scaleanchor); los demás se estiran.
    png = rep.fig_a_png(fig, ancho=None if "Croquis" in titulo else 1100)
    print(f"  {'✅' if png else '❌ sin kaleido'} {titulo}")
    imagenes.append((titulo, png))

ok = sum(1 for _, png in imagenes if png)
print(f"🖼️  Imágenes: {ok}/{len(imagenes)}")

# ── 5) Reportes ──
ctx = {
    "titulo": TITULO,
    "subtitulo": SUBTITULO,
    "fecha": date(2026, 7, 26),
    "dia": "DOMINGO",
    "ubicacion": "RP 18 km 12",
    "lugar": "Cruce RP 18 / Av. Principal",
    "analista": "Prueba",
    "fhp_data": res["fhp_data"],
    "resumen_agr": res["resumen_agr"],
    "resumen_plano": res["resumen_plano"],
    "pesados_hp": res["pesados_hp"],
    "totales": res["totales"],
    "excluidos": res["excluidos"],
    "imagenes": imagenes,
}

pdf = rep.generar_pdf(ctx)
assert pdf.startswith(b"%PDF"), "El PDF no tiene cabecera válida"
Path("test_reporte.pdf").write_bytes(pdf)
print(f"✅ test_reporte.pdf ({len(pdf):,} bytes)")

docx = rep.generar_docx(ctx)
assert docx[:2] == b"PK", "El DOCX no es un zip válido"
Path("test_reporte.docx").write_bytes(docx)
print(f"✅ test_reporte.docx ({len(docx):,} bytes)")

print("\n🎉 Reportes generados OK")

