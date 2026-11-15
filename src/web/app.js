"use strict";

const TOKEN_KEY = "rice.token";

const TABS = [
  { id: "apps", label: "Apps" },
  { id: "outputs", label: "Outputs" },
  { id: "layout", label: "Layout" },
  { id: "placement", label: "Placement" },
  { id: "startup", label: "Startup" },
  { id: "autostart", label: "Autostart" },
  { id: "widgets", label: "Widgets" },
  { id: "theme", label: "Theme" },
  { id: "apply", label: "Apply" },
];

const state = {
  token: "",
  config: null,
  validation: [],
  outputs: [],
  catalog: null,
  selected: { tab: "apps", zone: null, output: null },
  drag: null,
  dirty: false,
  busy: false,
};

const ZONE_MIN = 0.05;
const ZONE_MAX = 1;

const elements = {
  tabs: document.getElementById("tabs"),
  panel: document.getElementById("panel"),
  status: document.getElementById("status"),
  badge: document.getElementById("badge"),
  validate: document.getElementById("validate"),
  save: document.getElementById("save"),
  apply: document.getElementById("apply"),
};

// -- small DOM helpers ----------------------------------------------------

function make(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function setStatus(message, tone) {
  elements.status.textContent = message;
  if (tone) {
    elements.status.setAttribute("data-tone", tone);
  } else {
    elements.status.removeAttribute("data-tone");
  }
}

function setBusy(value) {
  state.busy = value;
  syncButtons();
}

function syncButtons() {
  const disabled = state.busy || !state.config;
  elements.validate.disabled = disabled;
  elements.save.disabled = disabled;
  elements.apply.disabled = disabled;
}

function markDirty() {
  state.dirty = true;
  elements.badge.hidden = false;
  setStatus(
    "Unsaved changes. Save writes the configuration; Apply saves and runs the rice pipeline.",
    "warn",
  );
}

// -- auth and API ---------------------------------------------------------

function readToken() {
  const incoming = new URLSearchParams(location.search).get("token");
  if (incoming) {
    // Keep the token out of history and out of copied links; it stays in this
    // tab's session storage only.
    sessionStorage.setItem(TOKEN_KEY, incoming);
    const params = new URLSearchParams(location.search);
    params.delete("token");
    const query = params.toString();
    const clean = location.pathname + (query ? "?" + query : "") + location.hash;
    window.history.replaceState(null, "", clean);
    return incoming;
  }
  return sessionStorage.getItem(TOKEN_KEY) || "";
}

function errorMessage(payload, status) {
  if (payload && typeof payload === "object") {
    if (typeof payload.error === "string" && payload.error) return payload.error;
    if (Array.isArray(payload.errors) && payload.errors.length) {
      return payload.errors.join("; ");
    }
  }
  return "Request failed with HTTP " + status;
}

async function api(path, options) {
  const settings = options || {};
  const headers = new Headers();
  headers.set("Authorization", "Bearer " + state.token);
  headers.set("Accept", "application/json");

  let body;
  if (settings.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = typeof settings.body === "string" ? settings.body : JSON.stringify(settings.body);
  }

  const response = await fetch(path, {
    method: settings.method || "GET",
    headers: headers,
    body: body,
    cache: "no-store",
  });

  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      payload = null;
    }
  }
  if (!response.ok) {
    throw new Error(errorMessage(payload, response.status));
  }
  return payload;
}

async function run(task) {
  if (state.busy) return;
  setBusy(true);
  try {
    await task();
  } catch (error) {
    setStatus(error && error.message ? error.message : String(error), "error");
  } finally {
    setBusy(false);
  }
}

// -- rendering ------------------------------------------------------------

function render() {
  renderTabs();
  elements.badge.hidden = !state.dirty;
  elements.panel.replaceChildren();

  if (!state.config) {
    elements.panel.append(
      make("h2", "", "No configuration"),
      make(
        "p",
        "muted",
        "rice.toml could not be loaded. Run rice install or rice config from a shell, then reload this page.",
      ),
    );
    syncButtons();
    return;
  }

  const renderer = RENDERERS[state.selected.tab] || renderApps;
  renderer(elements.panel);
  syncButtons();
}

