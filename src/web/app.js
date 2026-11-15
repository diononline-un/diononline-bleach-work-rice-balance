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
  applyError: "",
};

const ZONE_MIN = 0.05;
const ZONE_MAX = 1;

const ROLE_CHOICES = ["main", "side", "portrait", "custom"];
const STANDARD_ROLES = ROLE_CHOICES.filter((role) => role !== "custom");
const PLACEMENT_MODES = ["normal", "maximized", "fullscreen"];
const STARTUP_KEYS = [
  { key: "always", label: "Always" },
  { key: "private", label: "Private" },
];

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
    const error = new Error(errorMessage(payload, response.status));
    error.status = response.status;
    error.payload = payload;
    error.errors = payload && Array.isArray(payload.errors) ? payload.errors : [];
    throw error;
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
      const cellElement = make("td");
      if (cell instanceof Node) {
        cellElement.append(cell);
      } else {
        cellElement.textContent = cell === undefined || cell === null ? "" : String(cell);
      }
      rowElement.append(cellElement);
    }
    tbody.append(rowElement);
  }
  tableElement.append(thead, tbody);
  wrap.append(tableElement);
  panel.append(wrap);
}

// -- form helpers ---------------------------------------------------------

function commitEdit(needsRender) {
  markDirty();
  if (needsRender) render();
}

function inputValue(value) {
  return value === undefined || value === null ? "" : String(value);
}

function splitList(value) {
  const items = String(value === undefined || value === null ? "" : value).split(",");
  const cleaned = [];
  for (const item of items) {
    const trimmed = item.trim();
    if (trimmed) cleaned.push(trimmed);
  }
  return cleaned;
}

function textField(value, commit, options) {
  const settings = options || {};
  const input = make("input", "input");
  input.type = "text";
  input.value = inputValue(value);
  if (settings.placeholder) input.placeholder = settings.placeholder;
  if (settings.ariaLabel) input.setAttribute("aria-label", settings.ariaLabel);
  input.addEventListener("change", function () {
    commit(input.value, input);
    commitEdit(settings.rerender === true);
  });
  return input;
}

function numberField(value, commit, options) {
  const settings = options || {};
  const input = make("input", "input input-number");
  input.type = "number";
  input.step = settings.step || "1";
  input.value = typeof value === "number" && Number.isFinite(value) ? String(value) : "";
  if (settings.ariaLabel) input.setAttribute("aria-label", settings.ariaLabel);
  input.addEventListener("change", function () {
    const parsed = Number(input.value);
    commit(Number.isFinite(parsed) ? parsed : 0);
    commitEdit(settings.rerender === true);
  });
  return input;
}

function optionList(options) {
  return options.map(function (option) {
    return typeof option === "string" ? { value: option, label: option } : option;
  });
}

function selectField(value, options, commit, ariaLabel) {
  const select = make("select", "input input-select");
  const seen = new Set();
  for (const option of optionList(options)) {
    const element = make("option", "", option.label);
    element.value = option.value;
    seen.add(String(option.value));
    select.append(element);
  }
  const current = inputValue(value);
  if (current && !seen.has(current)) {
    const element = make("option", "", current);
    element.value = current;
    select.append(element);
  }
  select.value = current;
  if (ariaLabel) select.setAttribute("aria-label", ariaLabel);
  select.addEventListener("change", function () {
    commit(select.value);
    commitEdit(false);
  });
  return select;
}

function multiSelectField(values, options, commit, ariaLabel) {
  const select = make("select", "input input-select multiselect");
  select.multiple = true;
  const entries = optionList(options);
  select.size = String(Math.min(Math.max(entries.length, 3), 8));
  const selected = new Set(asArray(values));
  for (const option of entries) {
    const element = make("option", "", option.label);
    element.value = option.value;
    if (selected.has(option.value)) element.selected = true;
    select.append(element);
  }
  if (ariaLabel) select.setAttribute("aria-label", ariaLabel);
  select.addEventListener("change", function () {
    const picked = [];
    for (const option of select.selectedOptions) picked.push(option.value);
    commit(picked);
    commitEdit(false);
  });
  return select;
}

