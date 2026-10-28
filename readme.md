# Procesador de Censos Vehiculares (en construccion)

Aplicación en Python + Streamlit para procesar censos de tránsito vehicular.

## Características

- Lee censos desde Excel con 3 hojas (DATOS, MAPA, CONFIG).
- Calcula totales por bloque de 15 min, hora pico, FHP.
- Genera resumen agrupado por calle/sentido.
- Calcula % de vehículos pesados.
- Gráficos interactivos (líneas, barras, tortas) con **paleta de colores**:
  combinaciones predefinidas (estilo Excel, pastel, vibrante, etc.) y
  edición manual opcional de cada serie.
- Croquis de la intersección (**Cruz**, **T(sur)**, **T(norte)** o **Ruta**
  — el tipo se infiere del MAPA y es sobrescribible) con Entrada/Salida por
  rama, y descarga/copia de cada croquis en **SVG** o **PNG**.
- Posición de cada movimiento en el croquis vía la columna `posicion`
  de la hoja `MAPA`, generada con `mapeador_croquis.html`. Si falta, se
  usa el mapeo fijo (`M1`→`O_IZQ`, `M2`→`O_FTE`, …).
- La app trae el **mapeo de movimientos integrado**: asignás cada
  movimiento a una flecha del croquis y le ponés calle/sentido por rama,
  sin editar la hoja `MAPA` ni usar el mapeador HTML.
- El MAPA es la fuente de verdad: los movimientos de DATOS sin fila en
  MAPA se ignoran en todos los cálculos y gráficos.
- Tablas **Origen / Destino** bajo cada croquis (PDF), en el DOCX y en
  pantalla, con totales por fila/columna.
- Carga manual de **Fecha, Día, Ubicación, Lugar y Analista** para el reporte.
- Descarga de resultados en **Excel** (con **gráficos nativos**, editables en
  Excel/OnlyOffice), **PDF** (con fuente DejaVu embebida) y **DOCX** (fuente
  Arial, se abre en Word y LibreOffice).

## Instalación

```bash
pip install -r requirements.txt
```

> `plotly`, `plotly-mirage`, `reportlab` y `python-docx` van **con versión fija**:
> son los que garantizan que la exportación de imágenes y los reportes
> funcionen igual en cualquier máquina (Windows/Linux).

## Uso

```bash
streamlit run app.py
```

1. Subir el Excel del censo.
2. Se procesa automáticamente. Ajustá el **mapeo de movimientos** (si el
   Excel no trae hoja `MAPA`), la configuración (tipos a excluir, pesados),
   los datos del reporte (Fecha/Día/Ubicación/Lugar/Analista) y la paleta:
   se reprocesa solo.
3. Descargar Excel / PDF / DOCX desde la pestaña **Descargas** (el PDF y
   el DOCX se arman al pedirlos).

Las claves `ubicacion`, `lugar` y `analista` de la hoja `CONFIG` precargan
los campos homónimos del reporte (opcional).

## Tests

```bash
pip install -r requirements-dev.txt
python3 -m pytest tests/            # o: python3 tests/test_motor.py
```

Cubren hora pico, FHP, exclusión de tipos, total O-D y la exportación del
Excel con gráficos nativos.

## Tests manuales

```bash
python3 crear_ejemplo.py                                    # regenera los 3 ejemplos
python3 procesar_censo3.py censo_ejemplo_cruz.xlsx --verbose   # motor por consola
python3 test_croquis.py                                    # croquis → croquis_preview.html
python3 test_reportes.py                                   # reportes → test_reporte.pdf/.docx
```

Hay 3 archivos de ejemplo:
`censo_ejemplo_cruz.xlsx` (12 movimientos, 4 ramas),
`censo_ejemplo_T.xlsx` (9 movimientos, T(sur), sin rama Norte) y
`censo_ejemplo_ruta.xlsx` (2 movimientos, ida y vuelta).
La variante T(norte) se puede probar con `test_croquis.py`.
