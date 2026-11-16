local WIDTH = 830
local COLUMN_WIDTH = 260
local KEY_WIDTH = 142
local DESC_WIDTH = 138
local COLUMNS = 3

local function channel(value)
  local v = tonumber(value, 16) / 255
  if v <= 0.03928 then
    return v / 12.92
  end
  return ((v + 0.055) / 1.055) ^ 2.4
end

local function luminance(hex)
  if type(hex) ~= "string" then
    return 0.5
  end
  local r, g, b = string.match(hex, "^#(%x%x)(%x%x)(%x%x)")
  if r == nil then
    return 0.5
  end
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
end

local function inkFor(role)
  local value = noctalia.getColor(role)
  if type(value) ~= "string" then
    return noctalia.isDarkMode() and "#f7f7f7" or "#111111"
  end
  if luminance(value) > 0.5 then
    return "#111111"
  end
  return "#f7f7f7"
end

local function mutedFor(role)
  local value = noctalia.getColor(role)
  if type(value) ~= "string" then
    return noctalia.isDarkMode() and "#c8c8c8" or "#333333"
  end
  if luminance(value) > 0.5 then
    return "#333333"
  end
  return "#c8c8c8"
end

local INK = inkFor("surface_container")
local MUTED = mutedFor("surface_container")
local KEY_INK = inkFor("surface_container_high")
local KEY_BG = "surface_container_high"
local CARD_BG = "surface_container_high"

local groups = {
  {
    title = "Activities",
    rows = {
      { "Ctrl+Alt+1", "Work" },
      { "Ctrl+Alt+2", "Private" },
    },
  },
  {
    title = "Quickstart",
    rows = {
      { "Ctrl+Alt+Shift+1", "Work + apps" },
      { "Ctrl+Alt+Shift+2", "Private + apps" },
      { "Ctrl+Alt+Shift+Space", "Current area" },
    },
  },
  {
    title = "Windows",
    rows = {
      { "Meta+T", "Tile editor" },
      { "Ctrl+Alt+R", "Apply window layout" },
    },
  },
  {
    title = "Shell",
    rows = {
      { "Super", "Noctalia launcher" },
      { "Ctrl+Alt+S", "Control Center" },
      { "Ctrl+Alt+P", "Noctalia Settings" },
      { "Ctrl+Alt+H", "Shortcut sheet" },
      { "Meta+W", "Overview" },
      { "Meta+D", "Show desktop" },
    },
  },
  {
    title = "Themes",
    rows = {
      { "Ctrl+Alt+Shift+Left", "Previous theme" },
      { "Ctrl+Alt+Shift+Right", "Next theme" },
    },
  },
  {
    title = "Media",
    rows = {
      { "Ctrl+Alt+V", "Clipboard history" },
    },
  },
  {
    title = "Recording",
    rows = {
      { "F8 / F9", "GPU recorder" },
    },
  },
  {
    title = "Active window",
    rows = {
      { "Meta+M", "Maximize" },
      { "Meta+N", "Minimize" },
      { "Meta+Q", "Close" },
      { "Meta+H", "Left half" },
      { "Meta+J", "Right half" },
      { "Meta+Return", "Terminal" },
      { "Meta+Shift+Return", "Alternate terminal" },
      { "Meta+1", "Move to display 1" },
      { "Meta+2", "Move to display 2" },
      { "Meta+3", "Move to display 3" },
      { "Meta+Left", "Previous window" },
      { "Meta+Right", "Next window" },
    },
  },
}

local query = ""

local function keycap(text)
  return ui.row({
    height = 24,
    align = "center",
    justify = "center",
    fill = KEY_BG,
    radius = 6,
    paddingH = 7,
    border = "outline",
    borderWidth = 1,
  }, {
    ui.label({
      text = text,
      fontSize = 11,
      fontWeight = "semibold",
      color = KEY_INK,
      maxLines = 1,
    }),
  })
end

local function keycaps(sequence)
  local children = {}
  local first = true
  for part in string.gmatch(sequence, "[^+]+") do
    if not first then
      table.insert(children, ui.label({ text = "+", fontSize = 11, color = MUTED }))
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
      color = INK,
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
      table.insert(result, { title = group.title, rows = rows })
    end
  end
  return result
end

local function groupCard(group)
  local children = {
    ui.label({
      text = group.title,
      fontSize = 12,
      fontWeight = "bold",
      color = MUTED,
    }),
  }
  for _, row in ipairs(group.rows) do
    table.insert(children, shortcutRow(row[1], row[2]))
  end
  return ui.column({
    gap = 6,
    width = COLUMN_WIDTH,
    align = "stretch",
    fill = CARD_BG,
    padding = 10,
    radius = 12,
  }, children)
end

function onSearch(value)
  query = value or ""
  render()
end

local function render()
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
    table.insert(columnNodes, ui.column({
      gap = 10,
      width = COLUMN_WIDTH,
      align = "stretch",
    }, nodes))
  end

  local body
  if #shown == 0 then
    body = ui.column({ width = WIDTH, gap = 6, align = "center" }, {
      ui.glyph({ name = "search", size = 28, color = MUTED }),
      ui.label({ text = "No shortcuts found.", fontSize = 15, color = MUTED }),
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
      ui.label({
        text = string.format("%d shortcuts", shortcut_count),
        fontSize = 12,
        color = MUTED,
      }),
    }),
    ui.separator({ spacing = 2 }),
    body,
  }))
end

function onOpen(_context)
  query = ""
  render()
end