function checkboxField(checked, labelText, commit, ariaLabel) {
  const label = make("label", "check-item");
  const input = make("input");
  input.type = "checkbox";
  input.checked = checked === true;
  if (ariaLabel) input.setAttribute("aria-label", ariaLabel);
  input.addEventListener("change", function () {
    commit(input.checked);
    commitEdit(false);
  });
  label.append(input, make("span", "", labelText));
  return label;
}

function plainCheckbox(checked, commit, ariaLabel) {
  const input = make("input");
  input.type = "checkbox";
  input.checked = checked === true;
  input.setAttribute("aria-label", ariaLabel);
  input.addEventListener("change", function () {
    commit(input.checked);
    commitEdit(false);
  });
  return input;
}

function actionButton(label, ariaLabel, onClick, className) {
  const element = make("button", className || "", label);
  element.type = "button";
  if (ariaLabel) element.setAttribute("aria-label", ariaLabel);
  element.addEventListener("click", onClick);
  return element;
}

function removeButton(ariaLabel, onClick) {
  return actionButton("Remove", ariaLabel, onClick, "row-remove");
}

// -- config readers -------------------------------------------------------

function configObject(key) {
  const value = state.config ? state.config[key] : null;
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function appIds() {
  return asArray(state.config && state.config.app)
    .map((app) => app.id)
    .filter((id) => typeof id === "string" && id);
}

function activityRoles() {
  return Object.keys(configObject("activities"));
}

function activityOptions() {
  const activities = configObject("activities");
  return activityRoles().map(function (role) {
    const entry = activities[role];
    const name = entry && typeof entry === "object" ? entry.name : "";
    return { value: role, label: name ? role + " (" + name + ")" : role };
  });
}

function zoneOptions() {
  return asArray(state.config && state.config.zone).map(function (zone) {
    return { value: zone.id, label: zone.id + " (" + zone.kind + ")" };
  });
}

// -- apps -----------------------------------------------------------------

function newAppId() {
  const used = new Set(appIds());
  let index = 1;
  while (used.has("custom-app-" + index)) index += 1;
  return "custom-app-" + index;
}

function addApp() {
  if (!state.config) return;
  const apps = asArray(state.config.app);
  apps.push({
    id: newAppId(),
    name: "New app",
    command: ["true"],
    wm_class: "",
    activities: [],
  });
  state.config.app = apps;
  commitEdit(true);
}

function removeApp(index) {
  const apps = asArray(state.config.app);
  const app = apps[index];
  if (!app) return;
  const confirmed = window.confirm(
    "Remove app " + app.id + " and every placement, startup, and autostart reference?",
  );
  if (!confirmed) {
    setStatus("Remove cancelled.", "warn");
    return;
  }
  state.config.app = apps.filter((item, position) => position !== index);
  state.config.placement = asArray(state.config.placement).filter(
    (placement) => placement.app !== app.id,
  );
  const startup = configObject("startup");
  for (const entry of STARTUP_KEYS) {
    if (!Array.isArray(startup[entry.key])) continue;
    startup[entry.key] = startup[entry.key].filter((id) => id !== app.id);
  }
  const autostart = configObject("autostart");
  for (const role of Object.keys(autostart)) {
    const section = autostart[role];
    if (!section || !Array.isArray(section.apps)) continue;
    section.apps = section.apps.filter((id) => id !== app.id);
  }
  commitEdit(true);
}

function renderApps(panel) {
  heading(
    panel,
    "Apps",
    "Declared applications. Commands are argv lists split on commas and never pass through a shell.",
  );
  const apps = asArray(state.config.app);
  const rows = apps.map(function (app, index) {
    const label = app.id || "app " + (index + 1);
    return [
      textField(app.id, (value) => { app.id = value.trim(); }, {
        placeholder: "app-id",
        ariaLabel: "Id for " + label,
      }),
      textField(app.name || "", (value) => { app.name = value; }, {
        placeholder: "Display name",
        ariaLabel: "Name for " + label,
      }),
      textField(asArray(app.command).join(", "), (value) => {
        app.command = splitList(value);
      }, {
        placeholder: "firefox, --new-window",
        ariaLabel: "Command argv for " + label,
      }),
      textField(app.wm_class || "", (value) => { app.wm_class = value; }, {
        placeholder: "firefox",
        ariaLabel: "Window class for " + label,
      }),
      textField(asArray(app.activities).join(", "), (value) => {
        app.activities = splitList(value);
      }, {
        placeholder: "work, private",
        ariaLabel: "Activities for " + label,
      }),
      removeButton("Remove app " + label, function () { removeApp(index); }),
    ];
  });
  table(
    panel,
    [
      "Id",
      "Name",
      "Command (argv, comma-separated)",
      "Window class",
      "Activities (comma-separated)",
      "Actions",
    ],
    rows,
  );
  const actions = make("div", "table-actions");
  actions.append(
    actionButton("Add app", "Add a custom app", function () { addApp(); }),
  );
  panel.append(actions);

  const catalog = state.catalog;
  if (catalog && typeof catalog === "object") {
    const slots = Object.keys(catalog);
    if (slots.length) {
      panel.append(
        make("p", "muted", "Installer catalog slots: " + slots.join(", ") + "."),
      );
    }
  }
}

// -- outputs --------------------------------------------------------------

function isCustomRole(role) {
  return typeof role !== "string" || role === "" || !STANDARD_ROLES.includes(role);
}

function outputRoleValue(output) {
  return isCustomRole(output.role) ? "custom" : output.role;
}

function chooseOutputRole(output, value) {
  if (value === "custom") {
    if (!isCustomRole(output.role)) output.role = "custom";
  } else {
    output.role = value;
  }
  commitEdit(true);
}

function detectedFor(connector) {
  return (
    asArray(state.outputs).find((item) => item.connector === connector) || null
  );
}

function renderOutputs(panel) {
  heading(
    panel,
    "Outputs",
    "Output roles decide which physical display receives which layout. Connectors come from the detected outputs and the saved configuration.",
  );
  const outputs = asArray(state.config.output);
  if (!outputs.length) {
    panel.append(make("p", "muted", "No outputs configured."));
    return;
  }
  const rows = outputs.map(function (output) {
    const label = output.id || output.connector || "output";
    const detected = detectedFor(output.connector);
    const detectedText = detected
      ? detected.width + "x" + detected.height + " at " + detected.x + "," + detected.y
      : "not detected";
    const customInput = textField(
      isCustomRole(output.role) ? output.role : "",
      (value) => { output.role = value.trim(); },
      { placeholder: "custom role", ariaLabel: "Custom role for " + label },
    );
    customInput.disabled = !isCustomRole(output.role);
    return [
      make("span", "mono", output.id),
      make("span", "mono", output.connector || ""),
      make("span", "cell-note", detectedText),
      selectField(
        outputRoleValue(output),
        ROLE_CHOICES,
        (value) => { chooseOutputRole(output, value); },
        "Role for " + label,
      ),
      customInput,
      plainCheckbox(
        output.primary === true,
        (value) => { output.primary = value; },
        "Primary output " + label,
      ),
    ];
  });
  table(
    panel,
    ["Output", "Connector", "Detected", "Role", "Custom role", "Primary"],
    rows,
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
  if (Array.isArray(state.config.desktop_widget)) {
    state.config.desktop_widget = state.config.desktop_widget.filter(
      (widget) => widget.zone !== zone.id,
    );
  }
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

// -- placement ------------------------------------------------------------

function addPlacement() {
  if (!state.config) return;
  const placements = asArray(state.config.placement).slice();
  placements.push({
    app: appIds()[0] || "",
    activity: activityRoles()[0] || "",
    zone: asArray(state.config.zone)[0] ? state.config.zone[0].id : "",
    mode: "normal",
    priority: 0,
  });
  state.config.placement = placements;
  commitEdit(true);
}

function removePlacement(index) {
  const placements = asArray(state.config.placement);
  if (!placements[index]) return;
  state.config.placement = placements.filter((item, position) => position !== index);
  commitEdit(true);
}

function renderPlacement(panel) {
  heading(
    panel,
    "Placement",
    "Each placement pins an app to a zone for one activity. Choices come from the apps, activities, and zones in this configuration.",
  );
  const apps = appIds();
  const activities = activityOptions();
  const zones = zoneOptions();
  const rows = asArray(state.config.placement).map(function (placement, index) {
    const label = "placement " + (index + 1);
    return [
      selectField(placement.app, apps, (value) => { placement.app = value; }, "App for " + label),
      selectField(
        placement.activity,
        activities,
        (value) => { placement.activity = value; },
        "Activity for " + label,
      ),
      selectField(
        placement.zone,
        zones,
        (value) => { placement.zone = value; },
        "Zone for " + label,
      ),
      selectField(
        placement.mode,
        PLACEMENT_MODES,
        (value) => { placement.mode = value; },
        "Mode for " + label,
      ),
      numberField(
        typeof placement.priority === "number" ? placement.priority : 0,
        (value) => { placement.priority = value; },
        { step: "1", ariaLabel: "Priority for " + label },
      ),
      removeButton("Remove " + label, function () { removePlacement(index); }),
    ];
  });
  table(panel, ["App", "Activity", "Zone", "Mode", "Priority", "Actions"], rows);
  const actions = make("div", "table-actions");
  actions.append(
    actionButton("Add placement", "Add a placement row", function () { addPlacement(); }),
  );
  panel.append(actions);
}

// -- startup --------------------------------------------------------------

function startupList(key, create) {
  const startup = configObject("startup");
  if (Array.isArray(startup[key])) return startup[key];
  if (!create) return [];
  if (!state.config.startup || typeof state.config.startup !== "object") {
    state.config.startup = {};
  }
  state.config.startup[key] = [];
  return state.config.startup[key];
}

function toggleStartup(key, appId, enabled) {
  const current = startupList(key, true);
  const next = enabled
    ? current.concat([appId])
    : current.filter((id) => id !== appId);
  const unique = Array.from(new Set(next));
  state.config.startup[key] = unique;
}

function renderStartup(panel) {
  heading(
    panel,
    "Startup",
    "Apps started with every session or only with the private activity. Checked entries are written to startup.always or startup.private.",
  );
  const apps = appIds();
  const grid = make("div", "grid");
  panel.append(grid);
  if (!apps.length) {
    panel.append(make("p", "muted", "Add an app before choosing startup entries."));
    return;
  }
  for (const entry of STARTUP_KEYS) {
    const card = make("div", "card");
    const list = startupList(entry.key, false);
    card.append(make("h3", "", entry.label));
    const field = make("fieldset", "check-list");
    field.append(make("legend", "", entry.label + " startup"));
    for (const appId of apps) {
      const checked = list.includes(appId);
      field.append(
        checkboxField(
          checked,
          appId,
          (value) => { toggleStartup(entry.key, appId, value); },
          "Start " + appId + " with " + entry.label.toLowerCase(),
        ),
      );
    }
    card.append(field);
    grid.append(card);
  }
}

// -- autostart ------------------------------------------------------------

function autostartRoles() {
  const roles = activityRoles();
  for (const role of Object.keys(configObject("autostart"))) {
    if (!roles.includes(role)) roles.push(role);
  }
  return roles;
}

function autostartApps(role) {
  const section = configObject("autostart")[role];
  return section && Array.isArray(section.apps) ? section.apps : [];
}

function toggleAutostart(role, appId, enabled) {
  if (!state.config.autostart || typeof state.config.autostart !== "object") {
    state.config.autostart = {};
  }
  const section = state.config.autostart[role];
  const current = section && Array.isArray(section.apps) ? section.apps : [];
  const next = enabled ? current.concat([appId]) : current.filter((id) => id !== appId);
  const base = section && typeof section === "object" ? section : {};
  state.config.autostart[role] = Object.assign({}, base, {
    apps: Array.from(new Set(next)),
  });
}

function renderAutostart(panel) {
  heading(
    panel,
    "Autostart",
    "First-entry app sets per activity role. Checked apps are written to autostart.<role>.apps.",
  );
  const apps = appIds();
  const roles = autostartRoles();
  if (!roles.length) {
    panel.append(make("p", "muted", "No activity roles configured."));
    return;
  }
  if (!apps.length) {
    panel.append(make("p", "muted", "Add an app before choosing autostart entries."));
  }
  const grid = make("div", "grid");
  panel.append(grid);
  for (const role of roles) {
    const card = make("div", "card");
    const activities = configObject("activities");
    const name = activities[role] && activities[role].name;
    card.append(make("h3", "", name ? name + " (" + role + ")" : role));
    const current = autostartApps(role);
    const field = make("fieldset", "check-list");
    field.append(make("legend", "", role + " autostart"));
    if (!apps.length) {
      field.append(make("p", "muted", "No apps declared."));
    }
    for (const appId of apps) {
      field.append(
        checkboxField(
          current.includes(appId),
          appId,
          (value) => { toggleAutostart(role, appId, value); },
          "Autostart " + appId + " on " + role,
        ),
      );
    }
    card.append(field);
    grid.append(card);
  }
}

// -- widgets --------------------------------------------------------------

function shellZoneOptions() {
  const zones = asArray(state.config && state.config.zone);
  const shell = zones.filter((zone) => zone.kind === "shell");
  const ordered = shell.concat(zones.filter((zone) => zone.kind !== "shell"));
  return ordered.map(function (zone) {
    return { value: zone.id, label: zone.id + " (" + zone.kind + ")" };
  });
}

function addWidget() {
  if (!state.config) return;
  const zones = shellZoneOptions();
  const widgets = asArray(state.config.desktop_widget).slice();
  widgets.push({
    plugin: "clock",
    zone: zones.length ? zones[0].value : "",
    scale: 1.0,
  });
  state.config.desktop_widget = widgets;
  commitEdit(true);
}

function removeWidget(index) {
  const widgets = asArray(state.config.desktop_widget);
  if (!widgets[index]) return;
  state.config.desktop_widget = widgets.filter((item, position) => position !== index);
  commitEdit(true);
}

function renderWidgets(panel) {
  heading(
    panel,
    "Widgets",
    "Desktop widgets anchored to shell zones. The generated key is derived from the widget order in rice.toml.",
  );
  const zones = shellZoneOptions();
  const rows = asArray(state.config.desktop_widget).map(function (widget, index) {
    const label = "widget rice_" + index;
    return [
      make("span", "mono", "rice_" + index),
      textField(widget.plugin || "", (value) => { widget.plugin = value.trim(); }, {
        placeholder: "clock",
        ariaLabel: "Plugin for " + label,
      }),
      selectField(widget.zone, zones, (value) => { widget.zone = value; }, "Zone for " + label),
      numberField(
        typeof widget.scale === "number" ? widget.scale : 1.0,
        (value) => { widget.scale = value; },
        { step: "0.05", ariaLabel: "Scale for " + label },
      ),
      removeButton("Remove " + label, function () { removeWidget(index); }),
    ];
  });
  table(panel, ["Key", "Plugin", "Zone", "Scale", "Actions"], rows);
  if (!zones.length) {
    panel.append(make("p", "muted", "Add a zone before adding a widget."));
  }
  const actions = make("div", "table-actions");
  const addButton = actionButton(
    "Add widget",
    "Add a desktop widget",
    function () { addWidget(); },
  );
  addButton.disabled = !zones.length;
  actions.append(addButton);
  panel.append(actions);
}

// -- theme ----------------------------------------------------------------

function themeObject() {
  const theme = state.config ? state.config.theme : null;
  return theme && typeof theme === "object" && !Array.isArray(theme) ? theme : null;
}

function updateTheme(key, value) {
  if (!state.config) return;
  if (!state.config.theme || typeof state.config.theme !== "object" || Array.isArray(state.config.theme)) {
    state.config.theme = {};
  }
  state.config.theme[key] = value;
}

function themeValue(key, fallback) {
  const theme = themeObject();
  if (!theme || theme[key] === undefined || theme[key] === null) return fallback;
  return theme[key];
}

function themeOutputOptions() {
  const options = [];
  const seen = new Set();
  const add = function (value, label) {
    if (typeof value !== "string" || !value || seen.has(value)) return;
    seen.add(value);
    options.push({ value: value, label: label });
  };
  for (const output of asArray(state.config.output)) {
    add(output.connector, output.id + " (" + output.connector + ")");
  }
  for (const detected of asArray(state.outputs)) {
    add(detected.connector, detected.connector + " (detected)");
  }
  const theme = themeObject();
  for (const value of asArray(theme && theme.outputs)) {
    add(value, value + " (configured)");
  }
  return options;
}

function renderTheme(panel) {
  heading(
    panel,
    "Theme",
    "Wallpaper directory, target connectors, and rotation intent from the optional theme table.",
  );
  if (!themeObject()) {
    panel.append(
      make(
        "p",
        "muted",
        "rice.toml has no [theme] table yet. Editing any field adds it on the next Save or Apply.",
      ),
    );
  }
  const form = make("div", "form-grid");

  const directory = make("label", "field wide");
  directory.append(make("span", "field-label", "Wallpaper directory"));
  directory.append(
    textField(
      themeValue("wallpaper_dir", ""),
      (value) => { updateTheme("wallpaper_dir", value.trim()); },
      { placeholder: "~/Pictures/rice-wallpapers", ariaLabel: "Wallpaper directory" },
    ),
  );
  form.append(directory);

  const outputs = make("label", "field");
  outputs.append(make("span", "field-label", "Outputs (connector names)"));
  outputs.append(
    multiSelectField(
      themeValue("outputs", []),
      themeOutputOptions(),
      (values) => { updateTheme("outputs", values); },
      "Theme outputs",
    ),
  );
  form.append(outputs);

  const rotation = make("label", "field");
  rotation.append(make("span", "field-label", "Rotation intent"));
  rotation.append(
    textField(
      themeValue("rotation", ""),
      (value) => { updateTheme("rotation", value.trim()); },
      { placeholder: "hourly", ariaLabel: "Rotation intent" },
    ),
  );
  form.append(rotation);

  const toggles = make("fieldset", "field check-list");
  toggles.append(make("legend", "field-label", "Flags"));
  toggles.append(
    checkboxField(
      themeValue("same_image_all_outputs", true) === true,
      "Same image on all outputs",
      (value) => { updateTheme("same_image_all_outputs", value); },
      "Same image on all outputs",
    ),
  );
  toggles.append(
    checkboxField(
      themeValue("pause_on_fullscreen", true) === true,
      "Pause rotation on fullscreen",
      (value) => { updateTheme("pause_on_fullscreen", value); },
      "Pause rotation on fullscreen",
    ),
  );
  toggles.append(
    checkboxField(
      themeValue("pause_on_idle", true) === true,
      "Pause rotation when idle",
      (value) => { updateTheme("pause_on_idle", value); },
      "Pause rotation when idle",
    ),
  );
  form.append(toggles);
  panel.append(form);
  panel.append(
    make(
      "p",
      "muted",
      "Theme outputs are connector names. Pick them from the outputs above or the detected displays.",
    ),
  );
}

function renderApply(panel) {
  heading(
    panel,
    "Apply",
    "Apply saves the in-memory document, validates it, and runs the same pipeline as rice apply. Errors from validation and from the apply run appear here.",
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

  if (state.applyError) {
    const errorPanel = make("div", "card apply-error");
    errorPanel.setAttribute("role", "alert");
    errorPanel.append(make("h3", "", "Apply did not complete"));
    errorPanel.append(make("p", "apply-error-text", state.applyError));
    panel.append(errorPanel);
  }

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
    state.applyError = "";
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

function recordFailure(error) {
  state.applyError = error && error.message ? error.message : String(error);
  const errors = asArray(error && error.errors);
  if (errors.length) state.validation = errors;
  render();
  setStatus(state.applyError, "error");
}

async function validateDocument() {
  await run(async function () {
    setStatus("Validating the saved configuration...");
    const payload = await api("/api/validate", { method: "POST", body: {} });
    state.validation = asArray(payload && payload.errors);
    state.applyError = "";
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
    try {
      await api("/api/config", { method: "PUT", body: { config: state.config } });
    } catch (error) {
      recordFailure(error);
      return;
    }
    state.dirty = false;
    state.applyError = "";
    try {
      const payload = await api("/api/validate", { method: "POST", body: {} });
      state.validation = asArray(payload && payload.errors);
    } catch (error) {
      recordFailure(error);
      return;
    }
    render();
    if (state.validation.length) {
      setStatus(
        "Saved, but the validation endpoint reports " +
          state.validation.length +
          " error(s): " +
          state.validation.join("; "),
        "error",
      );
      return;
    }
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
    state.applyError = "";
    setStatus("Saving configuration...");
    try {
      await api("/api/config", { method: "PUT", body: { config: state.config } });
    } catch (error) {
      recordFailure(error);
      return;
    }
    state.dirty = false;
    state.validation = [];
    setStatus("Applying...");
    try {
      await api("/api/apply", { method: "POST", body: {} });
    } catch (error) {
      recordFailure(error);
      return;
    }
    render();
    setStatus("Configuration applied. The desktop now uses this configuration.", "ok");
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
