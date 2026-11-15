import subprocess

ACTIVITY_SERVICE = "org.kde.ActivityManager"
ACTIVITY_PATH = "/ActivityManager/Activities"
ACTIVITY_IFACE = "org.kde.ActivityManager.Activities"


def _qdbus(args) -> str:
    return subprocess.run(
        ["qdbus6", ACTIVITY_SERVICE, ACTIVITY_PATH, ACTIVITY_IFACE, *args],
        capture_output=True, text=True, check=True
    ).stdout.strip()


def list_activities(runner=None) -> dict[str, str]:
    runner = runner or _qdbus
    ids = [line.strip() for line in runner(["ListActivities"]).splitlines() if line.strip()]
    return {
        runner(["ActivityName", activity_id]): activity_id
        for activity_id in ids
    }


def ensure_activity(name: str, runner=None) -> str:
    runner = runner or _qdbus
    existing = list_activities(runner)
    if name in existing:
        return existing[name]
    return runner(["CreateActivity", name]).strip()


def switch_activity(activity_id: str, runner=None) -> None:
    runner = runner or _qdbus
    runner(["SetCurrentActivity", activity_id])
