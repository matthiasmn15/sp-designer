"use strict";

// ---------------------------------------------------------------- state
const SLOTS = ["A", "B", "C", "D"];
const CATEGORY_LABELS = {
  precious: "Precious metals", carrier: "Carrier metals", core: "Core materials", alloying: "Alloying elements",
};
const ORIGIN_LABELS = { auto: "auto", manual: "manual", user: "user", estimated: "est.", derived: "derived", price: "price" };

const state = {
  props: [],
  propMap: {},
  materials: [],
  matMap: {},
  slots: load("spd.slots", [
    { id: "Ir", on: true }, { id: "Pt", on: true }, { id: "Ir-10Rh", on: true }, { id: "Ru", on: false },
  ]),
  collapsed: new Set(load("spd.collapsed", [])),
  diffOnly: false,
  weights: load("spd.weights", null),
  settings: null,
  prices: [],
};

function load(key, fallback) {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
}
function save(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* ignore */ } }

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: options.body ? { "Content-Type": "application/json" } : {},
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* ignore */ }
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, 3200);
}

function fmt(value, key) {
  if (value === null || value === undefined) return "–";
  const d = state.propMap[key]?.decimals ?? 2;
  const abs = Math.abs(value);
  let decimals = d;
  if (abs !== 0 && abs < 1 && d < 3) decimals = 3;
  return value.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
const today = () => new Date().toISOString().slice(0, 10);

// ---------------------------------------------------------------- init
async function init() {
  initTheme();
  bindStatic();
  const [props, info, settings, providers] = await Promise.all([
    api("/api/properties"), api("/api/info"), api("/api/settings"), api("/api/providers"),
  ]);
  state.props = props;
  state.propMap = Object.fromEntries(props.map((p) => [p.key, p]));
  if (!state.weights) state.weights = defaultWeights();
  state.settings = settings;
  $("#dataDirHint").textContent = `User data (your materials, overrides and prices) is stored in ${info.data_dir}.`;
  $("#helpInfo").textContent = `Version ${info.version} · user data: ${info.data_dir}`;
  $("#providerSelect").innerHTML = providers.map((p) => `<option value="${esc(p.name)}">${esc(p.label)}</option>`).join("")
    + `<option value="none">Off (manual prices only)</option>`;
  await reloadMaterials();
  await reloadPrices();
  fillChartSelectors();
  renderSets();
  renderAll();
  applyRoute(location.hash);
}

function defaultWeights() {
  return Object.fromEntries(state.props.filter((p) => p.direction !== "none").map((p) => [p.key, p.default_weight]));
}

async function reloadMaterials() {
  state.materials = await api("/api/materials");
  state.matMap = Object.fromEntries(state.materials.map((m) => [m.id, m]));
  state.slots = state.slots.map((s) => (state.matMap[s.id] ? s : { id: "", on: s.on }));
}

async function reloadPrices() {
  state.prices = await api("/api/prices");
  const stale = state.prices.filter((p) => p.stale);
  const notice = $("#notice");
  if (stale.length) {
    notice.hidden = false;
    notice.textContent = `Prices older than ${state.settings.price_max_age_days} days: ${stale.map((p) => `${p.metal} (${p.date})`).join(", ")}. `
      + "Refresh them on the PRICES tab or enter current values manually.";
  } else {
    notice.hidden = true;
  }
}

function renderAll() {
  renderSlots();
  renderTable();
  renderRanking();
  renderDatabase();
  renderPrices();
  renderCharts();
}

// ---------------------------------------------------------------- theme, tabs, toolbar
function initTheme() {
  setTheme(load("spd.theme", "light"));
  $$(".theme-btn").forEach((b) => b.addEventListener("click", () => setTheme(b.dataset.themeSet)));
}
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $$(".theme-btn").forEach((b) => b.classList.toggle("active", b.dataset.themeSet === theme));
  save("spd.theme", theme);
  if (state.props.length) renderCharts();
}

