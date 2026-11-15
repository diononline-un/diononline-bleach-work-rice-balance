from rice.activities import current_activity, ensure_activity, list_activities


def fake_runner(args):
    if "ListActivities" in args:
        return "private-uuid\nwork-uuid\n"
    if "ActivityName" in args:
        return {"private-uuid": "Private", "work-uuid": "Work"}[args[-1]]
    if "CreateActivity" in args:
        return "new-uuid\n"
    raise AssertionError(args)


def test_list_activities_maps_names():
    assert list_activities(fake_runner) == {"Private": "private-uuid", "Work": "work-uuid"}


def test_ensure_activity_creates_missing():
    assert ensure_activity("Games", fake_runner) == "new-uuid"


def test_current_activity_returns_trimmed_id():
    assert current_activity(lambda args: "work-uuid\n") == "work-uuid"


def test_qdbus_passes_interface_qualified_method(monkeypatch):
    import types

    from rice import activities

    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return types.SimpleNamespace(stdout="work-uuid\n")

    monkeypatch.setattr(activities.subprocess, "run", fake_run)

    assert activities.current_activity() == "work-uuid"
    assert seen["command"][:4] == [
        "qdbus6",
        "org.kde.ActivityManager",
        "/ActivityManager/Activities",
        "org.kde.ActivityManager.Activities.CurrentActivity",
    ]
