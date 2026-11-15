local HOME = noctalia.getenv("HOME") or error("HOME is required")
local CONFIG = (noctalia.getenv("XDG_CONFIG_HOME") or (HOME .. "/.config")) .. "/noctalia/media.json"
local ok, config = pcall(noctalia.json.decode, noctalia.readFile(CONFIG) or "{}")
if not ok or type(config) ~= "table" then
  config = {}
end
local API = config.api_url or "http://127.0.0.1:26538/api/v1"
local snapshot = noctalia.state.get("rice_media")
local items = {}
local loading = true
local open = false
local lastError = ""

local function render()
  local children = {
    ui.row({ width = 398, align = "center", justify = "space_between" }, {
      ui.row({ gap = 8, align = "center" }, {
        ui.glyph({ name = "chart-bar", size = 20, color = "primary" }),
        ui.label({ text = "Warteschlange", fontSize = 17, fontWeight = "bold", color = "on_surface" }),
      }),
      ui.row({ gap = 6, align = "center" }, {
        ui.button({ glyph = "refresh", variant = "ghost", tooltip = "Queue neu laden", onClick = "onRefresh" }),
        ui.button({ glyph = "x", variant = "ghost", tooltip = "Schließen", onClick = "onClose" }),
      }),
    }),
  }

  if snapshot ~= nil and snapshot.available == true then
    table.insert(children, ui.row({
      width = 398,
      gap = 8,
      align = "center",
      fill = "surface_container_high",
      radius = 10,
      padding = 8,
    }, {
      ui.glyph({ name = "music", size = 18, color = "primary" }),
      ui.column({ gap = 1, align = "start", width = 330 }, {
        ui.label({ text = snapshot.title or "", fontSize = 13, fontWeight = "semibold", color = "on_surface", maxLines = 1 }),
        ui.label({ text = snapshot.artist or "", fontSize = 11, color = "on_surface_variant", maxLines = 1 }),
      }),
    }))
  end

  if loading then
    table.insert(children, ui.label({ text = "Lade Queue …", fontSize = 14, color = "on_surface_variant" }))
  elseif #items == 0 then
    table.insert(children, ui.label({ text = lastError ~= "" and lastError or "Queue ist leer.", fontSize = 14, color = "on_surface_variant" }))
  else
    table.insert(children, ui.label({ text = "Als Nächstes", fontSize = 11, fontWeight = "bold", color = "on_surface_variant" }))
    for index, item in ipairs(items) do
      local active = item.selected
      table.insert(children, ui.row({
        width = 398,
        gap = 8,
        align = "center",
        fill = active and "primary_container" or "surface_container",
        radius = 8,
        padding = 6,
      }, {
        ui.label({ text = tostring(index), width = 18, fontSize = 11, color = active and "on_primary_container" or "on_surface_variant" }),
        ui.column({ gap = 1, align = "start", width = 286 }, {
          ui.label({ text = item.title, fontSize = 13, fontWeight = active and "bold" or "normal", color = active and "on_primary_container" or "on_surface", maxLines = 1 }),
          ui.label({ text = item.artist, fontSize = 11, color = active and "on_primary_container" or "on_surface_variant", maxLines = 1 }),
        }),
        ui.label({ text = item.duration, width = 40, fontSize = 11, color = active and "on_primary_container" or "on_surface_variant" }),
      }))
    end
  end

  panel.render(ui.column({ flexGrow = 1, gap = 10, align = "stretch" }, children))
end

local function fetch()
  loading = true
  lastError = ""
  render()
  local accepted = noctalia.http({ url = API .. "/queue" }, function(response)
    loading = false
    if not response.ok or response.status < 200 or response.status >= 300 then
      items = {}
      lastError = "Queue nicht erreichbar."
      render()
      return
    end
    local ok, data = pcall(noctalia.json.decode, response.body)
    if not ok or type(data) ~= "table" or type(data.items) ~= "table" then
      items = {}
      lastError = "Queue konnte nicht gelesen werden."
      render()
      return
    end
    items = {}
    for _, entry in ipairs(data.items) do
      local renderer = entry.playlistPanelVideoRenderer
      if renderer ~= nil then
        local title = ""
        local artist = ""
        local duration = ""
        if renderer.title and renderer.title.runs and renderer.title.runs[1] then
          title = renderer.title.runs[1].text or ""
        end
        if renderer.longBylineText and renderer.longBylineText.runs and renderer.longBylineText.runs[1] then
          artist = renderer.longBylineText.runs[1].text or ""
        end
        if renderer.lengthText and renderer.lengthText.runs and renderer.lengthText.runs[1] then
          duration = renderer.lengthText.runs[1].text or ""
        end
        table.insert(items, {
          title = title,
          artist = artist,
          duration = duration,
          selected = renderer.selected == true,
        })
        if #items >= 8 then
          break
        end
      end
    end
    render()
  end)
  if not accepted then
    loading = false
    lastError = "Queue nicht erreichbar."
    render()
  end
end

function onRefresh()
  fetch()
end

function onOpen(_context)
  open = true
  items = {}
  loading = true
  render()
  fetch()
end

function onClose()
  open = false
  panel.close()
end

noctalia.state.watch("rice_media", function(value)
  snapshot = value
  if open then
    render()
  end
end)
