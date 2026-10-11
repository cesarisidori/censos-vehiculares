from croquis import dibujar_croquis_cruz

volumenes = {
    "M1": 127, "M2": 45, "M3": 30,
    "M4": 89, "M5": 200, "M6": 55,
    "M7": 40, "M8": 300, "M9": 20,
    "M10": 15, "M11": 150, "M12": 35,
}

fig = dibujar_croquis_cruz(
    volumenes=volumenes,
    nombres_ramas={
        "N": "RP 18 Norte",
        "S": "RP 18 Sur",
        "E": "El Caldén Este",
        "O": "El Caldén Oeste",
    },
    titulo="Croquis — hora pico",
)

fig.write_html("croquis_preview.html")
print("✅ Generado: croquis_preview.html — abrilo en el navegador")