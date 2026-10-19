"""
tests/test_motor.py — Tests básicos del motor (procesar_censo3).

Se pueden correr con pytest:

    python3 -m pytest tests/

o directamente (sin pytest):

    python3 tests/test_motor.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import croquis_svg
import procesar_censo3 as motor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EJEMPLO_CRUZ = os.path.join(RAIZ, "censo_ejemplo_cruz.xlsx")


def _a_minutos(hhmm):
    """'07:30' -> 450 (minutos desde medianoche)."""
    horas, minutos = hhmm.split(":")
    return int(horas) * 60 + int(minutos)


def test_claves_del_resultado():
    res = motor.procesar(EJEMPLO_CRUZ)
    for clave in ("df", "movs", "mapa", "totales", "pico", "fhp_data",
                  "resumen_plano", "resumen_agr", "pesados_hp", "excluidos"):
        assert clave in res, f"falta la clave {clave}"


def test_hora_pico_es_una_hora():
    """La hora pico es una ventana de 4 bloques de 15 min (1 hora)."""
    fhp = motor.procesar(EJEMPLO_CRUZ)["fhp_data"]
    inicio = fhp["hora_pico_inicio"]
    fin = fhp["hora_pico_fin"]
    assert _a_minutos(fin) - _a_minutos(inicio) == 60


def test_fhp_formula():
    """FHP = Volumen HP / (4 * volumen máximo de 15 min), redondeado a 3."""
    fhp = motor.procesar(EJEMPLO_CRUZ)["fhp_data"]
    esperado = round(fhp["volumen_hp"] / (4 * fhp["volumen_max_15min"]), 3)
    assert abs(fhp["fhp"] - esperado) < 1e-9


def test_excluir_tipo_reduce_el_volumen():
    """Un tipo excluido no suma en los totales ni en la hora pico."""
    res = motor.procesar(EJEMPLO_CRUZ)
    tipos = res["df"]["tipo_vehiculo"].value_counts()
    tipo = tipos.index[0]

    res_ex = motor.procesar(EJEMPLO_CRUZ, excluidos=[tipo])
    total = res["totales"]["TOTAL"].sum()
    total_ex = res_ex["totales"]["TOTAL"].sum()

    assert tipo in res_ex["excluidos"]
    assert total_ex < total
    assert res_ex["fhp_data"]["volumen_hp"] <= res["fhp_data"]["volumen_hp"]


def test_od_total_es_consistente():
    """La tabla O-D y la matriz O-D dan el mismo total."""
    volumenes = {"M1": 5, "M2": 7}
    mapeo = {"M1": "O_IZQ", "M2": "O_FTE"}
    ramas, matriz = croquis_svg.calcular_matriz_od(volumenes, mapeo, "Ruta")
    total_matriz = sum(v for fila in matriz for v in fila if v is not None)

    filas = croquis_svg.filas_tabla_od(volumenes, mapeo, "Ruta")
    total_tabla = int(filas[-1][-1])
    assert total_tabla == total_matriz == 12


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
