import json

from familylink_mcp import payloads


def body(text: str):
    return json.loads(text)


def test_downtime_mode_switch():
    assert body(payloads.downtime_mode("c1", "mode", True)) == [
        None, "c1", [[None, None, None, None], None, None, None, [None, [["mode", 2]]]], None, [1]
    ]


def test_downtime_day_state():
    assert body(payloads.downtime_day_state("c1", "day", False)) == [
        None, "c1", [[None, None, [["day", 1]], None], None, None, None, []], None, [1]
    ]


def test_downtime_day_times():
    assert body(payloads.downtime_day_times("c1", "day", "19:30", "7:00")) == [
        None, "c1", [[None, None, None, [["day", [19, 30], [7, 0]]]], None, None, None, []], None, [1]
    ]


def test_daily_limit_day_keeps_global_state():
    assert body(payloads.daily_limit_day("c1", "CAEQAQ", 45, False)) == [
        None, "c1", [None, [[1, None, None, [["CAEQAQ", 45]]]]], None, [1]
    ]


def test_app_restrictions():
    assert body(payloads.app_restriction("c1", "pkg", "blocked")) == ["c1", [[["pkg"], [1]]]]
    assert body(payloads.app_restriction("c1", "pkg", "unlimited")) == ["c1", [[["pkg"], None, None, [1]]]]
    assert body(payloads.app_restriction("c1", "pkg", "limit", 30)) == ["c1", [[["pkg"], None, [30, 1]]]]
    assert body(payloads.app_restriction("c1", "pkg", "default")) == ["c1", [[["pkg"]]]]


def test_device_lock_keeps_allowed_apps():
    assert body(payloads.device_lock("c1", "dev", True)) == [None, "c1", [[None, None, 7, "dev"]], [1]]
    assert body(payloads.device_lock("c1", "dev", False)) == [None, "c1", [[None, None, 4, "dev"]], [1]]


def test_time_bonus_shapes():
    android = body(payloads.time_bonus("c1", "dev", 30, False))[2][0]
    chromeos = body(payloads.time_bonus("c1", "dev", 30, True))[2][0]
    assert (android[2], len(android), android[-1]) == (10, 14, [[1800, 0]])
    assert (chromeos[2], len(chromeos), chromeos[-1]) == (6, 11, ["1800000"])


def test_contacts():
    assert body(payloads.contacts("c1", "added_by_parent")) == [None, "c1", None, None, 3]
