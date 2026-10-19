# AGENTS.md — Procesador de Censos Vehiculares

## Project overview
Aplicación Python + Streamlit para procesar censos de tránsito vehicular.
Lee un Excel con 3 hojas (`DATOS`, `MAPA`, `CONFIG`), calcula hora pico,
FHP, % de pesados, y genera gráficos, reportes (PDF/DOCX) y croquis
de intersección (cruz, T o ruta) basados en SVG.

**Stack:** Python 3.10+, Streamlit, pandas, openpyxl, plotly, reportlab,
python-docx, plotly-mirage.

**Entorno:** Windows (principal) y Linux Mint. En Windows usá `python`;
en Linux, `python3`.

## Setup commands
- Install deps: `pip install -r requirements.txt`
- Run app: `streamlit run app.py`
- Generate example Excel files: `python crear_ejemplo.py`
  (genera `censo_ejemplo_cruz.xlsx`, `censo_ejemplo_T.xlsx`,
  `censo_ejemplo_ruta.xlsx`)
- Test croquis SVG: `python test_croquis.py`
- Test reportes: `python test_reportes.py`
- Mapeador visual de movimientos: abrir `mapeador_croquis.html` en el
  navegador (autocontenido, no requiere servidor). Si cambiás los SVG de
  `assets/`, regeneralo con `python generar_mapeador.py`.
- Process console (verbose): `python procesar_censo3.py <archivo>.xlsx --verbose`

## Architecture
- `app.py` — Interfaz Streamlit. Punto de entrada. Importa `procesar_censo3`,
  `graficos`, `reportes`, `croquis_svg` y `excel_graficos`.
- `procesar_censo3.py` — Motor de cálculo. `leer_censo()` lee las 3 hojas
  (DATOS/MAPA/CONFIG) en una sola pasada; `procesar()` es el pipeline
  completo (lo usan la CLI y la app) y acepta ruta/buffer (BytesIO) o
  `precargado` con las hojas ya leídas, para no re-leer el Excel.
  `exportar()`/`exportar_buffer()` aceptan `hojas_extra` y un callback
  `al_escribir(libro)` que recibe el libro abierto (así la app agrega los
  gráficos nativos sin que el motor importe openpyxl).
- `graficos.py` — Figuras Plotly puras (reciben datos, devuelven `Figure`).
  Define `PALETA_DEFAULT` y `PALETAS_PREDEFINIDAS` (combinaciones estilo
  Excel, pastel, vibrante, etc.); la app ofrece esas combinaciones y,
  opcionalmente, color pickers para cada serie.
  Incluye `_safe_int()` para blindar contra NaN/None.
- `reportes.py` — Reportes descargables: PDF (reportlab, DejaVu **embebida**
  desde `fonts/`) y DOCX (python-docx, **Arial**). 
- `croquis_svg.py` — Renderiza los croquis (cruz, T, ruta) inyectando los
  valores de cada movimiento en los SVG base. Limpia el SVG antes de
  inyectarlo (elimina metadata de Inkscape, reemplaza `context-stroke`).
- `excel_graficos.py` — Gráficos **nativos** (openpyxl: línea, barras, dona)
  para el Excel de salida. `preparar_graficos()` devuelve `hojas_extra`
  (datos en formato ancho) y el callback `al_escribir` que el motor invoca
  con el libro abierto; los gráficos quedan en la hoja `Gráficos` y las
  series usan la paleta elegida en la app. El motor nunca importa openpyxl.
- `assets/croquis_cruz.svg`, `assets/croquis_T.svg`, `assets/croquis_ruta.svg`
  — SVGs base con IDs de texto para cada movimiento y caja.
- `crear_ejemplo.py` — Genera los 3 Excel de ejemplo.
- `mapeador_croquis.html` — Herramienta visual (HTML autocontenido) para
  asignar cada movimiento a una posición del croquis y exportar la hoja
  `MAPA` con la columna `posicion`. Se genera con `generar_mapeador.py`,
  que inyecta los SVG de `assets/` inline.
- `generar_mapeador.py` — Regenera `mapeador_croquis.html` desde los SVG.
- `test_croquis.py` — Test manual: genera los 3 HTML de croquis.
- `test_reportes.py` — Test manual: genera `test_reporte.pdf` y `test_reporte.docx`.
- `fonts/` — DejaVuSans.ttf (+ Bold) para embeber en el PDF.

