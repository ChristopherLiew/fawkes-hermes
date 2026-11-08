# Hermes Agent on Fly.io: Personal Cloud Guide (v4, Telegram webhook)

Telegram (webhook mode) + private dashboard · always on · Singapore (`sin`)

---

## 0. What you're building

```
   You (Telegram, any device)                 You (laptop browser)
            │                                          │
            ▼                                          ▼
   Telegram Bot API ── HTTPS POST ──┐            fly proxy (WireGuard)
   (X-Telegram-Bot-Api-Secret-Token)│                  │
                                    ▼                  │
┌──────────────────────── Fly edge :443 (TLS) ─────────┼───────┐
│ Fly app: fawkes-hermes (sin)                         │       │
│   only public route: 443 → 8443  /tg-<random>        │       │
│                                                      ▼       │
│  nousresearch/hermes-agent:<PINNED>  (s6 supervises both)    │
│   ├─ gateway run     → Telegram webhook :8443, cron ticker   │
│   └─ dashboard :9119 → private network only + basic auth     │
│                                                              │
│  Volume hermes_data → /opt/data                              │
│   ├─ config.yaml, .env, SOUL.md, memories/, sessions/        │
│   ├─ skills/          (bundled + agent-created)              │
│   ├─ skills-repo/     (repo skills/, root-owned read-only)   │
│   └─ .ssh/            (deploy key, root-only)                │
└──────────────────────────────────────────────────────────────┘
```

**Why it's built this way**

| Decision | Reason |
|---|---|
| Telegram **webhook** mode | Your choice. It needs a public HTTPS endpoint, so it's hardened with a secret header, a random path, and a user allowlist. |
| Always on, not scale-to-zero | Cron jobs only run while the gateway is up. A webhook can wake a stopped machine; a scheduled job can't. |
| Only 443→8443 is public | Fly only routes ports listed under `[[services]]`. The dashboard (9119) stays on the private network. |
| Official image, untouched entrypoint | Keeps s6 supervision, the zombie reaper, and the non-root `hermes` user (UID 10000). |
| Volume at `/opt/data` | That's where the image keeps all state. Anything written elsewhere is lost on redeploy. |
| Skills via `skills.external_dirs` | Avoids clashing with the bundled and agent-created skills in `skills/`. |
| Separate app for friends | A single gateway shares memory, skills, the terminal and the filesystem across every user. |

---

## 1. Before you start

### 1.1 Rotate the leaked bot token (do this first)
The v1 guide contained a live token, so treat it as compromised.
1. In @BotFather: `/mybots` → your bot → **API Token** → **Revoke current token**.
2. Keep the new token only in your password manager. Never put it in a doc, script or shell history.

### 1.2 Tools
```bash
brew install flyctl
fly auth login
```

### 1.3 Values to collect (store them in your password manager)
| Value | Where |
|---|---|
| `BOT_TOKEN` | @BotFather (the new token) |
| `MY_TG_ID` | DM @userinfobot. It's a number, not your username. |
| `GROUP_ID` (optional) | Add @userinfobot to the group, or read it from logs later. It starts with `-`. |
| `OPENROUTER_KEY` | openrouter.ai → Keys. **Create a dedicated key with a credit limit.** |
| `DASH_USER` / `DASH_PASS` | Pick a non-obvious username; password from `openssl rand -base64 24` |
| Webhook path and secret | Generated in §5 |

### 1.4 Pin a Hermes version
Pick the newest plain release tag at hub.docker.com/r/nousresearch/hermes-agent/tags. These look like `v0.23.0`; skip `-desktop`, `rc.*`, `main`, `stable` and `latest`. This guide calls it `<VERSION>`. **Never deploy `latest`.** Tags can be moved, so pin the digest as well: `image = "nousresearch/hermes-agent:<VERSION>@sha256:<DIGEST>"`. Get the full line with `make image-digest VERSION=<VERSION>`; it doesn't need Docker.

---

## 2. Telegram bot settings

