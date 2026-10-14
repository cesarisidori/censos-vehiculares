"""
crear_ejemplo.py
----------------
Genera los 3 archivos de ejemplo, uno por tipo de croquis:

  - censo_ejemplo_cruz.xlsx  (M1-M12, 4 ramas → croquis en cruz)
  - censo_ejemplo_T.xlsx     (M1-M6 y M10-M12, 3 ramas → croquis en T)
  - censo_ejemplo_ruta.xlsx  (M1-M2, ida y vuelta → croquis de ruta)

Cada uno tiene las 3 hojas (DATOS, MAPA, CONFIG). DATOS/MAPA/CONFIG
parten de los datos reales del censo de ejemplo original.
"""
import pandas as pd

# ── Datos base (censo real de ejemplo: 8 bloques × 4 tipos) ──
# (hora_inicio, hora_fin, tipo_vehiculo, M1..M12)
DATOS_BASE = [
    ("07:30", "07:45", "Autos",         1, 127, 0, 0, 11, 89, 3, 0, 0,  0, 42, 0),
    ("07:30", "07:45", "Bicicletas",    0,   0, 0, 0,  0,  0, 0, 0, 0,  0,  0, 0),
    ("07:30", "07:45", "Veh. Pesados",  0,  14, 0, 0,  0,  7, 1, 0, 0,  0,  1, 0),
    ("07:30", "07:45", "TUP",           0,   6, 0, 0,  0,  1, 0, 0, 0,  0,  0, 0),

    ("07:45", "08:00", "Autos",         1, 133, 0, 0,  7, 103, 7, 0, 0, 0, 52, 0),
    ("07:45", "08:00", "Bicicletas",    0,   0, 0, 0,  0,   0, 0, 0, 0, 0,  0, 0),
    ("07:45", "08:00", "Veh. Pesados",  0,  13, 0, 0,  0,   8, 0, 0, 0, 0,  1, 0),
    ("07:45", "08:00", "TUP",           0,   2, 0, 0,  0,   1, 0, 0, 0, 0,  1, 0),

    ("08:00", "08:15", "Autos",         0, 103, 0, 0,  3,  78, 1, 0, 0, 0, 14, 0),
    ("08:00", "08:15", "Bicicletas",    0,   0, 0, 0,  0,   0, 0, 0, 0, 0,  0, 0),
    ("08:00", "08:15", "Veh. Pesados",  0,  15, 0, 0,  1,   4, 0, 0, 0, 0,  2, 0),
    ("08:00", "08:15", "TUP",           0,   2, 0, 0,  0,   0, 0, 0, 0, 0,  0, 0),

    ("08:15", "08:30", "Autos",         0,  99, 0, 0,  7,  73, 3, 0, 0, 0, 10, 0),
    ("08:15", "08:30", "Bicicletas",    0,   0, 0, 0,  0,   0, 0, 0, 0, 0,  0, 0),
    ("08:15", "08:30", "Veh. Pesados",  0,  12, 0, 0,  0,   6, 2, 0, 0, 0,  1, 0),
    ("08:15", "08:30", "TUP",           0,   1, 0, 0,  1,   0, 0, 0, 0, 0,  0, 0),

    ("08:30", "08:45", "Autos",         0, 117, 0, 0,  5,   0, 0, 0, 0, 0, 15, 0),
    ("08:30", "08:45", "Bicicletas",    0,   0, 0, 0,  0,   0, 0, 0, 0, 0,  0, 0),
    ("08:30", "08:45", "Veh. Pesados",  0,  12, 0, 0,  0,   0, 0, 0, 0, 0,  0, 0),
    ("08:30", "08:45", "TUP",           0,   2, 0, 0,  0,   0, 0, 0, 0, 0,  2, 0),

    ("08:45", "09:00", "Autos",         0, 122, 1, 0,  8,  65, 2, 0, 0, 0, 30, 0),
    ("08:45", "09:00", "Bicicletas",    0,   0, 0, 0,  0,   0, 0, 0, 0, 0,  0, 0),
    ("08:45", "09:00", "Veh. Pesados",  0,   8, 0, 0,  2,   7, 0, 0, 0, 0,  1, 0),
    ("08:45", "09:00", "TUP",           0,   2, 0, 0,  0,   0, 0, 0, 0, 0,  1, 0),

    ("09:00", "09:15", "Autos",         0,  92, 0, 0,  6,  70, 0, 0, 0, 0, 12, 0),
    ("09:00", "09:15", "Bicicletas",    0,   0, 0, 0,  0,   0, 0, 0, 0, 0,  0, 0),
    ("09:00", "09:15", "Veh. Pesados",  0,  13, 0, 0,  0,  11, 0, 0, 0, 0,  1, 0),
    ("09:00", "09:15", "TUP",           0,   0, 0, 0,  1,   0, 0, 0, 0, 0,  0, 0),

    ("09:15", "09:30", "Autos",         0, 108, 0, 0,  2,  60, 2, 0, 0, 0, 14, 0),
    ("09:15", "09:30", "Bicicletas",    0,   0, 0, 0,  0,   0, 0, 0, 0, 0,  0, 0),
    ("09:15", "09:30", "Veh. Pesados",  0,   9, 0, 0,  1,  11, 1, 0, 0, 0,  0, 0),
    ("09:15", "09:30", "TUP",           0,   1, 0, 0,  1,   2, 0, 0, 0, 0,  0, 0),
]