function bindStatic() {
  $$(".main-tab").forEach((b) => b.addEventListener("click", () => navigate(b.dataset.page)));
  $$(".tab").forEach((tab) => tab.addEventListener("click", () => {
    const page = tab.closest("[data-subnav]").dataset.subnav;
    navigate(page, tab.dataset.tab);
  }));
  window.addEventListener("hashchange", () => applyRoute(location.hash));
  $("#explainToggle").addEventListener("change", (e) => document.body.classList.toggle("explain", e.target.checked));
  $("#helpBtn").addEventListener("click", () => $("#helpDialog").showModal());
  $("#expandAll").addEventListener("click", () => { state.collapsed.clear(); persistCollapsed(); renderTable(); });
  $("#collapseAll").addEventListener("click", () => {
    groups().forEach((g) => state.collapsed.add(g)); persistCollapsed(); renderTable();
  });
  $("#diffOnly").addEventListener("click", () => { state.diffOnly = !state.diffOnly; renderTable(); });
  $("#exportCsv").addEventListener("click", () => exportComparison("csv"));
  $("#exportXlsx").addEventListener("click", () => exportComparison("xlsx"));
  $("#resetWeights").addEventListener("click", () => { state.weights = defaultWeights(); save("spd.weights", state.weights); renderRanking(); });
  $("#rankCategory").addEventListener("change", renderRanking);
  ["#barProp", "#barCategory", "#mapX", "#mapY", "#mapXLog", "#mapYLog", "#mapCategory"].forEach((s) =>
    $(s).addEventListener("change", renderCharts));
  $("#dbSearch").addEventListener("input", renderDatabase);
  $("#dbCategory").addEventListener("change", renderDatabase);
  $("#addMaterial").addEventListener("click", openAddDialog);
  $("#addCompRow").addEventListener("click", () => addCompRow());
  $("#addKind").addEventListener("change", () => { $("#compBlock").hidden = $("#addKind").value !== "alloy"; });
  $("#addForm").addEventListener("submit", submitAddDialog);
  $("#editForm").addEventListener("submit", submitEditDialog);
  $("#refreshPrices").addEventListener("click", refreshPrices);
  $("#priceForm").addEventListener("submit", submitPrice);
  $("#settingsForm").addEventListener("submit", submitSettings);
  $("#setSelect").addEventListener("change", applySet);
  $("#setSave").addEventListener("click", saveSet);
  $("#setDelete").addEventListener("click", deleteSet);
}

