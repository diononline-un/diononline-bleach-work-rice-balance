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

    KGlobalAccel registers its components asynchronously right after login, so
    a pass can see only the kwin actions before plasmashell has published its
    own. The loop therefore keeps going until a full pass has observed every
    wanted action (or the retry budget runs out), instead of stopping as soon
    as *any* action was cleared. Each cleared action is returned as
    ``"component:action"``.
    """
    sleep = sleep or time.sleep
    cleared = []
    seen = set()
    wanted = {
        (component, name)
        for component, names in WANTED.items()
        for name in names
    }
    for _ in range(attempts):
        try:
            current = iface if iface is not None else _kglobalaccel()
            empty_sig = empty if empty is not None else _empty_shortcut()
            for component, names in WANTED.items():
                for action in current.allActionsForComponent([component]):
                    name = str(action[1])
                    if name not in names:
                        continue
                    seen.add((component, name))
                    entry = f"{component}:{name}"
                    if entry in cleared:
                        continue
                    current.setForeignShortcut(
                        [str(item) for item in action], empty_sig
                    )
                    cleared.append(entry)
            if wanted <= seen:
                break
        except Exception:
            if iface is not None:
                raise
            pass
        sleep(1)
    return cleared
