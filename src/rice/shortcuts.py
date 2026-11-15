"""Disable KDE global shortcuts that collide with the rice bindings.

The rice KWin script binds ``Meta+Q``, ``Meta+H``/``Meta+J``, and the
``Meta+1..3`` window-move shortcuts. KDE ships conflicting defaults for those
keys, so a login-time cleanup clears them through ``org.kde.kglobalaccel``.
"""

import sys
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

UNKNOWN_METHOD = "org.freedesktop.DBus.Error.UnknownMethod"


def _kglobalaccel():
    import dbus

    bus = dbus.SessionBus()
    return dbus.Interface(bus.get_object(BUS, PATH), IFACE)


def _empty_keys():
    import dbus

    return dbus.Array([], signature="(ai)")


def _empty_shortcut():
    import dbus

    return dbus.Array([], signature="i")


def _clear_action(iface, action, empty_keys, empty_shortcut):
    """Clear one action, preferring Plasma 6's ``setForeignShortcutKeys``.

    ``action`` is a four-element row from ``allActionsForComponent``; only the
    leading two elements (component and action id) are meaningful to the new
    method. Older Plasma releases that predate it fall back to the legacy
    ``setForeignShortcut`` call, which expects the full row.
    """
    component = action[0]
    name = str(action[1])
    try:
        iface.setForeignShortcutKeys([component, name], empty_keys)
    except Exception as exc:
        if getattr(exc, "get_dbus_name", lambda: "")() != UNKNOWN_METHOD:
            raise
        iface.setForeignShortcut([str(item) for item in action], empty_shortcut)


def disable_conflicts(
    iface=None, empty_keys=None, empty_shortcut=None, attempts=30, sleep=None
) -> list[str]:
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
    last_error = None
    for _ in range(attempts):
        try:
            current = iface if iface is not None else _kglobalaccel()
            keys = empty_keys if empty_keys is not None else _empty_keys()
            shortcut = (
                empty_shortcut if empty_shortcut is not None else _empty_shortcut()
            )
            for component, names in WANTED.items():
                for action in current.allActionsForComponent([component]):
                    name = str(action[1])
                    if name not in names:
                        continue
                    seen.add((component, name))
                    entry = f"{component}:{name}"
                    if entry in cleared:
                        continue
                    _clear_action(current, action, keys, shortcut)
                    cleared.append(entry)
            if wanted <= seen:
                break
        except Exception as exc:
            if iface is not None:
                raise
            last_error = exc
        sleep(1)
    if iface is None and last_error is not None and not (wanted <= seen):
        print(
            f"rice shortcuts: could not clear every conflicting shortcut "
            f"({last_error}); run 'rice shortcuts disable-conflicts' manually",
            file=sys.stderr,
        )
    return cleared
