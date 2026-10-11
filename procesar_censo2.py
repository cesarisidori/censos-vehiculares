"""
procesar_censo2.py
------------------
Lee un Excel con:
  - Hoja DATOS:  hora_inicio | hora_fin | tipo_vehiculo | M1..Mn
  - Hoja MAPA:   movimiento | calle | sentido  (opcional)
  - Hoja CONFIG: clave | valor                 (opcional)

Calcula:
  1. Totales por bloque de 15 min (excluyendo tipos).
  2. Hora pico = ventana deslizante de N bloques con mayor suma.
  3. Resumen hora pico PLANO (filas=tipo, columnas=movimientos).
  4. Resumen hora pico AGRUPADO (por calle+sentido) — solo si hay MAPA.

Exporta a 'resultado_<archivo>.xlsx' con hojas:
  - Resumen_Hora_Pico         (agrupada, encabezado multinivel)
  - Resumen_Hora_Pico_Plano   (plana, auditoría)
  - Totales_15min
  - Datos_Originales

Uso:
    python procesar_censo2.py censo.xlsx
    python procesar_censo2.py censo.xlsx --verbose
    python procesar_censo2.py censo.xlsx --excluir Bicicleta Peaton
    python procesar_censo2.py censo.xlsx --ventana 3
"""

import argparse
import re
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────────────────────
# Defaults
# ─────────────────────────────────────────────────────────────
TIPOS_EXCLUIDOS_DEFAULT = ["Bicicleta", "Bicicletas", "Peaton", "Peatón", "Peatones"]
NOMBRE_FILA_TOTAL_DEFAULT = "Total p/NS"
VENTANA_PICO_DEFAULT = 4

