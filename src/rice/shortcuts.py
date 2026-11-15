"""Disable KDE global shortcuts that collide with the rice bindings.

The rice KWin script binds ``Meta+Q``, ``Meta+H``/``Meta+J``, and the
``Meta+1..3`` window-move shortcuts. KDE ships conflicting defaults for those
keys, so a login-time cleanup clears them through ``org.kde.kglobalaccel``.
"""

import time

BUS = "org.kde.kglobalaccel"
PATH = "/kglobalaccel"
IFACE = "org.kde.KGlobalAccel"

WANTED = {
    "kwin": {"Window Quick Tile Left", "Window Quick Tile Right"},
    "plasmashell": {
        "manage activities",
        "activate task manager entry 1",
        "activate task manager entry 2",
        "activate task manager entry 3",
    },
}


def _kglobalaccel():
    import dbus

    bus = dbus.SessionBus()
    return dbus.Interface(bus.get_object(BUS, PATH), IFACE)


def _empty_shortcut():
    import dbus

    return dbus.Array([], signature="i")


def disable_conflicts(iface=None, empty=None, attempts=30, sleep=None) -> list[str]:
    """Clear the known conflicting KDE actions and return the cleared names.

    KGlobalAccel may not have registered every component yet right after login,
    so the call retries until the conflicting actions show up. Each cleared
    action is returned as ``"component:action"``.
    """
    sleep = sleep or time.sleep
    cleared = []
    for _ in range(attempts):
        try:
            current = iface if iface is not None else _kglobalaccel()
            empty_sig = empty if empty is not None else _empty_shortcut()
            for component, names in WANTED.items():
                for action in current.allActionsForComponent([component]):
                    if str(action[1]) not in names:
                        continue
                    current.setForeignShortcut(
                        [str(item) for item in action], empty_sig
                    )
                    cleared.append(f"{component}:{action[1]}")
            if cleared:
                break
        except Exception:
            if iface is not None:
                raise
            pass
        sleep(1)
    return cleared