// ---------------------------------------------------------------- navigation (#page/subpage)
const DEFAULT_SUB = { materials: "compare" };
function navigate(page, sub) {
  const hash = `#${page}${sub || DEFAULT_SUB[page] ? `/${sub || DEFAULT_SUB[page]}` : ""}`;
  if (location.hash !== hash) location.hash = hash; else applyRoute(hash);
}
function applyRoute(hash) {
  const [pageRaw, subRaw] = (hash || "").replace(/^#/, "").split("/");
  const page = $(`.main-tab[data-page="${pageRaw}"]`) ? pageRaw : "materials";
  $$(".main-tab").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  $$(".page").forEach((p) => { p.hidden = p.dataset.page !== page; });
  $$("[data-subnav]").forEach((n) => { n.hidden = n.dataset.subnav !== page; });
  $$(".materials-only").forEach((el) => { el.hidden = page !== "materials"; });
  $$(".export-group").forEach((el) => { el.hidden = !["materials", "design"].includes(page); });
  document.body.dataset.page = page;
  if (page === "design" && window.designPage) window.designPage.show();
  const nav = $(`[data-subnav="${page}"]`);
  if (nav) {
    const sub = $(`.tab[data-tab="${subRaw}"]`, nav) ? subRaw : DEFAULT_SUB[page];
    $$(".tab", nav).forEach((t) => t.classList.toggle("active", t.dataset.tab === sub));
    $$(`.page[data-page="${page}"] .panel`).forEach((p) => { p.hidden = p.id !== `tab-${sub}`; });
    if (sub === "charts") renderCharts();
  }
}

function persistCollapsed() { save("spd.collapsed", [...state.collapsed]); }
function persistSlots() { save("spd.slots", state.slots); }
function activeSlots() {
  return state.slots.map((s, i) => ({ ...s, letter: SLOTS[i] })).filter((s) => s.on && s.id && state.matMap[s.id]);
}

function exportComparison(format) {
  if (document.body.dataset.page === "design" && window.designPage) { window.designPage.exportDesigns(format); return; }
  const ids = activeSlots().map((s) => s.id);
  if (!ids.length) { toast("Select at least one material in A–D."); return; }
  window.location.href = `/api/export?format=${format}&ids=${encodeURIComponent(ids.join(","))}`;
}

// ---------------------------------------------------------------- comparison sets
function sets() { return load("spd.sets", {}); }
function renderSets(selected) {
  const all = sets();
  const names = Object.keys(all).sort();
  $("#setSelect").innerHTML = `<option value="">(current selection)</option>`
    + names.map((n) => `<option ${n === selected ? "selected" : ""}>${esc(n)}</option>`).join("");
}
function applySet() {
  const name = $("#setSelect").value;
  if (!name) return;
  const s = sets()[name];
  if (!s) return;
  state.slots = s.map((x) => ({ ...x }));
  persistSlots(); renderAll();
}
function saveSet() {
  const name = prompt("Name of the comparison set:", $("#setSelect").value || "");
  if (!name) return;
  const all = sets(); all[name] = state.slots; save("spd.sets", all); renderSets(name); toast(`Saved set "${name}".`);
}
function deleteSet() {
  const name = $("#setSelect").value;
  if (!name) return;
  const all = sets(); delete all[name]; save("spd.sets", all); renderSets(); toast(`Deleted set "${name}".`);
}

// ---------------------------------------------------------------- slots
function materialOptions(selected) {
  const byCat = {};
  for (const m of state.materials) {
    const cat = m.categories[0];
    (byCat[cat] ||= []).push(m);
  }
  let html = `<option value="">– none –</option>`;
  for (const cat of Object.keys(CATEGORY_LABELS)) {
    if (!byCat[cat]) continue;
    html += `<optgroup label="${CATEGORY_LABELS[cat]}">`
      + byCat[cat].map((m) => `<option value="${esc(m.id)}" ${m.id === selected ? "selected" : ""}>${esc(m.name)}${m.user_defined ? " (user)" : ""}</option>`).join("")
      + "</optgroup>";
  }
  return html;
}

function renderSlots() {
  $("#slots").innerHTML = state.slots.map((s, i) => {
    const m = state.matMap[s.id];
    const L = SLOTS[i];
    return `<div class="slot ${s.on ? "" : "off"}" style="--slot-color: var(--slot-${L})">
      <div class="slot-top">
        <input type="checkbox" data-slot-on="${i}" ${s.on ? "checked" : ""} aria-label="Show ${L}">
        <span>${L}</span><span class="swatch"></span>
        <span class="name">${m ? esc(m.name) : "–"}</span>
      </div>
      <div class="slot-row">
        <select data-slot-sel="${i}" aria-label="Material ${L}">${materialOptions(s.id)}</select>
        <button class="icon-btn" data-slot-edit="${i}" title="Edit material values" ${m ? "" : "disabled"}>✎</button>
      </div>
    </div>`;
  }).join("");
  $$("[data-slot-on]").forEach((el) => el.addEventListener("change", () => {
    state.slots[+el.dataset.slotOn].on = el.checked; persistSlots(); renderSlots(); renderTable(); renderCharts();
  }));
  $$("[data-slot-sel]").forEach((el) => el.addEventListener("change", () => {
    state.slots[+el.dataset.slotSel].id = el.value; persistSlots(); renderSlots(); renderTable(); renderCharts();
  }));
  $$("[data-slot-edit]").forEach((el) => el.addEventListener("click", () => {
    const id = state.slots[+el.dataset.slotEdit].id; if (id) openEditDialog(id);
  }));
  renderSummary();
}

function renderSummary() {
  $("#slotSummary").innerHTML = state.slots.map((s, i) => {
    const m = state.matMap[s.id];
    if (!m || !s.on) return "";
    const cat = m.categories[0];
    return `<li><span class="letter" style="color: var(--slot-${SLOTS[i]})">${SLOTS[i]}</span>
      <span>${esc(m.name)}</span><span class="pill ${cat}">${esc(cat)}</span></li>`;
  }).join("");
  const letters = activeSlots().map((s) => s.letter);
  $("#slotLetters").textContent = letters.length ? letters.join(" / ") : "";
}

// ---------------------------------------------------------------- property table
function groups() { return [...new Set(["General", ...state.props.map((p) => p.group)])]; }

function bestIndex(prop, mats) {
  if (prop.direction === "none" || mats.length < 2) return -1;
  let best = -1; let bestVal = null;
  mats.forEach((m, i) => {
    const v = m.properties[prop.key]?.value;
    if (v === undefined || v === null) return;
    if (bestVal === null || (prop.direction === "higher" ? v > bestVal : v < bestVal)) { bestVal = v; best = i; }
  });
  return best;
}

function renderTable() {
  const slots = activeSlots();
  const mats = slots.map((s) => state.matMap[s.id]);
  let html = `<thead><tr><th>Parameter</th>${slots.map((s) => `<th class="slot-col" style="color: var(--slot-${s.letter})">${s.letter}</th>`).join("")}</tr></thead><tbody>`;
  let diffCount = 0;

  const generalRows = [
    ["Kind", (m) => m.kind],
    ["Categories", (m) => m.categories.join(", ")],
    ["Composition [mass %]", (m) => Object.keys(m.composition).length
      ? Object.entries(m.composition).map(([k, v]) => `${k} ${(v * 100).toFixed(1)}`).join(" · ") : "–"],
  ];

  for (const group of groups()) {
    const collapsed = state.collapsed.has(group);
    const rows = [];
    if (group === "General") {
      for (const [label, fn] of generalRows) {
        const vals = mats.map(fn);
        const differs = new Set(vals).size > 1;
        if (differs) diffCount++;
        if (state.diffOnly && !differs) continue;
        rows.push(`<tr><td class="label">${label}</td>${vals.map((v) => `<td><div class="val">${esc(v)}</div></td>`).join("")}</tr>`);
      }
    } else {
      for (const p of state.props.filter((x) => x.group === group)) {
        const vals = mats.map((m) => m.properties[p.key]);
        const shown = vals.map((v) => fmt(v?.value, p.key));
        const differs = new Set(shown).size > 1;
        if (differs) diffCount++;
        if (state.diffOnly && !differs) continue;
        const best = bestIndex(p, mats);
        rows.push(`<tr><td class="label">${esc(p.label)} <span class="unit">[${esc(p.unit)}]</span>
            <div class="desc">${esc(p.description)}</div></td>
          ${vals.map((v, i) => {
            const tip = v ? [v.source, v.date, v.note].filter(Boolean).join(" · ") : "no value";
            const badge = v ? `<span class="badge o-${v.origin}">${ORIGIN_LABELS[v.origin]}</span>` : "";
            const cls = ["val", v ? "" : "empty", p.editable ? "editable" : "", i === best ? "best" : ""].join(" ");
            return `<td><div class="${cls}" title="${esc(tip)}" ${p.editable ? `data-edit="${esc(mats[i].id)}" data-prop="${p.key}"` : ""}>
              ${fmt(v?.value, p.key)}${badge}</div></td>`;
          }).join("")}</tr>`);
      }
    }
    if (!rows.length) continue;
    html += `<tr class="group ${collapsed ? "collapsed" : ""}" data-group="${esc(group)}"><td colspan="${slots.length + 1}"><span class="chev">▼</span>${esc(group)}</td></tr>`;
    if (!collapsed) html += rows.join("");
  }
  html += "</tbody>";
  if (!slots.length) html = `<tbody><tr><td class="hint">Select materials in A–D above.</td></tr></tbody>`;
  $("#propTable").innerHTML = html;
  $("#diffOnly").textContent = `Differences only (${diffCount})`;
  $("#diffOnly").classList.toggle("active", state.diffOnly);
  $$("#propTable tr.group").forEach((tr) => tr.addEventListener("click", () => {
    const g = tr.dataset.group;
    state.collapsed.has(g) ? state.collapsed.delete(g) : state.collapsed.add(g);
    persistCollapsed(); renderTable();
  }));
  $$("#propTable [data-edit]").forEach((el) => el.addEventListener("click", () => openEditDialog(el.dataset.edit, el.dataset.prop)));
}

// ---------------------------------------------------------------- edit dialog
let editing = null;
function openEditDialog(materialId, focusKey) {
  const m = state.matMap[materialId];
  editing = m;
  $("#editTitle").textContent = `Edit ${m.name}`;
  const editable = state.props.filter((p) => p.editable);
  $("#editFields").innerHTML = `<div class="edit-row"><b>Property</b><b>Value</b><b>Source</b><b>Note</b></div>`
    + editable.map((p) => {
      const v = m.properties[p.key];
      const isUser = v?.origin === "user";
      const placeholder = v && !isUser ? `${fmt(v.value, p.key)} (${ORIGIN_LABELS[v.origin]})` : "–";
      const step = p.kind === "rating" ? "1" : "any";
      const minmax = p.kind === "rating" ? 'min="1" max="5"' : "";
      return `<div class="edit-row ${p.key === focusKey ? "focus" : ""}" data-key="${p.key}">
        <div class="lbl">${esc(p.label)}<small>${esc(p.unit)}</small></div>
        <input type="number" step="${step}" ${minmax} name="value" value="${isUser ? v.value : ""}" placeholder="${esc(placeholder)}">
        <input name="source" value="${isUser ? esc(v.source ?? "") : ""}" placeholder="source">
        <input name="note" value="${isUser ? esc(v.note ?? "") : ""}" placeholder="note">
      </div>`;
    }).join("");
  $("#editDialog").showModal();
  if (focusKey) $(`.edit-row[data-key="${focusKey}"] input[name="value"]`)?.focus();
}

async function submitEditDialog(e) {
  if (e.submitter?.value !== "save" || !editing) return;
  e.preventDefault();
  const body = {};
  for (const row of $$("#editFields .edit-row[data-key]")) {
    const key = row.dataset.key;
    const raw = $('input[name="value"]', row).value.trim();
    const wasUser = editing.properties[key]?.origin === "user";
    if (raw === "") { if (wasUser) body[key] = null; continue; }
    body[key] = {
      value: Number(raw),
      source: $('input[name="source"]', row).value.trim() || "user entry",
      note: $('input[name="note"]', row).value.trim() || null,
      date: today(),
    };
  }
  try {
    await api(`/api/materials/${encodeURIComponent(editing.id)}/properties`, { method: "PUT", body });
    $("#editDialog").close();
    await reloadMaterials(); renderAll(); toast(`Saved ${editing.name}.`);
  } catch (err) { toast(`Error: ${err.message}`); }
}

// ---------------------------------------------------------------- add dialog
function elementOptions(selected) {
  return state.materials.filter((m) => m.kind === "element" || m.user_defined)
    .map((m) => `<option value="${esc(m.id)}" ${m.id === selected ? "selected" : ""}>${esc(m.name)}</option>`).join("");
}
function addCompRow(id = "", pct = "") {
  const row = document.createElement("div");
  row.className = "comp-row";
  row.innerHTML = `<select>${elementOptions(id)}</select>
    <input type="number" step="any" min="0" max="100" placeholder="mass %" value="${pct}">
    <button type="button" class="icon-btn" title="Remove">✕</button>`;
  $("button", row).addEventListener("click", () => row.remove());
  $("#compRows").appendChild(row);
}
function openAddDialog() {
  $("#addForm").reset();
  $("#compRows").innerHTML = "";
  addCompRow("Ir", 95); addCompRow("Rh", 5);
  $("#compBlock").hidden = false;
  $("#addError").textContent = "";
  $("#addDialog").showModal();
}
async function submitAddDialog(e) {
  if (e.submitter?.value !== "save") return;
  e.preventDefault();
  const f = new FormData($("#addForm"));
  const kind = f.get("kind");
  const composition = {};
  if (kind === "alloy") {
    for (const row of $$("#compRows .comp-row")) {
      const pct = Number($("input", row).value);
      if (pct > 0) composition[$("select", row).value] = (composition[$("select", row).value] || 0) + pct;
    }
    const total = Object.values(composition).reduce((a, b) => a + b, 0);
    if (Math.abs(total - 100) > 0.01) { $("#addError").textContent = `Composition sums to ${total.toFixed(2)} %, expected 100 %.`; return; }
  }
  const body = {
    name: f.get("name"), kind, categories: f.getAll("cat"),
    composition: Object.fromEntries(Object.entries(composition).map(([k, v]) => [k, v / 100])),
    description: f.get("description") || null,
  };
  if (!body.categories.length) { $("#addError").textContent = "Select at least one category."; return; }
  try {
    const m = await api("/api/materials", { method: "POST", body });
    $("#addDialog").close();
    await reloadMaterials(); renderAll();
    toast(`Created ${m.name}. Enter datasheet values where available.`);
    openEditDialog(m.id);
  } catch (err) { $("#addError").textContent = err.message; }
}

// ---------------------------------------------------------------- ranking
async function renderRanking() {
  const criteria = state.props.filter((p) => p.direction !== "none");
  $("#weights").innerHTML = criteria.map((p) => `<div class="weight">
      <span>${esc(p.label)} <span class="sub">[${esc(p.unit)}]</span></span>
      <span class="dir" title="${p.direction === "higher" ? "higher is better" : "lower is better"}">${p.direction === "higher" ? "↑ higher" : "↓ lower"}</span>
      <input type="range" min="0" max="5" step="1" value="${state.weights[p.key] ?? 0}" data-w="${p.key}">
      <output>${state.weights[p.key] ?? 0}</output></div>`).join("");
  $$("#weights [data-w]").forEach((el) => el.addEventListener("input", () => {
    state.weights[el.dataset.w] = Number(el.value);
    el.nextElementSibling.textContent = el.value;
    save("spd.weights", state.weights);
    clearTimeout(renderRanking._t); renderRanking._t = setTimeout(updateRankTable, 150);
  }));
  await updateRankTable();
}

async function updateRankTable() {
  let ranking;
  try {
    ranking = await api("/api/ranking", { method: "POST", body: { weights: state.weights, category: $("#rankCategory").value } });
  } catch (err) { $("#rankTable").innerHTML = `<tr><td class="error">${esc(err.message)}</td></tr>`; return; }
  $("#rankTable").innerHTML = `<thead><tr><th>#</th><th>Material</th><th>Score</th><th class="num">Coverage</th><th class="actions">Put into</th></tr></thead><tbody>`
    + ranking.map((r) => `<tr>
      <td>${r.rank ?? "–"}</td>
      <td>${esc(r.name)}</td>
      <td><div class="scorebar"><span style="width:${((r.score ?? 0) * 100).toFixed(0)}%"></span><em>${r.score === null ? "–" : (r.score * 100).toFixed(0)}</em></div></td>
      <td class="num ${r.coverage < 0.999 ? "warn" : ""}">${(r.coverage * 100).toFixed(0)} %</td>
      <td class="actions"><span class="assign">${SLOTS.map((L, i) => `<button data-assign="${i}" data-id="${esc(r.id)}" title="Put into ${L}" style="color: var(--slot-${L})">${L}</button>`).join("")}</span></td>
    </tr>`).join("") + "</tbody>";
  $$("#rankTable [data-assign]").forEach((b) => b.addEventListener("click", () => {
    state.slots[+b.dataset.assign] = { id: b.dataset.id, on: true };
    persistSlots(); renderSlots(); renderTable(); toast(`${state.matMap[b.dataset.id].name} → ${SLOTS[+b.dataset.assign]}`);
  }));
}

// ---------------------------------------------------------------- charts
function numericProps() { return state.props.filter((p) => p.kind === "number" || p.kind === "rating"); }
function fillChartSelectors() {
  const opts = (sel) => numericProps().map((p) => `<option value="${p.key}" ${p.key === sel ? "selected" : ""}>${esc(p.label)} [${esc(p.unit)}]</option>`).join("");
  $("#barProp").innerHTML = opts("melt_energy_density");
  $("#mapX").innerHTML = opts("cost_per_volume");
  $("#mapY").innerHTML = opts("melt_energy_density");
}

function chartTheme() {
  const css = getComputedStyle(document.documentElement);
  const c = (n) => css.getPropertyValue(n).trim();
  return {
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: c("--font"), color: c("--muted"), size: 13 },
    margin: { l: 70, r: 20, t: 20, b: 70 },
    xaxis: { gridcolor: c("--line"), linecolor: c("--border"), zerolinecolor: c("--border") },
    yaxis: { gridcolor: c("--line"), linecolor: c("--border"), zerolinecolor: c("--border") },
    colors: { muted: c("--chart-muted"), slot: Object.fromEntries(SLOTS.map((L) => [L, c(`--slot-${L}`)])), text: c("--text") },
  };
}