COLS_FIJAS = ["hora_inicio", "hora_fin", "tipo_vehiculo"]
PATRON_TOTAL_FILA = re.compile(r"^\s*total(es)?\b", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# Lectura
# ─────────────────────────────────────────────────────────────
def leer_config(ruta: str) -> dict:
    """Lee hoja CONFIG si existe."""
    try:
        df = pd.read_excel(ruta, sheet_name="CONFIG", dtype=str)
    except Exception:
        return {}

    df.columns = [str(c).strip().lower() for c in df.columns]
    if "clave" not in df.columns or "valor" not in df.columns:
        return {}

    cfg = {}
    for _, row in df.iterrows():
        clave = str(row["clave"]).strip().lower()
        valor = str(row["valor"]).strip() if pd.notna(row["valor"]) else ""
        cfg[clave] = valor
    return cfg


def leer_mapa(ruta: str):
    """Lee hoja MAPA si existe."""
    try:
        df = pd.read_excel(ruta, sheet_name="MAPA", dtype=str)
    except Exception:
        return None
    df.columns = [str(c).strip().lower() for c in df.columns]
    if not {"movimiento", "calle", "sentido"}.issubset(df.columns):
        print("⚠️  Hoja MAPA existe pero le faltan columnas. Se ignora.")
        return None
    df = df.dropna(subset=["movimiento"])
    df["movimiento"] = df["movimiento"].astype(str).str.strip()
    df["calle"] = df["calle"].fillna("").astype(str).str.strip()
    df["sentido"] = df["sentido"].fillna("").astype(str).str.strip()
    return df.reset_index(drop=True)


def leer_datos(ruta: str):
    """Lee hoja DATOS y valida."""
    df = pd.read_excel(ruta, sheet_name="DATOS", dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    faltantes = [c for c in COLS_FIJAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas obligatorias en DATOS: {faltantes}")

    movs = [c for c in df.columns if c not in COLS_FIJAS]
    if not movs:
        raise ValueError("No se detectaron columnas de movimientos en DATOS.")

    df = df.dropna(subset=["hora_inicio", "tipo_vehiculo"])
    df["hora_inicio"] = df["hora_inicio"].astype(str).str.strip().str.slice(0, 5)
    df["hora_fin"] = df["hora_fin"].astype(str).str.strip().str.slice(0, 5)
    df["tipo_vehiculo"] = df["tipo_vehiculo"].astype(str).str.strip()

    # Ignorar filas TOTAL
    totales = df["tipo_vehiculo"].str.match(PATRON_TOTAL_FILA, na=False)
    if totales.any():
        print(f"ℹ️  Ignoradas {int(totales.sum())} filas cuyo tipo_vehiculo es TOTAL.")
        df = df[~totales]

    for m in movs:
        df[m] = pd.to_numeric(df[m], errors="coerce").fillna(0).astype(int)

    dup = df.duplicated(subset=["hora_inicio", "tipo_vehiculo"], keep=False)
    if dup.any():
        print("⚠️  Filas duplicadas (mismo bloque + mismo tipo):")
        print(df[dup][["hora_inicio", "tipo_vehiculo"]].drop_duplicates().to_string(index=False))

    return df.reset_index(drop=True), movs


# ─────────────────────────────────────────────────────────────
# Cálculos
# ─────────────────────────────────────────────────────────────
def totales_15min(df, movs, excluidos):
    validos = df[~df["tipo_vehiculo"].isin(excluidos)]
    agg = (
        validos.groupby(["hora_inicio", "hora_fin"], as_index=False)[movs]
        .sum()
        .sort_values("hora_inicio")
        .reset_index(drop=True)
    )
    agg["TOTAL"] = agg[movs].sum(axis=1)
    return agg


def detectar_hora_pico(totales, ventana):
    serie = totales["TOTAL"].to_numpy()
    if len(serie) < ventana:
        raise ValueError(f"Se necesitan >= {ventana} bloques. Hay {len(serie)}.")
    sumas = [serie[i:i + ventana].sum() for i in range(len(serie) - ventana + 1)]
    idx = int(pd.Series(sumas).idxmax())
    ini = totales.loc[idx, "hora_inicio"]
    fin = totales.loc[idx + ventana - 1, "hora_fin"]
    return ini, fin, int(sumas[idx])


def resumen_plano_hora_pico(df, movs, excluidos, hora_ini, hora_fin):
    """Resumen plano: filas=tipo, columnas=movimiento."""
    bloques = df[(df["hora_inicio"] >= hora_ini) & (df["hora_fin"] <= hora_fin)]
    bloques = bloques[~bloques["tipo_vehiculo"].isin(excluidos)]
    resumen = bloques.groupby("tipo_vehiculo")[movs].sum()
    resumen.loc["TOTAL"] = resumen.sum()
    resumen["TOTAL"] = resumen.sum(axis=1)
    return resumen


def resumen_agrupado(df, movs, excluidos, mapa, hora_ini, hora_fin,
                     nombre_fila_total):
    """
    Tabla agrupada por (calle, sentido).
    - Filas: tipo_vehiculo + fila final <nombre_fila_total>.
    - Columnas: multinivel [grupo, movimiento/subtotal] + [Total, ""].
    """
    # 1) Resumen plano de la hora pico
    plano = resumen_plano_hora_pico(df, movs, excluidos, hora_ini, hora_fin)

    # 2) Detectar movimientos huérfanos
    movs_mapa = set(mapa["movimiento"]) if mapa is not None else set()
    huerfanos = [m for m in movs if m not in movs_mapa]
    if huerfanos and mapa is not None:
        print(f"⚠️  Movimientos en DATOS pero no en MAPA (se ignoran en agrupada): {huerfanos}")

    # 3) Filtrar movimientos a los que están en MAPA
    movs_agrup = [m for m in movs if m in movs_mapa]

    # 4) Orden de grupos según aparición en MAPA
    grupos_df = (
        mapa[mapa["movimiento"].isin(movs_agrup)][["calle", "sentido"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    grupos = list(grupos_df.itertuples(index=False, name=None))

    # 5) Tipos de vehículo en el orden del resumen plano
    tipos_orden = list(plano.index)
    tipos_validos = [t for t in tipos_orden
                     if t != nombre_fila_total and t not in excluidos]

    # 6) Construir la tabla
    filas = []
    for tipo in tipos_orden:
        fila = {}
        for calle, sentido in grupos:
            movs_grupo = mapa[
                (mapa["calle"] == calle)
                & (mapa["sentido"] == sentido)
                & (mapa["movimiento"].isin(movs_agrup))
            ]["movimiento"].tolist()

            for mov in movs_grupo:
                if tipo == nombre_fila_total:
                    valor = int(plano.loc[tipos_validos, mov].sum())
                else:
                    valor = int(plano.loc[tipo, mov])
                fila[(f"{calle} | {sentido}", mov)] = valor

            # subtotal del grupo
            if tipo == nombre_fila_total:
                sub = int(plano.loc[tipos_validos, movs_grupo].sum().sum())
            else:
                sub = int(plano.loc[tipo, movs_grupo].sum())
            fila[(f"{calle} | {sentido}", "Total")] = sub
        filas.append((tipo, fila))

    # 7) Construir DataFrame
    df_out = pd.DataFrame([f for _, f in filas])
    df_out.index = [t for t, _ in filas]
    df_out.index.name = "tipo_vehiculo"

    # 8) Columna Total general
    totales_gen = []
    for tipo in df_out.index:
        if tipo == nombre_fila_total:
            totales_gen.append(int(df_out.loc[tipos_validos].sum().sum()))
        else:
            totales_gen.append(int(df_out.loc[tipo].sum()))
    df_out[("Total", "")] = totales_gen

    # 9) Multinivel
    df_out.columns = pd.MultiIndex.from_tuples(df_out.columns)
    return df_out


# ─────────────────────────────────────────────────────────────
# Impresión terminal (aplanada)
# ─────────────────────────────────────────────────────────────
def imprimir(df, movs, totales, pico, resumen_plano_df, resumen_agr_df,
             excluidos, cfg):
    sep = "═" * 72
    print(sep)
    print("CENSO VEHICULAR — PROCESAMIENTO")
    print(sep)

    print(f"\nBloques de 15 min: {len(totales)}")
    print(f"Movimientos detectados: {len(movs)}")
    print(f"Tipos de vehículo: {sorted(df['tipo_vehiculo'].unique())}")
    print(f"Tipos excluidos: {excluidos}")
    print(f"Nombre fila total: '{cfg.get('nombre_fila_total')}'")

    print("\n── Totales por bloque de 15 min ──")
    print(totales[["hora_inicio", "hora_fin", "TOTAL"]].to_string(index=False))

    ini, fin, total = pico
    print(f"\n── HORA PICO ──")
    print(f"  Desde {ini} hasta {fin}")
    print(f"  Total (excluye {', '.join(excluidos)}): {total}")

    print("\n── Resumen hora pico (aplanado) ──")
    if resumen_agr_df is not None:
        aplanado = resumen_agr_df.copy()
        aplanado.columns = [
            f"{a}_{b}".strip("_") if b else a for a, b in aplanado.columns
        ]
        print(aplanado.to_string())
    else:
        print("(sin agrupación: no hay hoja MAPA)")


# ─────────────────────────────────────────────────────────────
# Exportación
# ─────────────────────────────────────────────────────────────
def exportar(salida, resumen_agr_df, resumen_plano_df, totales, df, cfg):
    with pd.ExcelWriter(salida, engine="openpyxl") as w:
        if resumen_agr_df is not None:
            resumen_agr_df.to_excel(w, sheet_name="Resumen_Hora_Pico")
        resumen_plano_df.to_excel(w, sheet_name="Resumen_Hora_Pico_Plano")
        totales.to_excel(w, sheet_name="Totales_15min", index=False)
        df.to_excel(w, sheet_name="Datos_Originales", index=False)
    print(f"\n✅ Exportado: {salida}")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Procesa un censo vehicular.")
    parser.add_argument("ruta", help="Ruta del Excel del censo")
    parser.add_argument("--excluir", nargs="*", default=None,
                        help="Tipos a excluir (sobrescribe CONFIG)")
    parser.add_argument("--ventana", type=int, default=VENTANA_PICO_DEFAULT,
                        help=f"Bloques para hora pico (default: {VENTANA_PICO_DEFAULT})")
    parser.add_argument("--verbose", action="store_true",
                        help="Imprime el resumen por terminal (default: silencioso)")
    args = parser.parse_args()

    # 1) Config
    cfg = leer_config(args.ruta)

    # 2) Excluidos (prioridad: --excluir > CONFIG > default)
    if args.excluir is not None:
        excluidos = args.excluir
    elif "tipos_excluidos" in cfg:
        excluidos = [t.strip() for t in cfg["tipos_excluidos"].split(",") if t.strip()]
    else:
        excluidos = TIPOS_EXCLUIDOS_DEFAULT

    nombre_fila_total = cfg.get("nombre_fila_total", NOMBRE_FILA_TOTAL_DEFAULT)

    # 3) MAPA y DATOS
    mapa = leer_mapa(args.ruta)
    df, movs = leer_datos(args.ruta)

    # 4) Cálculos
    totales = totales_15min(df, movs, excluidos)
    pico = detectar_hora_pico(totales, args.ventana)

    resumen_plano_df = resumen_plano_hora_pico(
        df, movs, excluidos, pico[0], pico[1]
    )

    resumen_agr_df = None
    if mapa is not None and len(mapa) > 0:
        resumen_agr_df = resumen_agrupado(
            df, movs, excluidos, mapa, pico[0], pico[1], nombre_fila_total
        )
    else:
        print("ℹ️  Sin hoja MAPA: se omite resumen agrupado.")

    # 5) Imprimir solo si --verbose
    if args.verbose:
        imprimir(df, movs, totales, pico, resumen_plano_df, resumen_agr_df,
                 excluidos, {"nombre_fila_total": nombre_fila_total})

    # 6) Exportar
    salida = Path(args.ruta).with_name(f"resultado_{Path(args.ruta).stem}.xlsx")
    exportar(salida, resumen_agr_df, resumen_plano_df, totales, df, cfg)


if __name__ == "__main__":
    main()