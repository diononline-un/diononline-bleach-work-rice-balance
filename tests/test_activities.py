from rice.activities import ensure_activity, list_activities


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