function slotLetterOf(id) {
  const s = activeSlots().find((x) => x.id === id);
  return s ? s.letter : null;
}
function chartMaterials(category) {
  const ids = new Set(activeSlots().map((s) => s.id));
  return state.materials.filter((m) => category === "all" ? m.categories[0] !== "alloying" || ids.has(m.id)
    : m.categories.includes(category) || ids.has(m.id));
}

function renderCharts() {
  if ($("#tab-charts").offsetParent === null || !state.props.length || !$("#barProp").value) return;
  if (!window.Plotly) {
    $("#barChart").innerHTML = $("#mapChart").innerHTML = `<div class="empty-chart">Charts need the Plotly library. Install it with: pip install plotly</div>`;
    return;
  }
  const { colors, ...t } = chartTheme();
  const config = { displaylogo: false, responsive: true, toImageButtonOptions: { format: "png", scale: 2 } };

  // bar chart
  const key = $("#barProp").value;
  const p = state.propMap[key];
  const mats = chartMaterials($("#barCategory").value).filter((m) => m.properties[key]?.value != null)
    .sort((a, b) => b.properties[key].value - a.properties[key].value);
  Plotly.react("barChart", [{
    type: "bar", x: mats.map((m) => m.name), y: mats.map((m) => m.properties[key].value),
    marker: { color: mats.map((m) => { const L = slotLetterOf(m.id); return L ? colors.slot[L] : colors.muted; }) },
    text: mats.map((m) => fmt(m.properties[key].value, key)), textposition: "outside", cliponaxis: false,
    hovertemplate: "%{x}: %{text}<extra></extra>",
  }], {
    ...t, yaxis: { ...t.yaxis, title: { text: `${p.label} [${p.unit}]` } }, xaxis: { ...t.xaxis, tickangle: -30 },
    showlegend: false,
  }, config);

  // selection map
  const kx = $("#mapX").value; const ky = $("#mapY").value;
  const px = state.propMap[kx]; const py = state.propMap[ky];
  const pts = chartMaterials($("#mapCategory").value).filter((m) => m.properties[kx]?.value != null && m.properties[ky]?.value != null);
  Plotly.react("mapChart", [{
    type: "scatter", mode: "markers+text",
    x: pts.map((m) => m.properties[kx].value), y: pts.map((m) => m.properties[ky].value),
    text: pts.map((m) => m.name), textposition: "top center", textfont: { color: colors.text },
    marker: {
      size: pts.map((m) => (slotLetterOf(m.id) ? 16 : 11)),
      color: pts.map((m) => { const L = slotLetterOf(m.id); return L ? colors.slot[L] : colors.muted; }),
      line: { width: 1, color: "rgba(0,0,0,0.25)" },
    },
    hovertemplate: `%{text}<br>${px.label}: %{x}<br>${py.label}: %{y}<extra></extra>`,
  }], {
    ...t,
    xaxis: { ...t.xaxis, title: { text: `${px.label} [${px.unit}]` }, type: $("#mapXLog").checked ? "log" : "linear" },
    yaxis: { ...t.yaxis, title: { text: `${py.label} [${py.unit}]` }, type: $("#mapYLog").checked ? "log" : "linear" },
    showlegend: false,
  }, config);
}

