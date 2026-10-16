import logging
from typing import Annotated, Literal

from mcp.server import MCPServer
from pydantic import Field

from .family import Family

mcp = MCPServer(
    "familylink",
    instructions=(
        "Google Family Link for the signed-in parent (Chrome session). "
        "Children are addressed by first name. Days: monday..sunday, comma separated, or all/weekdays/weekend. "
        "Times are HH:MM in the child's local time. Every write returns the state read back from Google."
    ),
)
family = Family()

Child = Annotated[str, Field(description="Child first name, e.g. 'emma'")]
Days = Annotated[str, Field(description="monday..sunday, comma separated, or all, weekdays, weekend")]
Clock = Annotated[str | None, Field(description="HH:MM, e.g. 19:30", pattern=r"^\d{1,2}:\d{2}$")]
Device = Annotated[str, Field(description="Device name, model or id, e.g. 'SM-A266B'")]


@mcp.tool()
def list_children() -> list[dict]:
    """Supervised children in the family."""
    return family.children()


@mcp.tool()
def get_settings(child: Child) -> dict:
    """All Family Link settings of a child: devices, downtime, daily limit, apps, contacts, websites, Google services, location and device restrictions."""
    return family.settings(child)


@mcp.tool()
def get_usage(child: Child, days: Annotated[int, Field(ge=1, le=30)] = 1) -> dict:
    """Screen time per day, app and device over the last `days` days, plus today's lock state and remaining time per device."""
    return family.usage(child, days)


@mcp.tool()
def list_apps(child: Child) -> list[dict]:
    """Installed apps with their supervision status: blocked, unlimited (always allowed), limit or default."""
    return family.apps(child)


@mcp.tool()
def set_downtime(child: Child, enabled: bool) -> dict:
    """Turn the weekly downtime (bedtime) schedule on or off."""
    return family.set_downtime(child, enabled)


@mcp.tool()
def set_downtime_days(child: Child, days: Days, start: Clock = None, end: Clock = None, enabled: bool | None = None) -> dict:
    """Change downtime per weekday: start and/or end time, and/or switch those days on or off."""
    return family.set_downtime_days(child, days, start, end, enabled)


@mcp.tool()
def set_daily_limit(child: Child, enabled: bool) -> dict:
    """Turn the daily screen time limit on or off."""
    return family.set_daily_limit(child, enabled)


@mcp.tool()
def set_daily_limit_minutes(child: Child, days: Days, minutes: Annotated[int, Field(ge=0, le=1440)]) -> dict:
    """Set the daily screen time limit in minutes for the given weekdays."""
    return family.set_daily_limit_minutes(child, days, minutes)


@mcp.tool()
def set_app(
    child: Child,
    app: Annotated[str, Field(description="App title or package name")],
    mode: Literal["blocked", "unlimited", "limit", "default"],
    minutes: Annotated[int, Field(ge=0, le=1440, description="Daily minutes, only for mode=limit")] = 0,
) -> dict:
    """Block an app, always allow it (unlimited, ignores limits and downtime), give it a daily limit, or reset it to follow the device limits."""
    return family.set_app(child, app, mode, minutes)


@mcp.tool()
def lock_device(child: Child, device: Device, locked: bool = True) -> dict:
    """Lock or unlock a device now. A locked device keeps the always-allowed apps reachable."""
    return family.lock_device(child, device, locked)


@mcp.tool()
def add_time(child: Child, device: Device, minutes: Annotated[int, Field(ge=1, le=600)]) -> dict:
    """Give extra screen time today on a device. Replaces the remaining time instead of adding to it."""
    return family.add_time(child, device, minutes)


@mcp.tool()
def remove_extra_time(child: Child, device: Device) -> dict:
    """Withdraw extra screen time given earlier on a device."""
    return family.remove_extra_time(child, device)


@mcp.tool()
def set_contacts(child: Child, level: Literal["anyone", "added_by_parent", "added_by_parent_and_groups"]) -> str:
    """Who the child can call and text."""
    return family.set_contacts(child, level)


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    mcp.run()
