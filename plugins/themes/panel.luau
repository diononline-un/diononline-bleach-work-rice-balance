local HOME = noctalia.getenv("HOME") or error("HOME is required")
local CACHE = (noctalia.getenv("XDG_CACHE_HOME") or (HOME .. "/.cache")) .. "/rice-theme"
local STATE = (noctalia.getenv("XDG_STATE_HOME") or (HOME .. "/.local/state")) .. "/rice/theme-current"
local RICE = HOME .. "/.local/bin/rice"
local INDEX = CACHE .. "/index.tsv"
local WIDTH = 1064
local TILE_WIDTH = 340
local TILE_IMAGE_WIDTH = 324
local TILE_IMAGE_HEIGHT = 182
local COLUMNS = 3
local PAGE_SIZE = 6

local entries = {}
local current = ""
local selected = 0
local query = ""
local loading = true
local render

local function load()
  local keep = selected
  entries = {}
  local text = noctalia.readFile(INDEX)
  if text then
    for line in string.gmatch(text, "[^\n]+") do
      local source, thumb, name = string.match(line, "^([^\t]+)\t([^\t]+)\t(.+)$")
      if source and thumb then
        table.insert(entries, { source = source, thumb = thumb, name = name })
      end
    end
  end
  local value = noctalia.readFile(STATE)
  if value then
    current = noctalia.string.trim(value)
  end

  local currentIndex = 0
  for index, entry in ipairs(entries) do
    if entry.source == current then
      currentIndex = index
      break
    end
  end
  if keep >= 1 and keep <= #entries then
    selected = keep
  elseif currentIndex > 0 then
    selected = currentIndex
  else
    selected = 1
  end
end

local function titleFor(path)
  if path == "" then
    return "-"
  end
  local name = string.match(path, "([^/]+)$") or path
  return (string.gsub(name, "%.[^.]+$", ""))
end

local function filtered()
  local needle = string.lower(query)
  if needle == "" then
    return entries
  end
  local result = {}
  for _, entry in ipairs(entries) do
    if string.find(string.lower(entry.name), needle, 1, true) then
      table.insert(result, entry)
    end
  end
  return result
end

