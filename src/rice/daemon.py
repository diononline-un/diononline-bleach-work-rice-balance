"""D-Bus daemon exposing session actions for the rice shell."""

import json
import subprocess

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

from .activities import current_activity, switch_activity
from .paths import state_home
from .startup import launch, run_autostart, run_startup, terminal_command
from .theme import next_theme, previous_theme

BUS_NAME = "org.rice.Rice"
OBJECT_PATH = "/Rice"
CHEATSHEET_PANEL = "rice/cheatsheet:panel"


class RiceDaemon(dbus.service.Object):
    def __init__(self, bus, runtime):
        super().__init__(bus, OBJECT_PATH)
        self.runtime = runtime
        self.fullscreen = {}

    @dbus.service.method(BUS_NAME, in_signature="s", out_signature="")
    def SwitchActivity(self, role):
        role = str(role)
        switch_activity(self.runtime["activities"][role]["kde_id"])
        run_autostart(self.runtime, role)

    @dbus.service.method(BUS_NAME, out_signature="")
    def RunStartup(self):
        run_startup(self.runtime)

    @dbus.service.method(BUS_NAME, in_signature="sb", out_signature="")
    def SetFullscreen(self, output, state):
        self.fullscreen[str(output)] = bool(state)

    @dbus.service.method(BUS_NAME, out_signature="b")
    def FullscreenActive(self):
        return any(self.fullscreen.values())

    @dbus.service.method(BUS_NAME, out_signature="")
    def ThemeNext(self):
        next_theme(self.runtime)

    @dbus.service.method(BUS_NAME, out_signature="")
    def ThemePrevious(self):
        previous_theme(self.runtime)

    @dbus.service.method(BUS_NAME, out_signature="")
    def QuickstartWork(self):
        run_autostart(self.runtime, "work")

    @dbus.service.method(BUS_NAME, out_signature="")
    def QuickstartPrivate(self):
        run_startup(self.runtime)

    @dbus.service.method(BUS_NAME, out_signature="")
    def QuickstartCurrent(self):
        role = self._current_role()
        if role == "private":
            run_startup(self.runtime)
        else:
            run_autostart(self.runtime, role)

    @dbus.service.method(BUS_NAME, out_signature="")
    def ToggleCheatSheet(self):
        subprocess.run(
            ["noctalia", "msg", "panel-toggle", CHEATSHEET_PANEL], check=True
        )

    @dbus.service.method(BUS_NAME, out_signature="")
    def OpenTerminal(self):
        self._open_terminal()

    @dbus.service.method(BUS_NAME, out_signature="")
    def OpenAnimatedTerminal(self):
        self._open_terminal()

    @dbus.service.method(BUS_NAME, out_signature="")
    def ReapplyPlacement(self):
        from .arrange import reload_layout

        reload_layout()

    def _current_role(self):
        roles = {
            entry["kde_id"]: role
            for role, entry in self.runtime.get("activities", {}).items()
            if isinstance(entry, dict) and entry.get("kde_id")
        }
        role = roles.get(current_activity().strip())
        if role is None:
            raise RuntimeError(
                "current KDE activity is not mapped to a rice role; run `rice apply` first"
            )
        return role

    def _open_terminal(self):
        command = terminal_command(self.runtime)
        if command:
            launch(command)


def runtime_path():
    return state_home() / "rice/runtime.json"


def load_runtime():
    return json.loads(runtime_path().read_text(encoding="utf-8"))


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    # Keep the BusName referenced while the loop runs so the name stays owned.
    bus_name = dbus.service.BusName(BUS_NAME, bus)
    daemon = RiceDaemon(bus, load_runtime())
    GLib.MainLoop().run()