// ---------------------------------------------------------------- database
function renderDatabase() {
  const q = $("#dbSearch").value.trim().toLowerCase();
  const cat = $("#dbCategory").value;
  const cols = ["density", "melting_point", "thermal_conductivity", "melt_energy_density", "price"];
  const mats = state.materials.filter((m) => (cat === "all" || m.categories.includes(cat))
    && (!q || m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q)));
  $("#dbTable").innerHTML = `<thead><tr><th>Material</th><th>Kind</th><th>Categories</th>
      ${cols.map((k) => `<th class="num">${esc(state.propMap[k].label)}<br><span class="sub">${esc(state.propMap[k].unit)}</span></th>`).join("")}
      <th class="actions"></th></tr></thead><tbody>`
    + mats.map((m) => `<tr>
      <td><b>${esc(m.name)}</b>${m.user_defined ? ' <span class="badge o-user">user</span>' : ""}
        ${m.has_overrides ? ' <span class="badge o-user" title="contains your overrides">edited</span>' : ""}
        ${Object.keys(m.composition).length ? `<div class="sub">${Object.entries(m.composition).map(([k, v]) => `${k} ${(v * 100).toFixed(1)}`).join(" · ")}</div>` : ""}</td>
      <td>${esc(m.kind)}</td><td>${esc(m.categories.join(", "))}</td>
      ${cols.map((k) => { const v = m.properties[k]; return `<td class="num" title="${esc(v ? [v.origin, v.source, v.date].filter(Boolean).join(" · ") : "")}">${fmt(v?.value, k)}</td>`; }).join("")}
      <td class="actions">
        <button class="btn small outline" data-db-edit="${esc(m.id)}">Edit</button>
        ${m.has_overrides ? `<button class="btn small outline" data-db-reset="${esc(m.id)}">Reset</button>` : ""}
        ${m.user_defined ? `<button class="btn small outline danger" data-db-del="${esc(m.id)}">Delete</button>` : ""}
      </td></tr>`).join("") + "</tbody>";
  $$("[data-db-edit]").forEach((b) => b.addEventListener("click", () => openEditDialog(b.dataset.dbEdit)));
  $$("[data-db-reset]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("Remove all your overrides for this material?")) return;
    await api(`/api/materials/${encodeURIComponent(b.dataset.dbReset)}/properties`, { method: "DELETE" });
    await reloadMaterials(); renderAll();
  }));
  $$("[data-db-del]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("Delete this material?")) return;
    try {
      await api(`/api/materials/${encodeURIComponent(b.dataset.dbDel)}`, { method: "DELETE" });
      await reloadMaterials(); renderAll();
    } catch (err) { toast(`Error: ${err.message}`); }
  }));
}

