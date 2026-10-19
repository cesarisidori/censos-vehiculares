"""
procesar_censo3.py
------------------
Lee un Excel con:
  - Hoja DATOS:  hora_inicio | hora_fin | tipo_vehiculo | M1..Mn
  - Hoja MAPA:   movimiento | calle | sentido  (opcional)
  - Hoja CONFIG: clave | valor                 (opcional)

Claves reconocidas en CONFIG:
  - tipos_excluidos       : "Bicicleta, Peaton"      (tipos fuera de totales y hora pico)
  - nombre_fila_total     : "Total p/NS"             (nombre de la fila resumen)
  - calcular_pct_pesados  : "SI" / "NO"              (habilitar cálculo % pesados)
  - tipos_pesados         : "Camiones, Ómnibus"      (tipos que cuentan como pesados)

Calcula:
  1. Totales por bloque de 15 min (excluyendo tipos).
  2. Hora pico = ventana deslizante de 4 bloques (1 hora).
  3. FHP = Volumen HP / (4 * Volumen máximo de 15 min).
  4. Resumen hora pico PLANO.
  5. Resumen hora pico AGRUPADO (por calle+sentido).
  6. % de vehículos pesados por movimiento (hora pico y total del censo).

Exporta a 'resultado_<archivo>.xlsx' con hojas:
  - FHP
  - Resumen_Hora_Pico
  - Resumen_Hora_Pico_Plano
  - Pesados_Hora_Pico      (si aplica)
  - Pesados_Total          (si aplica)
  - Totales_15min
  - Datos_Originales

Uso:
    python procesar_censo3.py censo.xlsx
    python procesar_censo3.py censo.xlsx --verbose
    python procesar_censo3.py censo.xlsx --excluir Bicicleta Peaton
"""

import argparse
import io
import re
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────────────────────
# Defaults
# ─────────────────────────────────────────────────────────────
TIPOS_EXCLUIDOS_DEFAULT = ["Bicicleta", "Bicicletas", "Peaton", "Peatón", "Peatones"]
NOMBRE_FILA_TOTAL_DEFAULT = "Total p/NS"
VENTANA_PICO = 4  # 4 bloques de 15 min = 1 hora (regla fija)

