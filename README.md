# familylink-mcp

MCP server for **Google Family Link**. Lets an AI assistant read and change the parental controls of your supervised children: downtime (bedtime), daily screen time limits, app rules, device lock, extra time and contacts.

It talks to the same private API as [familylink.google.com](https://familylink.google.com), using the Google session of the parent account in Chrome. No browser automation.

> Unofficial. The API is not public and can change without notice.

## Tools

| Tool | What it does |
|---|---|
| `list_children` | Supervised children |
| `get_settings` | Devices, downtime, daily limit, apps, contacts, website filter, Google services, location sharing, device restrictions (developer options, unknown sources, ...) |
| `get_usage` | Screen time per day, app and device; today's lock state and remaining time |
| `list_apps` | Installed apps and their status (blocked, unlimited, limit, default) |
| `set_downtime` | Weekly downtime schedule on/off |
| `set_downtime_days` | Start/end time and on/off per weekday |
| `set_daily_limit` | Daily limit on/off |
| `set_daily_limit_minutes` | Daily minutes per weekday |
| `set_app` | Block, always allow, limit or reset an app |
| `lock_device` | Lock or unlock a device now |
| `add_time` / `remove_extra_time` | Give or withdraw extra time today |
| `set_contacts` | Who the child can call and text |

Every write reads the state back from Google and returns it.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/), Google Chrome signed in to the **parent** account (open familylink.google.com once). On macOS the first run asks for Keychain access to "Chrome Safe Storage" so the cookies can be read.

```json
{
  "mcpServers": {
    "familylink": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/jantoebes/familylink-mcp", "familylink-mcp"]
    }
  }
}
```

## Not (yet) supported

School time, website allow/block lists, Google Play and YouTube settings, and changing device restrictions are read-only or missing. Apple Screen Time has no API and is out of scope.

## Development

```sh
uv sync
uv run pytest
```

## Credits

Request formats are based on the reverse engineering in [noiwid/HAFamilyLink](https://github.com/noiwid/HAFamilyLink) (MIT), plus own captures of the web app.

## License

MIT
