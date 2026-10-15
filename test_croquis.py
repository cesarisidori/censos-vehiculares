import croquis_svg

volumenes = {
    "M1": 127, "M2": 45, "M3": 30,
    "M4": 89, "M5": 200, "M6": 55,
    "M7": 40, "M8": 300, "M9": 20,
    "M10": 15, "M11": 150, "M12": 35,
}

# Generar croquis cruz
html_cruz, altura_cruz = croquis_svg.renderizar_svg_cruz(
    volumenes=volumenes,
    mapeo={
        "M1": "N_IZQ", "M2": "N_FTE", "M3": "N_DER",
        "M4": "S_IZQ", "M5": "S_FTE", "M6": "S_DER",
        "M7": "E_IZQ", "M8": "E_FTE", "M9": "E_DER",
        "M10": "O_IZQ", "M11": "O_FTE", "M12": "O_DER",
    },
    nombres_ramas={
        "N": "RP 18 Norte",
        "S": "RP 18 Sur",
        "E": "El Caldén Este",
        "O": "El Caldén Oeste",
    },
)

with open("croquis_cruz.html", "w") as f:
    f.write(html_cruz)
print("Generated: croquis_cruz.html")

# Generar croquis T
html_T, altura_T = croquis_svg.renderizar_svg_T(
    volumenes=volumenes,
    mapeo={
        "M1": "S_IZQ", "M2": "S_FTE", "M3": "S_DER",
        "M4": "O_IZQ", "M5": "O_FTE", "M6": "O_DER",
        "M7": "E_IZQ", "M8": "E_FTE", "M9": "E_DER",
    },
    nombres_ramas={
        "S": "RP 18 Sur",
        "O": "El Caldén Oeste",
        "E": "El Caldén Este",
    },
)

with open("croquis_T.html", "w") as f:
    f.write(html_T)
print("Generated: croquis_T.html")

# Generar croquis ruta
html_ruta, altura_ruta = croquis_svg.renderizar_svg_ruta(
    volumenes=volumenes,
    mapeo={
        "M1": "O_IZQ", "M2": "O_FTE",
    },
    nombres_extremos={
        "O": "El Caldén Oeste",
        "E": "El Caldén Este",
    },
)

with open("croquis_ruta.html", "w") as f:
    f.write(html_ruta)
print("Generated: croquis_ruta.html")