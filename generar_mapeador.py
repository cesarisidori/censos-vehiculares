# -*- coding: utf-8 -*-
"""Genera mapeador_croquis.html autocontenido con los SVG inline."""
import base64
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"


def limpiar_svg(texto: str) -> str:
    texto = re.sub(r"<\?xml[^>]*\?>", "", texto)
    texto = re.sub(r"<!DOCTYPE[^>]*>", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.DOTALL)
    texto = re.sub(r"<sodipodi:namedview\b.*?</sodipodi:namedview>", "",
                   texto, flags=re.DOTALL)
    texto = re.sub(r"<sodipodi:namedview\b[^>]*/>", "", texto, flags=re.DOTALL)
    return texto.strip()


svg_cruz = limpiar_svg((ASSETS / "croquis_cruz.svg").read_text(encoding="utf-8"))
svg_t = limpiar_svg((ASSETS / "croquis_T.svg").read_text(encoding="utf-8"))
svg_t_norte = limpiar_svg(
    (ASSETS / "croquis_T_norte.svg").read_text(encoding="utf-8"))
svg_ruta = limpiar_svg((ASSETS / "croquis_ruta.svg").read_text(encoding="utf-8"))

PLANTILLA = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mapeador de Movimientos → Croquis</title>
<style>
  :root {
    --azul: #1f3a93; --azul2: #2d5bd1; --verde: #1e8e3e;
    --naranja: #f57c00; --gris: #e8eef7; --borde: #c9d3e6;
    --fondo: #f4f6fb;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: "Segoe UI", Arial, sans-serif;
    background: var(--fondo); color: #1c2333;
  }
  header {
    background: linear-gradient(135deg, #1f3a93, #2d5bd1);
    color: #fff; padding: 18px 24px;
  }
  header h1 { margin: 0 0 4px; font-size: 20px; }
  header p { margin: 0; font-size: 13px; opacity: .9; }
  .wrap { max-width: 1200px; margin: 0 auto; padding: 18px 24px 60px; }
  .card {
    background: #fff; border: 1px solid var(--borde); border-radius: 10px;
    padding: 16px 18px; margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(20,40,90,.06);
  }
  .card h2 { margin: 0 0 10px; font-size: 15px; color: var(--azul); }
  label { font-size: 12px; font-weight: 600; color: #45506a; display: block; margin-bottom: 4px; }
  textarea, input[type=text] {
    width: 100%; border: 1px solid var(--borde); border-radius: 7px;
    padding: 8px 10px; font-size: 13px; font-family: inherit;
    background: #fbfcff; color: #1c2333;
  }
  textarea:focus, input:focus { outline: 2px solid #b9c8ee; border-color: var(--azul2); }
  button {
    border: 1px solid var(--borde); background: #fff; color: var(--azul);
    padding: 8px 14px; border-radius: 7px; cursor: pointer; font-size: 13px;
    font-weight: 600;
  }
  button:hover { background: var(--gris); }
  button.primary { background: var(--azul2); color: #fff; border-color: var(--azul2); }
  button.primary:hover { background: #244bb0; }
  button.verde { background: var(--verde); color: #fff; border-color: var(--verde); }
  button.verde:hover { background: #166f30; }
  .fila { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; }
  .fila > div { flex: 1; min-width: 220px; }
  .tipos { display: flex; gap: 8px; flex-wrap: wrap; }
  .tipo-btn.activo { background: var(--azul); color: #fff; border-color: var(--azul); }
  .grid { display: grid; grid-template-columns: minmax(0,1fr) 360px; gap: 16px; align-items: start; }
  @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }

  /* ── Visor del croquis ── */
  #svgbox { position: relative; width: 100%; }
  #svgbox svg { width: 100%; height: auto; display: block; }
  #overlay { position: absolute; inset: 0; pointer-events: none; }
  .hotspot {
    position: absolute; pointer-events: auto; cursor: pointer;
    border: 2px dashed #7d94d6; border-radius: 8px; background: rgba(125,148,214,.10);
    transition: background .12s, border-color .12s;
  }
  .hotspot:hover { background: rgba(45,91,209,.22); }
  .hotspot.asignado { border-style: solid; border-color: var(--verde); background: rgba(30,142,62,.14); }
  .hotspot.sel { border-color: var(--naranja); border-width: 3px; background: rgba(245,124,0,.20); }
  .hotspot .badge {
    position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%);
    background: #fff; border: 1px solid var(--borde); border-radius: 6px;
    padding: 1px 6px; font-size: 11px; font-weight: 700; color: #8a94ad; white-space: nowrap;
  }
  .hotspot.asignado .badge { color: var(--verde); border-color: var(--verde); }
  .hotspot.sel .badge { color: var(--naranja); border-color: var(--naranja); }

  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th, td { border: 1px solid var(--borde); padding: 6px 8px; text-align: left; }
  th { background: var(--gris); font-size: 12px; }
  tr.sel td { background: #fff4e5; }
  select { width: 100%; border: 1px solid var(--borde); border-radius: 6px; padding: 5px 6px; font-size: 13px; background:#fff; }
  .chip { display:inline-block; padding: 1px 7px; border-radius: 20px; font-size: 11px; font-weight:700; }
  .chip.ok { background:#e3f4e7; color: var(--verde); }
  .chip.no { background:#fdeaea; color:#c0392b; }
  pre#preview {
    background: #0f172a; color: #c7f9d0; padding: 12px; border-radius: 8px;
    font-size: 12px; overflow: auto; max-height: 240px; margin: 8px 0 0;
  }
  .aviso { font-size: 12px; color: #6a748c; margin-top: 6px; }
  .pista { font-size: 12px; color:#8a5a00; background:#fff7e6; border:1px solid #ffd591; border-radius:7px; padding:8px 10px; margin-top:10px; }
</style>
</head>
<body>
<header>
  <h1>Mapeador de Movimientos → Croquis</h1>
  <p>Asigná cada movimiento del censo a una flecha del croquis y exportá la hoja MAPA.</p>
</header>

<div class="wrap">

  <div class="card">
    <h2>1 · Tipo de croquis y movimientos</h2>
    <div class="fila">
      <div style="flex:0 0 auto;">
        <label>Tipo de croquis</label>
        <div class="tipos">
          <button class="tipo-btn activo" data-tipo="Cruz" onclick="cargarTipo('Cruz')">Cruz</button>
          <button class="tipo-btn" data-tipo="T" onclick="cargarTipo('T')">T(sur)</button>
          <button class="tipo-btn" data-tipo="T_norte" onclick="cargarTipo('T_norte')">T(norte)</button>
          <button class="tipo-btn" data-tipo="Ruta" onclick="cargarTipo('Ruta')">Ruta</button>
        </div>
      </div>
      <div style="flex:1;">
        <label>Movimientos (uno por línea, o separados por coma)</label>
        <textarea id="movs" rows="3" placeholder="M1&#10;M2&#10;M3"></textarea>
      </div>
      <div style="flex:0 0 auto;">
        <button class="primary" onclick="aplicarMovimientos()">Aplicar movimientos</button>
      </div>
    </div>
    <div class="pista">Click en una flecha/casillero del croquis para seleccionarla, y elegí el movimiento en la tabla de la derecha.</div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>2 · Croquis (click en cada flecha)</h2>
      <div id="svgbox"><div id="overlay"></div></div>
    </div>

    <div class="card">
      <h2>3 · Posiciones</h2>
      <div style="max-height: 60vh; overflow:auto;">
        <table id="tablaPos"><thead><tr><th>Posición</th><th>Movimiento</th></tr></thead><tbody></tbody></table>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>4 · Calle y sentido por rama <span class="aviso">(opcional, se exportan a MAPA)</span></h2>
    <div class="pista">Completá calle y sentido una sola vez por rama: se aplican a todos los movimientos asignados a esa rama.</div>
    <div style="max-height: 40vh; overflow:auto; margin-top:10px;">
      <table id="tablaMov"><thead><tr><th>Rama</th><th>Calle</th><th>Sentido</th><th>Movimientos</th></tr></thead><tbody></tbody></table>
    </div>
    <div id="bloqueSinPos" style="display:none; margin-top:14px;">
      <h3 style="margin:0 0 8px; font-size:13px; color:#8a5a00;">Movimientos sin posición (calle y sentido individual)</h3>
      <table id="tablaSinPos"><thead><tr><th>Movimiento</th><th>Calle</th><th>Sentido</th><th>Estado</th></tr></thead><tbody></tbody></table>
    </div>
    <div class="fila" style="margin-top:12px;">
      <div style="flex:1;">
        <label>Pegar MAPA actual (opcional): movimiento, calle, sentido</label>
        <textarea id="mapaPrev" rows="3" placeholder="M1,Calle Ppal,Este-Oeste&#10;M2,Calle Ppal,Este-Oeste"></textarea>
      </div>
      <div style="flex:0 0 auto;">
        <button onclick="importarMapaPrev()">Importar calles/sentidos</button>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>5 · Exportar hoja MAPA</h2>
    <label style="display:inline-flex; align-items:center; gap:6px; font-weight:500;">
      <input type="checkbox" id="incluirSin" onchange="renderPreview()"> incluir movimientos sin posición
    </label>
    <div class="fila" style="margin-top:10px;">
      <div style="flex:0 0 auto;"><button class="verde" onclick="descargarCSV()">⬇️ Descargar MAPA.csv</button></div>
      <div style="flex:0 0 auto;"><button class="primary" onclick="copiarTSV()">📋 Copiar tabla (con encabezado)</button></div>
      <div style="flex:0 0 auto;"><button onclick="window.print()">🖨️ Imprimir / PDF</button></div>
    </div>
    <div class="aviso">La columna <b>posicion</b> (ej. <code>N_IZQ</code>) es la que app.py lee para ubicar cada movimiento en el croquis.</div>
    <pre id="preview"></pre>
  </div>

</div>

<script>
__SCRIPT_SVG__const POSICIONES = {
  Cruz: ["N_IZQ","N_FTE","N_DER","S_IZQ","S_FTE","S_DER","E_IZQ","E_FTE","E_DER","O_IZQ","O_FTE","O_DER"],
  T:    ["S_IZQ","S_DER","O_FTE","O_DER","E_IZQ","E_FTE"],
  T_norte: ["N_IZQ","N_DER","O_FTE","O_IZQ","E_FTE","E_DER"],
  Ruta: ["O_IZQ","O_FTE"]
};
const ETIQUETA = {
  N_IZQ:"Norte · Izquierda", N_FTE:"Norte · Frente", N_DER:"Norte · Derecha",
  S_IZQ:"Sur · Izquierda",   S_FTE:"Sur · Frente",   S_DER:"Sur · Derecha",
  E_IZQ:"Este · Izquierda",  E_FTE:"Este · Frente",  E_DER:"Este · Derecha",
  O_IZQ:"Oeste · Izquierda", O_FTE:"Oeste · Frente", O_DER:"Oeste · Derecha"
};

let tipo = "Cruz";
let movimientos = [];
let asignacion = {};   // pos -> mov
let calles = {};       // mov -> {calle, sentido}
let posSel = null;
let elementos = {};    // pos -> [svg elements]
let hotspots = {};     // pos -> div

function leerMovimientos() {
  const txt = document.getElementById("movs").value;
  movimientos = [...new Set(txt.split(/[\n,;]+/).map(s => s.trim()).filter(Boolean))];
}

function aplicarMovimientos() {
  leerMovimientos();
  // quitar asignaciones a movimientos que ya no existen
  for (const p in asignacion) if (!movimientos.includes(asignacion[p])) delete asignacion[p];
  renderTablas();
  actualizarBadges();
}

function cargarTipo(t) {
  tipo = t;
  document.querySelectorAll(".tipo-btn").forEach(b => b.classList.toggle("activo", b.dataset.tipo === t));
  const validas = POSICIONES[t];
  for (const p in asignacion) if (!validas.includes(p)) delete asignacion[p];
  if (posSel && !validas.includes(posSel)) posSel = null;
  const box = document.getElementById("svgbox");
  box.innerHTML = '<div id="overlay"></div>' + SVG_SRC[t];
  limpiarPlaceholders(box);
  renderTablas();
  requestAnimationFrame(() => { mapearElementos(); reubicar(); });
}

function limpiarPlaceholders(box) {
  // Oculta los textos de ejemplo del SVG (nombres de movimiento, volúmenes,
  // calles y entradas/salidas). Se usa visibility:hidden (no display:none)
  // para conservar la geometría y que los hotspots sigan ubicándose bien.
  box.querySelectorAll("text").forEach(el => {
    if (/_nombre$|_volumen$|_calle_nombre$|_entrada$|_salida$/.test(el.id || "")) {
      el.style.visibility = "hidden";
    }
  });
}

function mapearElementos() {
  const box = document.getElementById("svgbox");
  elementos = {}; hotspots = {};
  const overlay = document.getElementById("overlay");
  POSICIONES[tipo].forEach(pos => {
    const els = [...box.querySelectorAll('[id="' + pos + '_nombre"],[id="' + pos + '_volumen"]')];
    elementos[pos] = els;
    const div = document.createElement("div");
    div.className = "hotspot";
    div.onclick = () => seleccionar(pos);
    const badge = document.createElement("span");
    badge.className = "badge"; badge.textContent = "+";
    div.appendChild(badge);
    overlay.appendChild(div);
    hotspots[pos] = div;
  });
  actualizarBadges();
}

function reubicar() {
  const box = document.getElementById("svgbox");
  const bb = box.getBoundingClientRect();
  POSICIONES[tipo].forEach(pos => {
    const els = elementos[pos] || [];
    const div = hotspots[pos];
    if (!div) return;
    if (!els.length) { div.style.display = "none"; return; }
    let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
    els.forEach(el => {
      const q = el.getBoundingClientRect();
      l = Math.min(l, q.left - bb.left); t = Math.min(t, q.top - bb.top);
      r = Math.max(r, q.right - bb.left); b = Math.max(b, q.bottom - bb.top);
    });
    const pad = 7;
    div.style.display = "block";
    div.style.left = (l - pad) + "px";
    div.style.top = (t - pad) + "px";
    div.style.width = (r - l + 2 * pad) + "px";
    div.style.height = (b - t + 2 * pad) + "px";
  });
}

function actualizarBadges() {
  POSICIONES[tipo].forEach(pos => {
    const div = hotspots[pos];
    if (!div) return;
    div.classList.toggle("asignado", !!asignacion[pos]);
    div.classList.toggle("sel", pos === posSel);
    div.querySelector(".badge").textContent = asignacion[pos] || "+";
  });
}

function seleccionar(pos) {
  posSel = (posSel === pos) ? null : pos;
  actualizarBadges();
  marcarFila();
}

function marcarFila() {
  document.querySelectorAll("#tablaPos tbody tr").forEach(tr => {
    tr.classList.toggle("sel", tr.dataset.pos === posSel);
  });
  if (posSel) {
    const sel = document.querySelector('#tablaPos select[data-pos="' + posSel + '"]');
    if (sel) sel.focus();
  }
}

function asignar(pos, mov) {
  if (mov) for (const p in asignacion) if (asignacion[p] === mov && p !== pos) delete asignacion[p];
  if (mov) asignacion[pos] = mov; else delete asignacion[pos];
  actualizarBadges();
  refrescarSelects();
  renderPreview();
}

function refrescarSelects() {
  document.querySelectorAll("#tablaPos select").forEach(sel => {
    const pos = sel.dataset.pos;
    sel.innerHTML = opcionesSelect(pos);
    sel.value = asignacion[pos] || "";
    const tr = sel.closest("tr");
    if (tr) tr.classList.toggle("sel", tr.dataset.pos === posSel);
  });
  renderTablaMov();
}

function opcionesSelect(posActual) {
  // Los movimientos ya asignados a otra posición se omiten para no
  // duplicarlos por error. El asignado a esta posición sí se mantiene.
  let html = '<option value="">— (vacío)</option>';
  const usados = Object.values(asignacion);
  movimientos.forEach(m => {
    if (usados.includes(m) && asignacion[posActual] !== m) return;
    html += '<option value="' + esc(m) + '">' + esc(m) + "</option>";
  });
  return html;
}

function renderTablas() {
  const tb = document.querySelector("#tablaPos tbody");
  tb.innerHTML = "";
  POSICIONES[tipo].forEach(pos => {
    const tr = document.createElement("tr");
    tr.dataset.pos = pos;
    const td1 = document.createElement("td"); td1.textContent = ETIQUETA[pos] || pos;
    const td2 = document.createElement("td");
    const sel = document.createElement("select");
    sel.dataset.pos = pos;
    sel.innerHTML = opcionesSelect(pos);
    sel.value = asignacion[pos] || "";
    sel.onchange = () => asignar(pos, sel.value);
    td2.appendChild(sel);
    tr.appendChild(td1); tr.appendChild(td2);
    tb.appendChild(tr);
  });
  renderTablaMov();
  marcarFila();
}

function claveGrupo(pos) {
  // En Cruz/T cada rama (N/S/E/O) agrupa sus 3 posiciones. En Ruta cada
  // extremo es su propia fila: ida y vuelta no comparten sentido.
  return tipo === "Ruta" ? pos : pos.split("_")[0];
}

function etiquetaGrupo(clave) {
  if (tipo === "Ruta") return ETIQUETA[clave] || clave;
  const ref = ETIQUETA[clave + "_IZQ"] || ETIQUETA[clave + "_FTE"]
           || ETIQUETA[clave + "_DER"] || clave;
  return ref.split(" · ")[0];
}

function gruposRama() {
  const grupos = [];
  POSICIONES[tipo].forEach(pos => {
    const clave = claveGrupo(pos);
    let g = grupos.find(x => x.clave === clave);
    if (!g) {
      g = { clave, etiqueta: etiquetaGrupo(clave), posiciones: [], movimientos: [] };
      grupos.push(g);
    }
    g.posiciones.push(pos);
    const m = asignacion[pos];
    if (m && !g.movimientos.includes(m)) g.movimientos.push(m);
  });
  return grupos;
}

function valoresComunes(ms, campo) {
  return [...new Set(ms.map(m => ((calles[m] || {})[campo] || "").trim())
                            .filter(Boolean))];
}

function valorComun(ms, campo) {
  const vals = valoresComunes(ms, campo);
  return vals.length === 1 ? vals[0] : "";
}

function placeholderComun(ms, campo, base) {
  const vals = valoresComunes(ms, campo);
  return vals.length > 1 ? "Mixto: " + vals.join(" / ") : base;
}

function aplicarAGrupo(ms, campo, valor) {
  ms.forEach(m => { (calles[m] = calles[m] || {})[campo] = valor; });
  renderPreview();
}

function inputGrupo(ms, campo, base) {
  const inp = document.createElement("input");
  inp.type = "text";
  inp.value = valorComun(ms, campo);
  inp.placeholder = ms.length ? placeholderComun(ms, campo, base) : "—";
  inp.disabled = !ms.length;
  inp.oninput = () => aplicarAGrupo(ms, campo, inp.value);
  return inp;
}

function renderTablaMov() {
  const tb = document.querySelector("#tablaMov tbody");
  tb.innerHTML = "";
  if (!movimientos.length) {
    tb.innerHTML = '<tr><td colspan="4" class="aviso">Cargá movimientos arriba.</td></tr>';
    renderTablaSinPos([]);
    return;
  }
  const usados = new Set(Object.values(asignacion));
  const sinPos = movimientos.filter(m => !usados.has(m));
  gruposRama().forEach(g => {
    const tr = document.createElement("tr");
    const tdR = document.createElement("td");
    tdR.innerHTML = "<b>" + esc(g.etiqueta) + "</b>"
                  + '<div class="aviso">' + esc(g.posiciones.join(" · ")) + "</div>";
    const tdC = document.createElement("td"); tdC.appendChild(inputGrupo(g.movimientos, "calle", "Calle"));
    const tdS = document.createElement("td"); tdS.appendChild(inputGrupo(g.movimientos, "sentido", "Sentido"));
    const tdM = document.createElement("td");
    tdM.textContent = g.movimientos.length ? g.movimientos.join(", ") : "—";
    tr.append(tdR, tdC, tdS, tdM);
    tb.appendChild(tr);
  });
  renderTablaSinPos(sinPos);
}

function renderTablaSinPos(sinPos) {
  const cont = document.getElementById("bloqueSinPos");
  const tb = document.querySelector("#tablaSinPos tbody");
  tb.innerHTML = "";
  cont.style.display = sinPos.length ? "block" : "none";
  sinPos.forEach(m => {
    const tr = document.createElement("tr");
    const c = calles[m] || {};
    const tdM = document.createElement("td"); tdM.innerHTML = "<b>" + esc(m) + "</b>";
    const tdC = document.createElement("td"); const inC = document.createElement("input"); inC.type = "text"; inC.value = c.calle || ""; inC.placeholder = "Calle"; inC.oninput = () => { (calles[m] = calles[m] || {}).calle = inC.value; renderPreview(); };
    const tdS = document.createElement("td"); const inS = document.createElement("input"); inS.type = "text"; inS.value = c.sentido || ""; inS.placeholder = "Sentido"; inS.oninput = () => { (calles[m] = calles[m] || {}).sentido = inS.value; renderPreview(); };
    const tdE = document.createElement("td"); tdE.innerHTML = '<span class="chip no">sin flecha</span>';
    tdC.appendChild(inC); tdS.appendChild(inS);
    tr.append(tdM, tdC, tdS, tdE);
    tb.appendChild(tr);
  });
}

function importarMapaPrev() {
  const txt = document.getElementById("mapaPrev").value;
  txt.split(/\n/).forEach(line => {
    const partes = line.split(/[\t,;]+/).map(s => s.trim());
    if (partes.length < 1 || !partes[0]) return;
    const m = partes[0];
    calles[m] = { calle: partes[1] || "", sentido: partes[2] || "" };
    if (!movimientos.includes(m)) movimientos.push(m);
  });
  document.getElementById("movs").value = movimientos.join("\n");
  renderTablas();
  renderPreview();
}

function filasExport() {
  const incluirSin = document.getElementById("incluirSin").checked;
  const rows = [];
  POSICIONES[tipo].forEach(pos => {
    const m = asignacion[pos]; if (!m) return;
    const c = calles[m] || {};
    rows.push([m, c.calle || "", c.sentido || "", pos]);
  });
  if (incluirSin) {
    const usados = Object.values(asignacion);
    movimientos.forEach(m => {
      if (usados.includes(m)) return;
      const c = calles[m] || {};
      rows.push([m, c.calle || "", c.sentido || "", ""]);
    });
  }
  return rows;
}

function renderPreview() {
  const rows = filasExport();
  const enc = ["movimiento", "calle", "sentido", "posicion"];
  const txt = [enc.join(";")].concat(rows.map(r => r.join(";"))).join("\n");
  document.getElementById("preview").textContent = rows.length ? txt : "(sin filas para exportar)";
}

function descargarCSV() {
  const rows = filasExport();
  if (!rows.length) { alert("No hay movimientos asignados para exportar."); return; }
  const enc = ["movimiento", "calle", "sentido", "posicion"];
  const csv = "\uFEFF" + [enc].concat(rows).map(r => r.map(csvCampo).join(";")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "MAPA.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

function copiarTSV() {
  const rows = filasExport();
  if (!rows.length) { alert("No hay movimientos asignados para exportar."); return; }
  const enc = ["movimiento", "calle", "sentido", "posicion"];
  const tsv = [enc].concat(rows).map(r => r.join("\t")).join("\n");
  const ok = () => alert("Tabla copiada. Pegala en la hoja MAPA (celda A1).");
  const fallback = () => {
    const ta = document.createElement("textarea");
    ta.value = tsv; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); ok(); }
    catch (e) { alert("No se pudo copiar. Usá 'Descargar MAPA.csv'."); }
    document.body.removeChild(ta);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(tsv).then(ok, fallback);
  } else fallback();
}

function csvCampo(v) {
  v = String(v == null ? "" : v);
  return /[",;\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
}
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

// ── init ──
document.getElementById("movs").value = Array.from({length: 12}, (_, i) => "M" + (i + 1)).join("\n");
leerMovimientos();
cargarTipo("Cruz");
aplicarMovimientos();
window.addEventListener("resize", reubicar);
if (window.ResizeObserver) new ResizeObserver(reubicar).observe(document.getElementById("svgbox"));
renderPreview();
</script>
</body>
</html>
"""

def b64(texto: str) -> str:
    return base64.b64encode(texto.encode("utf-8")).decode("ascii")


script_svg = (
    "function b64utf8(b64) {\n"
    "  const bin = atob(b64);\n"
    "  const bytes = Uint8Array.from(bin, c => c.charCodeAt(0));\n"
    "  return new TextDecoder('utf-8').decode(bytes);\n"
    "}\n"
    "const SVG_SRC = {\n"
    f"  Cruz: b64utf8('{b64(svg_cruz)}'),\n"
    f"  T: b64utf8('{b64(svg_t)}'),\n"
    f"  T_norte: b64utf8('{b64(svg_t_norte)}'),\n"
    f"  Ruta: b64utf8('{b64(svg_ruta)}')\n"
    "};\n"
)

html = PLANTILLA.replace("__SCRIPT_SVG__", script_svg)

salida = BASE / "mapeador_croquis.html"
salida.write_text(html, encoding="utf-8")
print("Generado:", salida, len(html), "bytes")