function renderTabs() {
  const buttons = elements.tabs.querySelectorAll("[data-tab]");
  for (const button of buttons) {
    if (button.dataset.tab === state.selected.tab) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  }
}

function bindTabs() {
  elements.tabs.addEventListener("click", function (event) {
    const button = event.target.closest("[data-tab]");
    if (!button) return;
    const id = button.dataset.tab;
    if (!TABS.some((tab) => tab.id === id)) return;
    state.selected.tab = id;
    render();
  });
}

function heading(panel, title, description) {
  panel.append(make("h2", "", title));
  if (description) panel.append(make("p", "muted", description));
}

function keyValue(list, key, value) {
  list.append(make("dt", "", key), make("dd", "", value));
}

function table(panel, headers, rows) {
  if (!rows.length) {
    panel.append(make("p", "muted", "Nothing configured."));
    return;
  }
  const wrap = make("div", "table-wrap");
  const tableElement = make("table");
  const headRow = make("tr");
  for (const header of headers) headRow.append(make("th", "", header));
  const thead = make("thead");
  thead.append(headRow);
  const tbody = make("tbody");
  for (const row of rows) {
    const rowElement = make("tr");
    for (const cell of row) {
      rowElement.append(make("td", "", cell === undefined || cell === null ? "" : cell));
    }
    tbody.append(rowElement);
  }
  tableElement.append(thead, tbody);
  wrap.append(tableElement);
  panel.append(wrap);
}

function renderApps(panel) {
  heading(
    panel,
    "Apps",
    "Declared applications. Commands are argv lists and never pass through a shell.",
  );
  table(
    panel,
    ["Id", "Name", "Command", "Window class"],
    asArray(state.config.app).map((app) => [
      app.id,
      app.name,
      asArray(app.command).join(" "),
      app.wm_class,
    ]),
  );
  const catalog = state.catalog;
  if (catalog && typeof catalog === "object") {
    const slots = Object.keys(catalog);
    if (slots.length) {
      panel.append(
        make("p", "muted", "Installer catalog slots: " + slots.join(", ") + "."),
      );
    }
  }
  panel.append(
    make("p", "muted", "Structured app editing arrives in a later task; this view is read-only."),
  );
}

function renderOutputs(panel) {
  heading(
    panel,
    "Outputs",
    "Output roles decide which physical display receives which layout.",
  );
  const outputs = asArray(state.config.output);
  if (!outputs.length) {
    panel.append(make("p", "muted", "No outputs configured."));
    return;
  }
  const grid = make("div", "grid");
  const detected = asArray(state.outputs);
  for (const output of outputs) {
    const card = make("div", "card");
    card.append(make("h3", "", output.id + " / " + (output.role || "no role")));
    const list = make("dl", "kv");
    keyValue(list, "Connector", output.connector);
    keyValue(list, "Primary", output.primary ? "yes" : "no");
    const match = detected.find((item) => item.connector === output.connector);
    keyValue(
      list,
      "Detected",
      match ? match.width + "x" + match.height + " at " + match.x + "," + match.y : "not detected",
    );
    card.append(list);
    grid.append(card);
  }
  panel.append(grid);
  panel.append(
    make("p", "muted", "Role mapping is read-only in this shell; full editing arrives later."),
  );
}

// -- zone geometry --------------------------------------------------------

function snap(value) {
  // Zone geometry is normalized to two decimals.
  return Math.round(value * 100) / 100;
}

function clampAxis(value, minimum, maximum) {
  const bounded = Math.min(1, Math.max(0, value));
  return Math.min(Math.max(bounded, minimum), maximum);
}

function findZone(zoneId) {
  return asArray(state.config && state.config.zone).find((zone) => zone.id === zoneId) || null;
}

function zonesFor(outputId) {
  return asArray(state.config.zone).filter((zone) => zone.output === outputId);
}

function outputAspect(output) {
  const detected = asArray(state.outputs).find((item) => item.connector === output.connector);
  if (detected && detected.width > 0 && detected.height > 0) {
    return detected.width / detected.height;
  }
  return 16 / 9;
}

