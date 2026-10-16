from datetime import date, timedelta
from functools import cached_property

from . import parse, payloads
from .client import Client, fail

TIME_LIMIT = {"capabilities": "TIME_LIMIT_CLIENT_CAPABILITY_SCHOOLTIME", "timeLimitKey.type": "SUPERVISED_DEVICES"}
APPS_AND_USAGE = {"capabilities": ["CAPABILITY_APP_USAGE_SESSION", "CAPABILITY_SUPERVISION_CAPABILITIES"]}
DAY_GROUPS = {"all": parse.DAYS, "weekdays": parse.DAYS[:5], "weekend": parse.DAYS[5:]}
CHROMEOS_ID_MIN_LENGTH = 60


def expand_days(days: str) -> list[str]:
    names = [d.strip().lower() for d in days.split(",") if d.strip()]
    expanded = [day for name in names for day in DAY_GROUPS.get(name, [name])]
    unknown = [d for d in expanded if d not in parse.DAYS]
    return fail(f"Unknown day(s): {', '.join(unknown)}") if unknown else expanded


def downtime_bodies(child_id: str, days: list[dict], start: str | None, end: str | None, enabled: bool | None) -> list[str]:
    times = [payloads.downtime_day_times(child_id, d["id"], start or d["start"], end or d["end"]) for d in days if start or end]
    states = [payloads.downtime_day_state(child_id, d["id"], enabled) for d in days if enabled is not None]
    return times + states


def field_values(item: dict, fields: tuple[str, ...]) -> list[str]:
    return [str(item.get(f) or "").lower() for f in fields]


def pick(items: list[dict], query: str, kind: str, *fields: str) -> dict:
    needle = query.strip().lower()
    exact = [i for i in items if needle in field_values(i, fields)]
    loose = [i for i in items if any(needle in v for v in field_values(i, fields))]
    found = exact or loose
    return (
        found[0] if len(found) == 1
        else fail(f"{kind} '{query}' is ambiguous: {', '.join(str(i.get(fields[0])) for i in found)}") if found
        else fail(f"{kind} '{query}' not found")
    )


