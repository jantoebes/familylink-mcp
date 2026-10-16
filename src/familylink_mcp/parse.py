from collections import defaultdict
from datetime import date

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
CONTACT_NAMES = {
    "communicationsRestrictionLevelUnspecified": "anyone",
    "communicationsRestrictionAllowAll": "anyone",
    "communicationsRestrictionAllowlistedOnly": "added_by_parent",
    "communicationsRestrictionAllowlistedAndSemiTrustedGroups": "added_by_parent_and_groups",
}


def is_on(state: str | None) -> bool:
    return state in ("timeLimitOn", "modeEnabled")


def clock(value: dict) -> str:
    return f'{value.get("hour", 0):02d}:{value.get("minute", 0):02d}'


def children(members: dict) -> list[dict]:
    return [
        {
            "name": m["profile"]["displayName"].split()[0].lower(),
            "display_name": m["profile"]["displayName"],
            "id": m["userId"],
            "email": m["profile"].get("email"),
        }
        for m in members.get("members", [])
        if m.get("memberSupervisionInfo", {}).get("isSupervisedMember")
    ]


def by_day(entries: list[dict], render) -> dict:
    ordered = sorted(entries, key=lambda e: DAYS.index(e["effectiveDay"]))
    return {e["effectiveDay"]: render(e) for e in ordered}


def downtime_mode(time_limit: dict) -> dict:
    modes = [m for m in time_limit.get("supervisionModes", []) if m.get("type") == "downtimeMode"]
    return modes[0] if modes else {}


def downtime(time_limit: dict) -> dict:
    window = time_limit.get("timeWindowLimit", {})
    mode = downtime_mode(time_limit)
    return {
        "enabled": is_on(mode.get("state")) if mode else is_on(window.get("state")),
        "mode_id": mode.get("id"),
        "days": by_day(
            window.get("entries", []),
            lambda e: {"enabled": is_on(e["state"]), "start": clock(e["startsAt"]), "end": clock(e["endsAt"]), "id": e["id"]},
        ),
    }


def daily_limit(time_limit: dict) -> dict:
    usage = (time_limit.get("timeUsageLimits") or [{}])[0]
    return {
        "enabled": is_on(usage.get("state")),
        "resets_at": clock(usage.get("resetsAt", {})),
        "days": by_day(
            usage.get("entries", []),
            lambda e: {"enabled": is_on(e["state"]), "minutes": e.get("usageQuotaMins", 0), "id": e["id"]},
        ),
    }


def app_status(app: dict) -> str:
    setting = app.get("supervisionSetting", {})
    always = setting.get("alwaysAllowedAppInfo", {}).get("alwaysAllowedState") == "alwaysAllowedStateEnabled"
    return (
        "blocked" if setting.get("hidden")
        else "unlimited" if always
        else "limit" if setting.get("usageLimit")
        else "default"
    )


def apps(apps_and_usage: dict) -> list[dict]:
    return sorted(
        (
            {
                "title": a.get("title", a["packageName"]),
                "package": a["packageName"],
                "status": app_status(a),
                "limit_minutes": a.get("supervisionSetting", {}).get("usageLimit", {}).get("dailyUsageLimitMins"),
                "system": bool(a.get("isSystemApp")),
            }
            for a in apps_and_usage.get("apps", [])
        ),
        key=lambda a: a["title"].lower(),
    )


def apps_summary(app_list: list[dict]) -> dict:
    grouped = defaultdict(list)
    for app in app_list:
        grouped[app["status"]].append(app["title"])
    return {
        "blocked": grouped["blocked"],
        "always_allowed": grouped["unlimited"],
        "limited": {a["title"]: a["limit_minutes"] for a in app_list if a["status"] == "limit"},
        "default_count": len(grouped["default"]),
    }


def devices(apps_and_usage: dict) -> list[dict]:
    return [
        {
            "id": d["deviceId"],
            "name": d.get("displayInfo", {}).get("friendlyName") or d.get("displayInfo", {}).get("model"),
            "model": d.get("displayInfo", {}).get("model"),
            "last_activity_ms": int(d.get("displayInfo", {}).get("lastActivityTimeMillis", 0)),
        }
        for d in apps_and_usage.get("deviceInfo", [])
    ]


def session_day(session: dict) -> date:
    d = session["date"]
    return date(d["year"], d["month"], d["day"])


def seconds(session: dict) -> float:
    return float(session.get("usage", "0s").rstrip("s"))


def usage(apps_and_usage: dict, since: date) -> dict:
    titles = {a["packageName"]: a.get("title", a["packageName"]) for a in apps_and_usage.get("apps", [])}
    names = {d["id"]: d["name"] for d in devices(apps_and_usage)}
    sessions = [s for s in apps_and_usage.get("appUsageSessions", []) if session_day(s) >= since]
    per_day, per_app, per_device = defaultdict(float), defaultdict(float), defaultdict(float)
    for s in sessions:
        package = s.get("appId", {}).get("androidAppPackageName", "?")
        per_day[session_day(s).isoformat()] += seconds(s)
        per_app[titles.get(package, package)] += seconds(s)
        per_device[names.get(s.get("deviceMudId"), s.get("deviceMudId"))] += seconds(s)
    return {
        "since": since.isoformat(),
        "minutes_per_day": {k: round(v / 60) for k, v in sorted(per_day.items())},
        "minutes_per_app": {k: round(v / 60) for k, v in sorted(per_app.items(), key=lambda kv: -kv[1]) if v >= 60},
        "minutes_per_device": {k: round(v / 60) for k, v in per_device.items()},
    }


def today(applied: dict, names: dict) -> list[dict]:
    return [
        {
            "device": names.get(a.get("deviceId"), a.get("deviceId")),
            "locked": a.get("isLocked", False),
            "used_minutes": int(a.get("currentUsageUsedMillis", 0)) // 60_000,
            "remaining_minutes": a.get("currentUsageRemainingMins"),
            "active_policy": a.get("activePolicy"),
        }
        for a in applied.get("appliedTimeLimits", [])
    ]


def is_bonus(override: dict, device_id: str) -> bool:
    return override.get("deviceId") == device_id and override.get("action") in ("unlockFor", "unlockUntilLockDeadline")


def contacts(trusted: dict) -> str:
    level = trusted.get("restrictionLevel", "communicationsRestrictionLevelUnspecified")
    return CONTACT_NAMES.get(level, level)


def websites(restrictions: dict) -> dict:
    return {
        "filter": restrictions.get("filterLevel"),
        "exceptions": [
            {"site": e.get("pattern"), "type": e.get("exceptionType")}
            for e in restrictions.get("explicitWebsiteExceptions", [])
        ],
    }


def without_header(value: dict) -> dict:
    return {k: v for k, v in value.items() if k != "apiHeader"}


def restriction(item: list, names: dict) -> dict:
    key, info, value = item[0], item[1], item[2]
    allowed = bool(value and value[0] == 1)
    texts = (info[6] or [[None, None]])[0] if len(info) > 6 else [None, None]
    return {
        "device": names.get(key[-1], key[-1]),
        "setting": info[0],
        "allowed": allowed,
        "meaning": texts[0] if allowed else texts[1],
    }


def device_restrictions(response: list, names: dict) -> list[dict]:
    groups = response[1] if len(response) > 1 and response[1] else []
    return [restriction(item, names) for group in groups for item in (group[2] or [])]