function placeZone(element, zone) {
  element.style.left = zone.x * 100 + "%";
  element.style.top = zone.y * 100 + "%";
  element.style.width = zone.w * 100 + "%";
  element.style.height = zone.h * 100 + "%";
}

// -- zone editing ---------------------------------------------------------

function dragZone(event, zone, handle) {
  if (event.button && event.button !== 0) return;
  const canvas = event.currentTarget.closest(".canvas");
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  event.preventDefault();

  const selectionChanged = state.selected.zone !== zone.id || state.selected.output !== zone.output;
  state.selected.zone = zone.id;
  state.selected.output = zone.output;
  state.drag = {
    zoneId: zone.id,
    resize: handle === true,
    moved: false,
    startX: event.clientX,
    startY: event.clientY,
    width: rect.width,
    height: rect.height,
    from: { x: zone.x, y: zone.y, w: zone.w, h: zone.h },
  };
  if (selectionChanged) render();
}

function moveDrag(event) {
  const drag = state.drag;
  if (!drag) return;
  const zone = findZone(drag.zoneId);
  if (!zone) {
    state.drag = null;
    return;
  }
  const dx = (event.clientX - drag.startX) / drag.width;
  const dy = (event.clientY - drag.startY) / drag.height;
  const from = drag.from;
  const next = { x: from.x, y: from.y, w: from.w, h: from.h };
  if (drag.resize) {
    next.w = snap(clampAxis(from.w + dx, ZONE_MIN, Math.max(0, ZONE_MAX - from.x)));
    next.h = snap(clampAxis(from.h + dy, ZONE_MIN, Math.max(0, ZONE_MAX - from.y)));
  } else {
    next.x = snap(clampAxis(from.x + dx, 0, Math.max(0, ZONE_MAX - from.w)));
    next.y = snap(clampAxis(from.y + dy, 0, Math.max(0, ZONE_MAX - from.h)));
  }
  if (next.x === zone.x && next.y === zone.y && next.w === zone.w && next.h === zone.h) {
    return;
  }
  zone.x = next.x;
  zone.y = next.y;
  zone.w = next.w;
  zone.h = next.h;
  drag.moved = true;
  const elements = document.querySelectorAll(".canvas .zone");
  for (const element of elements) {
    if (element.dataset.zoneId === zone.id) {
      placeZone(element, zone);
      break;
    }
  }
}

function endDrag() {
  const drag = state.drag;
  if (!drag) return;
  state.drag = null;
  if (drag.moved) {
    markDirty();
    render();
  }
}

function activeOutput() {
  const outputs = asArray(state.config && state.config.output);
  const zone = findZone(state.selected.zone);
  const owner = zone ? outputs.find((output) => output.id === zone.output) : null;
  if (owner) return owner;
  const selected = outputs.find((output) => output.id === state.selected.output);
  if (selected) return selected;
  return outputs.find((output) => output.primary) || outputs[0] || null;
}

function addZone(outputId) {
  if (!state.config) return null;
  const outputs = asArray(state.config.output);
  const output =
    outputs.find((item) => item.id === outputId) || outputs.find((item) => item.primary) || outputs[0];
  if (!output) return null;
  const zones = asArray(state.config.zone);
  const used = new Set(zones.map((zone) => zone.id));
  let index = 1;
  while (used.has("custom-" + index)) index += 1;
  const zone = {
    id: "custom-" + index,
    output: output.id,
    kind: "app",
    x: 0.1,
    y: 0.1,
    w: 0.3,
    h: 0.3,
    gap_px: 8,
  };
  zones.push(zone);
  state.config.zone = zones;
  state.selected.zone = zone.id;
  state.selected.output = output.id;
  markDirty();
  render();
  return zone;
}

function removeZone(zoneId) {
  const zone = findZone(zoneId);
  if (!zone) {
    setStatus("Select a zone before removing it.", "warn");
    return false;
  }
  const confirmed = window.confirm(
    "Remove zone " + zone.id + " and every placement that references it?",
  );
  if (!confirmed) {
    setStatus("Remove cancelled.", "warn");
    return false;
  }
  state.config.zone = asArray(state.config.zone).filter((item) => item.id !== zone.id);
  state.config.placement = asArray(state.config.placement).filter(
    (placement) => placement.zone !== zone.id,
  );
  if (state.selected.zone === zone.id) state.selected.zone = null;
  markDirty();
  render();
  return true;
}

