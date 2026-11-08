# CI/CD and the Fly.io release flow

How changes reach the running agent. Setup details live in [DESIGN.md](DESIGN.md), and the first-time setup is in [GO_LIVE.md](GO_LIVE.md). The security reasoning behind each control is in [SECURITY_REVIEW.md](SECURITY_REVIEW.md).

## One repo, two release paths

```
                         ┌──────────────────── hermes (monorepo) ─────────────────────┐
                         │  fly.toml · docs/ · Makefile   │   skills/<name>/SKILL.md  │
                         └───────────────┬────────────────┴─────────────┬─────────────┘
   local: pre-commit (gitleaks, validate-skills) on every commit        │
                                         │                              │
                     PR ──▶ ci.yml (lint · validate skills · shellcheck · image pin) ──▶ merge to protected main
                                         │                              │
                      INFRA: manual from laptop             SKILLS: deploy-skills.yml (auto)
                      make deploy  (fly deploy)             env: production → FLY_API_TOKEN
                                         │                  streams sync-skills.sh REF=<sha>
                                         ▼                              ▼
               ┌──────────────────────── Fly app hermes-me (sin) ───────────────────────────┐
               │ new machine image (pinned tag@digest)      /opt/data/skills-repo @ <sha>    │
               │ volume /opt/data persists across deploys   (root-owned, read-only)          │
               └────────────────────────────────────────────────────────────────────────────┘
```

| Change | Where | Pipeline | Trigger |
|---|---|---|---|
| Skills | `skills/` | `ci` → `deploy-skills` → `sync-skills.sh` | Merge to `main` (or manual dispatch) |
| Hermes version, VM, env, ports | `fly.toml` | `ci` (pin check) → `make deploy` | **You**, from your laptop |
| Secrets | Fly secrets (never git) | `fly secrets set` (deploys and restarts) | You, from your laptop |
| Agent config (`config.yaml`, model, tools) | On the volume | `hx config …` + `make restart` | You, over `make ssh` |
| Cron jobs | Agent state on the volume | `/cron add` in Telegram | You, in chat |

**Why infra deploys stay manual.** `deploy-skills` only syncs files and never runs `fly deploy`. Its token could technically deploy, but the workflow doesn't use it that way, and the token is confined to the `production` environment on `main`. Image bumps change the running binary and can lock you out, so a human runs them and watches the logs.

## Workflows

| File | Runs on | Secrets | Does |
|---|---|---|---|
| `.github/workflows/ci.yml` | Every PR, and pushes to `main` | none | `pre-commit run --all-files` (gitleaks over full history, private keys, skills validator), `validate_skills.py`, `shellcheck`, `make check-image` once `fly.toml` exists |
| `.github/workflows/deploy-skills.yml` | Pushes to `main` touching `skills/**`, the sync script or the workflow itself; `workflow_dispatch` | `FLY_API_TOKEN` (`production` env) | validate → stream `sync-skills.sh` with `REF=$GITHUB_SHA` → check `.revision` matches |
| `.github/dependabot.yml` | Monthly | none | PRs bumping the SHA-pinned actions |

Every action is pinned to a full commit SHA, with the tag in a comment. Workflows default to `permissions: contents: read` and use `persist-credentials: false`.

---

## Local gate

```bash
make setup          # once per clone: install pre-commit hooks
make lint           # every hook on every file
make skills-check   # skills validator + shellcheck (if installed)
```
A commit that contains a secret or an invalid skill is blocked. If gitleaks flags a public value, add it to the `[allowlist]` in `.gitleaks.toml`. Don't skip the hook with `--no-verify`.

## Release: skills (automatic)

1. Edit `skills/<name>/SKILL.md` following [skills/AGENTS.md](../skills/AGENTS.md), bump its `version`, and update the catalog in `skills/README.md`. Optionally test it live with `make local-up`, which mounts `./skills` read-only at the same path as production.
2. Open a PR. `ci` must pass.
3. Merge to `main`. `deploy-skills` publishes that exact commit, and its last step fails if the machine reports a different revision.
4. New sessions pick up the change. Send `/new` in Telegram, or run `make restart`.

Manual or emergency sync: run `make sync-skills` (publishes `origin/main`), or `make sync-skills REF=<sha>`. You can also use **Run workflow** on `deploy-skills` in the Actions tab.

## Release: infra / Hermes version (manual)

1. Read the Hermes release notes for the new `vX.Y.Z`. Use plain release tags, not `-desktop`, `rc.*`, `main`, `stable` or `latest`.
2. Run `make image-digest VERSION=vX.Y.Z` and paste the `image = "…@sha256:…"` line into `fly.toml`.
3. Optional: try it with `make local-up`, using the dev bot.
4. Open a PR; `ci` checks the pin. Merge it.
5. From an up-to-date `main`:
   ```bash
   make deploy          # lint → check-image → fly deploy --ha=false → fly status
   make logs            # expect "[telegram] Connected to Telegram (webhook mode)"
   make ssh             # then: hx doctor   (hx helper: DESIGN §7.1)
   ```
6. Smoke-test with `make webhook-info` and `make webhook-test`, then DM the bot.

## Secrets flow

```
password manager ──read -s──▶ shell var ──fly secrets set──▶ Fly (encrypted) ──env──▶ gateway process
                                   └─ unset immediately
GitHub: FLY_API_TOKEN ──▶ Environment "production" (main only) ──▶ deploy-skills job only
```
- The runtime secret names are in `.env.example`, and the local dev ones in `.env.local.example`. No values are in git.
- `fly secrets set` triggers a restart. Use `--stage` to batch several changes, then `make deploy`.
- Rotation procedures are in DESIGN §14.

## Rollback

| What broke | Roll back with |
|---|---|
| A bad skill | `git revert` + merge, which redeploys automatically. Faster: `make sync-skills REF=<last-good-sha>` |
| New Hermes image | `make releases`, put the previous `tag@digest` back in `fly.toml` (`git revert`), then `make deploy` |
| Corrupted state or config | Restore a volume snapshot: `make snapshots`, then create a volume from it (DESIGN §14) |
| A leaked secret | Rotate it at the source (BotFather / OpenRouter / GitHub / `fly tokens`), then `fly secrets set` |

## CI credentials inventory

| Credential | Lives in | Scope | Expiry |
|---|---|---|---|
| `FLY_API_TOKEN` | This repo → Settings → Environments → `production` (branch: `main`) | `fly tokens create deploy -a hermes-me` (root SSH) | 90 days. Set a reminder. |
| Deploy key | `/opt/data/.ssh/skills_deploy` (root, mode 600); public half in repo Deploy keys | Read-only, this repo | Rotate when compromised |
