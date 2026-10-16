import json

ON, OFF = 2, 1
LOCK_KEEP_ALLOWED_APPS, UNLOCK = 7, 4
ANDROID_BONUS, CHROMEOS_BONUS = 10, 6
CONTACT_LEVELS = {"anyone": 1, "added_by_parent": 3, "added_by_parent_and_groups": 4}


def dump(value) -> str:
    return json.dumps(value, separators=(",", ":"))


def flag(enabled: bool) -> int:
    return ON if enabled else OFF


def hour_minute(value: str) -> list[int]:
    hour, minute = value.split(":")
    return [int(hour), int(minute)]


def time_limit_update(child_id: str, block: list) -> str:
    return dump([None, child_id, block, None, [1]])


def downtime_mode(child_id: str, mode_id: str, enabled: bool) -> str:
    return time_limit_update(child_id, [[None, None, None, None], None, None, None, [None, [[mode_id, flag(enabled)]]]])


def downtime_day_state(child_id: str, entry_id: str, enabled: bool) -> str:
    return time_limit_update(child_id, [[None, None, [[entry_id, flag(enabled)]], None], None, None, None, []])


def downtime_day_times(child_id: str, entry_id: str, start: str, end: str) -> str:
    window = [entry_id, hour_minute(start), hour_minute(end)]
    return time_limit_update(child_id, [[None, None, None, [window]], None, None, None, []])


def daily_limit_state(child_id: str, enabled: bool) -> str:
    return time_limit_update(child_id, [None, [[flag(enabled), None, None, None]]])


def daily_limit_day(child_id: str, slot_id: str, minutes: int, enabled: bool) -> str:
    return time_limit_update(child_id, [None, [[flag(enabled), None, None, [[slot_id, minutes]]]]])


def app_restriction(child_id: str, package: str, mode: str, minutes: int = 0) -> str:
    rules = {
        "blocked": [[package], [1]],
        "unlimited": [[package], None, None, [1]],
        "limit": [[package], None, [minutes, 1]],
        "default": [[package]],
    }
    return dump([child_id, [rules[mode]]])


def device_lock(child_id: str, device_id: str, locked: bool) -> str:
    action = LOCK_KEEP_ALLOWED_APPS if locked else UNLOCK
    return dump([None, child_id, [[None, None, action, device_id]], [1]])


def time_bonus(child_id: str, device_id: str, minutes: int, chromeos: bool) -> str:
    android = [None, None, ANDROID_BONUS, device_id, *[None] * 9, [[minutes * 60, 0]]]
    chrome = [None, None, CHROMEOS_BONUS, device_id, *[None] * 6, [str(minutes * 60_000)]]
    return dump([None, child_id, [chrome if chromeos else android], [1]])


def contacts(child_id: str, level: str) -> str:
    return dump([None, child_id, None, None, CONTACT_LEVELS[level]])


def device_restrictions_query(child_id: str) -> str:
    return dump([None, child_id, None, None, None, None, [[2]]])
