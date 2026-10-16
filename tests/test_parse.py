from datetime import date

from familylink_mcp import parse

TIME_LIMIT = {
    "timeWindowLimit": {
        "state": "timeLimitOn",
        "entries": [
            {"id": "w2", "effectiveDay": "tuesday", "state": "timeLimitOff", "startsAt": {"hour": 20}, "endsAt": {"hour": 7, "minute": 30}},
            {"id": "w1", "effectiveDay": "monday", "state": "timeLimitOn", "startsAt": {"hour": 19}, "endsAt": {"hour": 7}},
        ],
    },
    "timeUsageLimits": [
        {"state": "timeLimitOff", "resetsAt": {"hour": 6}, "entries": [{"id": "CAEQAQ", "effectiveDay": "monday", "state": "timeLimitOn", "usageQuotaMins": 40}]}
    ],
    "supervisionModes": [{"id": "mode", "type": "downtimeMode", "state": "modeDisabled"}],
}

APPS = {
    "apps": [
        {"packageName": "a.blocked", "title": "Blocked", "supervisionSetting": {"hidden": True}},
        {"packageName": "a.always", "title": "Always", "supervisionSetting": {"alwaysAllowedAppInfo": {"alwaysAllowedState": "alwaysAllowedStateEnabled"}}},
        {"packageName": "a.limit", "title": "Limited", "supervisionSetting": {"usageLimit": {"dailyUsageLimitMins": 15}}},
        {"packageName": "a.free", "title": "Free", "supervisionSetting": {}},
    ],
    "deviceInfo": [{"deviceId": "d1", "displayInfo": {"model": "Phone", "friendlyName": "Phone", "lastActivityTimeMillis": "5"}}],
    "appUsageSessions": [
        {"usage": "600s", "appId": {"androidAppPackageName": "a.free"}, "deviceMudId": "d1", "date": {"year": 2026, "month": 1, "day": 2}},
        {"usage": "120s", "appId": {"androidAppPackageName": "a.limit"}, "deviceMudId": "d1", "date": {"year": 2026, "month": 1, "day": 2}},
        {"usage": "900s", "appId": {"androidAppPackageName": "a.free"}, "deviceMudId": "d1", "date": {"year": 2025, "month": 12, "day": 1}},
    ],
}


def test_downtime_prefers_supervision_mode_and_orders_days():
    result = parse.downtime(TIME_LIMIT)
    assert result["enabled"] is False
    assert result["mode_id"] == "mode"
    assert list(result["days"]) == ["monday", "tuesday"]
    assert result["days"]["tuesday"] == {"enabled": False, "start": "20:00", "end": "07:30", "id": "w2"}


def test_daily_limit():
    result = parse.daily_limit(TIME_LIMIT)
    assert result["enabled"] is False
    assert result["days"]["monday"] == {"enabled": True, "minutes": 40, "id": "CAEQAQ"}


def test_app_statuses_and_summary():
    statuses = {a["package"]: a["status"] for a in parse.apps(APPS)}
    assert statuses == {"a.blocked": "blocked", "a.always": "unlimited", "a.limit": "limit", "a.free": "default"}
    summary = parse.apps_summary(parse.apps(APPS))
    assert summary == {"blocked": ["Blocked"], "always_allowed": ["Always"], "limited": {"Limited": 15}, "default_count": 1}


def test_usage_since_date():
    result = parse.usage(APPS, date(2026, 1, 1))
    assert result["minutes_per_day"] == {"2026-01-02": 12}
    assert result["minutes_per_app"] == {"Free": 10, "Limited": 2}
    assert result["minutes_per_device"] == {"Phone": 12}


def test_contacts_levels():
    assert parse.contacts({"restrictionLevel": "communicationsRestrictionAllowlistedOnly"}) == "added_by_parent"
    assert parse.contacts({}) == "anyone"


def test_device_restrictions():
    item = [
        [None, None, None, None, ["DISALLOW_DEBUGGING_FEATURES", 1], 2, None, None, "d1"],
        ["Developer options", None, 1, [0], None, None, [["Can turn on", "Can not turn on"]]],
        [1],
        "token",
    ]
    result = parse.device_restrictions([[None, "1"], [[2, None, [item]]]], {"d1": "Phone"})
    assert result == [{"device": "Phone", "setting": "Developer options", "allowed": True, "meaning": "Can turn on"}]


def test_google_play_summary():
    services = {
        "playSettings": {
            "contentFilter": [
                {"info": {"label": "Apps", "optionsFilter": {"filterChoices": [{"level": 3, "labelSummary": "PEGI 12"}, {"labelSummary": "Allow all"}]}}, "value": {"selectedLevel": 3}},
                {"info": {"label": "Books", "binaryFilter": {"onChoice": {"labelSummary": "Restrictions on"}, "offChoice": {"labelSummary": "Allow all"}}}, "value": {}},
            ]
        }
    }
    assert parse.google_services(services)["google_play"] == {"Apps": "PEGI 12", "Books": "Allow all"}


def test_bonus_override():
    assert parse.is_bonus({"deviceId": "d1", "action": "unlockFor"}, "d1")
    assert not parse.is_bonus({"deviceId": "d1", "action": "lock"}, "d1")
