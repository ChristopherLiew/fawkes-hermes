# Architecture

A short map of how `fawkes-hermes` fits together and which properties must not break. Setup steps are in [GO_LIVE.md](GO_LIVE.md), the full reference is [DESIGN.md](DESIGN.md), the release flow is [CICD.md](CICD.md), and the reasoning behind each security control is [SECURITY_REVIEW.md](SECURITY_REVIEW.md). Day-to-day rules are in [DEVELOPMENT.md](DEVELOPMENT.md).

## System at a glance

One personal Hermes Agent (the prebuilt `nousresearch/hermes-agent` image) runs on a single always-on Fly.io machine in `sin`. This repo has no application code. It holds the pinned infra config, the agent's skills, the scripts that deliver them, and the docs.

```
 Telegram ──HTTPS POST──▶ Fly edge :443 ──▶ :8443 /tg-<random>   (only public route)
                                              │  secret header + user allowlist
                                              ▼
                      ┌── machine (1, always on, image pinned by tag@digest) ──┐
                      │ s6 supervises:                                          │
                      │   gateway  → webhook handler + cron ticker             │
                      │   dashboard :9119 (private network + basic auth)       │
                      │ runs as hermes (UID 10000); root only for ssh/sync     │
                      │                                                         │
                      │ volume hermes_data → /opt/data  (all state)             │
                      │   config.yaml, .env, memories/, sessions/, skills/      │
                      │   skills-repo/   root-owned, read-only to the agent     │
                      │   .ssh/skills_deploy   root-only deploy key             │
                      └─────────────────────────────────────────────────────────┘
 GitHub (this repo) ──▶ CI ──▶ deploy-skills (auto) / deploy-infra (manual) ──▶ fly ssh / fly deploy
```

## Components

| Component | Lives in | Owner at runtime | Notes |
|---|---|---|---|
| Hermes image | `fly.toml` (`image = "…:vX.Y.Z@sha256:…"`) | upstream, pinned | Never `latest`, `main` or a tag without a digest |
| Gateway + cron | one process in the image | `hermes` (10000) | Webhook and cron share it, so the machine must stay up |
| Dashboard | port 9119 | `hermes` | Reached only through `fly proxy`; never under `[[services]]` |
| State | volume at `/opt/data` | `hermes` (10000) | Survives deploys; snapshots are the only backup |
| Skills source | `skills/<name>/SKILL.md` | repo | Validated by `scripts/validate_skills.py` |
| Skills on the machine | `/opt/data/skills-repo` | root, read-only | Published by `scripts/sync-skills.sh`, loaded via `skills.external_dirs` |
| Secrets | Fly secrets (names in `.env.example`) | Fly | Never in git or GitHub |
| CI/CD | `.github/workflows/` | GitHub Actions | `FLY_API_TOKEN` only in the `production` environment, limited to `main` |
| Local instance | `compose.yaml`, `make local-*` | developer laptop | Optional, with a separate dev bot in polling mode |

## Trust boundaries

1. **Internet to webhook.** One port, a random path, `TELEGRAM_WEBHOOK_SECRET` and `TELEGRAM_ALLOWED_USERS`. Nothing else is routed.
2. **Agent to root.** The agent reads untrusted content (web, files, chat), so assume it is prompt-injectable and hostile. It owns `/opt/data` and can rename or replace anything there. Root must never execute or trust anything from the volume.
3. **Repo to machine.** Whoever can merge to `main` can change the agent's instructions, and whoever can run the `production` environment has root over SSH. GitHub Free gives no branch protection or approval gate, so the typed-version dispatch for infra and the validators stand in for them.
4. **Laptop to everything.** Runtime secrets are set from the laptop with `fly secrets set` and are never stored in GitHub.

## Data flows

- **Message:** Telegram POST, then secret and allowlist check, then the agent loop (model calls through OpenRouter), then the reply. Session and memory writes go to the volume.
- **Skill API calls:** skill scripts run in the agent's `terminal` sandbox and call LTA DataMall, data.gov.sg and Open-Meteo directly, with the keys Hermes passes through from `required_environment_variables`. The `flights` skill calls the remote Kiwi.com MCP server (`mcp_kiwi_search_flight`). All of these responses are untrusted input to the model.
- **Cron:** the ticker inside the gateway fires jobs stored in agent state. They start with no chat history and approvals default to deny, so skills must be self-contained.
- **Skills release:** merge to `main`, then `ci` and `deploy-skills`. The workflow validates, streams `sync-skills.sh` over `fly ssh` with `REF=$GITHUB_SHA`, and checks `/opt/data/skills-repo/.revision` matches. The script fetches into `/root`, publishes only `skills/`, and swaps it in with an atomic rename.
- **Infra release:** PR bumps the `fly.toml` pin, then `ci` checks it, then a person runs `deploy-infra` with the typed version, which runs `fly deploy --ha=false` and asserts one started machine on the pinned digest.

## Invariants (do not break)

| Invariant | Why | Enforced by |
|---|---|---|
| Exactly one machine; `auto_stop_machines = "off"` | Cron needs the gateway up, and two gateways on one token fight over the webhook | `deploy-infra` assertion, `--ha=false` |
| Only 443→8443 is public | Shrinks the attack surface | review of `fly.toml` |
| Image pinned by `vX.Y.Z@sha256:` | Reproducible, tamper-evident | `make check-image`, `ci` |
| Root never executes files from the volume | The agent can write there (SECURITY_REVIEW H1) | `sync-skills.sh` design (below) |
| `sync-skills.sh` is streamed, never stored on the volume | Same | `make sync-skills`, `deploy-skills` |
| Sync validates the deploy key (root-owned, mode 600, not a symlink) and fetches fresh into `/root` with hooks and symlinks off | Same | `sync-skills.sh` |
| Skills on the machine are root-owned and read-only, with no `.git/` | The agent cannot rewrite its own instructions | `sync-skills.sh` |
| No runtime secrets in GitHub; no personal identifiers in tracked files | Limits blast radius of a repo leak | gitleaks hooks and CI |
| No `pull_request_target` workflows; no auto `fly deploy` on push | Untrusted code must not reach secrets or production | review, `ci` |
| Deploy workflows share the `fly-fawkes-hermes` concurrency group | A sync never overlaps a deploy | workflow config |
| The owner is the only commit author | Provenance of what ships | `commit-msg` hook, CI |

## Key decisions

| Decision | Chosen | Instead of | Reason |
|---|---|---|---|
| Hosting | Fly.io, one always-on machine | scale-to-zero | Cron only runs while the gateway is up |
| Telegram transport | Webhook | Long polling | Owner's choice; hardened with path, secret header and allowlist |
| Skill delivery | Streamed sync script, pull over a read-only deploy key | Baking skills into an image or mounting from the volume | No image rebuilds, and root never trusts volume contents |
| Infra deploys | Manual dispatch with a typed version | Deploy on merge | An image bump changes the running binary, and Free has no approval gate |
| Image | Official, entrypoint untouched | Custom build | Keeps s6 supervision and the non-root user; no Docker needed to deploy |
| Friends or other users | A separate app | Shared gateway | One gateway shares memory, skills, terminal and filesystem across all users |

## Changing the architecture

Update, in the same PR: the matching DESIGN section and §15 checklist, the SECURITY_REVIEW finding it touches, CICD.md and GO_LIVE.md, and this file's invariants and decisions tables. Mark anything not yet confirmed on a real deploy with 🔎.
