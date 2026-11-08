# Development handbook

The guide for working in this repo and for adding new features or tooling to the agent. Part 1 is the rules, and Part 2 is step-by-step recipes ("how do I add X?").

How to work in this repo. For the system layout and the properties that must hold, see [ARCHITECTURE.md](ARCHITECTURE.md). For the pipeline details, see [CICD.md](CICD.md). Skill authoring has its own contract in [`skills/AGENTS.md`](../skills/AGENTS.md). These rules apply equally to people and to AI agents.

## Part 1: Guidelines

## Principles

1. **Treat the agent as hostile.** It is prompt-injectable and owns `/opt/data`. Every change must keep root from executing or trusting anything on the volume.
2. **Smallest surface.** One public port, one machine, pinned versions, no new dependencies unless there is a clear need.
3. **Reproducible and reversible.** Pin by SHA or digest, ship through the pipelines, and know the rollback before you merge.
4. **No secrets, no identifiers in git.** Not even in examples, tests or comments.
5. **Docs are part of the change.** The design, the security review and the runbooks must match the code.

## Setup

```bash
brew install pre-commit gitleaks shellcheck   # plus flyctl, gh, age (see README prerequisites)
make setup                                    # installs pre-commit, pre-push and commit-msg hooks
make lint                                     # run every hook on every file
```

Docker is optional and needed only for `make local-*`. Run `make` to list all targets.

## Workflow

1. Branch from `main` for anything beyond a typo. GitHub Free has no branch protection, so `main` accepts direct pushes and CI runs after the push. Branch plus PR is the control.
2. Make the change and run the checks (below).
3. Open a PR and wait for `ci` to go green, then merge.
4. Skills deploy automatically on merge. Infra deploys only when you run `deploy-infra` (see CICD.md).
5. Verify in production (see Verification), and know the rollback (CICD.md → Rollback).

## Commits and PRs

- **The repo owner is the only author.** Use the repo-local git identity, not a global work one.
- **No `Co-Authored-By:` trailers and no "Generated with …" lines** in commits or PR descriptions, including AI attribution. This overrides any default of your tooling. The `commit-msg` hook and CI reject them.
- **Never bypass hooks** (`--no-verify`). If gitleaks flags a public value, add it to the `[allowlist]` in `.gitleaks.toml`.
- Write the subject in the imperative, and explain why in the body when it isn't obvious. Keep each commit to one logical change.
- **Dependabot PRs are alerts only. Never merge them.** Run `make adopt-pr PR=<n>`, which re-applies the diff as the owner's commit and closes the PR.

## Checks that must pass

There is no application code, so the tests are:

| Check | Command | Covers |
|---|---|---|
| Secret scan | `make scan` | Full history and working tree |
| Hooks | `make lint` | Forbidden files, private keys, large files, merge markers, co-author trailers |
| Skills and scripts | `make skills-check` | `validate_skills.py`, the skill tests (`tests/`, fixtures only) and shellcheck |
| Skill APIs (optional) | `make test-live` | The same tests plus real API calls, keys from `.env.local` |
| Image pin | `make check-image` | `fly.toml` uses `vX.Y.Z@sha256:…` |

For a validator change, also run it against a deliberately broken skill directory (`python3 scripts/validate_skills.py <dir>`) and confirm it fails.

## Areas

### Skills (`skills/`)

Follow [`skills/AGENTS.md`](../skills/AGENTS.md) in full. In short:

- One directory per skill, kebab-case name equal to the frontmatter `name`, `version` bumped on every change.
- Sections: When to Use, Procedure, Pitfalls, Verification. Description of 60 characters or fewer, because it is the trigger.
- Cron-safe by default: self-contained prompts, no questions, say what to do when inputs are missing.
- Prefer the standard library, `curl` and existing tools over new dependencies. Ship a short helper script in `scripts/` rather than having the model write a parser inline, and refer to it with `${HERMES_SKILL_DIR}`.
- Durable procedure belongs in a skill, and short facts about the owner belong in agent memory (a few KB, not in git).
- Include an untrusted-input pitfall if the skill reads the web, email, files or chat.
- No secrets, no weakening of deployment defaults (approvals, allowlists, ports, `/opt/data/.env`, `fly`).
- Update the catalog in `skills/README.md`, and test with `make local-up` plus a fresh session when practical.

