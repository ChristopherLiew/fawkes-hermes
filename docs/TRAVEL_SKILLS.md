# Travel skills: sg-bus, weather, itinerary, flights

The spec for the four travel skills, finalised from the initial draft and implemented in this repo. **Where the draft and this repo's conventions disagreed, the repo won.** Every difference is listed under [Deviations from the draft](#deviations-from-the-draft).

## Goal and scope

Let the agent answer these kinds of request quickly and accurately, for **any user** of an instance:
- "When's the next 10 at my stop?", "buses near Bugis?", "is the MRT down?"
- "Will it rain in Tampines this afternoon?", "weather in Kyoto next week?"
- "Plan Saturday in Tokyo, I land at 9am", "half-day in Joo Chiat with a rain plan"
- "Best way to get to Osaka mid-March, ±3 days?", "is SQ worth the extra over Scoot?"

**Out of scope:** any booking or payment, Notion or Google Workspace, building or hosting MCP servers, and changes to Hermes core or `fly.toml`.

| Skill | Type | Data source | Secret |
|---|---|---|---|
| [`sg-bus`](../skills/sg-bus/SKILL.md) | script + instructions | LTA DataMall | `LTA_DATAMALL_KEY` (required) |
| [`weather`](../skills/weather/SKILL.md) | script + instructions | NEA via data.gov.sg (SG); Open-Meteo (elsewhere) | `DATA_GOV_SG_API_KEY` (optional) |
| [`itinerary`](../skills/itinerary/SKILL.md) | instructions + template | orchestrates `maps` (bundled with Hermes), `weather`, `sg-bus`, web search | none |
| [`flights`](../skills/flights/SKILL.md) | instructions + rubric + templates | Kiwi.com MCP `search-flight`, plus web search to cross-check | none (the MCP needs no key) |

## Layout

```
skills/<name>/SKILL.md (+ scripts/ references/ templates/)   # published read-only to /opt/data/skills-repo
tests/                                                        # repo-only: never published
  support.py · test_sg_bus.py · test_weather.py · test_flights_skill.py · test_skill_frontmatter.py
  fixtures/*.json                                             # recorded API responses, keys stripped
```

## Conventions applied

- **Frontmatter:**
  - Repo template (`skills/AGENTS.md`): `name` equals the directory, a description of 60 characters or fewer, `version`, `author: owner`, `metadata.hermes.category: travel`.
  - Upstream fields added: `license`, `platforms`, `tags`, `related_skills`, and `requires_toolsets: [terminal]` for the two skills with scripts.
- **Secrets:** declared under `required_environment_variables`. Hermes passes declared variables through to the `terminal` sandbox. The values live in Fly secrets and in gitignored `.env.local`, never in the repo.
- **Script paths:** always `python3 ${HERMES_SKILL_DIR}/scripts/<file>.py`. The validator now fails on a missing target or a hardcoded `~/.hermes` path.
- **Scripts:**
  - Python 3.11+, stdlib only, `argparse` subcommands, plain text sized for Telegram by default, `--json` for chaining.
  - HTTP: a 10 s timeout, one retry on 5xx or timeout, and `User-Agent: fawkes-hermes-skills/1.0`.
  - Errors are one actionable stderr line with a non-zero exit, and never include a key.
- **Cache:** `${SKILLS_CACHE_DIR:-${XDG_CACHE_HOME:-~/.cache}}/fawkes/<skill>/`. Only `sg-bus` uses it (the bus-stop list, 7-day TTL). Scripts never write inside the skill directory, which is read-only on the server and tested that way.
- **User context:** the skills hold no personal data. Order of resolution:
  1. The message.
  2. This user's memory, labelled with their name or handle, because several people can share one gateway's memory.
  3. Generic defaults, stated as assumptions.

  Never invent a personal anchor (stop, airport).

## Verified facts the skills rely on

| Fact | Source |
|---|---|
| LTA endpoints `v3/BusArrival`, `BusStops` (500 per page, `$skip`), `TrainServiceAlerts`, and their field meanings | LTA DataMall API User Guide v6.11, checked against live responses |
| NEA v2 shape: `{code, data: {area_metadata, items[].forecasts[]}}`, `records[]` for the 24-h forecast and 4-day outlook; 47 areas | live responses |
| Open-Meteo `forecast_hours=24` starts at the current local hour | live response |
| Kiwi `search-flight` schema: dates `dd/mm/yyyy`, flex days 0–10, bags per adult, `currency` | live `tools/list` → [kiwi-tool.md](../skills/flights/references/kiwi-tool.md) |
| Kiwi `price` includes the requested bags (448 → 629 SGD for one bag) | live search |
| Kiwi `allow_self_transfer=false` did **not** change results, and results have no self-transfer field | live search; the skill flags carrier or airport changes itself |
| Hermes cron suppresses delivery on an exact `[SILENT]` reply, and feeds each run the job's last non-silent output | Hermes v0.23.0 cron docs and `cron/scheduler_prompt.py` |
| Hermes registers MCP tools as `mcp_<server>_<tool>` (so `mcp_kiwi_search_flight`), filtered with `tools.include` | Hermes v0.23.0 MCP docs |

