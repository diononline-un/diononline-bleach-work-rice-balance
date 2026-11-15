local HOME = noctalia.getenv("HOME") or error("HOME is required")
local RUNTIME = (noctalia.getenv("XDG_STATE_HOME") or (HOME .. "/.local/state")) .. "/rice/runtime.json"
local RICE = "rice"

local workId = ""
local privateId = ""
local active = ""
local busy = false

-- Activity ids come from the generated runtime file so the widget never pins a
-- machine-specific UUID. Missing or unreadable runtime keeps the buttons inert.
local function loadRoles()
  local text = noctalia.readFile(RUNTIME)
  if not text then
    return
  end
  local ok, data = pcall(noctalia.json.decode, text)
  if not ok or type(data) ~= "table" then
    return
  end
  local activities = data.activities or {}
  local work = activities.work or {}
  local private = activities.private or {}
  workId = work.kde_id or ""
  privateId = private.kde_id or ""
end

local function render()
  local workActive = workId ~= "" and active == workId
  local privateActive = privateId ~= "" and active == privateId
  barWidget.render(ui.row({ gap = 4, align = "center" }, {
    ui.button({
      text = "Work",
      glyph = "briefcase",
      controlSize = "sm",
      variant = workActive and "primary" or "ghost",
      selected = workActive,
      onClick = "onWork",
    }),
    ui.button({
      text = "Private",
      glyph = "home",
      controlSize = "sm",
      variant = privateActive and "secondary" or "ghost",
      selected = privateActive,
      onClick = "onPrivate",
    }),
  }))
end

function refresh()
  if busy then
    return
  end
  busy = true
  loadRoles()
  noctalia.runAsync({ "qdbus6", "org.kde.ActivityManager", "/ActivityManager/Activities", "CurrentActivity" }, function(result)
    busy = false
    if result ~= nil and result.exitCode == 0 then
      local value = noctalia.string.trim(result.stdout)
      if value ~= active then
        active = value
        render()
      end
    end
  end)
end

function onWork()
  active = workId
  render()
  noctalia.runAsync({ RICE, "activity", "work" }, function()
    refresh()
  end)
end

function onPrivate()
  active = privateId
  render()
  noctalia.runAsync({ RICE, "activity", "private" }, function()
    refresh()
  end)
end

function update()
  refresh()
end

noctalia.setUpdateInterval(1500)
render()
refresh()