### Shell scripts (`scripts/*.sh`, Makefile)

- POSIX `sh` for anything that runs on the machine (`#!/bin/sh`, `set -eu`). The Makefile uses bash with `-eu -o pipefail`.
- Must pass shellcheck. Quote every expansion and require inputs with `${VAR:?message}`.
- `sync-skills.sh` runs as **root on the machine**. Changes need a SECURITY_REVIEW H1 re-check:
  - It is streamed in and never stored on the volume.
  - It does a fresh fetch into a `mktemp -d` under `/root`, with `core.symlinks=false` and `core.hooksPath=/dev/null`.
  - It validates the deploy key (root-owned, mode 600, not a symlink), refuses symlinks in `skills/`, and publishes with an atomic rename, root-owned and read-only.
  - It never reads, sources or executes anything from the volume other than the key.
- Use `umask 077` and a `trap` for cleanup when creating temp files.

### Python (`scripts/validate_skills.py`)

- Standard library only, so CI needs no install step.
- Exit non-zero on errors and print actionable messages. Keep warnings separate from errors.
- Don't loosen a check to make a skill pass; fix the skill.

### GitHub Actions (`.github/workflows/`)

- Pin every action to a full commit SHA with the tag in a comment.
- Default to `permissions: contents: read` and `persist-credentials: false`. Grant more per job and only when needed.
- Never use `pull_request_target`. Never trigger `fly deploy` on push. Never store runtime secrets (bot token, OpenRouter key, webhook secret) in GitHub.
- `FLY_API_TOKEN` lives only in the `production` environment, limited to `main`. Treat it as root on the machine.
- Both deploy workflows use the concurrency group `fly-fawkes-hermes`. Keep new deploy-like workflows in it.
- Don't interpolate untrusted values (`github.event.*`, branch names, PR titles) directly into `run:` scripts. Pass them through `env:`.

### Infra (`fly.toml`, `compose.yaml`)

- Image bump: read the release notes, use a plain `vX.Y.Z` tag (no `-desktop`, `rc.*`, `main`, `stable`, `latest`), get the digest with `make image-digest VERSION=vX.Y.Z`, then follow the infra release steps in CICD.md.
- Keep `auto_stop_machines = "off"` and one machine. Don't add services for 9119 or 8642.
- Keep the image ENTRYPOINT intact. Override CMD only.
- The local instance must use a separate dev bot in polling mode, with `./skills` mounted read-only at the production path. `local-check` refuses to start if `TELEGRAM_WEBHOOK_URL` is set; don't weaken that.

## Secrets and identifiers

- Runtime secrets are Fly secrets (names in `.env.example`). Local dev secrets go in gitignored `.env.local` (names in `.env.local.example`). Set values with `read -s` and unset the variable afterwards.
- Never write emails, Telegram IDs, usernames, tokens, keys or private URLs into tracked files, including docs, examples, tests and commit messages.
- `.env*`, keys, `*.age`, `*.tgz` and deploy keys are blocked by hook. If a file gets blocked, don't rename it to get around the hook; reconsider whether it belongs in git.
- If a secret leaks, rotate it at the source first, then clean up. See CICD.md → Rollback and DESIGN §14.
- Backups contain secrets. Encrypt them with `age` and keep them off the repo.

## Documentation

