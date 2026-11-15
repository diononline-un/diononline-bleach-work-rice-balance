local HOME = noctalia.getenv("HOME") or error("HOME is required")
local CONFIG = (noctalia.getenv("XDG_CONFIG_HOME") or (HOME .. "/.config")) .. "/noctalia/media.json"
local ok, config = pcall(noctalia.json.decode, noctalia.readFile(CONFIG) or "{}")
if not ok or type(config) ~= "table" then
  config = {}
end
local API = config.api_url or "http://127.0.0.1:26538/api/v1"
local STATE_KEY = "rice_media"

local dataDir = noctalia.pluginDataDir() or "/tmp"
local CACHE = (noctalia.getenv("XDG_CACHE_HOME") or (HOME .. "/.cache")) .. "/rice-theme"
local songBusy = false
local likeBusy = false
local lastSignature = ""
local imageUrl = ""
local imagePath = ""

local state = {
  available = false,
  title = "",
  artist = "",
  album = "",
  image = "",
  paused = true,
  liked = false,
  light = false,
}

local function readLight()
  local value = noctalia.readFile(CACHE .. "/light")
  return value ~= nil and noctalia.string.trim(value) == "1"
end

local function publish()
  local sig = table.concat({
    tostring(state.available),
    state.title,
    state.artist,
    state.album,
    state.image,
    tostring(state.paused),
    tostring(state.liked),
    tostring(state.light),
  }, "\0")
  if sig == lastSignature then
    return
  end
  lastSignature = sig
  noctalia.state.set(STATE_KEY, {
    available = state.available,
    title = state.title,
    artist = state.artist,
    album = state.album,
    image = state.image,
    paused = state.paused,
    liked = state.liked,
    light = state.light,
  })
end

local function updateImage(url)
  if url == imageUrl then
    return
  end
  imageUrl = url
  if url == "" then
    state.image = ""
    publish()
    return
  end

  local path = dataDir .. "/cover-" .. tostring(noctalia.nowMs()) .. ".jpg"
  local accepted = noctalia.download(url, path, function(success)
    if success then
      local old = imagePath
      imagePath = path
      state.image = path
      if old ~= "" and old ~= path then
        noctalia.removeFile(old)
      end
      lastSignature = ""
      publish()
    end
  end)
  if not accepted then
    state.image = ""
    publish()
  end
end

local function onSong(response)
  songBusy = false
  if not response.ok or response.status < 200 or response.status >= 300 then
    state.available = false
    publish()
    return
  end

  local ok, data = pcall(noctalia.json.decode, response.body)
  if not ok or type(data) ~= "table" then
    state.available = false
    publish()
    return
  end

  state.title = data.title or ""
  state.artist = data.artist or ""
  state.album = data.album or ""
  state.paused = data.isPaused == true
  state.available = state.title ~= ""
  updateImage(data.imageSrc or "")
  publish()
end

local function onLike(response)
  likeBusy = false
  if not response.ok or response.status < 200 or response.status >= 300 then
    return
  end
  local ok, data = pcall(noctalia.json.decode, response.body)
  if ok and type(data) == "table" then
    state.liked = data.state == "LIKE"
    publish()
  end
end

local function poll()
  local light = readLight()
  if light ~= state.light then
    state.light = light
    publish()
  end

  if not songBusy then
    songBusy = true
    local accepted = noctalia.http({ url = API .. "/song-info" }, onSong)
    if not accepted then
      songBusy = false
      state.available = false
      publish()
    end
  end

  if not likeBusy then
    likeBusy = true
    local accepted = noctalia.http({ url = API .. "/like-state" }, onLike)
    if not accepted then
      likeBusy = false
    end
  end
end

poll()
noctalia.setUpdateInterval(1000)

function update()
  poll()
end
