"""
tests/test_excel_graficos.py — Tests de los gráficos nativos del Excel.

Verifican que se generen las hojas de datos, los gráficos y que el libro
quede con las hojas auxiliares ocultas y activo en FHP.

    python3 -m pytest tests/
    python3 tests/test_excel_graficos.py
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from openpyxl import load_workbook

import excel_graficos
import procesar_censo3 as motor

_FHP = {
    "hora_pico_inicio": "07:00", "hora_pico_fin": "08:00", "volumen_hp": 100,
    "bloque_max_inicio": "07:00", "bloque_max_fin": "07:15",
    "volumen_max_15min": 40, "fhp": 0.9,
}


def _datos():
    df_cs = pd.DataFrame({
        "hora_inicio": ["07:00", "07:15", "07:30", "07:45"] * 2,
        "hora_fin": ["07:15", "07:30", "07:45", "08:00"] * 2,
        "calle": ["Av 1"] * 4 + ["Av 2"] * 4,
        "sentido": ["Norte"] * 4 + ["Sur"] * 4,
        "volumen": [10, 20, 30, 40, 15, 25, 35, 45],
    })
    agg = df_cs.copy()
    agg["hora_entera"] = agg["hora_inicio"].str.slice(0, 2) + ":00"
    agg = agg.groupby(["hora_entera", "calle", "sentido"],
                      as_index=False)["volumen"].sum()
    serie_hp = pd.Series({"Auto": 50, "Bus": 10})
    serie_total = pd.Series({"Auto": 200, "Bus": 40, "Moto": 5})
    pesados = pd.DataFrame({"M1": [0.1], "M2": [0.2], "Total": [0.15]},
                           index=["% pesados"])
    return df_cs, agg, serie_hp, serie_total, pesados


def _exportar():
    df_cs, agg, s_hp, s_tot, pesados = _datos()
    hojas, al_escribir = excel_graficos.preparar_graficos(
        df_cs, agg_hora=agg, periodos_hp=["07:00", "07:15"],
        serie_hp=s_hp, serie_total=s_tot, pesados_hp=pesados,
        titulo="VOLUMEN", paleta=["#4472C4", "#ED7D31", "#A5A5A5"],
    )
    return hojas, al_escribir


def test_hojas_de_datos_esperadas():
    hojas, _ = _exportar()
    for hoja in ("Graf_15min", "Graf_Hora", "Graf_15min_HP",
                 "Graf_Composicion", "Graf_Pesados"):
        assert hoja in hojas, f"falta la hoja {hoja}"


def test_libro_con_graficos_y_hojas_ocultas():
    hojas, al_escribir = _exportar()
    df_cs, _, _, _, _ = _datos()
    buf = motor.exportar_buffer(
        _FHP, None, pd.DataFrame({"a": [1]}), None, None,
        pd.DataFrame({"hora_inicio": ["07:00"], "hora_fin": ["07:15"],
                      "TOTAL": [10]}),
        df_cs, hojas_extra=hojas, al_escribir=al_escribir,
    )
    wb = load_workbook(io.BytesIO(buf.getvalue()))

    assert "Gráficos" in wb.sheetnames
    assert len(wb["Gráficos"]._charts) > 0
    assert wb["Graf_15min"].sheet_state == "hidden"
    assert wb.active.title == "FHP"


def _ejecutar_todos():
    pruebas = [v for k, v in sorted(globals().items())
               if k.startswith("test_") and callable(v)]
    fallos = 0
    for prueba in pruebas:
        try:
            prueba()
            print(f"OK   {prueba.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"FALLA {prueba.__name__}: {e}")
    print(f"\n{len(pruebas) - fallos}/{len(pruebas)} tests OK")
    return fallos


if __name__ == "__main__":
    sys.exit(1 if _ejecutar_todos() else 0)