COLS_FIJAS = ["hora_inicio", "hora_fin", "tipo_vehiculo"]
PATRON_TOTAL_FILA = re.compile(r"^\s*total(es)?\b", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# Lectura
# ─────────────────────────────────────────────────────────────
def _cfg_de_df(df) -> dict:
    """Normaliza la hoja CONFIG (DataFrame) a dict clave->valor (str)."""
    if df is None:
        return {}
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "clave" not in df.columns or "valor" not in df.columns:
        return {}
    cfg = {}
    for _, row in df.iterrows():
        clave = str(row["clave"]).strip().lower()
        valor = str(row["valor"]).strip() if pd.notna(row["valor"]) else ""
        cfg[clave] = valor
    return cfg


def leer_config(ruta) -> dict:
    """
    Lee hoja CONFIG si existe. Devuelve dict clave->valor (str).
    `ruta` puede ser una ruta (str/Path) o un buffer (BytesIO).
    """
    if hasattr(ruta, "seek"):
        ruta.seek(0)
    try:
        df = pd.read_excel(ruta, sheet_name="CONFIG", dtype=str)
    except Exception:
        return {}
    return _cfg_de_df(df)


def parse_lista(cfg: dict, clave: str) -> list:
    """Convierte 'a, b, c' en ['a', 'b', 'c']."""
    if clave not in cfg or not cfg[clave]:
        return []
    return [t.strip() for t in cfg[clave].split(",") if t.strip()]


def _mapa_de_df(df):
    """Normaliza la hoja MAPA (DataFrame). Devuelve None si no sirve."""
    if df is None:
        return None
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    if not {"movimiento", "calle", "sentido"}.issubset(df.columns):
        print("⚠️  Hoja MAPA existe pero le faltan columnas. Se ignora.")
        return None
    df = df.dropna(subset=["movimiento"])
    df["movimiento"] = df["movimiento"].astype(str).str.strip()
    df["calle"] = df["calle"].fillna("").astype(str).str.strip()
    df["sentido"] = df["sentido"].fillna("").astype(str).str.strip()
    return df.reset_index(drop=True)


def leer_mapa(ruta):
    """Lee hoja MAPA si existe. `ruta` puede ser ruta o buffer (BytesIO)."""
    if hasattr(ruta, "seek"):
        ruta.seek(0)
    try:
        df = pd.read_excel(ruta, sheet_name="MAPA", dtype=str)
    except Exception:
        return None
    return _mapa_de_df(df)


def _datos_de_df(df):
    """Normaliza la hoja DATOS (DataFrame). Devuelve (df, movs)."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    faltantes = [c for c in COLS_FIJAS if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"Faltan columnas obligatorias en la hoja DATOS: {faltantes}. "
            f"Se esperan {COLS_FIJAS} más una columna por movimiento."
        )

    movs = [c for c in df.columns if c not in COLS_FIJAS]
    if not movs:
        raise ValueError(
            "No se detectaron columnas de movimientos en DATOS. Agregá al "
            "menos una (p. ej. M1), además de hora_inicio, hora_fin y "
            "tipo_vehiculo."
        )

    df = df.dropna(subset=["hora_inicio", "tipo_vehiculo"])
    df["hora_inicio"] = df["hora_inicio"].astype(str).str.strip().str.slice(0, 5)
    df["hora_fin"] = df["hora_fin"].astype(str).str.strip().str.slice(0, 5)
    df["tipo_vehiculo"] = df["tipo_vehiculo"].astype(str).str.strip()

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


def leer_datos(ruta):
    """Lee hoja DATOS y valida. `ruta` puede ser ruta o buffer (BytesIO)."""
    if hasattr(ruta, "seek"):
        ruta.seek(0)
    try:
        df = pd.read_excel(ruta, sheet_name="DATOS", dtype=str)
    except Exception as e:
        raise ValueError(
            "El archivo no tiene una hoja 'DATOS' legible. Se esperan las "
            "hojas DATOS (obligatoria), y opcionalmente MAPA y CONFIG."
        ) from e
    return _datos_de_df(df)


def leer_censo(ruta):
    """
    Lee las 3 hojas (DATOS, MAPA, CONFIG) en UNA sola apertura del archivo.
    Devuelve (cfg, mapa, df, movs). `ruta` puede ser ruta o buffer (BytesIO).

    Pensada para la app: lee el Excel una sola vez y luego `procesar` puede
    recibir el resultado vía `precargado`, sin volver a leer.
    """
    if hasattr(ruta, "seek"):
        ruta.seek(0)
    try:
        libro = pd.ExcelFile(ruta)
    except Exception as e:
        raise ValueError(f"No se pudo abrir el archivo Excel: {e}") from e

    hojas = set(libro.sheet_names)
    if "DATOS" not in hojas:
        raise ValueError(
            "El archivo no tiene una hoja 'DATOS'. Se esperan las hojas "
            "DATOS (obligatoria), y opcionalmente MAPA y CONFIG."
        )

    cfg = _cfg_de_df(libro.parse("CONFIG", dtype=str)) if "CONFIG" in hojas else {}
    mapa = _mapa_de_df(libro.parse("MAPA", dtype=str)) if "MAPA" in hojas else None
    df, movs = _datos_de_df(libro.parse("DATOS", dtype=str))
    return cfg, mapa, df, movs


# ─────────────────────────────────────────────────────────────
# Cálculos — Hora pico y FHP
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


def detectar_hora_pico(totales, ventana=VENTANA_PICO):
    serie = totales["TOTAL"].to_numpy()
    if len(serie) < ventana:
        raise ValueError(
            f"El censo tiene {len(serie)} bloque(s) de 15 min; se necesitan "
            f"al menos {ventana} (1 hora) para calcular la hora pico."
        )
    sumas = [serie[i:i + ventana].sum() for i in range(len(serie) - ventana + 1)]
    idx = int(pd.Series(sumas).idxmax())
    ini = totales.loc[idx, "hora_inicio"]
    fin = totales.loc[idx + ventana - 1, "hora_fin"]
    return ini, fin, int(sumas[idx])


def calcular_fhp(totales, hora_ini, hora_fin, ventana=VENTANA_PICO):
    """
    FHP = Volumen HP / (ventana * Volumen máximo de 15 min dentro de la HP).
    """
    bloques = totales[
        (totales["hora_inicio"] >= hora_ini) &
        (totales["hora_fin"] <= hora_fin)
    ].reset_index(drop=True)

    if len(bloques) != ventana:
        raise ValueError(
            f"Se esperaban {ventana} bloques en la hora pico, hay {len(bloques)}."
        )

    volumen_hp = int(bloques["TOTAL"].sum())
    idx_max = int(bloques["TOTAL"].idxmax())
    bloque_max_ini = bloques.loc[idx_max, "hora_inicio"]
    bloque_max_fin = bloques.loc[idx_max, "hora_fin"]
    volumen_max = int(bloques.loc[idx_max, "TOTAL"])

    fhp = volumen_hp / (ventana * volumen_max) if volumen_max > 0 else 0.0

    return {
        "hora_pico_inicio": hora_ini,
        "hora_pico_fin": hora_fin,
        "volumen_hp": volumen_hp,
        "bloque_max_inicio": bloque_max_ini,
        "bloque_max_fin": bloque_max_fin,
        "volumen_max_15min": volumen_max,
        "fhp": round(fhp, 3),
    }


# ─────────────────────────────────────────────────────────────
# Cálculos — Resúmenes de hora pico
# ─────────────────────────────────────────────────────────────
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
    """Tabla agrupada por (calle, sentido) con encabezado multinivel."""
    plano = resumen_plano_hora_pico(df, movs, excluidos, hora_ini, hora_fin)

    movs_mapa = set(mapa["movimiento"]) if mapa is not None else set()
    huerfanos = [m for m in movs if m not in movs_mapa]
    if huerfanos and mapa is not None:
        print(f"⚠️  Movimientos en DATOS pero no en MAPA (se ignoran en agrupada): {huerfanos}")

    movs_agrup = [m for m in movs if m in movs_mapa]

    grupos_df = (
        mapa[mapa["movimiento"].isin(movs_agrup)][["calle", "sentido"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    grupos = list(grupos_df.itertuples(index=False, name=None))

    tipos_orden = list(plano.index)
    tipos_validos = [t for t in tipos_orden
                     if t != nombre_fila_total and t not in excluidos]

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

    df_out = pd.DataFrame([f for _, f in filas])
    df_out.index = [t for t, _ in filas]
    df_out.index.name = "tipo_vehiculo"

    # 8) Columna Total general: sumar SOLO los movimientos individuales,
    #    NO los subtotales de grupo (evita doble conteo).
    columnas_movs = [c for c in df_out.columns if c[1] != "Total"]

    totales_gen = []
    for tipo in df_out.index:
        if tipo == nombre_fila_total:
            totales_gen.append(int(df_out.loc[tipos_validos, columnas_movs].sum().sum()))
        else:
            totales_gen.append(int(df_out.loc[tipo, columnas_movs].sum()))
    df_out[("Total", "")] = totales_gen

    df_out.columns = pd.MultiIndex.from_tuples(df_out.columns)
    return df_out


# ─────────────────────────────────────────────────────────────
# Cálculos — % de pesados
# ─────────────────────────────────────────────────────────────
def tabla_pesados(df_origen, movs, tipos_pesados, tipos_excluidos,
                  nombre_fila_total):
    """
    Construye la tabla de % de pesados sobre el df_origen (ya filtrado al
    período deseado: hora pico o censo completo).

    Estructura:
        filas = tipos de vehículo presentes + filas resumen
        columnas = movimientos + Total
        filas especiales al final:
            - TOTAL pesados
            - TOTAL vehículos
            - % pesados  (0-100, 2 decimales)
    """
    movs_validos = [m for m in movs if m in df_origen.columns]

    # Tipos que NO son excluidos
    df_validos = df_origen[~df_origen["tipo_vehiculo"].isin(tipos_excluidos)]

    # Tabla base: tipos × movimientos
    base = df_validos.groupby("tipo_vehiculo")[movs_validos].sum()

    # Fila TOTAL pesados (solo tipos en tipos_pesados)
    tipos_pesados_validos = [t for t in base.index
                             if t in tipos_pesados and t not in tipos_excluidos]
    if tipos_pesados_validos:
        total_pesados = base.loc[tipos_pesados_validos].sum()
    else:
        total_pesados = pd.Series(0, index=movs_validos)

    # Fila TOTAL vehículos (todos los tipos no excluidos)
    total_vehiculos = base.sum()

    # % pesados
    pct = (total_pesados / total_vehiculos * 100)
    pct = pct.replace([float("inf"), float("-inf")], 0).fillna(0).round(2)

    # Agregar columnas Total
    base["Total"] = base.sum(axis=1)
    total_pesados["Total"] = total_pesados.sum()
    total_vehiculos["Total"] = total_vehiculos.sum()
    pct["Total"] = (
        round(total_pesados["Total"] / total_vehiculos["Total"] * 100, 2)
        if total_vehiculos["Total"] > 0 else 0.0
    )

    # Ensamblar
    df_out = base.copy()
    df_out.loc["TOTAL pesados"] = total_pesados
    df_out.loc["TOTAL vehículos"] = total_vehiculos
    df_out.loc["% pesados"] = pct

    df_out.index.name = "tipo_vehiculo"
    return df_out


# ─────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────
def procesar(ruta=None, excluidos=None, nombre_fila_total=None,
             calcular_pesados=None, tipos_pesados=None, precargado=None):
    """
    Pipeline completo de cálculo. Acepta ruta o buffer (BytesIO).

    Los parámetros en None se toman de la hoja CONFIG (con sus defaults).
    Es la misma función que usa la app Streamlit y la CLI (`main`).

    `precargado`: dict opcional con las hojas ya leídas y normalizadas
    ({"cfg", "mapa", "datos": (df, movs)}), para no volver a leer el Excel.
    Si se pasa, se ignora `ruta`. Lo arma `leer_censo`.

    Devuelve un dict con: cfg, mapa, df, movs, excluidos,
    nombre_fila_total, totales, pico, fhp_data, resumen_plano,
    resumen_agr, pesados_hp, pesados_total.
    """
    if precargado is not None:
        cfg = precargado.get("cfg", {})
        mapa = precargado.get("mapa")
        df, movs = precargado["datos"]
    else:
        cfg, mapa, df, movs = leer_censo(ruta)

    if excluidos is None:
        if "tipos_excluidos" in cfg:
            excluidos = parse_lista(cfg, "tipos_excluidos")
        else:
            excluidos = TIPOS_EXCLUIDOS_DEFAULT
    if nombre_fila_total is None:
        nombre_fila_total = cfg.get("nombre_fila_total",
                                    NOMBRE_FILA_TOTAL_DEFAULT)
    if calcular_pesados is None:
        calcular_pesados = (cfg.get("calcular_pct_pesados", "NO")
                            .strip().upper() == "SI")
    if tipos_pesados is None:
        tipos_pesados = parse_lista(cfg, "tipos_pesados")

    # El MAPA es la fuente de verdad: los movimientos de DATOS que no
    # tienen fila en MAPA se ignoran en todo el pipeline (totales, hora
    # pico, FHP, resúmenes, pesados y — vía res["movs"] — también en la
    # app: gráficos, croquis y reportes).
    if mapa is not None and len(mapa) > 0:
        movs_mapa = {str(m).strip() for m in mapa["movimiento"]}
        huerfanos = [m for m in movs if m not in movs_mapa]
        if huerfanos:
            print(f"ℹ️  Ignorados {len(huerfanos)} movimientos sin fila en "
                  f"MAPA: {', '.join(huerfanos)}")
            movs = [m for m in movs if m in movs_mapa]

    totales = totales_15min(df, movs, excluidos)
    pico = detectar_hora_pico(totales, VENTANA_PICO)
    fhp_data = calcular_fhp(totales, pico[0], pico[1], VENTANA_PICO)
    resumen_plano = resumen_plano_hora_pico(df, movs, excluidos,
                                            pico[0], pico[1])

    resumen_agr = None
    if mapa is not None and len(mapa) > 0:
        resumen_agr = resumen_agrupado(df, movs, excluidos, mapa,
                                       pico[0], pico[1], nombre_fila_total)

    pesados_hp = None
    pesados_total = None
    if calcular_pesados and tipos_pesados:
        df_hp = df[(df["hora_inicio"] >= pico[0]) & (df["hora_fin"] <= pico[1])]
        pesados_hp = tabla_pesados(df_hp, movs, tipos_pesados, excluidos,
                                   nombre_fila_total)
        pesados_total = tabla_pesados(df, movs, tipos_pesados, excluidos,
                                      nombre_fila_total)
    elif calcular_pesados and not tipos_pesados:
        print("⚠️  calcular_pct_pesados = SI pero 'tipos_pesados' "
              "está vacío. Se omite.")

    return {
        "cfg": cfg,
        "mapa": mapa,
        "df": df,
        "movs": movs,
        "excluidos": excluidos,
        "nombre_fila_total": nombre_fila_total,
        "totales": totales,
        "pico": pico,
        "fhp_data": fhp_data,
        "resumen_plano": resumen_plano,
        "resumen_agr": resumen_agr,
        "pesados_hp": pesados_hp,
        "pesados_total": pesados_total,
    }


# ─────────────────────────────────────────────────────────────
# Impresión terminal (aplanada)
# ─────────────────────────────────────────────────────────────
def imprimir(df, movs, totales, pico, resumen_plano_df, resumen_agr_df,
             excluidos, cfg, fhp_data, pesados_hp, pesados_total):
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

    print("\n── FACTOR DE HORA PICO (FHP) ──")
    print(f"  Volumen HP: {fhp_data['volumen_hp']}")
    print(f"  Bloque máx 15 min: {fhp_data['bloque_max_inicio']} – {fhp_data['bloque_max_fin']}")
    print(f"  Volumen máx 15 min: {fhp_data['volumen_max_15min']}")
    print(f"  FHP = {fhp_data['volumen_hp']} / (4 × {fhp_data['volumen_max_15min']})"
          f" = {fhp_data['fhp']}")

    print("\n── Resumen hora pico (aplanado) ──")
    if resumen_agr_df is not None:
        aplanado = resumen_agr_df.copy()
        aplanado.columns = [
            f"{a}_{b}".strip("_") if b else a for a, b in aplanado.columns
        ]
        print(aplanado.to_string())
    else:
        print("(sin agrupación: no hay hoja MAPA)")

    if pesados_hp is not None:
        print("\n── % PESADOS (hora pico) ──")
        print(pesados_hp.to_string())


# ─────────────────────────────────────────────────────────────
# Exportación
# ─────────────────────────────────────────────────────────────
def _escribir_hojas(w, fhp_data, resumen_agr_df, resumen_plano_df,
                    pesados_hp, pesados_total, totales, df,
                    hojas_extra=None):
    """Escribe todas las hojas del resultado en un ExcelWriter abierto."""
    # 1) FHP
    fhp_df = pd.DataFrame([
        ("Hora pico inicio",   fhp_data["hora_pico_inicio"]),
        ("Hora pico fin",      fhp_data["hora_pico_fin"]),
        ("Volumen HP",         fhp_data["volumen_hp"]),
        ("Bloque máx inicio",  fhp_data["bloque_max_inicio"]),
        ("Bloque máx fin",     fhp_data["bloque_max_fin"]),
        ("Volumen máx 15 min", fhp_data["volumen_max_15min"]),
        ("FHP",                fhp_data["fhp"]),
    ], columns=["concepto", "valor"])
    fhp_df.to_excel(w, sheet_name="FHP", index=False)

    # 2) Resumen agrupado
    if resumen_agr_df is not None:
        resumen_agr_df.to_excel(w, sheet_name="Resumen_Hora_Pico")

    # 3) Resumen plano
    resumen_plano_df.to_excel(w, sheet_name="Resumen_Hora_Pico_Plano")

    # 4) Pesados hora pico
    if pesados_hp is not None:
        pesados_hp.to_excel(w, sheet_name="Pesados_Hora_Pico")

    # 5) Pesados total
    if pesados_total is not None:
        pesados_total.to_excel(w, sheet_name="Pesados_Total")

    # 6) Totales 15 min
    totales.to_excel(w, sheet_name="Totales_15min", index=False)

    # 7) Datos originales
    df.to_excel(w, sheet_name="Datos_Originales", index=False)

    # 8) Hojas extra (opcionales)
    if hojas_extra:
        for nombre, hoja in hojas_extra.items():
            hoja.to_excel(w, sheet_name=nombre, index=False)


def exportar(salida, fhp_data, resumen_agr_df, resumen_plano_df,
             pesados_hp, pesados_total, totales, df, hojas_extra=None):
    """Exporta el resultado a un archivo (ruta o buffer)."""
    with pd.ExcelWriter(salida, engine="openpyxl") as w:
        _escribir_hojas(w, fhp_data, resumen_agr_df, resumen_plano_df,
                        pesados_hp, pesados_total, totales, df, hojas_extra)
    print(f"\n✅ Exportado: {salida}")


def exportar_buffer(fhp_data, resumen_agr_df, resumen_plano_df,
                    pesados_hp, pesados_total, totales, df,
                    hojas_extra=None):
    """Exporta el resultado a un buffer en memoria (descarga desde la app)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        _escribir_hojas(w, fhp_data, resumen_agr_df, resumen_plano_df,
                        pesados_hp, pesados_total, totales, df, hojas_extra)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Procesa un censo vehicular.")
    parser.add_argument("ruta", help="Ruta del Excel del censo")
    parser.add_argument("--excluir", nargs="*", default=None,
                        help="Tipos a excluir (sobrescribe CONFIG)")
    parser.add_argument("--verbose", action="store_true",
                        help="Imprime el resumen por terminal (default: silencioso)")
    args = parser.parse_args()

    # Pipeline completo (misma función que usa la app Streamlit)
    res = procesar(args.ruta, excluidos=args.excluir)

    if args.verbose:
        imprimir(res["df"], res["movs"], res["totales"], res["pico"],
                 res["resumen_plano"], res["resumen_agr"], res["excluidos"],
                 {"nombre_fila_total": res["nombre_fila_total"]},
                 res["fhp_data"], res["pesados_hp"], res["pesados_total"])

    salida = Path(args.ruta).with_name(f"resultado_{Path(args.ruta).stem}.xlsx")
    exportar(salida, res["fhp_data"], res["resumen_agr"], res["resumen_plano"],
             res["pesados_hp"], res["pesados_total"], res["totales"], res["df"])


if __name__ == "__main__":
    main()