# Security review: Hermes on Fly.io (pre-implementation)

- **Scope:** `docs/DESIGN.md` (v4), monorepo CI/CD (`.github/workflows/`, `scripts/`) and repository secret handling
- **Date:** 2026-11-08
- **Status:** design fixes applied to DESIGN.md where marked ✅. Items marked 🔎 must be verified on first deploy.

## Threat model (short)

| Actor | Can reach | Goal |
|---|---|---|
| Internet | `https://fawkes-hermes.fly.dev:443` (webhook path only) | Inject updates, run up cost |
| Content the agent reads (web pages, docs, group chat) | The model's context, through **prompt injection** | Get the agent to run commands, read secrets, escalate to root |
| The agent process (UID 10000) | Everything under `/opt/data`, its own env, outbound network | Same as above, once injected |
| Anyone who can merge to `main` of this repo / run the `production` environment | `FLY_API_TOKEN` → root SSH; `skills/` → agent instructions | Full machine takeover; steer the agent |
| A compromised laptop or repo | Local keys, git history | Credential theft |

The main assumption in this review: **treat the agent as potentially hostile.** Every boundary between the agent (UID 10000) and root has to hold even if the agent is fully prompt-injected.

---

## Findings

### H1. Root executes files the agent controls → privilege escalation ✅ fixed in design
**Where:** DESIGN §9.3 (old version), §16 `chown` fix.
**Issue:** `/opt/data` is owned by UID 10000. Owning the parent directory lets the agent **rename or replace any entry under it**, including root-owned `bin/` and `.ssh/`. The old design had root:
1. execute `/opt/data/bin/sync-skills.sh`, which the agent could swap for its own script, and
2. run `git fetch` / `reset` inside `/opt/data/skills-repo`. That directory was `chown -R 10000`, so the agent could edit `.git/config` (`core.fsmonitor`, etc.), and `safe.directory` explicitly told git to trust it.

Either path gives root on the next sync, which means the deploy key, every secret, and the whole volume.
**Fix applied:**
- The script lives in this repo (`scripts/sync-skills.sh`) and is streamed in by base64 over `fly ssh console`. It is never stored on the volume.
- Every sync fetches the exact `REF` (a CI commit SHA) at depth 1 into `/root/` temp space, with hooks and symlinks disabled. It refuses symlinks in `skills/` and publishes only `skills/`.
- It publishes a **root-owned, read-only** copy without `.git/`, via staging and an atomic `mv -T`.
- Before using the key, it checks that the key is a root-owned regular file with mode 600 and not a symlink.
- The known_hosts line is embedded in the script instead of being read from the volume.
- **PATH (found at first sync, fixed):** the image's PATH puts `/opt/data/.local/bin` (agent-owned, where pip entry points go) ahead of `/usr/bin`. That applies to root's `fly ssh` sessions too, so a planted `git`, `sh` or `base64` there would run as root. The script now pins `PATH=/usr/sbin:/usr/bin:/sbin:/bin` and uses `/usr/bin/ssh`. Every command root runs over `fly ssh` (CI and Makefile) uses absolute paths (`/bin/sh`, `/usr/bin/base64`, `/bin/cat`, `/bin/tar`, `/bin/rm`). At the time of the fix, the directory held only pip entry points, none shadowing a system binary. **Rule:** any root command on the machine uses absolute paths, including in `make ssh` sessions.

### H2. The agent can probably read its own runtime secrets 🔎 verify
**Where:** DESIGN §5, §11.1.
**Issue:** Fly secrets are injected as environment variables into the gateway process. `/opt/data/.env` and `config.yaml` are owned by UID 10000. If the terminal or code-execution tool inherits the environment, or can `cat /proc/<gateway-pid>/environ` (same UID, so it can), a prompt injection can exfiltrate `TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`, `GH_PAT` and the webhook secret.
**Mitigations:**
- 🔎 On first deploy, ask the agent to run `env | cut -d= -f1` and `cat /proc/1/environ | tr '\0' '\n' | cut -d= -f1`, then confirm which secrets it can see. If they're visible and you don't need the terminal day to day, **disable the terminal and code-execution toolsets** on `fawkes-hermes` as well, or move them to the Modal backend (§12).
- The limits on damage already in the design: an OpenRouter credit limit, a Telegram allowlist (a leaked bot token lets someone impersonate the bot but not command the agent), and a read-only, fine-grained `GH_PAT` ✅ (added to §11.1).
- Keep `approvals.mode: smart` and the cron `deny` default (already in §7.5).
- Rotate any secret you suspect has leaked using §14.

