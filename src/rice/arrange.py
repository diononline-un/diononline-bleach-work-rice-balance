"""Reload the generated role-based placement rules into a running KWin.

``rice arrange`` re-applies the layout by asking KWin to load and run the
generated ``arrange.js`` script through the KWin scripting D-Bus interface.
The script re-places every open window according to the current rules, then
stops and unloads itself, so the call is a one-shot reapply.
"""

from .paths import data_home

KWIN_SERVICE = "org.kde.KWin"
SCRIPTING_PATH = "/Scripting"
SCRIPTING_IFACE = "org.kde.kwin.Scripting"
SCRIPT_IFACE = "org.kde.kwin.Script"
ARRANGE_PLUGIN = "rice-arrange"


def arrange_script_path():
    """Return the generated arrange script written by ``rice apply``."""
    return data_home() / "kwin" / "scripts" / "rice-placement" / "arrange.js"


def reload_layout(script_path=None, bus=None, dbus_mod=None):
    """Load and run the arrange script in the running KWin session.

    ``loadScript`` returns a non-negative script id; a negative id means the
    plugin id is already registered, so it is unloaded first and retried.
    """
    if dbus_mod is None:
        import dbus as dbus_mod

    path = str(script_path or arrange_script_path())
    bus = bus or dbus_mod.SessionBus()
    scripting = dbus_mod.Interface(
        bus.get_object(KWIN_SERVICE, SCRIPTING_PATH), SCRIPTING_IFACE
    )
    script_id = scripting.loadScript(path, ARRANGE_PLUGIN)
    if script_id < 0:
        scripting.unloadScript(ARRANGE_PLUGIN)
        script_id = scripting.loadScript(path, ARRANGE_PLUGIN)
    if script_id < 0:
        raise RuntimeError("KWin refused to load the arrange script")

    script = dbus_mod.Interface(
        bus.get_object(KWIN_SERVICE, f"{SCRIPTING_PATH}/Script{script_id}"),
        SCRIPT_IFACE,
    )
    try:
        script.run()
    finally:
        try:
            script.stop()
        except Exception:
            pass
        scripting.unloadScript(ARRANGE_PLUGIN)
