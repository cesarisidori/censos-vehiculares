# Procesador de Censos Vehiculares

Aplicación en Python + Streamlit para procesar censos de tránsito vehicular.

## Características

- Lee censos desde Excel con 3 hojas (DATOS, MAPA, CONFIG).
- Calcula totales por bloque de 15 min, hora pico, FHP.
- Genera resumen agrupado por calle/sentido.
- Calcula % de vehículos pesados.
- Gráficos interactivos (líneas, barras, tortas).
- Croquis de intersección en cruz con Entrada/Salida por rama.

## Instalación

```bash
pip install -r requirements.txt