### M1. CI token grants root, and the workflow used `@master` ✅ fixed in design
**Where:** DESIGN §9.4.
**Issue:** `fly tokens create deploy` lets the holder `fly ssh console` as root. It was valid for one year, held as a plain repo secret, and passed to `superfly/flyctl-actions/setup-flyctl@master`, a mutable ref.
**Fix applied (`.github/workflows/deploy-skills.yml`, `deploy-infra.yml`):** 90-day expiry, a GitHub `production` environment limited to `main` (applied), `permissions: contents: read`, actions pinned by full SHA (with Dependabot updates), `persist-credentials: false`, and a `validate` job gating `deploy`.
**Monorepo note:** the token now sits in the same repo as infra. That's acceptable because PR-triggered workflows (`ci.yml`) never get the `production` environment, so a malicious PR can't read the token. Never add `pull_request_target` workflows to this repo.
**GitHub Free limits (confirmed 2026-11-08):** branch protection and environment required reviewers aren't available for this private repo. Accepted risk, because only the owner has push access. Compensating controls:
- The environment branch policy keeps the token on `main` only.
- `deploy-infra` is `workflow_dispatch` only, with a typed version that must match `fly.toml`.
- Both deploy workflows re-validate before acting and share one concurrency group.
- Local pre-push gitleaks blocks a leaked secret before it reaches `main`.

Revisit if you upgrade to Pro, or before adding any collaborator.
🔎 Check whether your flyctl version supports a narrower token than `deploy` (for example a machine-exec-scoped token). If it does, use it.

### M2. Unpinned `npx -y` MCP server runs with a PAT in its env ✅ fixed in design
**Where:** DESIGN §11.1. **Fix applied:** pin an exact version, use a read-only fine-grained PAT, and check the package is still maintained.

### M5. Travel skills: third-party data and API keys in the agent's reach ✅ accepted, mitigated
**Where:** [TRAVEL_SKILLS.md](TRAVEL_SKILLS.md), DESIGN §11.2.
**Risk:**
- The Kiwi.com MCP server, LTA, NEA and Open-Meteo responses enter the model's context. Kiwi's own tool description already tries to steer the output format.
- `LTA_DATAMALL_KEY` and `DATA_GOV_SG_API_KEY` are readable by the agent (H2), and so could be exfiltrated if it's injected.

**Mitigation:**
- Every skill treats tool and web output as data, and `flights` explicitly ignores the tool's formatting instructions.
- Kiwi is filtered to `search-flight` only, and the skills never book, sign in or enter details.
- Both keys are free, read-only and rate-limited, and rotate in minutes with `make skill-secrets`.
- Scripts are stdlib-only, read-only on the machine, send keys only as headers (never in URLs or errors), and write only to the per-user cache dir. Tests enforce this.

### M3. Backups contain secrets and were handled in plaintext ✅ fixed in design
**Where:** DESIGN §14.
**Issue:** The tarball includes `/opt/data/.env` and config. It was written with a world-readable umask to `/tmp`, downloaded into the current directory (possibly this repo), and the guide said "store encrypted" without saying how.
**Fix applied:** `umask 077`, written under `/root`, downloaded into `~/hermes-backups` (0700, outside the repo), encrypted with `age`, and the plaintext deleted. `.gitignore` also blocks `*.tgz` and `*.age`.

### M4. Image pinned by tag only ✅ fixed in design
Tags can be moved after you pin them. §1.4 now requires `:<VERSION>@sha256:<DIGEST>`.

### L1. Deploy private key left on the laptop without a passphrase ✅ fixed in design
§9.3 now deletes the local copy once it's uploaded. The key is only needed on the server; regenerate it if you ever need a new one.

