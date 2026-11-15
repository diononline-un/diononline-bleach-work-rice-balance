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

local function render()
  local s = snapshot
  if s == nil or s.available ~= true then
    desktopWidget.setVisible(false)
    return
  end
  desktopWidget.setVisible(true)

  local light = s.light == true
  local ink = light and "#111111" or "#f7f7f7"
  local muted = light and "#333333" or "#c8c8c8"

  local function iconButton(glyph, size, handler, color)
    return ui.row({
      width = 44,
      height = 44,
      align = "center",
      justify = "center",
      onClick = handler,
    }, {
      ui.glyph({ name = glyph, size = size, color = color or ink }),
    })
  end

  local buttons = ui.row({ gap = 8, align = "start" }, {
    iconButton("player-skip-back", 28, "previous"),
    iconButton((s.paused and "player-play" or "player-pause"), 36, "togglePlay"),
    iconButton("player-skip-forward", 28, "next"),
    iconButton("chart-bar", 28, "openQueue"),
    iconButton("heart", 28, "toggleLike", s.liked and "primary" or ink),
  })

  local text = ui.column({ gap = 4, align = "start" }, {
    ui.label({
      text = s.title or "",
      fontSize = 26,
      fontWeight = "bold",
      color = ink,
      shadow = true,
      maxWidth = 360,
      maxLines = 2,
    }),
    ui.label({
      text = s.artist or "",
      fontSize = 18,
      color = muted,
      shadow = true,
      maxWidth = 360,
      maxLines = 1,
    }),
    buttons,
  })

  local children = {}
  if (s.image or "") ~= "" then
    table.insert(children, ui.image({
      path = s.image,
      width = 220,
      height = 220,
      radius = 18,
      fit = "cover",
      onClick = "togglePlay",
    }))
  end
  table.insert(children, text)

  desktopWidget.render(ui.row({ gap = 16, align = "center" }, children))
end

noctalia.state.watch("rice_media", function(value)
  snapshot = value
  render()
end)

render()