class Family:
    def __init__(self, client: Client | None = None):
        self._client = client

    @cached_property
    def client(self) -> Client:
        return self._client or Client()

    def people(self, child_id: str, path: str) -> str:
        return f"people/{child_id}/{path}"

    def children(self) -> list[dict]:
        return parse.children(self.client.get("families/mine/members"))

    def child(self, name: str) -> dict:
        return pick(self.children(), name, "Child", "name", "display_name", "id", "email")

    def time_limit(self, child_id: str) -> dict:
        return self.client.get(self.people(child_id, "timeLimit"), **TIME_LIMIT)["timeLimit"]

    def apps_and_usage(self, child_id: str) -> dict:
        return self.client.get(self.people(child_id, "appsandusage"), **APPS_AND_USAGE)

    def device_names(self, apps_and_usage: dict) -> dict:
        return {d["id"]: d["name"] for d in parse.devices(apps_and_usage)}

    def device_restrictions(self, child_id: str, names: dict) -> list[dict]:
        response = self.client.request(
            "POST", self.people(child_id, "restrictions:listByGroups"), body=payloads.device_restrictions_query(child_id)
        )
        return parse.device_restrictions(response, names)

    def settings(self, name: str) -> dict:
        kid = self.child(name)
        cid = kid["id"]
        time_limit = self.time_limit(cid)
        usage = self.apps_and_usage(cid)
        names = self.device_names(usage)
        services = parse.without_header(self.client.get(self.people(cid, "googleServiceSettings")))
        location = self.client.get(self.people(cid, "locationsettings")).get("locationSharingSettings", {})
        return {
            "child": kid,
            "devices": parse.devices(usage),
            "downtime": parse.downtime(time_limit),
            "daily_limit": parse.daily_limit(time_limit),
            "apps": parse.apps_summary(parse.apps(usage)),
            "contacts": parse.contacts(self.client.get(self.people(cid, "trustedcontacts"))),
            "websites": parse.websites(self.client.get(self.people(cid, "websites:listRestrictions"))),
            "google_services": services,
            "location_sharing": location.get("locationSharingState"),
            "device_restrictions": self.device_restrictions(cid, names),
        }

    def usage(self, name: str, days: int) -> dict:
        cid = self.child(name)["id"]
        usage = self.apps_and_usage(cid)
        applied = self.client.get(self.people(cid, "appliedTimeLimits"), capabilities=TIME_LIMIT["capabilities"])
        return parse.usage(usage, date.today() - timedelta(days=days - 1)) | {
            "today": parse.today(applied, self.device_names(usage))
        }

    def apps(self, name: str) -> list[dict]:
        return parse.apps(self.apps_and_usage(self.child(name)["id"]))

    def update_time_limit(self, child_id: str, body: str) -> None:
        self.client.request("PUT", self.people(child_id, "timeLimit:update"), body=body)

    def set_downtime(self, name: str, enabled: bool) -> dict:
        cid = self.child(name)["id"]
        mode_id = parse.downtime(self.time_limit(cid))["mode_id"] or fail("No downtime schedule found for this child")
        self.update_time_limit(cid, payloads.downtime_mode(cid, mode_id, enabled))
        return parse.downtime(self.time_limit(cid))

    def set_downtime_days(self, name: str, days: str, start: str | None, end: str | None, enabled: bool | None) -> dict:
        cid = self.child(name)["id"]
        schedule = parse.downtime(self.time_limit(cid))["days"]
        targets = [schedule[d] for d in expand_days(days) if d in schedule]
        for body in downtime_bodies(cid, targets, start, end, enabled):
            self.update_time_limit(cid, body)
        return parse.downtime(self.time_limit(cid))

    def set_daily_limit(self, name: str, enabled: bool) -> dict:
        cid = self.child(name)["id"]
        self.update_time_limit(cid, payloads.daily_limit_state(cid, enabled))
        return parse.daily_limit(self.time_limit(cid))

    def set_daily_limit_minutes(self, name: str, days: str, minutes: int) -> dict:
        cid = self.child(name)["id"]
        current = parse.daily_limit(self.time_limit(cid))
        for day in expand_days(days):
            self.update_time_limit(cid, payloads.daily_limit_day(cid, current["days"][day]["id"], minutes, current["enabled"]))
        return parse.daily_limit(self.time_limit(cid))

    def set_app(self, name: str, app: str, mode: str, minutes: int) -> dict:
        cid = self.child(name)["id"]
        target = pick(parse.apps(self.apps_and_usage(cid)), app, "App", "title", "package")
        self.client.request("POST", self.people(cid, "apps:updateRestrictions"), body=payloads.app_restriction(cid, target["package"], mode, minutes))
        return pick(parse.apps(self.apps_and_usage(cid)), target["package"], "App", "package")

    def device(self, child_id: str, query: str) -> dict:
        return pick(parse.devices(self.apps_and_usage(child_id)), query, "Device", "name", "model", "id")

    def device_today(self, child_id: str, device: dict) -> dict:
        applied = self.client.get(self.people(child_id, "appliedTimeLimits"), capabilities=TIME_LIMIT["capabilities"])
        states = parse.today(applied, {device["id"]: device["name"]})
        return next((s for s in states if s["device"] == device["name"]), {"device": device["name"]})

    def create_override(self, child_id: str, body: str) -> None:
        self.client.request("POST", self.people(child_id, "timeLimitOverrides:batchCreate"), body=body)

    def lock_device(self, name: str, device: str, locked: bool) -> dict:
        cid = self.child(name)["id"]
        target = self.device(cid, device)
        self.create_override(cid, payloads.device_lock(cid, target["id"], locked))
        return self.device_today(cid, target)

    def add_time(self, name: str, device: str, minutes: int) -> dict:
        cid = self.child(name)["id"]
        target = self.device(cid, device)
        chromeos = len(target["id"]) >= CHROMEOS_ID_MIN_LENGTH
        self.create_override(cid, payloads.time_bonus(cid, target["id"], minutes, chromeos))
        return self.device_today(cid, target)

    def remove_extra_time(self, name: str, device: str) -> dict:
        cid = self.child(name)["id"]
        target = self.device(cid, device)
        bonuses = [o["id"] for o in self.time_limit(cid).get("overrides", []) if parse.is_bonus(o, target["id"])]
        for override_id in bonuses:
            self.client.request("POST", self.people(cid, f"timeLimitOverride/{override_id}"), params={"$httpMethod": "DELETE"})
        return self.device_today(cid, target) | {"removed": len(bonuses)}

    def set_contacts(self, name: str, level: str) -> str:
        cid = self.child(name)["id"]
        self.client.request("POST", self.people(cid, "trustedcontacts:update"), body=payloads.contacts(cid, level))
        return parse.contacts(self.client.get(self.people(cid, "trustedcontacts")))
