"use strict";
// Electrode design page. Uses helpers from app.js ($, $$, api, esc, toast, load, save, state, SLOTS).

(() => {
  const TYPE_LABELS = {
    multi_pad: "Multi-pad (rectangular pads)",
    j_gap: "J-gap (one electrode pair)",
    annular: "Annular (cylindrical faces)",
  };

  const electrode = (over = {}) => ({
    material_id: "Ir", shape: "rect", width: 1.5, height: 1.5, diameter: 1.5, length: 2.0,
    thickness: 0.6, carrier_id: "Alloy-600", cu_core: false, ...over,
  });
  const DEFAULTS = [
    { on: true, design: { name: "J-gap Ir / Pt-Ir", type: "j_gap", gap: 0.3, n_ground: 1,
      center: electrode({ material_id: "Ir-2Rh", shape: "round", diameter: 2.0, thickness: 0.8, cu_core: true }),
      ground: electrode({ material_id: "Pt-10Ir", shape: "rect", width: 2.5, height: 2.5, thickness: 0.8 }) } },
    { on: true, design: { name: "Multi-pad 4×", type: "multi_pad", gap: 0.3, n_ground: 4,
      center: electrode({ material_id: "Ir-10Rh", width: 1.5, height: 2.0, thickness: 0.6, cu_core: true }),
      ground: electrode({ material_id: "Ir-10Rh", width: 1.5, height: 2.0, thickness: 0.6 }) } },
    { on: true, design: { name: "Annular Ir / Pt-Ir", type: "annular", gap: 0.3, n_ground: 1,
      center: electrode({ material_id: "Ir", diameter: 4.0, length: 3.0, thickness: 0.5, cu_core: true }),
      ground: electrode({ material_id: "Pt-10Ir", length: 3.0, thickness: 0.5 }) } },
    { on: false, design: { name: "J-gap rectangular", type: "j_gap", gap: 0.3, n_ground: 1,
      center: electrode({ width: 2.0, height: 2.0 }), ground: electrode({ width: 2.0, height: 2.0 }) } },
  ];

  const d = {
    slots: load("spd.designSlots", null) || structuredClone(DEFAULTS),
    collapsed: new Set(load("spd.designCollapsed", [])),
    diffOnly: false,
    results: {}, // slot index -> result
    library: [],
    bound: false,
  };
  const persist = () => save("spd.designSlots", d.slots);

  // ------------------------------------------------------------ relevance of fields
  function fieldApplies(design, side, key) {
    const e = design[side];
    switch (design.type) {
      case "multi_pad": return ["width", "height", "thickness"].includes(key);
      case "j_gap":
        if (key === "shape" || key === "thickness") return true;
        return e.shape === "round" ? key === "diameter" : ["width", "height"].includes(key);
      case "annular":
        if (side === "center") return ["diameter", "length", "thickness"].includes(key);
        return ["length", "thickness"].includes(key);
      default: return false;
    }
  }

  // ------------------------------------------------------------ row specification
  const fmtNum = (v, dec = 3) => (v === null || v === undefined ? "–"
    : v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec }));

  function electrodeRows(side) {
    const label = side === "center" ? "Centre electrode" : "Ground electrode";
    const dimLabel = (key, design) => {
      if (design?.type === "annular" && key === "diameter") return "Outer diameter (sleeve)";
      if (design?.type === "annular" && key === "thickness") return "Precious metal thickness (radial)";
      return null;
    };
    return [
      { group: label, label: "Precious metal", unit: "", input: "material", side, key: "material_id", applies: () => true },
      { group: label, label: "Pad shape", unit: "", input: "shape", side, key: "shape",
        applies: (x) => x.type === "j_gap" },
      { group: label, label: "Width", unit: "mm", input: "number", side, key: "width", applies: (x) => fieldApplies(x, side, "width") },
      { group: label, label: "Height", unit: "mm", input: "number", side, key: "height", applies: (x) => fieldApplies(x, side, "height") },
      { group: label, label: "Diameter", unit: "mm", input: "number", side, key: "diameter", dynLabel: dimLabel,
        applies: (x) => fieldApplies(x, side, "diameter") },
      { group: label, label: "Axial length", unit: "mm", input: "number", side, key: "length", applies: (x) => fieldApplies(x, side, "length") },
      { group: label, label: "Precious metal thickness", unit: "mm", input: "number", side, key: "thickness", dynLabel: dimLabel,
        applies: () => true },
      { group: label, label: "Carrier material", unit: "", input: "carrier", side, key: "carrier_id", applies: () => true },
      { group: label, label: "Cu core", unit: "", input: "check", side, key: "cu_core", applies: () => true },
    ];
  }

  function resultRows() {
    const per = (side, key, label, unit, dec, best) => ({ group: "Results", label, unit, best,
      value: (r) => r?.[side]?.[key], dec });
    return [
      { group: "Results", label: "Number of gaps", unit: "–", value: (r) => r?.n_gaps, dec: 0 },
      per("center", "face_area", "Facing area per gap – centre", "mm²", 3),
      per("ground", "face_area", "Facing area per gap – ground", "mm²", 3),
      { group: "Results", label: "Common (wear) area per gap", unit: "mm²", value: (r) => r?.common_area, dec: 3 },
      { group: "Results", label: "Total wear area", unit: "mm²", value: (r) => r?.total_wear_area, dec: 3, best: "higher" },
      { group: "Results", label: "Ground ring inner diameter", unit: "mm", value: (r) => r?.ground_inner_diameter, dec: 3 },
      per("center", "pm_volume", "Precious metal volume – centre", "mm³", 3),
      per("ground", "pm_volume", "Precious metal volume – ground", "mm³", 3),
      per("center", "wearable_volume", "Wearable volume – centre", "mm³", 3, "higher"),
      per("ground", "wearable_volume", "Wearable volume – ground", "mm³", 3, "higher"),
      per("center", "pm_mass", "Precious metal mass – centre", "mg", 1),
      per("ground", "pm_mass", "Precious metal mass – ground", "mg", 1),
      { group: "Results", label: "Precious metal mass – plug", unit: "mg", value: (r) => r?.pm_mass, dec: 1 },
      per("center", "pm_cost", "Precious metal cost – centre", "USD", 2),
      per("ground", "pm_cost", "Precious metal cost – ground", "USD", 2),
      { group: "Results", label: "Precious metal cost – plug", unit: "USD", value: (r) => r?.pm_cost, dec: 2, best: "lower" },
    ];
  }

  const GENERAL_ROWS = [
    { group: "General", label: "Spark plug type", unit: "", input: "type", key: "type", applies: () => true },
    { group: "General", label: "Initial gap", unit: "mm", input: "number", key: "gap", applies: () => true },
    { group: "General", label: "Number of ground electrodes", unit: "–", input: "int", key: "n_ground",
      applies: (x) => x.type === "multi_pad" },
  ];
  const GROUPS = ["General", "Centre electrode", "Ground electrode", "Results"];

  // ------------------------------------------------------------ helpers
  const active = () => d.slots.map((s, i) => ({ ...s, i, letter: SLOTS[i] })).filter((s) => s.on);
  function materialSelect(selected, category) {
    const mats = state.materials.filter((m) => m.categories.includes(category) || m.id === selected);
    return mats.map((m) => `<option value="${esc(m.id)}" ${m.id === selected ? "selected" : ""}>${esc(m.name)}</option>`).join("");
  }
  const getVal = (design, row) => (row.side ? design[row.side][row.key] : design[row.key]);
  function setVal(design, row, value) {
    if (row.side) design[row.side][row.key] = value; else design[row.key] = value;
  }

  // ------------------------------------------------------------ evaluation
  let evalTimer = null;
  function scheduleEvaluate() { clearTimeout(evalTimer); evalTimer = setTimeout(evaluateAll, 120); }
  async function evaluateAll() {
    const slots = active();
    if (!slots.length) { d.results = {}; renderTable(); renderSketches(); return; }
    try {
      const out = await api("/api/designs/evaluate", { method: "POST", body: slots.map((s) => s.design) });
      d.results = {};
      out.forEach((o, k) => { d.results[slots[k].i] = { ok: true, ...o.result }; });
    } catch (err) {
      // evaluate one by one to find the invalid variant
      d.results = {};
      for (const s of slots) {
        try {
          const [o] = await api("/api/designs/evaluate", { method: "POST", body: [s.design] });
          d.results[s.i] = { ok: true, ...o.result };
        } catch (e) { d.results[s.i] = { ok: false, error: e.message }; }
      }
    }
    renderTable();
    renderSketches();
  }

  // ------------------------------------------------------------ slots
  function renderSlots() {
    $("#designSlots").innerHTML = d.slots.map((s, i) => {
      const L = SLOTS[i];
      return `<div class="slot ${s.on ? "" : "off"}" style="--slot-color: var(--slot-${L})">
        <div class="slot-top">
          <input type="checkbox" data-d-on="${i}" ${s.on ? "checked" : ""} aria-label="Show ${L}">
          <span>${L}</span><span class="swatch"></span>
          <input class="slot-name" data-d-name="${i}" value="${esc(s.design.name)}" maxlength="80" aria-label="Name ${L}">
        </div>
        <div class="slot-row">
          <select data-d-type="${i}" aria-label="Type ${L}">
            ${Object.entries(TYPE_LABELS).map(([k, v]) => `<option value="${k}" ${k === s.design.type ? "selected" : ""}>${v}</option>`).join("")}
          </select>
        </div>
        <div class="slot-row">
          <select data-d-lib="${i}" aria-label="Load ${L} from library">
            <option value="">Load from library…</option>
            ${d.library.map((x) => `<option value="${esc(x.id)}">${esc(x.name)}</option>`).join("")}
          </select>
          <button class="icon-btn" data-d-save="${i}" title="Save to library">⤓</button>
          <button class="icon-btn" data-d-reset="${i}" title="Reset to example">↺</button>
        </div>
      </div>`;
    }).join("");
    $$("[data-d-on]").forEach((el) => el.addEventListener("change", () => {
      d.slots[+el.dataset.dOn].on = el.checked; persist(); renderSlots(); evaluateAll();
    }));
    $$("[data-d-name]").forEach((el) => el.addEventListener("change", () => {
      const s = d.slots[+el.dataset.dName];
      const name = el.value.trim() || "Design";
      if (s.design.id && name !== s.design.name) delete s.design.id; // renamed -> saved as a new design
      s.design.name = name; persist(); renderTable(); renderSketches(); updateLetters();
    }));
    $$("[data-d-type]").forEach((el) => el.addEventListener("change", () => {
      const s = d.slots[+el.dataset.dType];
      s.design.type = el.value;
      if (el.value === "multi_pad") { s.design.center.shape = "rect"; s.design.ground.shape = "rect"; }
      persist(); evaluateAll();
    }));
    $$("[data-d-lib]").forEach((el) => el.addEventListener("change", () => {
      const x = d.library.find((y) => y.id === el.value);
      if (!x) return;
      d.slots[+el.dataset.dLib] = { on: true, design: structuredClone(x) };
      persist(); renderSlots(); evaluateAll(); toast(`Loaded "${x.name}" into ${SLOTS[+el.dataset.dLib]}.`);
    }));
    $$("[data-d-save]").forEach((el) => el.addEventListener("click", () => saveToLibrary(+el.dataset.dSave)));
    $$("[data-d-reset]").forEach((el) => el.addEventListener("click", () => {
      const i = +el.dataset.dReset;
      if (!confirm(`Reset ${SLOTS[i]} to the example design?`)) return;
      d.slots[i] = structuredClone(DEFAULTS[i]); d.slots[i].on = true; persist(); renderSlots(); evaluateAll();
    }));
    updateLetters();
  }
  function updateLetters() {
    $("#dSlotLetters").textContent = active().map((s) => s.letter).join(" / ");
  }

  async function saveToLibrary(i) {
    const s = d.slots[i];
    const r = d.results[i];
    if (r && !r.ok) { toast(`Cannot save: ${r.error}`); return; }
    try {
      const stored = await api("/api/designs", { method: "POST", body: s.design });
      s.design.id = stored.id; persist();
      await loadLibrary(); renderSlots();
      toast(`Saved "${stored.name}" to the library.`);
    } catch (err) { toast(`Error: ${err.message}`); }
  }
  async function loadLibrary() { d.library = await api("/api/designs"); }

  async function openLibrary() {
    await loadLibrary();
    $("#libraryTable").innerHTML = d.library.length
      ? `<thead><tr><th>Name</th><th>Type</th><th class="num">Gap [mm]</th><th>Centre</th><th>Ground</th><th></th></tr></thead><tbody>`
        + d.library.map((x) => `<tr><td><b>${esc(x.name)}</b></td><td>${esc(TYPE_LABELS[x.type])}</td>
          <td class="num">${fmtNum(x.gap, 2)}</td><td>${esc(x.center.material_id)}</td><td>${esc(x.ground.material_id)}</td>
          <td class="actions"><button type="button" class="btn small outline danger" data-lib-del="${esc(x.id)}">Delete</button></td></tr>`).join("")
        + "</tbody>"
      : `<tbody><tr><td class="hint">No saved designs yet. Use ⤓ on a variant to save it.</td></tr></tbody>`;
    $$("[data-lib-del]").forEach((b) => b.addEventListener("click", async () => {
      if (!confirm("Delete this design from the library?")) return;
      await api(`/api/designs/${encodeURIComponent(b.dataset.libDel)}`, { method: "DELETE" });
      d.slots.forEach((s) => { if (s.design.id === b.dataset.libDel) delete s.design.id; });
      persist(); await openLibrary(); renderSlots();
    }));
    if (!$("#libraryDialog").open) $("#libraryDialog").showModal();
  }

  // ------------------------------------------------------------ table
  function inputCell(s, row) {
    const design = s.design;
    if (row.applies && !row.applies(design)) return `<td><div class="val na">–</div></td>`;
    const v = getVal(design, row);
    const attrs = `data-cell="${s.i}" data-side="${row.side || ""}" data-key="${row.key}" data-input="${row.input}"`;
    switch (row.input) {
      case "number":
        return `<td><input class="cell-input" type="number" step="0.01" min="0.001" value="${v}" ${attrs}></td>`;
      case "int":
        return `<td><input class="cell-input" type="number" step="1" min="1" max="12" value="${v}" ${attrs}></td>`;
      case "type":
        return `<td><select class="cell-input" ${attrs}>${Object.entries(TYPE_LABELS).map(([k, t]) => `<option value="${k}" ${k === v ? "selected" : ""}>${t}</option>`).join("")}</select></td>`;
      case "shape":
        return `<td><select class="cell-input" ${attrs}><option value="round" ${v === "round" ? "selected" : ""}>round</option><option value="rect" ${v === "rect" ? "selected" : ""}>rectangular</option></select></td>`;
      case "material":
        return `<td><select class="cell-input" ${attrs}>${materialSelect(v, "precious")}</select></td>`;
      case "carrier":
        return `<td><select class="cell-input" ${attrs}><option value="">– none –</option>${materialSelect(v, "carrier")}</select></td>`;
      case "check":
        return `<td><div class="cell-check"><input type="checkbox" ${v ? "checked" : ""} ${attrs}></div></td>`;
      default: return "<td></td>";
    }
  }

  function bestOf(row, slots) {
    if (!row.best || slots.length < 2) return -1;
    let best = -1; let bv = null;
    slots.forEach((s, k) => {
      const v = row.value(d.results[s.i]);
      if (v === null || v === undefined) return;
      if (bv === null || (row.best === "higher" ? v > bv : v < bv)) { bv = v; best = k; }
    });
    return best;
  }

  function renderTable() {
    const slots = active();
    if (!slots.length) { $("#designTable").innerHTML = `<tbody><tr><td class="hint">Activate at least one variant.</td></tr></tbody>`; return; }
    let html = `<thead><tr><th>Parameter</th>${slots.map((s) => `<th class="slot-col" style="color: var(--slot-${s.letter})">${s.letter}</th>`).join("")}</tr></thead><tbody>`;
    let diffCount = 0;
    const inputRows = [...GENERAL_ROWS, ...electrodeRows("center"), ...electrodeRows("ground")];
    for (const group of GROUPS) {
      const rows = [];
      if (group !== "Results") {
        for (const row of inputRows.filter((r) => r.group === group)) {
          const shown = slots.map((s) => (row.applies(s.design) ? JSON.stringify(getVal(s.design, row)) : "–"));
          const differs = new Set(shown).size > 1;
          if (differs) diffCount++;
          if (d.diffOnly && !differs) continue;
          if (slots.every((s) => !row.applies(s.design))) continue;
          const label = slots.length === 1 && row.dynLabel ? (row.dynLabel(row.key, slots[0].design) || row.label) : row.label;
          rows.push(`<tr><td class="label">${esc(label)}${row.unit ? ` <span class="unit">[${esc(row.unit)}]</span>` : ""}</td>
            ${slots.map((s) => inputCell(s, row)).join("")}</tr>`);
        }
      } else {
        for (const row of resultRows()) {
          const vals = slots.map((s) => row.value(d.results[s.i]));
          if (vals.every((v) => v === null || v === undefined)) continue;
          const shown = vals.map((v) => fmtNum(v, row.dec));
          const differs = new Set(shown).size > 1;
          if (differs) diffCount++;
          if (d.diffOnly && !differs) continue;
          const best = bestOf(row, slots);
          rows.push(`<tr><td class="label">${esc(row.label)} <span class="unit">[${esc(row.unit)}]</span></td>
            ${shown.map((v, k) => `<td><div class="val result ${v === "–" ? "empty" : ""} ${k === best ? "best" : ""}">${v}</div></td>`).join("")}</tr>`);
        }
        const notes = slots.map((s) => {
          const r = d.results[s.i];
          if (!r) return "";
          return r.ok ? r.warnings.join("<br>") : `Invalid input: ${esc(r.error)}`;
        });
        if (notes.some(Boolean)) {
          rows.push(`<tr><td class="label">Notes</td>${notes.map((n) => `<td><div class="val warning">${n || "–"}</div></td>`).join("")}</tr>`);
        }
      }
      if (!rows.length) continue;
      const collapsed = d.collapsed.has(group);
      html += `<tr class="group ${collapsed ? "collapsed" : ""}" data-dgroup="${esc(group)}"><td colspan="${slots.length + 1}"><span class="chev">▼</span>${esc(group)}</td></tr>`;
      if (!collapsed) html += rows.join("");
    }
    $("#designTable").innerHTML = html + "</tbody>";
    $("#dDiffOnly").textContent = `Differences only (${diffCount})`;
    $("#dDiffOnly").classList.toggle("active", d.diffOnly);

    $$("#designTable tr.group").forEach((tr) => tr.addEventListener("click", () => {
      const g = tr.dataset.dgroup;
      d.collapsed.has(g) ? d.collapsed.delete(g) : d.collapsed.add(g);
      save("spd.designCollapsed", [...d.collapsed]); renderTable();
    }));
    $$("#designTable [data-cell]").forEach((el) => el.addEventListener("change", () => {
      const s = d.slots[+el.dataset.cell];
      const row = { side: el.dataset.side || null, key: el.dataset.key };
      let value;
      if (el.dataset.input === "check") value = el.checked;
      else if (el.dataset.input === "number") value = Number(el.value);
      else if (el.dataset.input === "int") value = Math.round(Number(el.value));
      else value = el.value || null;
      if ((el.dataset.input === "number" || el.dataset.input === "int") && !(value > 0)) {
        toast("Please enter a positive number."); el.value = getVal(s.design, row); return;
      }
      setVal(s.design, row, value);
      if (row.key === "type" && value === "multi_pad") { s.design.center.shape = "rect"; s.design.ground.shape = "rect"; }
      persist();
      if (row.key === "type") renderSlots();
      evaluateAll();
    }));
  }

  // ------------------------------------------------------------ sketches (face view)
  function renderSketches() {
    const slots = active();
    $("#designSketches").innerHTML = slots.map((s) => {
      const r = d.results[s.i];
      const x = s.design;
      const sub = x.type === "multi_pad" ? `per gap · ${x.n_ground} gaps` : x.type === "annular" ? "top view" : "face view";
      const area = r?.ok ? `common area ${fmtNum(r.common_area, 2)} mm² per gap` : (r ? "invalid input" : "");
      return `<div class="sketch" style="--slot-color: var(--slot-${s.letter})">
        <h4><span style="color: var(--slot-${s.letter})">${s.letter}</span> · ${esc(x.name)}</h4>
        <div class="sub">${esc(TYPE_LABELS[x.type])} · ${sub}</div>
        ${sketchSvg(x, s.i)}
        <div class="sub">${area}</div>
      </div>`;
    }).join("");
  }

  function shapeSvg(e, shape, cx, cy, k, attrs) {
    if (shape === "round") return `<circle cx="${cx}" cy="${cy}" r="${(e.diameter / 2) * k}" ${attrs}/>`;
    const w = e.width * k; const h = e.height * k;
    return `<rect x="${cx - w / 2}" y="${cy - h / 2}" width="${w}" height="${h}" ${attrs}/>`;
  }

  function sketchSvg(x, i) {
    const W = 260; const H = 200; const cx = W / 2; const cy = H / 2 - 4;
    const hatch = `<defs><pattern id="hx${i}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="6" stroke="var(--accent)" stroke-width="2"/></pattern></defs>`;
    if (x.type === "annular") {
      const c = x.center; const g = x.ground;
      const rCo = c.diameter / 2; const rCi = Math.max(rCo - c.thickness, 0);
      const rGi = rCo + x.gap; const rGo = rGi + g.thickness;
      const k = (Math.min(W, H) / 2 - 14) / rGo;
      const ring = (ro, ri, fill, line) => `<path fill-rule="evenodd" fill="${fill}" stroke="${line}" stroke-width="1.5"
        d="M ${cx - ro * k} ${cy} a ${ro * k} ${ro * k} 0 1 0 ${2 * ro * k} 0 a ${ro * k} ${ro * k} 0 1 0 ${-2 * ro * k} 0 Z
           M ${cx - ri * k} ${cy} a ${ri * k} ${ri * k} 0 1 0 ${2 * ri * k} 0 a ${ri * k} ${ri * k} 0 1 0 ${-2 * ri * k} 0 Z"/>`;
      return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Annular electrode top view">${hatch}
        ${ring(rGo, rGi, "var(--pad-g)", "var(--pad-g-line)")}
        ${ring(rCo, rCi, "var(--pad-c)", "var(--pad-c-line)")}
        <circle cx="${cx}" cy="${cy}" r="${rCo * k}" fill="none" stroke="var(--accent)" stroke-width="3" stroke-dasharray="5 3"/>
        <text x="${cx}" y="${H - 4}" text-anchor="middle" font-size="11" fill="var(--muted)">Ø ${fmtNum(c.diameter, 2)} · gap ${fmtNum(x.gap, 2)} · overlap L ${fmtNum(Math.min(c.length, g.length), 2)} mm</text>
      </svg>`;
    }
    const c = x.center; const g = x.ground;
    const sc = x.type === "multi_pad" ? "rect" : c.shape;
    const sg = x.type === "multi_pad" ? "rect" : g.shape;
    const ext = (e, s) => (s === "round" ? [e.diameter, e.diameter] : [e.width, e.height]);
    const [cw, ch] = ext(c, sc); const [gw, gh] = ext(g, sg);
    const k = Math.min((W - 40) / Math.max(cw, gw), (H - 44) / Math.max(ch, gh));
    const clipId = `cl${i}`;
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Facing areas">${hatch}
      <defs><clipPath id="${clipId}">${shapeSvg(g, sg, cx, cy, k, "")}</clipPath></defs>
      ${shapeSvg(g, sg, cx, cy, k, 'fill="var(--pad-g)" stroke="var(--pad-g-line)" stroke-width="1.5"')}
      ${shapeSvg(c, sc, cx, cy, k, 'fill="var(--pad-c)" stroke="var(--pad-c-line)" stroke-width="1.5" stroke-dasharray="5 3"')}
      <g clip-path="url(#${clipId})">${shapeSvg(c, sc, cx, cy, k, `fill="url(#hx${i})" stroke="none"`)}</g>
      <text x="${cx}" y="${H - 4}" text-anchor="middle" font-size="11" fill="var(--muted)">centre ${sc === "round" ? `Ø ${fmtNum(cw, 2)}` : `${fmtNum(cw, 2)} × ${fmtNum(ch, 2)}`} · ground ${sg === "round" ? `Ø ${fmtNum(gw, 2)}` : `${fmtNum(gw, 2)} × ${fmtNum(gh, 2)}`} mm</text>
    </svg>`;
  }

  // ------------------------------------------------------------ export
  async function exportDesigns(format) {
    const slots = active();
    if (!slots.length) { toast("Activate at least one variant."); return; }
    try {
      const res = await fetch("/api/designs/export", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ designs: slots.map((s) => s.design), format }),
      });
      if (!res.ok) throw new Error((await res.json()).detail?.[0]?.msg || res.statusText);
      const blob = await res.blob();
      const name = (res.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/)?.[1] || `designs.${format}`;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = name; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    } catch (err) { toast(`Export failed: ${err.message}`); }
  }

  // ------------------------------------------------------------ page lifecycle
  async function show() {
    if (!state.materials.length) return; // app.js not initialised yet; applyRoute calls again
    if (!d.bound) {
      d.bound = true;
      $("#dExpandAll").addEventListener("click", () => { d.collapsed.clear(); save("spd.designCollapsed", []); renderTable(); });
      $("#dCollapseAll").addEventListener("click", () => { GROUPS.forEach((g) => d.collapsed.add(g)); save("spd.designCollapsed", [...d.collapsed]); renderTable(); });
      $("#dDiffOnly").addEventListener("click", () => { d.diffOnly = !d.diffOnly; renderTable(); });
      $("#dLibrary").addEventListener("click", openLibrary);
      try { await loadLibrary(); } catch { d.library = []; }
    }
    renderSlots();
    await evaluateAll();
  }

  window.designPage = { show, exportDesigns };
})();
