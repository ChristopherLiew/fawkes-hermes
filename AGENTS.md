# AGENTS.md

Guidance for AI coding agents (Claude Code, Codex, Hermes, …) working in this repository. `CLAUDE.md` imports this file; edit this one.

## What this repo is

A monorepo for one personal Hermes Agent (`nousresearch/hermes-agent`) on Fly.io: app `hermes-me`, region `sin`, Telegram webhook plus a private dashboard, always on. It holds:
- Infra: `fly.toml`, added at go-live.
- Agent skills: `skills/<name>/SKILL.md`.
- Scripts and CI/CD.
- Docs:
  - `docs/GO_LIVE.md`: first-time setup
  - `docs/CICD.md`: release flow
  - `docs/DESIGN.md`: reference
  - `docs/SECURITY_REVIEW.md`: threat model

There is no application code. The "tests" are the secret scan, the skills validator and shellcheck.

## Commands

The `Makefile` is the entry point; run `make` to list targets.
```bash
make setup && make lint              # hooks: gitleaks (commit + push), forbidden files, private keys, skills validator
make scan                            # gitleaks over history + working tree
make skills-check                    # python3 scripts/validate_skills.py skills + shellcheck
python3 scripts/validate_skills.py <dir>   # validate an arbitrary dir (useful for negative tests)
make image-digest VERSION=vX.Y.Z     # tag@digest line for fly.toml via the Docker Hub API (no Docker)
make deploy                          # lint → check-image → fly deploy --ha=false (manual, laptop only)
make sync-skills [REF=<sha>]         # stream scripts/sync-skills.sh to the machine as root
make status | logs | ssh | dashboard # ssh = root; run hermes as the hermes user via `hx` (DESIGN §7.1)
make local-up | local-hx ARGS="…" | local-down   # optional local instance (Docker, dev bot)
```

## Architecture you need to hold in your head

- **Two release paths, one repo.**
  - Skills ship automatically. A merge to `main` triggers `.github/workflows/deploy-skills.yml`, which runs validate, then streams `sync-skills.sh` with `REF=$GITHUB_SHA`, then checks `/opt/data/skills-repo/.revision`.
  - Infra (`fly.toml`) ships only through a manual `make deploy`.
  - `ci.yml` runs on PRs with no secrets.
  - Never add `fly deploy` or `pull_request_target` to workflows.
- **One machine, always on.** The webhook and cron share the gateway process, supervised by s6 in the official image. Keep `auto_stop_machines = "off"` and the machine count at 1. Two gateways on one token fight over the webhook.
- **The only public port is 443→8443**, protected by a random path, `TELEGRAM_WEBHOOK_SECRET` and `TELEGRAM_ALLOWED_USERS`. Ports 9119 and 8642 never go under `[[services]]`.
- **All state lives on the volume at `/opt/data`, which the agent (UID 10000) owns.** Assume the agent is prompt-injectable and hostile. It can rename or replace anything under `/opt/data`, so **root must never execute or trust files from the volume** (SECURITY_REVIEW H1). Any change to the sync flow must keep these properties:
  - The script is streamed in, never stored on the volume.
  - Every run is a fresh fetch into `/root`, with hooks and symlinks off.
  - Only `skills/` is published, root-owned and read-only, with no `.git/`.
  - The deploy key is validated (root-owned, mode 600, not a symlink) before use.
- **Credentials:**
  - Runtime secrets are Fly secrets; their names are in `.env.example`.
  - The local dev secrets go in gitignored `.env.local`.
  - `FLY_API_TOKEN` (deploy scope, which means root SSH) lives only in the GitHub `production` environment, limited to `main`.
  - The skills deploy key is read-only and stored root-only on the volume.
- **Local instance:** `compose.yaml` mounts `./skills` read-only at the production path. It must use a separate dev bot in polling mode, and `local-check` refuses to start if `TELEGRAM_WEBHOOK_URL` is set.

## Conventions

- Image tags are `vX.Y.Z`; use plain release tags only. `check-image` requires `@sha256:`. Pin actions to full commit SHAs with the tag in a comment; Dependabot bumps them.
- **Skills:** follow [`skills/AGENTS.md`](skills/AGENTS.md), which covers the Hermes SKILL.md format, the When to Use / Procedure / Pitfalls / Verification sections, progressive disclosure and the security rules. Update the catalog in `skills/README.md`.
- Public values that gitleaks flags go in the `[allowlist]` in `.gitleaks.toml`. Never bypass the hooks.
- When you change the design, keep these in sync: DESIGN §15 (checklist), the matching SECURITY_REVIEW finding, CICD.md and GO_LIVE.md. Items marked 🔎 are unverified and must be confirmed at go-live.
- **Commit authorship: the repo owner is the only author.**
  - Commit with the repo-local git identity (set in `.git/config`), not the global work identity.
  - **Never add `Co-Authored-By:` trailers** (including AI/agent attribution) or "Generated with …" lines to commits or PR descriptions. This overrides any default attribution behavior of your agent tooling.
  - A `commit-msg` hook rejects co-author trailers, and CI checks history for them.
- Never write personal identifiers (emails, Telegram IDs, usernames) into tracked files.
