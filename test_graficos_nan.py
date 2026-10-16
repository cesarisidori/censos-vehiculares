"""
test_graficos_nan.py
--------------------
Tests para verificar que graficos.py tolera NaN/None sin crashear.
Ejecutable directamente: python test_graficos_nan.py
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import graficos


def test_safe_int():
    """El helper _safe_int convierte NaN/None a 0."""
    assert graficos._safe_int(np.nan) == 0
    assert graficos._safe_int(None) == 0
    assert graficos._safe_int(10) == 10
    assert graficos._safe_int(10.7) == 10
    assert graficos._safe_int(True) == 1
    assert graficos._safe_int(False) == 0
    assert graficos._safe_int('42') == 42
    assert graficos._safe_int('abc') == 0


def test_fig_lineas_con_nan():
    """NaN en df_cs debe convertirse a 0, no lanzar ValueError."""
    df_cs = pd.DataFrame({
        'hora_inicio': ['07:00', '07:15', '07:30'],
        'calle':       ['C1', 'C1', 'C1'],
        'sentido':     ['N_IZQ', 'N_IZQ', 'N_IZQ'],
        'volumen':     [10.0, np.nan, 5.0],
    })

    fig = graficos.fig_lineas(df_cs, 'T', 'S')
    assert fig is not None
    assert fig.data[0].y[1] == 0


def test_fig_barras_agrupadas_con_nan():
    """NaN en el pivote debe convertirse a 0 sin crash."""
    df = pd.DataFrame({
        'hora_inicio': ['07:00', '07:15', '07:30'],
        'calle':       ['C1', 'C1', 'C1'],
        'sentido':     ['N_IZQ', 'N_IZQ', 'N_IZQ'],
        'volumen':     [10.0, np.nan, 5.0],
    })

    fig = graficos.fig_barras_agrupadas(
        df, 'hora_inicio', ['07:00', '07:15', '07:30'],
        'T', 'S', 'V'
    )
    assert fig is not None
    assert fig.data[0].y[1] == 0


def test_fig_torta_con_nan():
    """Series con NaN en la torta no debe lanzar excepción."""
    series = pd.Series({'Auto': 100, 'Moto': np.nan, 'Camion': 50})

    fig = graficos.fig_torta(series, 'T', 'S')
    assert fig is not None or series.sum() == 0


def test_fig_pesados_con_nan():
    """NaN en la fila % pesados debe manejarse sin crash."""
    pesados_hp = pd.DataFrame({
        'M1': [3, 10, 2, 15, 20.0],
        'M2': [10, 50, 5, 65, 77.0],
        'M3': [2, 3, 4, 9, 44.0],
        'Total': [15, 63, 11, 89, 70.0],
    }, index=['Auto', 'Moto', 'Camion', 'TOTAL pesados', '% pesados'])
    # Inyectar NaN en la fila '% pesados'
    pesados_hp.loc['% pesados', 'M2'] = np.nan
    pesados_hp.loc['% pesados', 'M3'] = 30.0

    fig = graficos.fig_pesados(pesados_hp)
    if fig is not None:
        assert len(fig.data) > 0


def test_fig_pesados_sin_nan():
    """fig_pesados con dataframe completo (incluye fila '% pesados') tampoco crashee."""
    pesados_hp = pd.DataFrame({
        'M1': [3, 10, 2, 15, 20.0],
        'M2': [10, 50, 5, 65, 77.0],
        'M3': [2, 3, 4, 9, 44.0],
        'Total': [15, 63, 11, 89, 70.0],
    }, index=['Auto', 'Moto', 'Camion', 'TOTAL pesados', '% pesados'])

    fig = graficos.fig_pesados(pesados_hp)
    if fig is not None:
        assert len(fig.data) > 0


if __name__ == '__main__':
    tests = [
        test_safe_int,
        test_fig_lineas_con_nan,
        test_fig_barras_agrupadas_con_nan,
        test_fig_torta_con_nan,
        test_fig_pesados_con_nan,
        test_fig_pesados_sin_nan,
    ]
    failures = []
    for t in tests:
        try:
            t()
            print(f'PASO: {t.__name__}')
        except Exception as e:
            failures.append((t.__name__, e))
            print(f'FAIL: {t.__name__} -> {type(e).__name__}: {e}')

    if failures:
        print()
        print(f'RESULTADO: {len(failures)} fallo(s) de {len(tests)}')
        sys.exit(1)
    print()
    print(f'RESULTADO: {len(tests)} OK - todas las pruebas pasaron.')