function zoneElement(zone) {
  const element = make("div", "zone");
  element.dataset.zoneId = zone.id;
  placeZone(element, zone);
  element.setAttribute("role", "button");
  element.setAttribute("tabindex", "0");
  element.setAttribute(
    "aria-label",
    "Zone " + zone.id + ", " + zone.kind + ", x " + zone.x + ", y " + zone.y,
  );
  if (state.selected.zone === zone.id) {
    element.setAttribute("aria-selected", "true");
  }
  element.append(make("span", "zone-label", zone.id));

  const handle = make("span", "resize-zone");
  handle.dataset.handle = "resize";
  handle.title = "Resize zone " + zone.id;
  handle.setAttribute("role", "presentation");
  handle.addEventListener("pointerdown", function (event) {
    event.stopPropagation();
    dragZone(event, zone, true);
  });
  element.append(handle);

  element.addEventListener("pointerdown", function (event) {
    if (event.target.closest(".resize-zone")) return;
    dragZone(event, zone, false);
  });
  element.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    state.selected.zone = zone.id;
    state.selected.output = zone.output;
    render();
  });
  return element;
}

function renderLayout(panel) {
  heading(
    panel,
    "Layout",
    "Drag a zone to move it, or drag the handle in its corner to resize it. Edits stay local until Save or Apply.",
  );
  const outputs = asArray(state.config.output);
  if (!outputs.length) {
    panel.append(make("p", "muted", "Add an output before drawing zones."));
    return;
  }

  const preview = make("div", "layout-preview");
  for (const output of outputs) {
    const section = make("section", "output-panel");
    const title = make("h3", "", output.id + " / " + (output.role || "no role"));
    const detected = asArray(state.outputs).find((item) => item.connector === output.connector);
    const aspectText =
      detected && detected.width > 0 && detected.height > 0
        ? detected.width + "x" + detected.height + " detected"
        : "16:9 default";
    section.append(title, make("p", "muted", aspectText));

    const canvas = make("div", "canvas");
    canvas.dataset.outputId = output.id;
    canvas.style.aspectRatio = String(outputAspect(output));
    canvas.setAttribute("role", "group");
    canvas.setAttribute("aria-label", "Zone layout for " + output.id);
    canvas.addEventListener("pointerdown", function (event) {
      if (event.target !== canvas) return;
      state.selected.output = output.id;
      render();
    });

    const zones = zonesFor(output.id);
    for (const zone of zones) canvas.append(zoneElement(zone));
    section.append(canvas);
    if (!zones.length) {
      section.append(make("p", "muted", "No zones on this output yet."));
    }
    preview.append(section);
  }
  panel.append(preview);

  const target = activeOutput();
  const selected = findZone(state.selected.zone);
  const card = make("div", "card zone-card");
  if (selected) {
    card.append(make("h3", "", "Selected zone " + selected.id));
    const list = make("dl", "kv");
    keyValue(list, "Output", selected.output);
    keyValue(list, "Kind", selected.kind);
    keyValue(list, "Bounds", "x " + selected.x + " / y " + selected.y);
    keyValue(list, "Size", "w " + selected.w + " / h " + selected.h);
    keyValue(list, "Gap (px)", selected.gap_px);
    card.append(list);
  } else {
    card.append(make("h3", "", "No zone selected"));
    card.append(make("p", "muted", "Click a zone to select it. New zones go to the selected output."));
  }

  const buttons = make("div", "buttons");
  const addButton = make("button", "add-zone", "Add zone");
  addButton.type = "button";
  addButton.disabled = !target;
  addButton.setAttribute("aria-label", target ? "Add zone to " + target.id : "Add zone");
  addButton.addEventListener("click", function () {
    addZone(target ? target.id : null);
  });
  const removeButton = make("button", "remove-zone", "Remove zone");
  removeButton.type = "button";
  removeButton.disabled = !selected;
  removeButton.setAttribute(
    "aria-label",
    selected ? "Remove zone " + selected.id : "Remove zone",
  );
  removeButton.addEventListener("click", function () {
    removeZone(state.selected.zone);
  });
  buttons.append(addButton, removeButton);
  card.append(buttons);
  panel.append(card);
}

