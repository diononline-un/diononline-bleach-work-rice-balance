local WIDTH = 830
local COLUMN_WIDTH = 260
local KEY_WIDTH = 174
local DESC_WIDTH = 126
local COLUMNS = 3
local CARD_BG = "surface_container_high"

local MOD = { fill = "#173f49", text = "#7fe3f2", border = "#2a8a9c" }
local CTRL = { fill = "#4a3d16", text = "#ffd479", border = "#9b7a22" }
local SHIFT = { fill = "#4d2c17", text = "#ffb86b", border = "#a5572a" }
local ALT = { fill = "#3d214a", text = "#d7a4ff", border = "#7b3e9b" }
local KEY = { fill = "#25292d", text = "#e8edf0", border = "#4b555d" }

local function capStyle(token)
  if token == "Meta" or token == "Super" or token == "Mod" then
    return MOD
  elseif token == "Ctrl" then
    return CTRL
  elseif token == "Shift" then
    return SHIFT
  elseif token == "Alt" then
    return ALT
  end
  return KEY
end

local groups = {
  {
    title = "Focus & Activities",
    accent = "#7fd1a7",
    rows = {
      { "Ctrl+Alt+1", "Work activity" },
      { "Ctrl+Alt+2", "Private activity" },
      { "Ctrl+Alt+Shift+1", "Quickstart work" },
      { "Ctrl+Alt+Shift+2", "Quickstart private" },
      { "Ctrl+Alt+Shift+Space", "Quickstart current" },
    },
  },
  {
    title = "Windows",
    accent = "#ff9b6b",
    rows = {
      { "Meta+M", "Maximize" },
      { "Meta+N", "Minimize" },
      { "Meta+Q", "Close" },
      { "Meta+H", "Tile left" },
      { "Meta+J", "Tile right" },
      { "Meta+Left", "Previous window" },
      { "Meta+Right", "Next window" },
      { "Meta+T", "Tile editor" },
      { "Ctrl+Alt+R", "Apply layout" },
    },
  },
  {
    title = "Move & Displays",
    accent = "#f2c14e",
    rows = {
      { "Meta+1", "Move to main" },
      { "Meta+2", "Move to side" },
      { "Meta+3", "Move to portrait" },
      { "Meta+Return", "Terminal" },
      { "Meta+Shift+Return", "Alternate terminal" },
    },
  },
  {
    title = "Themes",
    accent = "#c79bff",
    rows = {
      { "Ctrl+Alt+Shift+Left", "Previous theme" },
      { "Ctrl+Alt+Shift+Right", "Next theme" },
    },
  },
  {
    title = "Media & Clipboard",
    accent = "#7eb8ff",
    rows = {
      { "Ctrl+Alt+V", "Clipboard history" },
    },
  },
  {
    title = "Shell",
    accent = "#7fd1a7",
    rows = {
      { "Meta", "Noctalia launcher" },
      { "Ctrl+Alt+S", "Control Center" },
      { "Ctrl+Alt+P", "Noctalia Settings" },
      { "Ctrl+Alt+H", "Shortcut sheet" },
      { "Meta+W", "Overview" },
      { "Meta+D", "Show desktop" },
    },
  },
  {
    title = "Recording",
    accent = "#ff8fa3",
    rows = {
      { "F8", "GPU recorder" },
      { "F9", "GPU recorder" },
    },
  },
}

local query = ""
local render

local function keycap(token)
  local style = capStyle(token)
  local label = (token == "Meta" or token == "Super") and "Mod" or token
  return ui.row({
    height = 24,
    align = "center",
    justify = "center",
    fill = style.fill,
    radius = 6,
    paddingH = 7,
    border = style.border,
    borderWidth = 1,
  }, {
    ui.label({
      text = label,
      fontSize = 11,
      fontWeight = "semibold",
      color = style.text,
      maxLines = 1,
    }),
  })
end

local function keycaps(sequence)
  local children = {}
  local first = true
  for part in string.gmatch(sequence, "[^+]+") do
    if not first then
      table.insert(children, ui.label({ text = "+", fontSize = 10, color = "#7c8790" }))
    end
    table.insert(children, keycap(part))
    first = false
  end
  return ui.row({ gap = 3, align = "center", width = KEY_WIDTH }, children)