1. @BotFather → `/mybots` → bot → **Bot Settings → Group Privacy → Turn off**. Only needed if you use the bot in groups.
2. If the bot is already in a group, **remove it and add it back**. Telegram caches the privacy setting when the bot joins. Making the bot a group admin also works.
3. **Never run Hermes elsewhere with this token.** While a webhook is set, any other process polling with the same token gets `409 Conflict`. Starting a second gateway that registers its own webhook would steal the bot.

---

## 3. Create the Fly app and volume

```bash
mkdir -p ~/hermes-cloud/fawkes-hermes && cd ~/hermes-cloud/fawkes-hermes

fly apps create fawkes-hermes
fly volumes create hermes_data --app fawkes-hermes --region sin --size 3 --yes
```

---

## 4. `fly.toml`

> **Source of truth: the repo's [`fly.toml`](../fly.toml).** The block below is the original sketch. The live file differs: it sets `processes = ["app"]` on the service and VM, and its CMD starts the dashboard alongside the gateway, because s6 doesn't run on Fly (Appendix item 1).

```toml
app = "fawkes-hermes"
primary_region = "sin"

[build]
  image = "nousresearch/hermes-agent:<VERSION>"   # pinned, never "latest"

# Overrides CMD only. The image ENTRYPOINT (s6 supervisor) stays intact.
[processes]
  app = "gateway run"

[env]
  TZ = "Asia/Singapore"            # cron fires on the machine clock
  TELEGRAM_WEBHOOK_PORT = "8443"   # default; matches internal_port below
  # Dashboard: private network only (nothing routes 9119 publicly)
  HERMES_DASHBOARD = "1"
  HERMES_DASHBOARD_PORT = "9119"
  HERMES_DASHBOARD_HOST = "::"     # Fly's private IPv6 network (see §8)

[mounts]
  source = "hermes_data"
  destination = "/opt/data"

# The ONLY public route: Telegram → 443 → 8443
[[services]]
  internal_port = 8443
  protocol = "tcp"
  auto_stop_machines = "off"       # must stay up for cron
  auto_start_machines = true
  min_machines_running = 1

  [services.concurrency]
    type = "requests"
    soft_limit = 20
    hard_limit = 50

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [[services.tcp_checks]]
    interval = "30s"
    timeout = "5s"
    grace_period = "30s"

[[vm]]
  size = "shared-cpu-1x"
  memory = "2gb"
```

The webhook URL, and the random path in it, is set as a secret in §5. Hermes reads the path from the URL.

---

## 5. Secrets

`read -s` keeps the values out of your shell history.

```bash
cd ~/hermes-cloud/fawkes-hermes

read -rsp "Bot token: " BOT_TOKEN; echo
read -rsp "OpenRouter key: " OPENROUTER_KEY; echo
read -rp  "Dashboard username: " DASH_USER
read -rsp "Dashboard password: " DASH_PASS; echo
read -rp  "Your Telegram user ID: " MY_TG_ID

WEBHOOK_PATH="/tg-$(openssl rand -hex 12)"
WEBHOOK_SECRET="$(openssl rand -hex 32)"
echo "Webhook path: $WEBHOOK_PATH   (save it in your password manager)"

fly secrets set --stage \
  TELEGRAM_BOT_TOKEN="$BOT_TOKEN" \
  TELEGRAM_ALLOWED_USERS="$MY_TG_ID" \
  TELEGRAM_WEBHOOK_URL="https://fawkes-hermes.fly.dev$WEBHOOK_PATH" \
  TELEGRAM_WEBHOOK_SECRET="$WEBHOOK_SECRET" \
  OPENROUTER_API_KEY="$OPENROUTER_KEY" \
  HERMES_DASHBOARD_BASIC_AUTH_USERNAME="$DASH_USER" \
  HERMES_DASHBOARD_BASIC_AUTH_PASSWORD="$DASH_PASS" \
  HERMES_DASHBOARD_BASIC_AUTH_SECRET="$(openssl rand -hex 32)"

unset OPENROUTER_KEY DASH_USER DASH_PASS WEBHOOK_SECRET   # keep BOT_TOKEN for §6.2, then unset it
```