function renderPlacement(panel) {
  heading(
    panel,
    "Placement",
    "Each placement pins an app to a zone for one activity.",
  );
  table(
    panel,
    ["App", "Activity", "Zone", "Mode"],
    asArray(state.config.placement).map((placement) => [
      placement.app,
      placement.activity,
      placement.zone,
      placement.mode,
    ]),
  );
}

function listCard(panel, title, values) {
  const card = make("div", "card");
  card.append(make("h3", "", title));
  if (!values.length) {
    card.append(make("p", "muted", "None."));
  } else {
    const list = make("ul");
    for (const value of values) list.append(make("li", "", value));
    card.append(list);
  }
  panel.append(card);
}

function renderStartup(panel) {
  heading(panel, "Startup", "Apps started with every session or only with the private activity.");
  const startup = state.config.startup || {};
  const grid = make("div", "grid");
  panel.append(grid);
  listCard(grid, "Always", asArray(startup.always));
  listCard(grid, "Private", asArray(startup.private));
}

function renderAutostart(panel) {
  heading(panel, "Autostart", "First-entry app sets per activity role.");
  const autostart = state.config.autostart || {};
  const roles = Object.keys(autostart);
  if (!roles.length) {
    panel.append(make("p", "muted", "No autostart sections configured."));
    return;
  }
  const grid = make("div", "grid");
  panel.append(grid);
  for (const role of roles) {
    listCard(grid, role, asArray((autostart[role] || {}).apps));
  }
}

function jsonEditor(panel, title, initial, commit) {
  const label = make("label", "editor");
  label.append(make("span", "editor-label", title + " (JSON)"));
  const area = make("textarea", "json-editor");
  area.spellcheck = false;
  area.value = JSON.stringify(initial === undefined ? null : initial, null, 2);
  area.addEventListener("change", function () {
    try {
      const parsed = JSON.parse(area.value);
      commit(parsed);
      markDirty();
      render();
    } catch (error) {
      setStatus("Invalid JSON: " + (error && error.message ? error.message : error), "error");
    }
  });
  label.append(area);
  panel.append(label);
}

function renderWidgets(panel) {
  heading(panel, "Widgets", "Desktop widgets anchored to shell zones.");
  table(
    panel,
    ["Plugin", "Zone", "Scale"],
    asArray(state.config.desktop_widget).map((widget) => [
      widget.plugin,
      widget.zone,
      widget.scale,
    ]),
  );
  jsonEditor(panel, "desktop_widget", asArray(state.config.desktop_widget), function (value) {
    if (!Array.isArray(value)) {
      throw new Error("desktop_widget must be a JSON list.");
    }
    state.config.desktop_widget = value;
  });
}

function renderTheme(panel) {
  heading(panel, "Theme", "Wallpaper and rotation settings from the optional theme table.");
  const theme = state.config.theme;
  if (!theme) {
    panel.append(
      make(
        "p",
        "muted",
        "rice.toml has no theme table yet. Enter one as JSON to add it, or leave it empty.",
      ),
    );
  }
  jsonEditor(panel, "theme", theme || {}, function (value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error("theme must be a JSON object.");
    }
    state.config.theme = value;
  });
}

function renderApply(panel) {
  heading(
    panel,
    "Apply",
    "Apply saves the in-memory document, validates it, and runs the same pipeline as rice apply.",
  );
  const card = make("div", "card");
  const list = make("dl", "kv");
  keyValue(list, "Unsaved changes", state.dirty ? "yes" : "no");
  keyValue(list, "Validation errors", String(asArray(state.validation).length));
  keyValue(list, "Outputs", String(asArray(state.config.output).length));
  keyValue(list, "Zones", String(asArray(state.config.zone).length));
  keyValue(list, "Apps", String(asArray(state.config.app).length));
  card.append(list);
  panel.append(card);

  const errors = asArray(state.validation);
  if (errors.length) {
    const errorList = make("ul", "error-list");
    for (const error of errors) errorList.append(make("li", "", error));
    panel.append(make("h3", "", "Validation errors"), errorList);
  } else {
    panel.append(make("p", "muted", "No validation errors reported for the saved configuration."));
  }
}