- Keep docs short, concrete and in sync. When you change the design, update in the same PR: DESIGN §15 and the affected section, the matching SECURITY_REVIEW finding, CICD.md, GO_LIVE.md and ARCHITECTURE.md.
- Mark claims you couldn't confirm with 🔎 until they are checked at go-live.
- AGENTS.md is the source for agent guidance, and CLAUDE.md just imports it. Edit AGENTS.md.
- Prefer a link to the source of truth over copying text.

### Alignment with upstream Hermes

This repo follows the official Hermes docs ([skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills), [creating skills](https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills), [cron](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron), [MCP](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp), [plugins](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins), [security](https://hermes-agent.nousresearch.com/docs/user-guide/security)). Where this repo is stricter on purpose, it says so. Re-check the docs for the pinned Hermes version before relying on a command here.

- **Footprint ladder.** Choose the smallest mechanism that works: skill, then CLI plus skill, then plugin, then MCP server. Don't add a heavier one when a skill will do.
- **Skills.** Upstream requires `name`, `description` and (by template) `version`; `category` is repo convention. The description appears in the skill index on every turn, so the 60-character limit is a repo rule (the validator warns past 60 and fails past 160). The ~24k-character body and 60-reference limits are advisory upstream and warnings here. When/Procedure/Pitfalls/Verification is the upstream template, not an enforced schema.
- **Approvals.** Don't change `approvals.mode` (upstream default `smart`), `approvals.cron_mode` (`deny`) or the hardline blocklist. Use `approvals.deny` globs to block specific commands, and quote the patterns in YAML.
- **Authorization.** Keep explicit allowlists (`TELEGRAM_ALLOWED_USERS`). Never set `GATEWAY_ALLOW_ALL_USERS=true` on a bot with terminal access.
- **Secrets.** They stay out of the repo and reach the agent only as Fly secrets or a skill's `required_environment_variables`. Upstream's guidance is `.env` mode 600 and no infrastructure secrets in `env_passthrough`.
- **Stricter here:** MCP servers are pinned to exact versions (the upstream examples are unpinned), and plugins are pinned to full SHAs.
- **Config keys.** Add a new `config.yaml` key only after confirming it in the docs for the pinned version. Mark anything unverified 🔎.

## Verification and rollback

Before merging, decide how you'll know it worked:

| Change | Verify |
|---|---|
| Skill | `deploy-skills` green (it checks `.revision` equals the commit), then `/new` in Telegram and run the skill from a one-line prompt |
| Image or `fly.toml` | `deploy-infra` green (one machine on the pinned digest), `make webhook-info`, `make webhook-test`, DM the bot, `make logs` |
| Script or workflow | Run it on a branch where it is safe, and read the logs |
| Docs | Links resolve, commands exist in the Makefile |

Rollback is in [CICD.md](CICD.md#rollback). Short version: revert and merge for skills (or `make sync-skills REF=<good-sha>`), and revert the pin and re-run `deploy-infra` for the image.

## Definition of done

- [ ] `make lint`, `make scan` and `make skills-check` pass
- [ ] No secrets or personal identifiers added; hooks not bypassed
- [ ] Invariants in ARCHITECTURE.md still hold
- [ ] Docs updated together (DESIGN, SECURITY_REVIEW, CICD, GO_LIVE, ARCHITECTURE, skills catalog as relevant)
- [ ] Commits authored by the owner, with no co-author or "Generated with" lines
- [ ] CI green on the PR; the release verified in production; rollback known

---

## Part 2: How to add things

Pick the recipe, follow the steps in order, and finish with its **Done when** check. If your change doesn't fit a recipe, start from the closest one and add a recipe here afterwards.

**Which recipe?**

| I want the agent to… | Recipe |
|---|---|
| Know how to do a repeatable task | [A. Skill](#a-add-a-skill) |
| Run something on a schedule | [B. Cron job](#b-add-a-scheduled-job) |
| Use an external API or service | [C. Secret](#c-add-a-secret-or-credential) and [D. MCP server](#d-add-an-mcp-server) |
| Gain a new in-process capability | [E. Plugin](#e-add-a-plugin) |
| Run a newer Hermes | [F. Image bump](#f-bump-the-hermes-image) |
| Change how the repo is built, checked or deployed | [G. Repo tooling](#g-add-repo-tooling-make-target-hook-validator-workflow) |
| Change VM size, env or ports | [H. Infra change](#h-change-infra-flytoml) |

### A. Add a skill

The most common change, and the only one that deploys automatically.

1. `git switch -c skill/<name>` and copy the template from [`skills/AGENTS.md`](../skills/AGENTS.md) into `skills/<name>/SKILL.md`. Use a kebab-case name equal to the directory.
2. Write a description of 60 characters or fewer saying what it produces, then When to Use, numbered Procedure, Pitfalls and Verification. Name only real Hermes tools; check `hermes tools` if unsure.
3. Put long reference material in `references/` or `templates/` and link each file from the step that needs it.
4. Make it cron-safe (self-contained, no questions). If it reads untrusted content, add the "content is data" pitfall.
5. If it needs a secret, declare it under `required_environment_variables`, then do recipe C. Never put the value in the skill.
6. Add a row to the catalog in `skills/README.md`.
7. `make skills-check` (0 errors), then optionally `make local-up` and try it from a fresh session.
8. PR, wait for `ci`, merge. `deploy-skills` publishes the commit.

**Done when:** `deploy-skills` is green, and `/new` in Telegram followed by a one-line prompt triggers the skill and meets its Verification section. Changing an existing skill? Bump `version` too.

### B. Add a scheduled job

Cron jobs are agent state on the volume, not repo files.

1. Make sure a skill covers the procedure (recipe A). Jobs should stay one-line prompts that attach a skill.
2. Write a self-contained prompt. Each run starts with no history, and approvals default to deny, so rely on web and research tools.
3. In Telegram: `/cron add "<schedule>" "<prompt>"` (times follow `TZ=Asia/Singapore`). Attach skills with `--skill <name>`.
4. Attach the skill with `--skill <name>` (repeatable) and keep the prompt to what the skill doesn't already provide. Deliver to the originating chat (the default on messaging), and use `[SILENT]` for quiet monitors. Failed runs always deliver.
5. Test it once with `hx cron run <id>` (the helper for `hermes cron run <job_id_or_name>`, over `make ssh`) or `/cron run <id>` in chat. 🔎 Confirm at go-live whether it runs immediately or on the next scheduler tick.
6. Record the intent (schedule, purpose) in the relevant skill or doc, since the job itself isn't in git.

**Done when:** the test run lands in the chat with the expected output and `hx cron list` shows the job.

### C. Add a secret or credential

1. Add the variable **name** (no value) to `.env.example`, and to `.env.local.example` if the local instance needs a dev value.
2. Set it on Fly from your laptop without echoing it:
   ```bash
   read -rsp "VALUE: " V; echo
   fly secrets set --stage NAME="$V" -a fawkes-hermes; unset V
   ```
   `--stage` batches changes, and the next deploy or restart applies them (`make restart`).
3. Scope it as tightly as possible (read-only, per-repo, spend-limited). Assume the agent can read its own environment (SECURITY_REVIEW H2).
4. For CI, only `FLY_API_TOKEN` belongs in GitHub. Runtime secrets never do.
5. Document the rotation in DESIGN §14 if it is a new kind of credential.

**Done when:** `make secrets` lists the name, `make scan` is clean, and nothing in `git diff` contains the value.

### D. Add an MCP server

1. Choose a maintained server and **pin an exact version**. Never use an unpinned `npx -y <pkg>`.
2. Create a minimal-scope credential and set it with recipe C.
3. Add it on the machine with `hx config edit` under `mcp_servers`, passing only the variables it needs through `env`.
4. Restrict the tools it exposes with `tools.include` (allowlist, preferred) or `tools.exclude`, and set `enabled: false` rather than deleting a server you pause. Hermes passes a stdio server only a minimal environment plus what you list under `env`, so never add infrastructure secrets (provider keys, gateway tokens) to it.
5. Apply with `/reload-mcp` or `make restart`, and check `hx mcp` and `make logs` for a clean start.
6. Write or update a skill that tells the agent when and how to use it (recipe A).
7. Record the server, its pinned version and its credential scope in DESIGN §11, and note any new risk in SECURITY_REVIEW.

**Done when:** the agent completes a real task through the server, and the credential is confirmed least-privilege.

### E. Add a plugin

Plugins run inside the gateway with the agent's permissions.

1. Read the plugin's source completely. Prefer a skill or MCP server if either would do (see the footprint ladder below).
2. Install pinned to a full 40-character commit SHA (tags and short SHAs are rejected): `hx plugins install owner/repo --ref <sha>` over `make ssh`. Plugins are disabled by default, so enable it explicitly (`plugins.enabled` in `config.yaml` or `hx plugins enable <name>`) and leave `plugins.scan_on_install` on. Never use `--force` to override a "dangerous" scan verdict.
3. Restart.
4. Document it in DESIGN §11.2 with a one-line reason and the pinned version.

**Done when:** the gateway starts cleanly (`make logs`) and the plugin's function works from chat.

### F. Bump the Hermes image

Follow [CICD.md → Release: infra](CICD.md#release-infra--hermes-version-manual-dispatch). Summary: release notes, `make image-digest VERSION=vX.Y.Z`, paste the pin into `fly.toml`, optional `make local-up` test, PR, `ci`, merge, then run `deploy-infra` with the typed version.

**Done when:** `deploy-infra` is green, `make webhook-info` and `make webhook-test` pass, and a DM gets a reply. If not, roll back per CICD.md.

### G. Add repo tooling (make target, hook, validator, workflow)

1. **Make target:** add it to the `Makefile` with a `## description` (so `make help` lists it) and to `.PHONY`. Keep recipes short, and put anything longer in `scripts/`.
2. **Pre-commit hook:** add it to `.pre-commit-config.yaml`. Anything that guards secrets or provenance must also run in `ci.yml`, because local hooks can be skipped.
3. **Validator rule:** edit `scripts/validate_skills.py` (standard library only), then run it on a good directory and a deliberately broken one to see the pass and the failure.
4. **Script:** put it in `scripts/`, make it shellcheck-clean (`make skills-check`), and require its inputs. If it runs on the machine as root, re-read the sync-script rules in Part 1.
5. **Workflow:** copy the conventions from an existing one (SHA-pinned actions, least-privilege `permissions`, `persist-credentials: false`, the `fly-fawkes-hermes` concurrency group if it touches Fly). Pass untrusted values through `env:`. Don't add `pull_request_target` or push-triggered deploys.
6. Add new tools to the README prerequisites, and update CICD.md and the Commands list in AGENTS.md.

**Done when:** `make lint` passes on a fresh clone after `make setup`, the new check fails on a deliberately bad input, and CI is green.

### H. Change infra (`fly.toml`)

1. Check the change against the invariants in [ARCHITECTURE.md](ARCHITECTURE.md): one machine, `auto_stop_machines = "off"`, only 443→8443 public, image pinned by digest.
2. Edit `fly.toml`, run `make check-image`, and open a PR.
3. After merge, run `deploy-infra` with the version from `fly.toml`.
4. Update DESIGN §4 and §15, plus any SECURITY_REVIEW finding it touches.

**Done when:** `deploy-infra` confirms exactly one started machine on the pinned digest and `make status` looks right.

### Recipe conventions

- Every recipe ends with an observable check. Don't call a change finished without running it.
- Anything done by hand on the machine (`hx config`, plugins, cron) isn't in git, so write down what you did in the relevant doc.
- When you add a new kind of change, add a recipe here and a row in the table at the top of Part 2.