### L2. The dashboard on 6PN is reachable from other apps in the same Fly org
Basic auth is the only control between the dashboard and other apps on the private network. Keep the org limited to your own apps. If you add `hermes-friends` to the same org, it can reach `fawkes-hermes.internal:9119`, so consider a **separate Fly org** for the friends app.

### L3. Compromised v1 bot token 🔎 verify
Confirm it was revoked in BotFather, and purge any copies: old notes, chat logs, shell history (`history | grep -E '[0-9]{8,10}:'`).

### M6. Group members can command the agent, and the agent can edit its own gateway config ✅ accepted (owner decision)
- **What changed:** `platforms.telegram.allow_from` was removed at the owner's request. In the whitelisted groups (`allowed_chats`), **any member** can command the agent by @mentioning it (`require_mention: true`). DMs should still be limited by `TELEGRAM_ALLOWED_USERS` 🔎 verify (DM the bot from a non-allowlisted account). Every member of those groups is now a prompt-injection and spend source: anything they ask runs with the agent's tools and OpenRouter credit.
- **How it changed:** the agent's `patch` tool refuses to write `config.yaml`, but the agent made the change through its terminal with `hermes config unset`. Treat that guard as advisory: the agent (UID 10000) owns `/opt/data` and can change any gateway setting, including the Telegram allowlists, approvals and model routing.
- **Mitigations:** keep `allowed_chats` to groups whose members you trust, keep `require_mention: true`, keep the OpenRouter credit limit, and review `hx config get platforms.telegram` after any chat that touches config. A gateway restart now restarts the machine (`[[restart]] policy = "always"`), so a config change can no longer take the bot offline.

### Info: first-deploy observations (2026-11-08)
- No s6 on Fly (PID 1 is `/fly/init`), so there's no supervision tree. The non-root boundary still holds: the gateway and dashboard both run as UID 10000.
- Hermes starts a loopback-only API server on `127.0.0.1:8642` with an auto-generated key. It isn't in `[[services]]` and isn't reachable off-machine. Keep it that way.
- Hermes logs that it ingested `OPENROUTER_API_KEY` into its credential pool, which enables spend. The key's credit limit is the cap.

### Info: things that are already right
- Webhook protected by a secret header, a random path and a user allowlist; the §6.3 negative test is built in.
- Only 443→8443 is public. The dashboard and API server go through the proxy only.
- `read -s` keeps secrets out of shell history.
- GitHub's ed25519 host key in §9.3 matches the published fingerprint.
- `approvals: smart`, cron `deny`, `allow_private_urls: false`.

---

## Repository secret handling (implemented)

| Control | File |
|---|---|
| Ignore secrets, keys and backups | `.gitignore` |
| A list of secret **names** only, never values | `.env.example` |
| **Commit hook:** gitleaks on staged changes (custom Telegram, OpenRouter and Fly rules, all verified against fake tokens), forbidden filenames (`.env*`, keys, `*_deploy`, backups), `detect-private-key`, skills validator | `.pre-commit-config.yaml`, `.gitleaks.toml` |
| **Push hook:** gitleaks over the full history, so nothing leaves the laptop unscanned | `.pre-commit-config.yaml` (`pre-push`) |
| **CI:** checksum-pinned gitleaks 8.30.1, all hooks plus a full-history scan on every PR | `.github/workflows/ci.yml` |
| **GitHub:** Secret scanning + Push protection (server-side backstop) | repo settings (GO_LIVE step 1) |
| Manual audit: `make scan` (history plus working tree, including ignored files) | `Makefile` |
| No personal identifiers in tracked files: dashboard username and Telegram IDs are prompted at setup | DESIGN §5, `.env*.example` |
| A dedicated personal commit identity | repo-local `git config user.email` |

**One-time setup per clone:** `pre-commit install && pre-commit run --all-files`.
When the repo goes to GitHub, keep it **private** and turn on *Secret scanning* and *Push protection* (Settings → Code security).

## Implementation gate

Don't deploy until the following are done:
- [ ] H2 verification plan is ready (know which toolsets you'll disable if secrets are visible)
- [ ] This repo has `main` protection (required `ci` checks) and the `production` environment before `FLY_API_TOKEN` is added
- [ ] Image digest filled in `fly.toml` (`make image-digest`); action SHAs are already pinned
- [ ] L3 confirmed