## Testing

- `make test`: stdlib `unittest`, fixtures only, no network. It covers parse and format, an empty `EstimatedArrival`, `Monitored = 0`, minute rounding, stop search and nearby search, train alerts, NEA area fuzzy-matching, WMO table sync, the 401/429/5xx messages, the key-never-in-URL-or-error rule, the stop cache, a read-only skill directory, flights content rules, and generic-content and secret scans.
- `make test-live`: the same, plus real API calls. It needs `SKILLS_LIVE=1`, and the keys come from `.env.local`. CI never has keys.
- CI: a `tests` job in `ci.yml` (Python 3.11, pinned PyYAML for the frontmatter YAML check). `deploy-skills` also runs the tests before publishing. A pre-commit hook runs them on changes to `skills/` or `tests/`.

## Deviations from the draft

| Draft | Implemented | Why |
|---|---|---|
| Separate `hermes-skills` repo, flat skill dirs, `sync.yml` | `skills/<name>/` in this monorepo; existing `deploy-skills.yml` / `sync-skills.sh` | Repo architecture (AGENTS.md); flat dirs kept |
| Fly app `hermes-me` | `fawkes-hermes` | The real app name |
| `author: Chris` | `author: owner` | Repo rule: no personal identifiers in tracked files |
| Descriptions ≤ 80 chars | ≤ 60, ending in a period | Repo rule and the Hermes hardline (index width) |
| pytest + `pip install pytest pyyaml`; new `test.yml` | stdlib `unittest`; a `tests` job in `ci.yml` with only pinned PyYAML; `make test` | DEVELOPMENT.md: Python tooling is stdlib-only, so CI needs no install step. One workflow for PR checks |
| `@pytest.mark.live`, run whenever the key is set | `SKILLS_LIVE=1` opt-in as well | Keeps the default local run offline and deterministic |
| Live tests load `.env.local` via `conftest.py` | `tests/support.py` loads `.env.local` only for live tests | No pytest |
| `.env.local` holds only the two keys | The two keys added to the existing `.env.local` (also the compose env file); names in `.env.local.example` and `.env.example` | One local secrets file, already gitignored |
| "No file contains 'Chris'" check | Checks for emails, @handles, secret-looking strings, `author: owner` | Writing the owner's name into a test would itself break the identifier rule |
| Arrivals flag `WAB` buses | Arrivals flag **non**-WAB buses (`no WAB`) | Almost every bus is WAB, so flag the exception |
| Load shown alongside `(sched)` | `(sched)` replaces load for timetable times | Load isn't meaningful without a live position |
| Self-transfer detected from Kiwi data | Flagged as "possible self-transfer" when the carrier or airport changes | The results carry no ticketing field, and the filter param had no effect in testing |
| Allowed subdirs: scripts/references/templates/assets | Also `examples/` | Existing validator contract |
| Record LTA fixtures live for every endpoint | Live for arrivals, stops and normal train alerts. The disrupted train-alert fixture is built from the guide's documented fields | A real disruption can't be recorded on demand |
| `npx @modelcontextprotocol/inspector` to capture the Kiwi schema | Plain JSON-RPC over `curl` | No third-party package needed |

## Manual steps (owner)

1. **Secrets:** done. Both keys are Fly secrets on `fawkes-hermes`. Re-run `make skill-secrets` after rotating a key in `.env.local` (this restarts the machine).
2. **Kiwi MCP** (inside `make ssh`, with `hx` defined as in DESIGN §7.1):
   ```bash
   hx mcp add kiwi --url https://mcp.kiwi.com
   hx mcp configure kiwi     # enable search-flight only; leave feedback-to-devs off
   ```
   Equivalent config: `mcp_servers.kiwi: {url: https://mcp.kiwi.com, tools: {include: [search-flight]}}`. Then run `/reload-mcp` or `make restart`. It's a remote server, so there's no package version to pin. Treat its output as untrusted (SECURITY_REVIEW M5).
3. **Publish skills:** merge the PR. `deploy-skills` publishes once `FLY_API_TOKEN` is in the `production` environment (GO_LIVE step 8). Until then, use `make sync-skills`.
4. **Check:** `make ssh`, then `hx skills list | grep -E "sg-bus|weather|itinerary|flights"`.
5. **Try it** in Telegram after `/new`: "next bus at 83139", "rain in Tampines later?", "plan Saturday in Tokyo, land 9am", "best flights SIN→Osaka mid-March ±3 days, 1 bag".
6. **Optional:** set up a price watch from [price-watch-cron.md](../skills/flights/templates/price-watch-cron.md).

Each user tells the agent their own anchors once ("my home stop is 83139", "I fly from SIN, always 1 bag"), and the agent saves them to memory under that user's label.
