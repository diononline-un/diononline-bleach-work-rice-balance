local WIDTH = 830
local COLUMN_WIDTH = 270
local KEY_WIDTH = 126
local DESC_WIDTH = 132

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
local CHIP_INK = inkFor("surface_container_high")

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
      { "Ctrl+Alt+Shift+Space", "Current activity" },
    },
  },
  {
    title = "Windows",
    rows = {
      { "Meta+M", "Maximize" },
      { "Meta+N", "Minimize" },
      { "Meta+Q", "Close" },
      { "Meta+H", "Left half" },
      { "Meta+J", "Right half" },
      { "Ctrl+Alt+R", "Reapply layout" },
    },
  },
  {
    title = "Displays",
    rows = {
      { "Meta+1", "Window to main" },
      { "Meta+2", "Window to side" },
      { "Meta+3", "Window to portrait" },
      { "Meta+Left", "Previous window" },
      { "Meta+Right", "Next window" },
    },
  },
  {
    title = "Terminal",
    rows = {
      { "Meta+Return", "Terminal" },
      { "Meta+Shift+Return", "Animated terminal" },
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
    title = "Shell",
    rows = {
      { "Super", "Noctalia Launcher" },
      { "Ctrl+Alt+S", "Control Center" },
      { "Ctrl+Alt+P", "Noctalia Settings" },
      { "Ctrl+Alt+H", "Cheat Sheet" },
      { "Meta+W", "Overview" },
      { "Meta+D", "Show desktop" },
    },
  },
  {
    title = "Recording",
    rows = {
      { "F8 / F9", "GPU Recorder (gsr-ui)" },
    },
  },
}

local function keyLabel(text)
  return ui.row({
    width = KEY_WIDTH,
    height = 22,
    align = "center",
    justify = "center",
    fill = "surface_container_high",
    radius = 6,
    paddingH = 6,
    border = "outline",
    borderWidth = 1,
  }, {
    ui.label({
      text = text,
      fontSize = 11,
      fontWeight = "semibold",
      color = CHIP_INK,
      maxLines = 1,
    }),
  })
end

local function shortcutRow(key, description)
  return ui.row({ gap = 8, align = "center", width = COLUMN_WIDTH }, {
    keyLabel(key),
    ui.label({
      text = description,
      width = DESC_WIDTH,
      fontSize = 12,
      color = INK,
      maxLines = 2,
    }),
  })
end

local function groupColumn(group)
  local children = {
    ui.label({
      text = group.title,
      fontSize = 12,
      fontWeight = "bold",
      color = INK,
    }),
  }
  for _, row in ipairs(group.rows) do
    table.insert(children, shortcutRow(row[1], row[2]))
  end
  return ui.column({ gap = 6, width = COLUMN_WIDTH, align = "stretch" }, children)
end

local function header()
  return ui.row({ width = WIDTH, align = "center", justify = "space_between" }, {
    ui.row({ gap = 10, align = "center" }, {
      ui.glyph({ name = "keyboard", size = 22, color = INK }),
      ui.label({ text = "Rice · Shortcuts", fontSize = 24, fontWeight = "bold", color = INK }),
    }),
    ui.label({ text = "Ctrl+Alt+H", fontSize = 13, color = MUTED }),
  })
end

local function render()
  local left = ui.column({ gap = 18, width = COLUMN_WIDTH, align = "stretch" }, {
    groupColumn(groups[1]),
    groupColumn(groups[2]),
    groupColumn(groups[3]),
  })
  local middle = ui.column({ gap = 18, width = COLUMN_WIDTH, align = "stretch" }, {
    groupColumn(groups[4]),
    groupColumn(groups[5]),
    groupColumn(groups[6]),
  })
  local right = ui.column({ gap = 18, width = COLUMN_WIDTH, align = "stretch" }, {
    groupColumn(groups[7]),
    groupColumn(groups[8]),
  })
  local body = ui.row({ gap = 10, align = "start", width = WIDTH }, { left, middle, right })

  panel.render(ui.column({
    flexGrow = 1,
    gap = 14,
    align = "stretch",
    fill = "surface_container",
    radius = 16,
    padding = 16,
  }, {
    header(),
    ui.separator({ spacing = 2 }),
    body,
  }))
end

function onOpen(_context)
  render()
end
