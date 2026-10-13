# Procesador de Censos Vehiculares

Aplicación en Python + Streamlit para procesar censos de tránsito vehicular.

## Características

- Lee censos desde Excel con 3 hojas (DATOS, MAPA, CONFIG).
- Calcula totales por bloque de 15 min, hora pico, FHP.
- Genera resumen agrupado por calle/sentido.
- Calcula % de vehículos pesados.
- Gráficos interactivos (líneas, barras, tortas) con **paleta de colores personalizable**.
- Croquis de intersección en cruz con Entrada/Salida por rama.
- Carga manual de **Fecha, Día, Ubicación, Lugar y Analista** para el reporte.
- Descarga de resultados en **Excel**, **PDF** (con fuente DejaVu embebida)
  y **DOCX** (fuente Arial, se abre en Word y LibreOffice).

## Instalación

```bash
pip install -r requirements.txt
```

> `plotly`, `kaleido`, `reportlab` y `python-docx` van **con versión fija**:
> son los que garantizan que la exportación de imágenes y los reportes
> funcionen igual en cualquier máquina (Windows/Linux).

## Uso

```bash
streamlit run app.py
```

1. Subir el Excel del censo.
2. Ajustar la configuración (tipos a excluir, pesados), los datos del
   reporte (Fecha/Día/Ubicación/Lugar/Analista) y la paleta de colores.
3. Clic en **▶️ Procesar censo**.
4. Descargar Excel / PDF / DOCX desde la sección final.

Las claves `ubicacion`, `lugar` y `analista` de la hoja `CONFIG` precargan
los campos homónimos del reporte (opcional).

## Tests manuales

```bash
python procesar_censo3.py censo_ejemplo.xlsx --verbose   # motor por consola
python test_croquis.py                                   # croquis → croquis_preview.html
python test_reportes.py                                  # reportes → test_reporte.pdf/.docx
```
