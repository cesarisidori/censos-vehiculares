# AGENTS.md — Procesador de Censos Vehiculares

## Project overview
Aplicación Python + Streamlit para procesar censos de tránsito vehicular.
Lee un Excel con 3 hojas (`DATOS`, `MAPA`, `CONFIG`), calcula hora pico,
FHP, % de pesados, y genera gráficos y croquis de intersección.

**Stack:** Python 3.10+, Streamlit, pandas, openpyxl, plotly.

## Setup commands
- Install deps: `pip install -r requirements.txt`
- Run app: `streamlit run app.py`
- Generate example Excel files (cruz / T / ruta): `python3 crear_ejemplo.py`
- Test croquis (genera HTML): `python test_croquis.py`
- Test reportes (genera PDF y DOCX): `python test_reportes.py`
- Process console (verbose): `python procesar_censo3.py censo_ejemplo.xlsx --verbose`

## Architecture
- `app.py` — Interfaz Streamlit. Punto de entrada. Importa `procesar_censo3`,
  `graficos`, `reportes` y `croquis`.
- `procesar_censo3.py` — Motor de cálculo. NO sabe de Excel, trabaja con DataFrames.
  `procesar()` es el pipeline completo (lo usan la CLI y la app) y acepta
  ruta o buffer (BytesIO).
- `graficos.py` — Figuras Plotly puras (reciben datos, devuelven `Figure`).
  Define `PALETA_DEFAULT`; la app la personaliza con color pickers.
- `reportes.py` — Reportes descargables: PDF (reportlab, DejaVu **embebida**
  desde `fonts/`) y DOCX (python-docx, **Arial**). Convierte figuras a PNG con
  kaleido.
- `croquis.py` — Dibuja el croquis de la intersección en cruz con Plotly.
- `crear_ejemplo.py` — Genera `censo_ejemplo.xlsx` con datos de prueba.
- `test_croquis.py` — Test manual: genera `croquis_preview.html`.
- `test_reportes.py` — Test manual: genera `test_reporte.pdf` y `test_reporte.docx`.
- `fonts/` — DejaVuSans.ttf (+ Bold) para embeber en el PDF.
- `censo_ejemplo_*.xlsx` — 3 ejemplos (cruz/T/ruta, en .gitignore con
  excepción `!censo_ejemplo*.xlsx`, se suben explícitamente).

**Filosofía:** El motor no depende del Excel. Los adaptadores/lectores viven en `app.py`.
Esto permite que Streamlit maneje la UI mientras el motor permanece agnóstico.

## Código — reglas estrictas
- Comentarios y nombres de variables/funciones **en español**.
- Funciones puras siempre que se pueda. Una función = una responsabilidad.
- El motor (`procesar_censo3.py`) **NO** debe importar `openpyxl` ni `pandas.read_excel`.
- Los tipos de vehículo, calles, sentidos y movimientos son **dinámicos**.
  NUNCA hardcodear listas de tipos, calles o movimientos.
- El croquis usa 12 posiciones fijas: `N_IZQ`, `N_FTE`, `N_DER`, `S_IZQ`, `S_FTE`,
  `S_DER`, `E_IZQ`, `E_FTE`, `E_DER`, `O_IZQ`, `O_FTE`, `O_DER`.
- Tipografía de reportes fija: PDF → DejaVu **embebida** (`fonts/`); DOCX → **Arial**.
  NO cambiarla (nada de Calibri, Helvetica ni Segoe UI).
- En `requirements.txt`, `plotly`/`kaleido`/`reportlab`/`python-docx` van **con
  versión fija**: la exportación de imágenes depende de esa combinación exacta.

## Lógica de negocio (crítica)
- Hora pico = ventana deslizante de 4 bloques de 15 min (1 hora).
- FHP = Volumen HP / (4 × Volumen máximo de 15 min dentro de la HP).
- Tipos excluidos (bicis, peatones) **NO** suman en totales, hora pico ni FHP.
- Los nombres de hojas del Excel son exactos: `DATOS`, `MAPA`, `CONFIG`.
- El croquis calcula Entrada/Salida según la tabla de destinos en `croquis.py`.
  Si modificás esa tabla, verificá los totales con `test_croquis.py`.

## Testing
- Para probar la app: `streamlit run app.py`, subir `censo_ejemplo.xlsx`, procesar.
- Para probar el motor solo: `python procesar_censo3.py censo_ejemplo.xlsx --verbose`.
- Para probar el croquis: `python test_croquis.py` y abrir `croquis_preview.html`.
- Para probar los reportes: `python test_reportes.py` → `test_reporte.pdf` / `test_reporte.docx`.
- NO hay suite de tests automáticos. Cualquier cambio debe verificarse manualmente.

## Boundaries
- **SIEMPRE:** mantené la separación motor/app. El motor no lee Excel.
- **SIEMPRE:** usá nombres en español para variables y comentarios.
- **PREGUNTAR ANTES DE:** cambiar la estructura del Excel de entrada (hojas, columnas).
- **PREGUNTAR ANTES DE:** modificar la tabla de destinos del croquis.
- **NUNCA:** commitear archivos `.xlsx` con datos reales (están en `.gitignore`).
- **NUNCA:** hardcodear tipos de vehículo, calles o movimientos.
- **NUNCA:** romper la compatibilidad con `censo_ejemplo.xlsx` sin avisar.