local function pageCount(shown)
  return math.max(1, math.ceil(#shown / PAGE_SIZE))
end

local function currentPage()
  return math.floor((selected - 1) / PAGE_SIZE)
end

local function apply(source)
  noctalia.runAsync({ RICE, "theme", "set", source }, function(result)
    if result ~= nil and result.exitCode == 0 then
      panel.close()
    else
      noctalia.notifyError("Theme", "Could not apply the selected theme.")
    end
  end)
end

local function refresh()
  loading = true
  render()
  noctalia.runAsync({ RICE, "theme", "refresh" }, function()
    loading = false
    load()
    render()
  end)
end

function onRandom()
  noctalia.runAsync({ RICE, "theme", "random" }, function(result)
    if result ~= nil and result.exitCode == 0 then
      panel.close()
    end
  end)
end

function onRefresh()
  refresh()
end

function onClose()
  panel.close()
end

function onSearch(value)
  query = value or ""
  selected = 1
  render()
end

function onPrevPage()
  local shown = filtered()
  if loading or #shown == 0 then
    return
  end
  local page = currentPage()
  if page > 0 then
    selected = (page - 1) * PAGE_SIZE + 1
    render()
  end
end

function onNextPage()
  local shown = filtered()
  if loading or #shown == 0 then
    return
  end
  local page = currentPage()
  if page < pageCount(shown) - 1 then
    selected = (page + 1) * PAGE_SIZE + 1
    render()
  end
end

local function header(shown)
  local page = math.max(0, currentPage())
  local pages = pageCount(shown)
  return ui.row({ width = WIDTH, align = "center", justify = "space_between" }, {
    ui.row({ gap = 10, align = "center" }, {
      ui.glyph({ name = "palette", size = 24, color = "primary" }),
      ui.label({ text = "Bleach Themes", fontSize = 24, fontWeight = "bold", color = "on_surface" }),
    }),
    ui.row({ gap = 6, align = "center" }, {
      ui.button({ key = "theme-prev", glyph = "chevron-left", variant = "ghost", tooltip = "Previous page", enabled = page > 0, onClick = "onPrevPage" }),
      ui.label({ text = string.format("%d / %d", page + 1, pages), fontSize = 12, color = "on_surface_variant" }),
      ui.button({ key = "theme-next", glyph = "chevron-right", variant = "ghost", tooltip = "Next page", enabled = page < pages - 1, onClick = "onNextPage" }),
      ui.button({ key = "theme-random", text = "Random", variant = "primary", onClick = "onRandom" }),
      ui.button({ key = "theme-refresh", glyph = "refresh", variant = "ghost", tooltip = "Rebuild thumbnails", onClick = "onRefresh" }),
      ui.button({ key = "theme-close", glyph = "x", variant = "ghost", tooltip = "Close", onClick = "onClose" }),
    }),
  })
end

local function tile(entry, index)
  local active = entry.source == current
  local isSelected = index == selected
  return ui.column({
    key = "theme-" .. index,
    width = TILE_WIDTH,
    gap = 6,
    fill = "surface_container",
    radius = 12,
    padding = 8,
    border = isSelected and "tertiary" or (active and "primary" or "outline_variant"),
    borderWidth = isSelected and 2 or 1,
    onClick = function()
      selected = index
      apply(entry.source)
    end,
  }, {
    ui.image({
      path = entry.thumb,
      width = TILE_IMAGE_WIDTH,
      height = TILE_IMAGE_HEIGHT,
      radius = 8,
      fit = "cover",
    }),
    ui.label({
      text = entry.name,
      fontSize = 13,
      fontWeight = active and "bold" or "normal",
      color = active and "primary" or "on_surface",
      maxLines = 1,
    }),
  })
end

local function footer()
  return ui.label({
    text = "Type to search · Tab to select · Enter to apply · Esc to close",
    fontSize = 12,
    color = "on_surface_variant",
    maxLines = 1,
  })
end

function render()
  local shown = filtered()
  if not loading and #shown > 0 then
    selected = math.max(1, math.min(#shown, selected))
  elseif #shown == 0 then
    selected = 1
  end

  local currentRow = ui.row({ width = WIDTH, align = "center", justify = "space_between" }, {
    ui.label({
      text = "Current: " .. titleFor(current),
      fontSize = 13,
      color = "on_surface_variant",
    }),
    ui.label({ text = "Ctrl+Alt+Shift+←/→ cycles · Ctrl+Alt+Shift+T opens this panel", fontSize = 13, color = "on_surface_variant" }),
  })

  local searchRow = ui.row({ width = WIDTH, gap = 10, align = "center", justify = "space_between" }, {
    ui.input({
      key = "theme-search",
      width = 360,
      placeholder = "Search themes …",
      fontSize = 14,
      controlSize = "sm",
      value = query,
      focus = true,
      onChange = "onSearch",
    }),
    ui.label({
      text = string.format("%d themes", #shown),
      fontSize = 12,
      color = "on_surface_variant",
    }),
  })

  local body
  if loading then
    body = ui.label({ text = "Loading themes …", fontSize = 16, color = "on_surface_variant" })
  elseif #entries == 0 then
    body = ui.label({ text = "No wallpapers found in the configured directory.", fontSize = 15, color = "error" })
  elseif #shown == 0 then
    body = ui.label({ text = "No matches.", fontSize = 15, color = "on_surface_variant" })
  else
    local pageStart = currentPage() * PAGE_SIZE + 1
    local pageEnd = math.min(#shown, pageStart + PAGE_SIZE - 1)
    local rows = {}
    local rowTiles = {}
    for index = pageStart, pageEnd do
      table.insert(rowTiles, tile(shown[index], index))
      if #rowTiles == COLUMNS then
        table.insert(rows, ui.row({ gap = 20, align = "start" }, rowTiles))
        rowTiles = {}
      end
    end
    if #rowTiles > 0 then
      table.insert(rows, ui.row({ gap = 20, align = "start" }, rowTiles))
    end
    body = ui.column({ width = WIDTH, gap = 20, align = "start" }, rows)
  end

  local children = {
    header(shown),
    currentRow,
    searchRow,
    ui.separator({ spacing = 2 }),
    body,
  }
  if not loading and #shown > 0 then
    table.insert(children, footer())
  end

  panel.render(ui.column({
    flexGrow = 1,
    gap = 12,
    align = "stretch",
    fill = "surface_container",
    radius = 16,
    padding = 14,
  }, children))
end

function onOpen(_context)
  query = ""
  selected = 0
  loading = true
  render()
  refresh()
end