Notes:
- `TELEGRAM_WEBHOOK_SECRET` is **required** in webhook mode; the gateway won't start without it. Telegram sends it in the `X-Telegram-Bot-Api-Secret-Token` header on every update, and Hermes rejects requests where it doesn't match.
- `TELEGRAM_ALLOWED_USERS` is required too. Without it, Hermes denies everyone.
- Groups (optional): `fly secrets set --stage TELEGRAM_GROUP_ALLOWED_CHATS="<GROUP_ID>"`. **Every member** of an allowed group can then use the bot.
- Leave `API_SERVER_ENABLED` unset.

---

## 6. Deploy and verify

### 6.1 Deploy
```bash
fly deploy --ha=false
fly scale count 1 --yes
fly ips list            # expect a shared IPv4 and an IPv6 (both free)
fly logs
```
In the logs, look for: `[telegram] Connected to Telegram (webhook mode)`.

### 6.2 Check that Telegram sees the webhook
```bash
curl -s "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo" | python3 -m json.tool
unset BOT_TOKEN
```
You want:
- `url` = `https://fawkes-hermes.fly.dev/tg-…`
- `pending_update_count` at or near 0
- no `last_error_message`. If there is one, it tells you what Telegram saw, such as a 404 or a TLS error.

### 6.3 Check that unauthenticated requests are rejected
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -H 'Content-Type: application/json' -d '{"update_id":1}' \
  "https://fawkes-hermes.fly.dev$WEBHOOK_PATH"
```
A 4xx (401 or 403) means the secret header check works ✅. A 200 means the check isn't being enforced, so stop and investigate. A 502 or 503 means nothing is listening on 8443; check `fly logs`.

### 6.4 Say hi
DM the bot. It should reply. If no model is configured yet, the reply may be an error asking you to set one up.

---

## 7. First-run configuration (inside the machine)

### 7.1 Shell and helper
`fly ssh console` logs you in as **root**. Run `hermes` as the `hermes` user, or it will create root-owned files the gateway can't read.
```bash
fly ssh console -a fawkes-hermes

# --- inside ---
HB=$(command -v hermes || echo /opt/hermes/.venv/bin/hermes)
hx() { runuser -u hermes -- env HERMES_HOME=/opt/data "$HB" "$@"; }

hx --version
hx doctor          # fix anything it flags
```

### 7.2 Model
```bash
hx model     # OpenRouter → deepseek/deepseek-v4-pro (check the current price on its OpenRouter page)
```

### 7.3 Web search and tools
```bash
hx tools     # make sure web search, browser, etc. are enabled and have a backend
```
Daily research needs a working web-search backend. `hermes setup --portal` (Nous Portal) is one documented way to get one.

### 7.4 Telegram settings
```bash
hx config set telegram.require_mention true
hx config set telegram.observe_unmentioned_group_messages true   # only if you use groups
hx config set platforms.telegram.extra.status_indicator true
hx config set platforms.telegram.extra.status_online "✨ Online"
hx config set platforms.telegram.extra.status_offline "💤 Offline"
```
- Leave `max_concurrent_updates` at its default of 32.
- Groups: in `hx config edit`, give `allowed_chats` and `group_allowed_chats` the **same** IDs:
  ```yaml
  telegram:
    allowed_chats: ["<GROUP_ID>"]
    group_allowed_chats: ["<GROUP_ID>"]
    require_mention: true
    observe_unmentioned_group_messages: true
  ```
  With observe mode on, everything said in the group is stored as context. Tell the group.

### 7.5 Safety defaults: keep them
In `hx config edit`, confirm:
- `approvals.mode: smart`. Never `off`, never YOLO.
- Cron, single-query and unattended approvals stay at the default `deny`.
- `security.allow_private_urls: false`
- `group_sessions_per_user: true`
- Optional: `security.allow_lazy_installs: false`, once everything you need is installed.

### 7.6 Persona (optional)
Write `/opt/data/SOUL.md`, then run `chown 10000:10000 /opt/data/SOUL.md`.

### 7.7 Apply
```bash
exit
fly apps restart fawkes-hermes
```

---

## 8. Dashboard access (private network only)

The dashboard is never exposed on the internet. You reach it through an encrypted WireGuard tunnel that `flyctl` opens from your laptop, and basic auth is the second layer.

### 8.1 How it's protected

| Layer | Control |
|---|---|
| Network | Port 9119 isn't under `[[services]]`, so Fly's edge doesn't route it. `fawkes-hermes.fly.dev:9119` doesn't answer. |
| Transport | `fly proxy` tunnels over WireGuard to the app's private (6PN) address. Nothing crosses the public internet unencrypted, and the local end listens on `localhost` only. |
| Identity | You must be authenticated to the Fly org (`fly auth login`) to open the tunnel. |
| Application | Dashboard basic auth: `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` / `_PASSWORD` / `_SECRET` (Fly secrets, set in §5). |

Residual risk: other apps in the same Fly org can reach `fawkes-hermes.internal:9119` on 6PN, and basic auth is the only control against them (SECURITY_REVIEW L2). Keep the org to your own apps.

### 8.2 Open it

```bash
make dashboard                         # = fly proxy 9119:9119 -a fawkes-hermes
# in a browser on the same machine: http://localhost:9119
# log in with the dashboard username and password from your password manager
```
- Leave the terminal running while you use it, and press Ctrl-C to close the tunnel.
- If local port 9119 is busy (for example `make local-up` is running), pick another: `fly proxy 9120:9119 -a fawkes-hermes`, then open `http://localhost:9120`.
- The `http://` is expected. The tunnel is already encrypted end to end, and the local end is only reachable from your own machine.
- Don't forward it to other interfaces (`fly proxy 0.0.0.0:9119:9119`) or put it behind a tunnel you don't control.

