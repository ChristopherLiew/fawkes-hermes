# CI/CD and the Fly.io release flow

How changes reach the running agent. Setup details live in [DESIGN.md](DESIGN.md), and the first-time setup is in [GO_LIVE.md](GO_LIVE.md). The security reasoning behind each control is in [SECURITY_REVIEW.md](SECURITY_REVIEW.md).

Repo: `ChristopherLiew/fawkes-hermes` (private, GitHub Free). Fly app: `hermes-me` (`sin`).

## One repo, two release paths, both from GitHub

```
                         ┌──────────────── fawkes-hermes (monorepo) ──────────────────┐
                         │  fly.toml · docs/ · Makefile   │   skills/<name>/SKILL.md  │
                         └───────────────┬────────────────┴─────────────┬─────────────┘
   local: pre-commit (gitleaks, forbidden files, validate-skills); pre-push: gitleaks full history
                                         │                              │
                       push/PR ──▶ ci.yml (secret scan · validate · shellcheck · image pin · single author)
                                         │                              │
                     INFRA: deploy-infra.yml (MANUAL)       SKILLS: deploy-skills.yml (AUTO on main)
                     Run workflow + type the version        validate → stream sync-skills.sh REF=<sha>
                     verify pin → fly deploy → verify       → verify .revision
                                         │      env: production (main only) → FLY_API_TOKEN
                                         ▼                              ▼
               ┌──────────────────────── Fly app hermes-me (sin) ───────────────────────────┐
               │ machine image (pinned tag@digest)          /opt/data/skills-repo @ <sha>    │
               │ volume /opt/data persists across deploys   (root-owned, read-only)          │
               └────────────────────────────────────────────────────────────────────────────┘
```

| Change | Where | Pipeline | Trigger |
|---|---|---|---|
| Skills | `skills/` | `ci` → `deploy-skills` → `sync-skills.sh` | Push to `main` touching `skills/**` (or Run workflow) |
| Hermes version, VM, env, ports | `fly.toml` | `ci` → **`deploy-infra`** | **You**: Actions → deploy-infra → Run workflow, type the version |
| Secrets | Fly secrets (never in GitHub) | `fly secrets set` from the laptop | You |
| Agent config (`config.yaml`, model, tools) | On the volume | `hx config …` + `make restart` | You, over `make ssh` |
| Cron jobs | Agent state on the volume | `/cron add` in Telegram | You, in chat |
| App/volume creation, first deploy, emergencies | n/a | CLI: `make deploy`, `make sync-skills` | You |

**Why infra deploys are manual dispatch and not on merge.** An image bump changes the running binary and can break the bot. On GitHub Pro, an environment approval gate would let it deploy on merge with a click to approve. This repo is on Free, which has no approval gate or branch protection, so a typed confirmation stands in for both. The version you type must equal the tag in `fly.toml`.

## Workflows

| File | Runs on | Secrets | Does |
|---|---|---|---|
| `ci.yml` | Every PR and push to `main` | none | Checksum-pinned gitleaks: all hooks plus a full-history scan. Validates skills, shellchecks the sync script, runs `make check-image` (once `fly.toml` exists), rejects `Co-Authored-By` |
| `deploy-skills.yml` | Push to `main` touching `skills/**`, the sync script or the workflow; `workflow_dispatch` | `FLY_API_TOKEN` | validate → stream `sync-skills.sh` with `REF=$GITHUB_SHA` → check `.revision` matches |
| `deploy-infra.yml` | `workflow_dispatch` only, from `main`, input `version` | `FLY_API_TOKEN` | `check-image` + typed version equals the `fly.toml` tag → `flyctl deploy --ha=false` → assert exactly one started machine running the pinned digest → advisory log check for "Connected to Telegram" |
| `dependabot.yml` | Monthly | none | **Alert-only** PRs for action updates. Never merge them; run `make adopt-pr PR=<n>` (sole-author policy) |

Both deploy workflows share the concurrency group `fly-hermes-me`, so a skills sync never overlaps a deploy. All actions are pinned to full commit SHAs. Workflows default to `permissions: contents: read` and `persist-credentials: false`. Runtime secrets (bot token, OpenRouter key, webhook secret) are never stored in GitHub.