const RENDERERS = {
  apps: renderApps,
  outputs: renderOutputs,
  layout: renderLayout,
  placement: renderPlacement,
  startup: renderStartup,
  autostart: renderAutostart,
  widgets: renderWidgets,
  theme: renderTheme,
  apply: renderApply,
};

// -- actions --------------------------------------------------------------

async function loadState() {
  await run(async function () {
    setStatus("Loading configuration...");
    const payload = await api("/api/state");
    state.config =
      payload && payload.config && typeof payload.config === "object" ? payload.config : null;
    state.validation = asArray(payload && payload.validation);
    state.outputs = asArray(payload && payload.outputs);
    state.catalog = payload ? payload.catalog : null;
    state.dirty = false;
    render();
    if (!state.config) {
      setStatus("No rice.toml could be loaded from the configured path.", "warn");
      return;
    }
    if (state.validation.length) {
      setStatus(
        state.validation.length + " validation error(s) in the saved configuration: " +
          state.validation.join("; "),
        "error",
      );
      return;
    }
    setStatus(
      "Loaded " +
        asArray(state.config.output).length +
        " output(s), " +
        asArray(state.config.zone).length +
        " zone(s), " +
        asArray(state.config.app).length +
        " app(s).",
      "ok",
    );
  });
}

async function validateDocument() {
  await run(async function () {
    setStatus("Validating the saved configuration...");
    const payload = await api("/api/validate", { method: "POST", body: {} });
    state.validation = asArray(payload && payload.errors);
    if (state.validation.length) {
      setStatus(
        state.validation.length + " validation error(s): " + state.validation.join("; "),
        "error",
      );
    } else {
      const suffix = state.dirty
        ? " Saved file is valid; unsaved edits are checked on Save or Apply."
        : "";
      setStatus("Configuration is valid." + suffix, "ok");
    }
    render();
  });
}

async function saveDocument() {
  await run(async function () {
    if (!state.config) throw new Error("There is no configuration to save.");
    setStatus("Saving...");
    await api("/api/config", { method: "PUT", body: { config: state.config } });
    const payload = await api("/api/validate", { method: "POST", body: {} });
    state.validation = asArray(payload && payload.errors);
    state.dirty = false;
    render();
    setStatus("Configuration saved.", "ok");
  });
}

function confirmApply() {
  return window.confirm("Save and apply this configuration to the desktop?");
}

async function applyDocument() {
  if (state.busy) return;
  if (!state.config) {
    setStatus("There is no configuration to apply.", "error");
    return;
  }
  if (!confirmApply()) {
    setStatus("Apply cancelled.", "warn");
    return;
  }
  await run(async function () {
    setStatus("Saving...");
    await api("/api/config", { method: "PUT", body: { config: state.config } });
    state.dirty = false;
    setStatus("Applying...");
    await api("/api/apply", { method: "POST", body: {} });
    render();
    setStatus("Configuration applied.", "ok");
  });
}

// -- startup --------------------------------------------------------------

window.addEventListener("beforeunload", function (event) {
  if (!state.dirty) return;
  event.preventDefault();
  event.returnValue = "";
});

function start() {
  bindTabs();
  elements.validate.addEventListener("click", validateDocument);
  elements.save.addEventListener("click", saveDocument);
  elements.apply.addEventListener("click", applyDocument);
  document.addEventListener("pointermove", moveDrag);
  document.addEventListener("pointerup", endDrag);
  document.addEventListener("pointercancel", endDrag);

  state.token = readToken();
  if (!state.token) {
    setStatus("No access token in the URL. Start the configurator with rice config.", "error");
    elements.panel.replaceChildren(
      make("h2", "", "Access token required"),
      make(
        "p",
        "muted",
        "Open the URL printed by rice config. It carries a per-session token in the query string.",
      ),
    );
    syncButtons();
    return;
  }

  loadState();
}

start();