// ---------------------------------------------------------------- prices
function renderPrices() {
  $("#priceTable").innerHTML = `<thead><tr><th>Metal</th><th class="num">USD/ozt</th><th class="num">USD/g</th>
      <th>Date</th><th class="num">Age</th><th>Origin</th><th>Source</th><th class="actions"></th></tr></thead><tbody>`
    + state.prices.map((p) => `<tr>
      <td><b>${esc(state.matMap[p.metal]?.name ?? p.metal)}</b> <span class="sub">${esc(p.metal)}</span></td>
      <td class="num">${p.usd_per_ozt.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
      <td class="num">${p.usd_per_g.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
      <td>${esc(p.date)}</td>
      <td class="num ${p.stale ? "stale" : ""}">${p.age_days} d</td>
      <td><span class="badge o-${p.origin === "auto" ? "auto" : p.origin === "manual" ? "user" : "manual"}">${esc(p.origin)}</span></td>
      <td class="sub">${esc(p.source ?? "")}</td>
      <td class="actions"><button class="btn small outline" data-history="${esc(p.metal)}">History</button></td>
    </tr>`).join("") + "</tbody>";
  $$("[data-history]").forEach((b) => b.addEventListener("click", () => openHistory(b.dataset.history)));
  $("#priceMetal").innerHTML = state.materials.filter((m) => m.kind === "element")
    .map((m) => `<option value="${esc(m.id)}">${esc(m.name)} (${esc(m.id)})</option>`).join("");
  $('#priceForm [name="date"]').value ||= today();
  const s = state.settings;
  $("#providerSelect").value = s.price_provider;
  $('#settingsForm [name="price_max_age_days"]').value = s.price_max_age_days;
}