end

local function shortcutRow(key, description)
  return ui.row({ gap = 8, align = "center", width = COLUMN_WIDTH }, {
    keycaps(key),
    ui.label({
      text = description,
      width = DESC_WIDTH,
      fontSize = 12,
      color = "#e8edf0",
      maxLines = 2,
    }),
  })
end

local function matches(key, description)
  if query == "" then
    return true
  end
  local needle = string.lower(query)
  return string.find(string.lower(key), needle, 1, true) ~= nil
    or string.find(string.lower(description), needle, 1, true) ~= nil
end

local function visibleGroups()
  local result = {}
  for _, group in ipairs(groups) do
    local rows = {}
    for _, row in ipairs(group.rows) do
      if matches(row[1], row[2]) then
        table.insert(rows, row)
      end
    end
    if #rows > 0 then
      table.insert(result, { title = group.title, accent = group.accent, rows = rows })
    end
  end
  return result
end

local function groupCard(group)
  local children = {
    ui.row({ gap = 7, align = "center" }, {
      ui.label({ text = "●", fontSize = 14, color = group.accent }),
      ui.label({
        text = string.upper(group.title),
        fontSize = 11,
        fontWeight = "bold",
        color = "#e8edf0",
      }),
    }),
  }
  for _, row in ipairs(group.rows) do
    table.insert(children, shortcutRow(row[1], row[2]))
  end
  return ui.column({
    gap = 7,
    width = COLUMN_WIDTH,
    align = "stretch",
    fill = CARD_BG,
    padding = 10,
    radius = 10,
    border = group.accent,
    borderWidth = 1,
  }, children)
end

local function modifierLegend()
  local items = {
    { "Mod", MOD, "= Super" },
    { "Ctrl", CTRL, "" },
    { "Shift", SHIFT, "" },
    { "Alt", ALT, "" },
  }
  local children = {
    ui.label({ text = "MODIFIERS:", fontSize = 11, fontWeight = "bold", color = "#7c8790" }),
  }
  for _, item in ipairs(items) do
    table.insert(children, keycap(item[1]))
    if item[3] ~= "" then
      table.insert(children, ui.label({ text = item[3], fontSize = 11, color = "#aab4bb" }))
    end
  end
  return ui.row({ width = WIDTH, gap = 8, align = "center" }, children)
end

render = function()
  local shown = visibleGroups()
  local shortcut_count = 0
  for _, group in ipairs(shown) do
    shortcut_count = shortcut_count + #group.rows
  end
  local columns = { {}, {}, {} }
  for index, group in ipairs(shown) do
    table.insert(columns[((index - 1) % COLUMNS) + 1], group)
  end

  local columnNodes = {}
  for index = 1, COLUMNS do
    local nodes = {}
    for _, group in ipairs(columns[index]) do
      table.insert(nodes, groupCard(group))
    end
    table.insert(columnNodes, ui.column({ gap = 10, width = COLUMN_WIDTH, align = "stretch" }, nodes))
  end

  local body
  if #shown == 0 then
    body = ui.column({ width = WIDTH, gap = 6, align = "center" }, {
      ui.glyph({ name = "search", size = 28, color = "#7c8790" }),
      ui.label({ text = "No shortcuts found.", fontSize = 15, color = "#aab4bb" }),
    })
  else
    body = ui.row({ gap = 10, align = "start", width = WIDTH }, columnNodes)
  end

  panel.render(ui.column({
    flexGrow = 1,
    gap = 12,
    align = "stretch",
    fill = "surface_container",
    radius = 18,
    padding = 16,
  }, {
    ui.row({ width = WIDTH, gap = 10, align = "center" }, {
      ui.input({
        key = "shortcut-search",
        width = WIDTH - 120,
        placeholder = "Search shortcuts...",
        fontSize = 14,
        controlSize = "sm",
        value = query,
        focus = true,
        onChange = "onSearch",
      }),
      ui.label({ text = string.format("%d shortcuts", shortcut_count), fontSize = 12, color = "#7c8790" }),
    }),
    modifierLegend(),
    ui.separator({ spacing = 2 }),
    body,
  }))
end

function onSearch(value)
  query = value or ""
  render()
end

function onOpen(_context)
  query = ""
  render()
end