COLS_BASE = ["hora_inicio", "hora_fin", "tipo_vehiculo"] + \
            [f"M{i}" for i in range(1, 13)]

# MAPA de la cruz: 2 calles × 2 sentidos (4 ramas N/S/E/O vía MAPEO_FIJO)
MAPA_CRUZ = [
    ("M1",  "Calle Ppal", "Este-Oeste"),
    ("M2",  "Calle Ppal", "Este-Oeste"),
    ("M3",  "Calle Ppal", "Este-Oeste"),
    ("M4",  "Calle Ppal", "Oeste-Este"),
    ("M5",  "Calle Ppal", "Oeste-Este"),
    ("M6",  "Calle Ppal", "Oeste-Este"),
    ("M7",  "Calle Sec",  "Norte-Sur"),
    ("M8",  "Calle Sec",  "Norte-Sur"),
    ("M9",  "Calle Sec",  "Norte-Sur"),
    ("M10", "Calle Sec",  "Sur-Norte"),
    ("M11", "Calle Sec",  "Sur-Norte"),
    ("M12", "Calle Sec",  "Sur-Norte"),
]

CONFIG = [
    ("tipos_excluidos",      "Bicicletas"),
    ("nombre_fila_total",    "Total p/NS"),
    ("calcular_pct_pesados", "SI"),
    ("tipos_pesados",        "Veh. Pesados, TUP"),
    ("fecha_censo",          "2026-07-26"),
]

# Movimientos de cada ejemplo. La T no tiene rama Norte (M7-M9); con el
# mapeo fijo, M1 (O_IZQ), M6 (E_DER) y M11 (S_FTE) caen en slots
# inválidos de la T y se muestran con "—" en el croquis.
MOVS_CRUZ = [f"M{i}" for i in range(1, 13)]
MOVS_T = ["M1", "M2", "M3", "M4", "M5", "M6", "M10", "M11", "M12"]
MOVS_RUTA = ["M1", "M2"]


def _mapa_para(movs):
    """Filtra el MAPA de la cruz a los movimientos del ejemplo."""
    return [fila for fila in MAPA_CRUZ if fila[0] in movs]


def _generar(nombre, movs, mapa_filas):
    """Escribe un Excel con hojas DATOS / MAPA / CONFIG."""
    df_datos = pd.DataFrame(DATOS_BASE, columns=COLS_BASE)
    df_datos = df_datos[["hora_inicio", "hora_fin", "tipo_vehiculo"] + movs]
    df_mapa = pd.DataFrame(mapa_filas,
                           columns=["movimiento", "calle", "sentido"])
    df_config = pd.DataFrame(CONFIG, columns=["clave", "valor"])

    with pd.ExcelWriter(nombre, engine="openpyxl") as w:
        df_datos.to_excel(w, sheet_name="DATOS", index=False)
        df_mapa.to_excel(w, sheet_name="MAPA", index=False)
        df_config.to_excel(w, sheet_name="CONFIG", index=False)
    print(f"✅ Generado: {nombre}  "
          f"(DATOS {df_datos.shape}, MAPA {df_mapa.shape})")


if __name__ == "__main__":
    _generar("censo_ejemplo_cruz.xlsx", MOVS_CRUZ, MAPA_CRUZ)
    _generar("censo_ejemplo_T.xlsx", MOVS_T, _mapa_para(MOVS_T))
    # La ruta: misma calle, un sentido por extremo (ida y vuelta).
    mapa_ruta = [
        ("M1", "Calle Ppal", "Oeste-Este"),
        ("M2", "Calle Ppal", "Este-Oeste"),
    ]
    _generar("censo_ejemplo_ruta.xlsx", MOVS_RUTA, mapa_ruta)
MOVS_RUTA = ["M1", "M2"]