async function openHistory(metal) {
  const rows = await api(`/api/prices/${encodeURIComponent(metal)}/history`);
  $("#historyTitle").textContent = `Price history – ${state.matMap[metal]?.name ?? metal}`;
  $("#historyTable").innerHTML = `<thead><tr><th>Date</th><th class="num">USD/ozt</th><th>Origin</th><th>Source</th><th></th></tr></thead><tbody>`
    + rows.slice().reverse().map((r) => `<tr><td>${esc(r.date)}</td>
      <td class="num">${r.usd_per_ozt.toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
      <td>${esc(r.origin)}</td><td class="sub">${esc(r.source ?? "")}</td>
      <td class="actions">${r.origin !== "seed" ? `<button type="button" class="btn small outline danger" data-del-price="${esc(r.date)}" data-origin="${esc(r.origin)}">Delete</button>` : ""}</td></tr>`).join("")
    + "</tbody>";
  $$("[data-del-price]").forEach((b) => b.addEventListener("click", async () => {
    await api(`/api/prices/${encodeURIComponent(metal)}/${b.dataset.delPrice}?origin=${b.dataset.origin}`, { method: "DELETE" });
    await afterPriceChange(); openHistory(metal);
  }));
  if (!$("#historyDialog").open) $("#historyDialog").showModal();
}

