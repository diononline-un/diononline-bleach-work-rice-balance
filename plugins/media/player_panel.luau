local HOME = noctalia.getenv("HOME") or error("HOME is required")
local CONFIG = (noctalia.getenv("XDG_CONFIG_HOME") or (HOME .. "/.config")) .. "/noctalia/media.json"
local ok, config = pcall(noctalia.json.decode, noctalia.readFile(CONFIG) or "{}")
if not ok or type(config) ~= "table" then
  config = {}
end
local API = config.api_url or "http://127.0.0.1:26538/api/v1"
local snapshot = noctalia.state.get("rice_media")

local function post(path)
  noctalia.http({ url = API .. path, method = "POST" }, function() end)
end

function previous()
  post("/previous")
end

function togglePlay()
  post("/toggle-play")
end

function next()
  post("/next")
end

function toggleLike()
  post("/like")
end

function openQueue()
  noctalia.togglePanel("rice/media:queue")
end

function closePanel()
  panel.close()
end

local function iconButton(glyph, size, handler, color)
  return ui.row({
    width = 48,
    height = 48,
    align = "center",
    justify = "center",
    onClick = handler,
  }, {
    ui.glyph({ name = glyph, size = size, color = color or "on_surface" }),
  })
end

local function header()
  return ui.row({ width = 944, align = "center", justify = "space_between" }, {
    ui.row({ gap = 10, align = "center" }, {
      ui.glyph({ name = "music", size = 20, color = "primary" }),
      ui.label({ text = "YouTube Music", fontSize = 14, fontWeight = "semibold", color = "on_surface_variant" }),
    }),
    ui.button({ glyph = "x", variant = "ghost", tooltip = "Close", onClick = "closePanel" }),
  })
end

local function render()
  local s = snapshot
  if s == nil or s.available ~= true then
    panel.render(ui.column({ flexGrow = 1, gap = 18, align = "center", justify = "center" }, {
      header(),
      ui.label({ text = "YouTube Music is not active.", fontSize = 18, color = "on_surface_variant" }),
    }))
    return
  end

  local cover = nil
  if (s.image or "") ~= "" then
    cover = ui.image({
      path = s.image,
      width = 300,
      height = 300,
      radius = 18,
      fit = "cover",
      onClick = "togglePlay",
    })
  end

  local controls = ui.row({ gap = 10, align = "start" }, {
    iconButton("player-skip-back", 32, "previous"),
    iconButton((s.paused and "player-play" or "player-pause"), 42, "togglePlay"),
    iconButton("player-skip-forward", 32, "next"),
    iconButton("chart-bar", 32, "openQueue"),
    iconButton("heart", 32, "toggleLike", s.liked and "primary" or "on_surface"),
  })

  local text = ui.column({ gap = 6, width = 600, align = "start" }, {
    ui.label({
      text = s.title or "",
      fontSize = 30,
      fontWeight = "bold",
      color = "on_surface",
      maxWidth = 600,
      maxLines = 2,
    }),
    ui.label({
      text = s.artist or "",
      fontSize = 20,
      color = "on_surface_variant",
      maxWidth = 600,
      maxLines = 1,
    }),
    ui.label({
      text = s.album or "",
      fontSize = 14,
      color = "on_surface_variant",
      maxWidth = 600,
      maxLines = 1,
    }),
    controls,
  })

  local rowChildren = {}
  if cover ~= nil then
    table.insert(rowChildren, cover)
  end
  table.insert(rowChildren, text)

  panel.render(ui.column({ flexGrow = 1, gap = 14, align = "stretch" }, {
    header(),
    ui.row({ gap = 24, align = "center" }, rowChildren),
  }))
end

noctalia.state.watch("rice_media", function(value)
  snapshot = value
  render()
end)

function onOpen(_context)
  render()
end