**Filosofía:** El motor no depende del Excel. Los adaptadores/lectores viven
en `app.py`. Esto permite que Streamlit maneje la UI mientras el motor
permanece agnóstico.

## Croquis: tipos e inferencia
La app soporta 3 tipos de croquis, inferidos automáticamente por cantidad
de movimientos:
- **Cruz**: 12 movimientos (4 ramas × 3).
- **T**: 6-9 movimientos (3 ramas × 3, con la rama Norte ausente).
- **Ruta**: 2 movimientos (M1 ida, M2 vuelta).

El usuario puede sobrescribir la inferencia con un selector en la app.

Mapeo fijo del SVG:
- **Cruz**: `N_IZQ`, `N_FTE`, `N_DER`, `S_*`, `E_*`, `O_*` (12 posiciones).
- **T**: `S_IZQ`, `S_FTE`(no), `S_DER`, `O_IZQ`(no), `O_FTE`, `O_DER`,
  `E_IZQ`, `E_FTE`, `E_DER`(no). Slots no válidos = `—`.
- **Ruta**: `M1`, `M2` (2 extremos).

Mapeo personalizado (censos con otros números): la hoja `MAPA` puede traer
una 4.ª columna opcional `posicion` (ej. `N_IZQ`). `app.py` la lee con
`_posicion_de()` para ubicar cada movimiento; si la columna falta o está
vacía, cae al `MAPEO_FIJO` (M1→`O_IZQ`, M2→`O_FTE`, …). El mapeador visual
genera esa columna.

## Código — reglas estrictas
- Comentarios y nombres de variables/funciones **en español**.
- Funciones puras siempre que se pueda. Una función = una responsabilidad.
- El motor (`procesar_censo3.py`) **NO** debe importar `openpyxl` ni
  `pandas.read_excel`.
- Los tipos de vehículo, calles, sentidos y movimientos son **dinámicos**.
  NUNCA hardcodear listas de tipos, calles o movimientos.
- Tipografía de reportes fija: PDF → DejaVu **embebida** (`fonts/`);
  DOCX → **Arial**. NO cambiarla.
- En `requirements.txt`, `plotly`/`reportlab`/`python-docx` van
  **con versión fija** (la exportación de imágenes depende de esa combinación).

## Lógica de negocio (crítica)
- Hora pico = ventana deslizante de 4 bloques de 15 min (1 hora).
- FHP = Volumen HP / (4 × Volumen máximo de 15 min dentro de la HP).
- Tipos excluidos (bicis, peatones) **NO** suman en totales, hora pico ni FHP.
- Los nombres de hojas del Excel son exactos: `DATOS`, `MAPA`, `CONFIG`.
- El croquis calcula Entrada/Salida según la tabla de destinos en
  `croquis_svg.py`. Si modificás esa tabla, verificá los totales con
  `test_croquis.py`.
- Filtro de huérfanos: movimientos en `DATOS` sin entrada en `MAPA` se
  avisan por consola y se ignoran en el croquis agrupado.

## Testing
- App: `streamlit run app.py`, subir un `censo_ejemplo_*.xlsx`, procesar.
- Motor solo: `python procesar_censo3.py censo_ejemplo_cruz.xlsx --verbose`.
- Croquis: `python test_croquis.py` → genera los 3 HTML.
- Reportes: `python test_reportes.py` → `test_reporte.pdf` / `.docx`.
- NaN en gráficos: `python test_graficos_nan.py`.
- NO hay suite de tests automáticos. Verificación manual siempre.

## Boundaries
- **SIEMPRE:** mantené la separación motor/app. El motor no lee Excel.
- **SIEMPRE:** usá nombres en español para variables y comentarios.
- **SIEMPRE:** usá `python` en Windows y `python3` en Linux.
- **PREGUNTAR ANTES DE:** cambiar la estructura del Excel de entrada
  (hojas, columnas).
- **PREGUNTAR ANTES DE:** modificar la tabla de destinos del croquis.
- **PREGUNTAR ANTES DE:** tocar los SVG de `assets/` (afecta los 3 croquis).
- **NUNCA:** commitear archivos `.xlsx` con datos reales (están en
  `.gitignore`).
- **NUNCA:** hardcodear tipos de vehículo, calles o movimientos.
- **NUNCA:** romper la compatibilidad con `censo_ejemplo_cruz.xlsx`,
  `censo_ejemplo_T.xlsx` ni `censo_ejemplo_ruta.xlsx` sin avisar.