async function afterPriceChange() {
  await Promise.all([reloadMaterials(), reloadPrices()]);
  renderAll();
}

async function refreshPrices() {
  const status = $("#priceStatus");
  status.textContent = "Fetching prices…";
  try {
    const r = await api("/api/prices/refresh", { method: "POST" });
    const errs = Object.entries(r.errors);
    status.textContent = `Updated: ${r.updated.join(", ") || "none"}.`
      + (errs.length ? ` Not available: ${errs.map(([m, e]) => `${m} (${e})`).join("; ")}.` : "");
    await afterPriceChange();
  } catch (err) { status.textContent = `Error: ${err.message}`; }
}

async function submitPrice(e) {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api("/api/prices", { method: "POST", body: {
      metal: f.get("metal"), value: Number(f.get("value")), unit: f.get("unit"),
      date: f.get("date"), source: f.get("source") || null,
    } });
    e.target.reset();
    await afterPriceChange(); toast("Price added.");
  } catch (err) { toast(`Error: ${err.message}`); }
}

async function submitSettings(e) {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    state.settings = await api("/api/settings", { method: "PUT", body: {
      price_provider: f.get("price_provider"), price_max_age_days: Number(f.get("price_max_age_days")),
    } });
    await reloadPrices(); renderPrices(); toast("Settings saved.");
  } catch (err) { toast(`Error: ${err.message}`); }
}

window.addEventListener("resize", () => { clearTimeout(window._rz); window._rz = setTimeout(renderCharts, 200); });
init().catch((err) => { document.body.insertAdjacentHTML("afterbegin", `<p class="error">Failed to start: ${esc(err.message)}</p>`); });
