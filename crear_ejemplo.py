"""
crear_ejemplo.py
----------------
Genera 'censo_ejemplo.xlsx' con el tercer formato ya convertido
a la plantilla canónica (hora_inicio, hora_fin, tipo_vehiculo, M1..M4).
"""
import pandas as pd

# Datos del tercer formato (fila TOTAL ya eliminada)
datos = [
    # hora_ini, hora_fin, tipo,          M1, M2, M3, M4
    ("07:00", "07:15", "Auto/cam.",       62,  5, 51,  3),
    ("07:00", "07:15", "Motos",            4,  0,  7,  0),
    ("07:00", "07:15", "Colectivos",       5,  0,  4,  0),
    ("07:00", "07:15", "Cam. Sin acoplado",1,  0,  1,  0),
    ("07:00", "07:15", "Cam. CON acoplado",0,  0,  1,  0),
    ("07:00", "07:15", "Semirremolque",    4,  0,  4,  0),
    ("07:00", "07:15", "Bicicleta",        1,  0,  4,  0),

    ("07:15", "07:30", "Auto/cam.",       52,  5, 60,  2),
    ("07:15", "07:30", "Motos",            6,  1,  8,  0),
    ("07:15", "07:30", "Colectivos",       4,  0,  2,  0),
    ("07:15", "07:30", "Cam. Sin acoplado",4,  0,  3,  0),
    ("07:15", "07:30", "Cam. CON acoplado",0,  0,  0,  0),
    ("07:15", "07:30", "Semirremolque",    1,  0,  2,  0),
    ("07:15", "07:30", "Bicicleta",        7,  1,  6,  0),

    ("07:30", "07:45", "Auto/cam.",       68,  6, 84,  2),
    ("07:30", "07:45", "Motos",           14,  1, 15,  0),
    ("07:30", "07:45", "Colectivos",       3,  0,  4,  0),
    ("07:30", "07:45", "Cam. Sin acoplado",5,  0,  5,  0),
    ("07:30", "07:45", "Cam. CON acoplado",0,  0,  2,  0),
    ("07:30", "07:45", "Semirremolque",    0,  0,  4,  0),
    ("07:30", "07:45", "Bicicleta",        2,  0,  4,  0),

    ("07:45", "08:00", "Auto/cam.",      108, 10, 89,  2),
    ("07:45", "08:00", "Motos",           14,  0, 25,  0),
    ("07:45", "08:00", "Colectivos",       9,  0,  6,  0),
    ("07:45", "08:00", "Cam. Sin acoplado",1,  0,  7,  0),
    ("07:45", "08:00", "Cam. CON acoplado",0,  0,  0,  0),
    ("07:45", "08:00", "Semirremolque",    2,  0,  1,  0),
    ("07:45", "08:00", "Bicicleta",        1,  0,  3,  0),

    ("08:00", "08:15", "Auto/cam.",       87,  7, 90,  9),
    ("08:00", "08:15", "Motos",           12,  0, 18,  0),
    ("08:00", "08:15", "Colectivos",       3,  0,  2,  0),
    ("08:00", "08:15", "Cam. Sin acoplado",2,  0,  4,  0),
    ("08:00", "08:15", "Cam. CON acoplado",0,  0,  0,  0),
    ("08:00", "08:15", "Semirremolque",    3,  0,  1,  0),
    ("08:00", "08:15", "Bicicleta",        5,  0,  3,  0),

    ("08:15", "08:30", "Auto/cam.",       79, 12, 89,  6),
    ("08:15", "08:30", "Motos",            2,  0, 14,  0),
    ("08:15", "08:30", "Colectivos",       0,  0,  3,  0),
    ("08:15", "08:30", "Cam. Sin acoplado",3,  0,  2,  0),
    ("08:15", "08:30", "Cam. CON acoplado",1,  0,  1,  0),
    ("08:15", "08:30", "Semirremolque",    2,  0,  7,  0),
    ("08:15", "08:30", "Bicicleta",        0,  0,  5,  0),

    ("08:30", "08:45", "Auto/cam.",       74, 10, 75,  2),
    ("08:30", "08:45", "Motos",            3,  0, 10,  0),
    ("08:30", "08:45", "Colectivos",       6,  0,  3,  0),
    ("08:30", "08:45", "Cam. Sin acoplado",8,  0,  2,  0),
    ("08:30", "08:45", "Cam. CON acoplado",0,  0,  1,  0),
    ("08:30", "08:45", "Semirremolque",    1,  0,  4,  0),
    ("08:30", "08:45", "Bicicleta",        0,  0,  2,  0),

    ("08:45", "09:00", "Auto/cam.",       62, 12, 93,  2),
    ("08:45", "09:00", "Motos",            6,  0,  7,  0),
    ("08:45", "09:00", "Colectivos",       3,  0,  3,  0),
    ("08:45", "09:00", "Cam. Sin acoplado",2,  0,  1,  0),
    ("08:45", "09:00", "Cam. CON acoplado",1,  0,  0,  0),
    ("08:45", "09:00", "Semirremolque",    2,  0,  4,  0),
    ("08:45", "09:00", "Bicicleta",        1,  0,  2,  0),

    ("09:00", "09:15", "Auto/cam.",       82, 10, 76,  2),
    ("09:00", "09:15", "Motos",            4,  0, 10,  0),
    ("09:00", "09:15", "Colectivos",       4,  0,  4,  0),
    ("09:00", "09:15", "Cam. Sin acoplado",3,  0,  4,  0),
    ("09:00", "09:15", "Cam. CON acoplado",1,  0,  0,  0),
    ("09:00", "09:15", "Semirremolque",    6,  0,  6,  0),
    ("09:00", "09:15", "Bicicleta",        0,  0,  2,  0),
]

df = pd.DataFrame(datos, columns=[
    "hora_inicio", "hora_fin", "tipo_vehiculo", "M1", "M2", "M3", "M4"
])

# Guardar
df.to_excel("censo_ejemplo.xlsx", index=False)
print(f"✅ Generado: censo_ejemplo.xlsx  ({len(df)} filas)")