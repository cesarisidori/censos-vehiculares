"""
procesar_censo.py
-----------------
Lee un Excel con estructura:
    hora_inicio | hora_fin | tipo_vehiculo | M1 | M2 | ... | Mn

- Una fila por (bloque 15 min × tipo de vehículo).
- Las columnas después de tipo_vehiculo son movimientos (da igual el nombre).
- Las filas cuyo tipo_vehiculo sea TOTAL/Totales se ignoran automáticamente.

Calcula:
    1. Total por bloque de 15 min (excluyendo tipos excluidos).
    2. Hora pico = ventana deslizante de 4 bloques (1 hora) con mayor suma.
    3. Resumen de la hora pico: filas = tipo, columnas = movimiento.

Uso:
    python procesar_censo.py censo.xlsx
    python procesar_censo.py censo.xlsx --excluir Bicicleta Peaton Moto
    python procesar_censo.py censo.xlsx --ventana 4
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────────────────────
# Configuración por defecto
# ─────────────────────────────────────────────────────────────
TIPOS_EXCLUIDOS_DEFAULT = [
    "Bicicleta", "Bicicletas",
    "Peaton", "Peatón", "Peatones",
]
VENTANA_PICO_DEFAULT = 4  # 4 bloques de 15 min = 1 hora

COLS_FIJAS = ["hora_inicio", "hora_fin", "tipo_vehiculo"]

# Patrón para detectar filas TOTAL (case-insensitive, con o sin acento)
PATRON_TOTAL = re.compile(r"^\s*total(es)?\b", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# Lectura y validación
# ─────────────────────────────────────────────────────────────
def leer_plantilla(ruta: str) -> tuple[pd.DataFrame, list[str]]:
    """Lee el Excel, valida estructura y limpia."""
    df = pd.read_excel(ruta, dtype=str)

    # Normalizar nombres de columnas
    df.columns = [str(c).strip() for c in df.columns]

    # Validar columnas fijas
    faltantes = [c for c in COLS_FIJAS if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"Faltan columnas obligatorias: {faltantes}\n"
            f"Las 3 primeras columnas deben llamarse: {COLS_FIJAS}"
        )

    # Detectar columnas de movimientos
    movs = [c for c in df.columns if c not in COLS_FIJAS]
    if not movs:
        raise ValueError("No se detectaron columnas de movimientos.")

    # Descartar filas sin hora o sin tipo
    df = df.dropna(subset=["hora_inicio", "tipo_vehiculo"])

    # Normalizar texto
    df["hora_inicio"] = df["hora_inicio"].astype(str).str.strip().str.slice(0, 5)
    df["hora_fin"] = df["hora_fin"].astype(str).str.strip().str.slice(0, 5)
    df["tipo_vehiculo"] = df["tipo_vehiculo"].astype(str).str.strip()

    # Descartar filas cuyo tipo sea TOTAL
    totales = df["tipo_vehiculo"].str.match(PATRON_TOTAL, na=False)
    if totales.any():
        n = int(totales.sum())
        print(f"ℹ️  Ignoradas {n} filas cuyo tipo_vehiculo es TOTAL.")
        df = df[~totales]

    # Convertir movimientos a numérico (vacío → 0)
    for m in movs:
        df[m] = pd.to_numeric(df[m], errors="coerce").fillna(0).astype(int)

    # Chequeo de duplicados (mismo bloque + mismo tipo)
    dup = df.duplicated(subset=["hora_inicio", "tipo_vehiculo"], keep=False)
    if dup.any():
        filas = df[dup][["hora_inicio", "tipo_vehiculo"]].drop_duplicates()
        print("⚠️  Filas duplicadas (mismo bloque + mismo tipo):")
        print(filas.to_string(index=False))

    return df, movs


# ─────────────────────────────────────────────────────────────
# Cálculos
# ─────────────────────────────────────────────────────────────
def totales_15min(df: pd.DataFrame, movs: list[str],
                  excluidos: list[str]) -> pd.DataFrame:
    """Totales por bloque de 15 min, excluyendo tipos."""
    validos = df[~df["tipo_vehiculo"].isin(excluidos)]
    agg = (
        validos.groupby(["hora_inicio", "hora_fin"], as_index=False)[movs]
        .sum()
        .sort_values("hora_inicio")
        .reset_index(drop=True)
    )
    agg["TOTAL"] = agg[movs].sum(axis=1)
    return agg


def detectar_hora_pico(totales: pd.DataFrame, ventana: int):
    """Ventana deslizante de N bloques con mayor suma."""
    serie = totales["TOTAL"].to_numpy()
    if len(serie) < ventana:
        raise ValueError(
            f"Se necesitan al menos {ventana} bloques para detectar la hora pico. "
            f"Hay {len(serie)}."
        )
    sumas = [serie[i:i + ventana].sum() for i in range(len(serie) - ventana + 1)]
    idx = int(pd.Series(sumas).idxmax())  # primera ocurrencia si hay empate
    ini = totales.loc[idx, "hora_inicio"]
    fin = totales.loc[idx + ventana - 1, "hora_fin"]
    return ini, fin, int(sumas[idx]), idx


def resumen_hora_pico(df: pd.DataFrame, movs: list[str], excluidos: list[str],
                      hora_ini: str, hora_fin: str) -> pd.DataFrame:
    """Tabla resumen: filas=tipo, columnas=movimiento, valores=suma en hora pico."""
    bloques = df[(df["hora_inicio"] >= hora_ini) & (df["hora_fin"] <= hora_fin)]
    bloques = bloques[~bloques["tipo_vehiculo"].isin(excluidos)]
    resumen = bloques.groupby("tipo_vehiculo")[movs].sum()
    resumen.loc["TOTAL"] = resumen.sum()
    resumen["TOTAL"] = resumen.sum(axis=1)
    return resumen


# ─────────────────────────────────────────────────────────────
# Salida
# ─────────────────────────────────────────────────────────────
def imprimir(df, movs, totales, pico, resumen, excluidos):
    sep = "═" * 72
    print(sep)
    print("CENSO VEHICULAR — PROCESAMIENTO")
    print(sep)

    print(f"\nBloques de 15 min detectados: {len(totales)}")
    print(f"Movimientos detectados: {len(movs)}")
    print(f"Tipos de vehículo: {sorted(df['tipo_vehiculo'].unique())}")
    print(f"Tipos excluidos del cálculo: {excluidos}")

    print("\n── Totales por bloque de 15 min ──")
    print(totales[["hora_inicio", "hora_fin", "TOTAL"]].to_string(index=False))

    ini, fin, total, idx = pico
    print(f"\n── HORA PICO ──")
    print(f"  Desde {ini} hasta {fin}")
    print(f"  Total vehículos (excluye {', '.join(excluidos)}): {total}")

    print("\n── Resumen hora pico ──")
    print(resumen.to_string())


def exportar(resumen: pd.DataFrame, totales: pd.DataFrame,
             df: pd.DataFrame, salida: Path):
    with pd.ExcelWriter(salida, engine="openpyxl") as w:
        resumen.to_excel(w, sheet_name="Resumen_Hora_Pico")
        totales.to_excel(w, sheet_name="Totales_15min", index=False)
        df.to_excel(w, sheet_name="Datos_Originales", index=False)
    print(f"\n✅ Exportado: {salida}")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Procesa un censo vehicular.")
    parser.add_argument("ruta", help="Ruta del Excel del censo")
    parser.add_argument(
        "--excluir", nargs="*", default=None,
        help="Tipos a excluir del cálculo (default: Bicicleta, Peaton)"
    )
    parser.add_argument(
        "--ventana", type=int, default=VENTANA_PICO_DEFAULT,
        help=f"Cantidad de bloques para hora pico (default: {VENTANA_PICO_DEFAULT})"
    )
    args = parser.parse_args()

    excluidos = args.excluir if args.excluir is not None else TIPOS_EXCLUIDOS_DEFAULT

    df, movs = leer_plantilla(args.ruta)
    totales = totales_15min(df, movs, excluidos)
    pico = detectar_hora_pico(totales, args.ventana)
    resumen = resumen_hora_pico(df, movs, excluidos, pico[0], pico[1])

    imprimir(df, movs, totales, pico, resumen, excluidos)

    salida = Path(args.ruta).with_name(f"resultado_{Path(args.ruta).stem}.xlsx")
    exportar(resumen, totales, df, salida)


if __name__ == "__main__":
    main()