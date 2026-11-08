# Security review: Hermes on Fly.io (pre-implementation)

- **Scope:** `docs/DESIGN.md` (v4) and repository secret handling
- **Date:** 2026-11-08
- **Status:** design fixes applied to DESIGN.md where marked ✅. Items marked 🔎 must be verified on first deploy.

## Threat model (short)

| Actor | Can reach | Goal |
|---|---|---|
| Internet | `https://hermes-me.fly.dev:443` (webhook path only) | Inject updates, run up cost |
| Content the agent reads (web pages, docs, group chat) | The model's context, through **prompt injection** | Get the agent to run commands, read secrets, escalate to root |
| The agent process (UID 10000) | Everything under `/opt/data`, its own env, outbound network | Same as above, once injected |
| Anyone who can push to `hermes-skills` / GitHub Actions | `FLY_API_TOKEN` → root SSH | Full machine takeover |
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
- The script lives in the `hermes-skills` repo and is streamed in by base64 over `fly ssh console`. It is never stored on the volume.
- Every sync does a fresh shallow clone into `/root/` temp space, with hooks and symlinks disabled.
- It publishes a **root-owned, read-only** copy without `.git/`, via staging and an atomic `mv -T`.
- Before using the key, it checks that the key is a root-owned regular file with mode 600 and not a symlink.
- The known_hosts line is embedded in the script instead of being read from the volume.

### H2. The agent can probably read its own runtime secrets 🔎 verify
**Where:** DESIGN §5, §11.1.
**Issue:** Fly secrets are injected as environment variables into the gateway process. `/opt/data/.env` and `config.yaml` are owned by UID 10000. If the terminal or code-execution tool inherits the environment, or can `cat /proc/<gateway-pid>/environ` (same UID, so it can), a prompt injection can exfiltrate `TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`, `GH_PAT` and the webhook secret.
**Mitigations:**
- 🔎 On first deploy, ask the agent to run `env | cut -d= -f1` and `cat /proc/1/environ | tr '\0' '\n' | cut -d= -f1`, then confirm which secrets it can see. If they're visible and you don't need the terminal day to day, **disable the terminal and code-execution toolsets** on `hermes-me` as well, or move them to the Modal backend (§12).
- The limits on damage already in the design: an OpenRouter credit limit, a Telegram allowlist (a leaked bot token lets someone impersonate the bot but not command the agent), and a read-only, fine-grained `GH_PAT` ✅ (added to §11.1).
- Keep `approvals.mode: smart` and the cron `deny` default (already in §7.5).
- Rotate any secret you suspect has leaked using §14.

### M1. CI token grants root, and the workflow used `@master` ✅ fixed in design
**Where:** DESIGN §9.4.
**Issue:** `fly tokens create deploy` lets the holder `fly ssh console` as root. It was valid for one year, held as a plain repo secret, and passed to `superfly/flyctl-actions/setup-flyctl@master`, a mutable ref.
**Fix applied:** 90-day expiry, a GitHub `production` environment limited to `main`, branch protection, `permissions: contents: read`, actions pinned by full SHA, and `persist-credentials: false`.
🔎 Check whether your flyctl version supports a narrower token than `deploy` (for example a machine-exec-scoped token). If it does, use it.

### M2. Unpinned `npx -y` MCP server runs with a PAT in its env ✅ fixed in design
**Where:** DESIGN §11.1. **Fix applied:** pin an exact version, use a read-only fine-grained PAT, and check the package is still maintained.

### M3. Backups contain secrets and were handled in plaintext ✅ fixed in design
**Where:** DESIGN §14.
**Issue:** The tarball includes `/opt/data/.env` and config. It was written with a world-readable umask to `/tmp`, downloaded into the current directory (possibly this repo), and the guide said "store encrypted" without saying how.
**Fix applied:** `umask 077`, written under `/root`, downloaded into `~/hermes-backups` (0700, outside the repo), encrypted with `age`, and the plaintext deleted. `.gitignore` also blocks `*.tgz` and `*.age`.

### M4. Image pinned by tag only ✅ fixed in design
Tags can be moved after you pin them. §1.4 now requires `:<VERSION>@sha256:<DIGEST>`.

### L1. Deploy private key left on the laptop without a passphrase ✅ fixed in design
§9.3 now deletes the local copy once it's uploaded. The key is only needed on the server; regenerate it if you ever need a new one.

### L2. The dashboard on 6PN is reachable from other apps in the same Fly org
Basic auth is the only control between the dashboard and other apps on the private network. Keep the org limited to your own apps. If you add `hermes-friends` to the same org, it can reach `hermes-me.internal:9119`, so consider a **separate Fly org** for the friends app.

### L3. Compromised v1 bot token 🔎 verify
Confirm it was revoked in BotFather, and purge any copies: old notes, chat logs, shell history (`history | grep -E '[0-9]{8,10}:'`).

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
| Pre-commit secret scanning (gitleaks with Telegram, OpenRouter and Fly token rules, plus `detect-private-key`) | `.pre-commit-config.yaml`, `.gitleaks.toml` |
| A dedicated personal commit identity | repo-local `git config user.email` |

**One-time setup per clone:** `pre-commit install && pre-commit run --all-files`.
When the repo goes to GitHub, keep it **private** and turn on *Secret scanning* and *Push protection* (Settings → Code security).

## Implementation gate

Don't deploy until the following are done:
- [ ] H2 verification plan is ready (know which toolsets you'll disable if secrets are visible)
- [ ] `hermes-skills` repo has `main` protection and the `production` environment before `FLY_API_TOKEN` is added
- [ ] Action SHAs and the image digest have been looked up and filled in
- [ ] L3 confirmed