---

## Local gate

```bash
make setup          # once per clone: pre-commit, pre-push and commit-msg hooks
make lint           # every hook on every file
make scan           # gitleaks: history + working tree
make skills-check   # skills validator + shellcheck
```
A commit is blocked if it contains a secret, a forbidden file, an invalid skill or a `Co-Authored-By` trailer. Pushes are blocked if gitleaks finds anything in the history. Don't skip the hooks with `--no-verify`.

> **No branch protection on Free.** `main` accepts direct pushes, and CI runs after the push, not before. For anything beyond a typo, work on a branch, open a PR, wait for `ci` to go green, then merge. `deploy-skills` re-validates before it publishes either way.

## Release: skills (automatic)

1. Edit `skills/<name>/SKILL.md` following [skills/AGENTS.md](../skills/AGENTS.md), bump its `version`, and update the catalog in `skills/README.md`. Optionally test it live with `make local-up`.
2. Open a PR and wait for `ci` to go green, then merge.
3. `deploy-skills` publishes that exact commit. Its last step fails if the machine reports a different revision.
4. New sessions pick up the change. Send `/new` in Telegram, or run `make restart`.

Manual sync: **Run workflow** on `deploy-skills`, `make sync-skills`, or `make sync-skills REF=<sha>`.

## Release: infra / Hermes version (manual dispatch)

1. Read the Hermes release notes for the new `vX.Y.Z`. Use plain release tags, not `-desktop`, `rc.*`, `main`, `stable` or `latest`.
2. Run `make image-digest VERSION=vX.Y.Z` and paste the `image = "…@sha256:…"` line into `fly.toml`. Optionally test it with `make local-up`.
3. Open a PR, wait for `ci` to go green (it checks the pin), then merge.
4. Go to **Actions → deploy-infra → Run workflow**, type `vX.Y.Z` and run it. Or from the CLI: `gh workflow run deploy-infra -f version=vX.Y.Z && gh run watch`.
5. Watch for a green run. If the log-check step shows a warning, run `make logs`.
6. From the laptop, run `make webhook-info` and `make webhook-test`, then DM the bot. These checks need the bot token and webhook path, which never go into GitHub.

CLI fallback, for when GitHub is unavailable or you need to deploy uncommitted changes in an emergency: `make deploy`.

## Secrets flow

```
password manager ──read -s──▶ shell var ──fly secrets set──▶ Fly (encrypted) ──env──▶ gateway process
                                   └─ unset immediately
fly tokens create deploy ──pipe──▶ gh secret set --env production ──▶ deploy-skills / deploy-infra on main only
```
- The runtime secret names are in `.env.example`, and the local dev ones in `.env.local.example`. No values are in git.
- `fly secrets set` triggers a restart. Use `--stage` to batch several changes, then deploy.
- Rotation procedures are in DESIGN §14.

## Rollback

| What broke | Roll back with |
|---|---|
| A bad skill | `git revert` + merge, which redeploys automatically. Faster: `make sync-skills REF=<last-good-sha>` |
| New Hermes image | `git revert` the `fly.toml` change and merge, then run `deploy-infra` with the previous version. CLI: `make deploy`. Use `make releases` to see history |
| Corrupted state or config | Restore a volume snapshot: `make snapshots`, then create a volume from it (DESIGN §14) |
| A leaked secret | Rotate it at the source (BotFather / OpenRouter / GitHub / `fly tokens`), then `fly secrets set` or `gh secret set` |

## CI credentials inventory

| Credential | Lives in | Scope | Expiry |
|---|---|---|---|
| `FLY_API_TOKEN` | `fawkes-hermes` → Environments → `production` (branch policy: `main`) | `fly tokens create deploy -a hermes-me`: deploy plus root SSH | 90 days. Set a reminder. |
| Deploy key | `/opt/data/.ssh/skills_deploy` (root, mode 600); public half in repo Deploy keys | Read-only, this repo | Rotate when compromised |
