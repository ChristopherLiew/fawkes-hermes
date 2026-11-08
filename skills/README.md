# Skills

This directory holds the procedures the Hermes agent (`fawkes-hermes`) loads on demand. Each subdirectory is one skill, in the [Hermes SKILL.md format](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills). Merging to `main` publishes this directory to the machine, read-only.

> Writing or editing a skill, as a human or an AI agent? Follow **[AGENTS.md](AGENTS.md)**: format, style rules and the validation gate.

## Catalog

| Skill | Category | What it does |
|---|---|---|
| [`research-brief`](research-brief/SKILL.md) | research | Daily news brief per topic: deduped, cited bullets. Built for cron. |
| [`sg-bus`](sg-bus/SKILL.md) | travel | Singapore bus arrivals (also near a Telegram pin), stop lookup and MRT alerts (LTA DataMall). Needs `LTA_DATAMALL_KEY`. |
| [`weather`](weather/SKILL.md) | travel | NEA forecasts for Singapore, Open-Meteo elsewhere. Optional `DATA_GOV_SG_API_KEY`. |
| [`itinerary`](itinerary/SKILL.md) | travel | Day-by-day trip plans with timed legs, costs, rain plans and sources. |
| [`flights`](flights/SKILL.md) | travel | Compares and ranks flights via the Kiwi.com MCP. Research only; never books. |
| [`telegram-format`](telegram-format/SKILL.md) | personal | Default layout for every Telegram message: scannable, phone-sized, per-case templates. |

Keep this table in sync when you add or remove a skill.

The travel skills' spec, secrets and Kiwi MCP setup are in [docs/TRAVEL_SKILLS.md](../docs/TRAVEL_SKILLS.md). Script tests live in [`tests/`](../tests) (`make test`).

## How Hermes uses these files

```
skills_list()               → name + description + category of every skill   (always in context, kept small)
skill_view("research-brief") → the full SKILL.md                              (only when the task matches)
skill_view(name, "templates/brief.md") → one supporting file                  (only when the procedure asks for it)
```
That's why descriptions are short and specific, and why long detail goes in `references/` instead of `SKILL.md`.

On the machine, this directory becomes `/opt/data/skills-repo`. It's registered in `skills.external_dirs`, owned by root and read-only, so the agent can use these skills but can't edit them.

> **Shadowing:** Hermes checks its local `skills/` directory before `external_dirs`. A skill the agent creates itself with the same name **silently overrides** the one here. Don't let the agent "improve" a repo skill in place. Copy its improvements back into this repo through a PR instead.

## Workflow

```bash
# 1. write: skills/<name>/SKILL.md (start from the template in AGENTS.md)
make skills-check                  # 2. validate (also runs on commit and in CI)
make local-up                      # 3. optional: try it live; ./skills is mounted read-only
make local-hx ARGS="skills list"
git switch -c skill/<name> && git commit -am "skill: <name> 1.0.0" && gh pr create --fill
# 4. merge → deploy-skills publishes it → send /new in Telegram to start a fresh session
```

To attach a skill to a scheduled job: `/cron add "every day at 8am" "<self-contained prompt>" --skill research-brief`.

Rollback: `git revert` and merge, or `make sync-skills REF=<last-good-sha>`. See [docs/CICD.md](../docs/CICD.md).