### 8.3 Verify it's private

```bash
curl -m 5 https://fawkes-hermes.fly.dev:9119 || echo "not public ✅"   # must fail or time out
fly ips list -a fawkes-hermes                                          # no port-9119 service anywhere
grep -n 9119 fly.toml                                                  # only in [env], never in [[services]]
```
Run these after every `fly.toml` change.

### 8.4 Credentials

- Store the username and password in your password manager. Never put them in git, chat or `.env.local` (that file is for the dev instance's separate credentials).
- Rotate: `read -rsp "New dashboard password: " P; echo; fly secrets set HERMES_DASHBOARD_BASIC_AUTH_PASSWORD="$P" HERMES_DASHBOARD_BASIC_AUTH_SECRET="$(openssl rand -hex 32)" -a fawkes-hermes; unset P`. The restart that follows invalidates existing sessions.
- Rotate right away if the password was shown in a terminal that's logged or shared.

### 8.5 Troubleshooting

| Symptom | Fix |
|---|---|
| `fly proxy` connects but the page hangs | Run `ss -ltnp \| grep 9119` in `make ssh`. If it shows only `0.0.0.0`, set `HERMES_DASHBOARD_HOST = "fly-local-6pn"` in `fly.toml` and redeploy. |
| `bind: address already in use` | Another process holds 9119. Use a different local port (8.2). |
| Login fails or the dashboard won't start | Check the `HERMES_DASHBOARD_BASIC_AUTH_*` secret names with `make secrets`. |
| Proxy errors or timeouts | Check `make status` (machine started) and `fly auth whoami`. |

### 8.6 Phone or shared access

Use Telegram from a phone. If you later need the dashboard on a phone, use a private overlay such as Tailscale, or Cloudflare Tunnel with Access, which needs a custom image or sidecar and is a new design item (add it to §15 and SECURITY_REVIEW first). **Never** add 9119 to `[[services]]`, and never use `fly proxy` bound to a public interface.

---

## 9. Skills (monorepo `skills/`, read-only on the machine, synced on merge)

Skills live in **this repo** under `skills/`. Only that directory reaches the agent, as a root-owned, read-only `/opt/data/skills-repo`. The CI/CD flow is in [CICD.md](CICD.md); the first-time setup steps are in [GO_LIVE.md](GO_LIVE.md).

### 9.1 Layout
```
skills/<name>/SKILL.md          # frontmatter: name (= dir), description, version (semver)
scripts/validate_skills.py      # pre-commit hook + CI gate
scripts/sync-skills.sh          # runs as root on the machine, streamed in, never stored there
.github/workflows/deploy-skills.yml
```

### 9.2 Deploy key (read-only, this repo only)
```bash
ssh-keygen -t ed25519 -C "hermes-skills-deploy" -f ~/.ssh/hermes_skills_deploy -N ""
cat ~/.ssh/hermes_skills_deploy.pub    # GitHub → this repo → Settings → Deploy keys → Add, write access UNCHECKED
```
The key can read the whole repo. That's acceptable because nothing secret is committed, and the sync publishes only `skills/`.

### 9.3 Put the key on the volume (root-only)

> **Security rule (see [SECURITY_REVIEW.md](SECURITY_REVIEW.md) H1):** `/opt/data` is owned by the agent (UID 10000), so the agent can rename or replace anything inside it, including root-owned subdirectories. Anything that **root executes or trusts** must not live on the volume. That's why `sync-skills.sh` is streamed in on every run, clones fresh into `/root` temp space, and publishes a copy with no `.git/`.

```bash
fly ssh console -a fawkes-hermes -C "mkdir -p /opt/data/.ssh"
fly ssh sftp shell -a fawkes-hermes
» put /Users/<you>/.ssh/hermes_skills_deploy /opt/data/.ssh/skills_deploy
» exit
fly ssh console -a fawkes-hermes -C "sh -c 'chown -R root:root /opt/data/.ssh && chmod 700 /opt/data/.ssh && chmod 600 /opt/data/.ssh/skills_deploy'"
rm -P ~/.ssh/hermes_skills_deploy      # the key now exists only on the server
```
`which git ssh` inside `fly ssh console` must show both; otherwise use the HTTPS fallback below.

What `scripts/sync-skills.sh` does, given `REPO` and `REF` (a commit SHA from CI, or a branch name):
1. Checks that the key is a root-owned regular file with mode 600 and not a symlink.
2. Pins GitHub's host key inline, then fetches `REF` at depth 1 into `mktemp -d /root/…` with hooks and symlinks disabled.
3. Refuses any symlinks in `skills/`, copies `skills/` into a staging directory, `chown root`, `chmod go=rX`, and writes `.revision`.
4. Atomically swaps the staging directory into `/opt/data/skills-repo` with `mv -T`.

Run it manually with `make sync-skills` (publishes `origin/main`; use `REF=<sha>` to pin a commit).

Register the directory once, in `hx config edit` (define `hx` as in §7.1 first):
```yaml
skills:
  external_dirs:
    - /opt/data/skills-repo
```
Then run `fly apps restart fawkes-hermes` and check with `hx skills list`.

**Shadowing:** Hermes resolves skills in this order: project, then local (`/opt/data/skills/`), then `skills.create_dir`, then `external_dirs`. A skill the agent creates with the same name as a repo skill **silently overrides** it. If `hx skills list` shows a repo skill coming from the wrong path, delete the local copy and land its changes here through a PR. Authoring rules are in `skills/AGENTS.md`.

**HTTPS fallback (if the image has no `ssh`):** create a fine-grained GitHub PAT with *Contents: read-only* on this repo. Store it at `/opt/data/.ssh/gh_pat` (root-owned, mode 600, validated like `KEY`). Pass it with `git -c http.extraHeader="Authorization: Basic …"` instead of putting it in the URL.

### 9.4 Auto-sync on merge
`.github/workflows/deploy-skills.yml` runs on pushes to `main` that touch `skills/**` or the sync script, and can also be triggered manually. It re-validates, then streams the script with `REF=${{ github.sha }}`, then checks that `/opt/data/skills-repo/.revision` matches that commit.

The workflow's `FLY_API_TOKEN` can SSH in as root, so treat it as your most sensitive credential:
```bash
fly tokens create deploy -a fawkes-hermes -x 2160h   # 90 days; put a rotation reminder in your calendar
```
- Store it as a secret on the **`production` environment**, limited to the `main` branch. Don't make it a repo secret.
- Protect `main`: require PRs and passing `ci` checks, and block force-pushes.
- Actions are pinned to full commit SHAs, and Dependabot proposes updates.

New skills are picked up when a session starts. If one doesn't appear, send `/new` in Telegram or restart the app.

---

## 10. Cron jobs

Message the bot:
```
/cron add "every day at 8am" "Daily brief: search news on <topics A, B, C> from the last 24h. 5 bullets per topic, each with a source link."
/cron add "every day at 8pm" "Evening digest: <self-contained instructions>"
```
- Every run starts a **fresh session** with no chat history, so each prompt must be self-contained. Attach skills with `--skill <name>`.
- Times follow `TZ=Asia/Singapore`. Results arrive in the chat where you created the job.
- Command approvals inside cron default to deny, so build jobs around web and research tools.
- From the shell: `hx cron list`, `hx cron status`, `hx cron run <id>`.

---

## 11. MCP servers and plugins

### 11.1 MCP (GitHub example)
```bash
read -rsp "GH PAT: " GHP; echo
fly secrets set GH_PAT="$GHP" -a fawkes-hermes; unset GHP
```
In `hx config edit`:
```yaml
mcp_servers:
  github:
    command: npx
    args: ["-y", "<github-mcp-package>@<EXACT_VERSION>"]   # pin it; never resolve "latest" at runtime
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GH_PAT}"
```
- `GH_PAT` must be **fine-grained, read-only, and scoped to the specific repos** the agent needs. Assume the agent can read it (see SECURITY_REVIEW H2).
- Pin the MCP package to an exact version. `npx -y <pkg>` with no version downloads and runs whatever was last published, with your PAT in its environment. Check whether the reference `@modelcontextprotocol/server-github` package is still maintained, or whether GitHub's official server has replaced it.

MCP subprocesses only receive the variables listed under `env`. `hx mcp` opens the built-in catalog of approved servers.

### 11.2 Plugins
Plugins run inside the gateway, so only install ones you've read. See `hx plugins --help`.
```python
import httpx

def check_deploy_status(service: str) -> dict:
    """Check if a service's /health endpoint returns 2xx."""
    try:
        ok = httpx.get(f"https://{service}.example.com/health", timeout=5).is_success
    except httpx.HTTPError:
        ok = False
    return {"service": service, "status": "healthy" if ok else "down"}
```

### 11.3 If you later need the API server
```bash
fly secrets set API_SERVER_ENABLED=true API_SERVER_HOST=:: \
  API_SERVER_KEY="$(openssl rand -hex 32)" -a fawkes-hermes
```
Reach it only through `fly proxy 8642:8642`. Never add it to `[[services]]`.

---

## 12. Friends: a separate app

**Don't add friends to `fawkes-hermes`.** Sessions are per user, but one gateway shares memory, skills, the terminal and the filesystem.

1. Create a **second bot** in BotFather. One token can't serve two gateways.
2. Create a **second OpenRouter key** with its own credit limit.
3. Copy the folder to `~/hermes-cloud/hermes-friends`. In its `fly.toml`, set `app = "hermes-friends"` and `memory = "1gb"`.
4. Run `fly apps create hermes-friends` and `fly volumes create hermes_data -a hermes-friends -r sin -s 2`.
5. Set secrets as in §5, with a new path and secret, `TELEGRAM_WEBHOOK_URL=https://hermes-friends.fly.dev/tg-…`, and `TELEGRAM_ALLOWED_USERS="<id1>,<id2>,…"`.
6. Lock down tools:
   - **Research and itinerary only (recommended):** in `hx tools`, turn off the terminal and code-execution toolsets.
   - **If friends need a shell:** use a Modal sandbox:
     ```bash
     fly secrets set MODAL_TOKEN_ID=... MODAL_TOKEN_SECRET=... -a hermes-friends
     ```
     ```yaml
     terminal:
       backend: modal
       container_cpu: 1
       container_memory: 2048
       container_persistent: false
       docker_forward_env: []
     ```
     Then run `hx doctor`.

---

## 13. Cost

Check these against fly.io/pricing with the **Singapore** region selected.

| Item | Monthly |
|---|---|
| `fawkes-hermes`: shared-cpu-1x, 2 GB, always on | about $12.70 at the Ashburn rate; Singapore is higher |
| Volume, 3 GB | about $0.45 |
| Shared IPv4 + IPv6 | $0 (don't allocate a dedicated IPv4) |
| Egress (Asia-Pacific) | cents |
| OpenRouter, you alone | measure it; budget $5–15 to start |
| *Optional* `hermes-friends`: 1 GB + 2 GB volume | about $6.70 + $0.30 (Ashburn rate), plus any Modal usage |

Spending controls:
- **Set a credit limit on each OpenRouter key.** This is the real spending cap.
- OpenRouter's `max_price` is a per-million-token ceiling for choosing providers, not a per-request cap.
- After a week, check OpenRouter → Activity and size your budget from actual usage.

---

## 14. Updates, rotation, backups

**Update Hermes:** read the release notes, bump `<VERSION>` in `fly.toml`, then run `fly deploy`, `fly logs` and `hx doctor`. Config migrations write timestamped backups automatically.

**Rotate the webhook secret or path:**
```bash
fly secrets set TELEGRAM_WEBHOOK_SECRET="$(openssl rand -hex 32)" \
  TELEGRAM_WEBHOOK_URL="https://fawkes-hermes.fly.dev/tg-$(openssl rand -hex 12)" -a fawkes-hermes
```
Hermes re-registers the webhook on restart. Confirm with `getWebhookInfo` (§6.2).

**Rotate the bot token:** revoke it in BotFather, then `fly secrets set TELEGRAM_BOT_TOKEN=…`.

**Backups**
- Daily Fly snapshots: run `fly volumes list -a fawkes-hermes`, then `fly volumes snapshots list <vol-id>`.
- Monthly off-site copy. It holds your memories, sessions and `/opt/data/.env`, so it is a **secret** and must be encrypted before it touches disk (`brew install age`; keep the age identity in your password manager):
  ```bash
  # On the server: write to a root-only temp file
  fly ssh console -a fawkes-hermes -C "sh -c 'umask 077; tar czf /root/hermes-backup.tgz -C /opt/data --exclude=./installs --exclude=./.ssh --exclude=./.skills-stage.* .'"
  # Download into a 0700 directory OUTSIDE this repo, encrypt it, then shred the plaintext
  mkdir -m 700 -p ~/hermes-backups && cd ~/hermes-backups
  fly ssh sftp get /root/hermes-backup.tgz ./plain.tgz -a fawkes-hermes
  age -r <YOUR_AGE_PUBLIC_KEY> -o hermes-backup-$(date +%F).tgz.age plain.tgz && rm -P plain.tgz
  fly ssh console -a fawkes-hermes -C "rm -f /root/hermes-backup.tgz"
  ```

---

## 15. Security checklist

- [ ] Old bot token revoked; the new one lives only in Fly secrets and your password manager
- [ ] `TELEGRAM_WEBHOOK_SECRET` set (32-byte hex); the unauthenticated `curl` in §6.3 returns 4xx
- [ ] Random webhook path, stored as a secret
- [ ] `TELEGRAM_ALLOWED_USERS` contains only your ID; no `*_ALLOW_ALL_USERS` flags
- [ ] Group allowlist, if used, contains only groups whose members you trust with the agent
- [ ] The only `[[services]]` route is 443→8443; `https://fawkes-hermes.fly.dev:9119` is unreachable
- [ ] Exactly one machine, with `auto_stop_machines = "off"`
- [ ] Dashboard reachable only through `fly proxy`, with basic auth set
- [ ] API server disabled, or private with a key
- [ ] Approvals set to `smart`; cron and headless approvals `deny`; no YOLO
- [ ] Deploy key is read-only, scoped to one repo, and stored root-owned with mode 600; the local copy is deleted
- [ ] Nothing root executes or trusts lives under `/opt/data` (sync script streamed in; no persistent `.git/`)
- [ ] `/opt/data/skills-repo` is root-owned and read-only to the agent
- [ ] Fly deploy token: 90-day expiry, held in a GitHub `production` environment; `main` protected; actions pinned by SHA
- [ ] Inside the agent's terminal tool, `env` shows no `TELEGRAM_*`, `OPENROUTER_*` or `GH_PAT` values (SECURITY_REVIEW H2)
- [ ] `GH_PAT` (if used) is fine-grained and read-only; MCP packages pinned to exact versions
- [ ] Every OpenRouter key has a credit limit
- [ ] Image pinned by tag **and digest**; `hx doctor` is clean
- [ ] Friends run on a separate app, with a sandbox or no terminal
- [ ] Monthly backup taken

---

## 16. Troubleshooting

| Symptom | Check / fix |
|---|---|
| Bot silent | Check `getWebhookInfo` (§6.2) → `last_error_message`, then `fly logs`. Is your ID in `TELEGRAM_ALLOWED_USERS`? |
| `last_error_message: 404` | The path in `TELEGRAM_WEBHOOK_URL` doesn't match what Hermes serves. Redeploy after fixing the secret. |
| `last_error_message: 502/503` or connection errors | Nothing is listening on 8443. Check the `internal_port`, the `TELEGRAM_WEBHOOK_PORT` env, and `fly status`. |
| `401` / `403` in Telegram's error | Secret mismatch. Restart the app so Hermes re-registers the webhook with the current secret. |
| Gateway won't start | `TELEGRAM_WEBHOOK_SECRET` missing. It's required in webhook mode. |
| `409 Conflict` | Something else is using the token (local Hermes or a second machine). Stop it and run `fly scale count 1`. |
| Updates pile up (`pending_update_count` growing) | The app was down. It drains once it's back up; check `fly logs` for crashes. |
| Group messages ignored | Privacy mode: turn it off and **re-add the bot**, or make it an admin. Also check `allowed_chats` and `group_allowed_chats`. |
| `Permission denied` under `/opt/data` | You probably ran `hermes` as root. Fix: `fly ssh console -C "sh -c 'chown -R 10000:10000 /opt/data && chown -R root:root /opt/data/.ssh /opt/data/skills-repo'"`, then restart. |
| Dashboard won't start | No auth provider. Check the `HERMES_DASHBOARD_BASIC_AUTH_*` secrets. |
| `fly proxy` connects but the page hangs | Bind issue (§8). Try `HERMES_DASHBOARD_HOST = "fly-local-6pn"`. |
| Cron didn't fire | Run `hx cron status`. The gateway must be up; check `TZ`. |
| Skill missing | Check `cat /opt/data/skills-repo/.revision`, re-run `deploy-skills` (or `make sync-skills`), check `external_dirs`, run `hx skills list`, then start a new session. |
| State gone after deploy | The volume isn't mounted at `/opt/data`. |

---

## Appendix: verify these on your first deploy

Results from the first deploy on 2026-11-08 (v0.23.0) are marked ✅, ❌ or 🔎.

1. ❌→✅ **s6 does not run on Fly.** `/fly/init` is PID 1, so the entrypoint logs "not PID 1 … supervised services are unavailable" and runs only the CMD. With `app = "gateway run"` the dashboard never started. **Fix (in the repo's `fly.toml`):** the CMD is `sh -c '<dashboard restart loop> & exec hermes gateway run'`. The image's `main-wrapper.sh` drops it to `hermes`, and the gateway runs in the foreground, so if it exits the machine restarts. Both processes were confirmed running as UID 10000.
2. ✅ A fresh volume is bootstrapped and owned by `hermes:hermes` (`/opt/data` mode 700, `.env` mode 600).
3. ✅ The webhook listens on `0.0.0.0:8443`, and the log shows `[Telegram] Connected to Telegram (webhook mode)`. Other listeners: the dashboard on 9119 (private network), Hermes's own loopback API server on `127.0.0.1:8642` (with an auto-generated `API_SERVER_KEY`), and Fly SSH on 22 (private network).
4. Hermes registers the webhook itself on startup (`getWebhookInfo` shows your URL).
5. Unauthenticated POSTs to the webhook path return 4xx (§6.3).
6. 🔎 The dashboard reports `HERMES_DASHBOARD_READY port=9119` and is unreachable at `https://fawkes-hermes.fly.dev:9119` ✅. Still to check: login through `make dashboard`.
7. ✅ `git`, `ssh`, `node` and `npx` exist in the image (no HTTPS fallback needed for skills sync).
8. `fly ssh console` from GitHub Actions works with an app-scoped deploy token.

**References:** Hermes docs (hermes-agent.nousresearch.com/docs): Telegram, Docker, Security, Skills, Cron · fly.io/pricing · core.telegram.org/bots/api (setWebhook, getWebhookInfo) · OpenRouter provider-routing docs.
