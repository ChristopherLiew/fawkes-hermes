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
│ Fly app: hermes-me (sin)                             │       │
│   only public route: 443 → 8443  /tg-<random>        │       │
│                                                      ▼       │
│  nousresearch/hermes-agent:<PINNED>  (s6 supervises both)    │
│   ├─ gateway run     → Telegram webhook :8443, cron ticker   │
│   └─ dashboard :9119 → private network only + basic auth     │
│                                                              │
│  Volume hermes_data → /opt/data                              │
│   ├─ config.yaml, .env, SOUL.md, memories/, sessions/        │
│   ├─ skills/          (bundled + agent-created)              │
│   ├─ skills-repo/     (your private repo, read-only)         │
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
| `DASH_PASS` | `openssl rand -base64 24` |
| Webhook path and secret | Generated in §5 |

### 1.4 Pin a Hermes version
Pick the newest `X.Y.Z` tag at hub.docker.com/r/nousresearch/hermes-agent/tags. This guide calls it `<VERSION>`. **Never deploy `latest`.** Tags can be moved, so pin the digest as well: `image = "nousresearch/hermes-agent:<VERSION>@sha256:<DIGEST>"`. Get the digest with `docker buildx imagetools inspect nousresearch/hermes-agent:<VERSION>`.

---

## 2. Telegram bot settings

1. @BotFather → `/mybots` → bot → **Bot Settings → Group Privacy → Turn off**. Only needed if you use the bot in groups.
2. If the bot is already in a group, **remove it and add it back**. Telegram caches the privacy setting when the bot joins. Making the bot a group admin also works.
3. **Never run Hermes elsewhere with this token.** While a webhook is set, any other process polling with the same token gets `409 Conflict`. Starting a second gateway that registers its own webhook would steal the bot.

---

## 3. Create the Fly app and volume

```bash
mkdir -p ~/hermes-cloud/hermes-me && cd ~/hermes-cloud/hermes-me

fly apps create hermes-me
fly volumes create hermes_data --app hermes-me --region sin --size 3 --yes
```

---

## 4. `fly.toml`

```toml
app = "hermes-me"
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
cd ~/hermes-cloud/hermes-me

read -rsp "Bot token: " BOT_TOKEN; echo
read -rsp "OpenRouter key: " OPENROUTER_KEY; echo
read -rsp "Dashboard password: " DASH_PASS; echo
read -rp  "Your Telegram user ID: " MY_TG_ID

WEBHOOK_PATH="/tg-$(openssl rand -hex 12)"
WEBHOOK_SECRET="$(openssl rand -hex 32)"
echo "Webhook path: $WEBHOOK_PATH   (save it in your password manager)"

fly secrets set --stage \
  TELEGRAM_BOT_TOKEN="$BOT_TOKEN" \
  TELEGRAM_ALLOWED_USERS="$MY_TG_ID" \
  TELEGRAM_WEBHOOK_URL="https://hermes-me.fly.dev$WEBHOOK_PATH" \
  TELEGRAM_WEBHOOK_SECRET="$WEBHOOK_SECRET" \
  OPENROUTER_API_KEY="$OPENROUTER_KEY" \
  HERMES_DASHBOARD_BASIC_AUTH_USERNAME="chris" \
  HERMES_DASHBOARD_BASIC_AUTH_PASSWORD="$DASH_PASS" \
  HERMES_DASHBOARD_BASIC_AUTH_SECRET="$(openssl rand -hex 32)"

unset OPENROUTER_KEY DASH_PASS WEBHOOK_SECRET   # keep BOT_TOKEN for §6.2, then unset it
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
- `url` = `https://hermes-me.fly.dev/tg-…`
- `pending_update_count` at or near 0
- no `last_error_message`. If there is one, it tells you what Telegram saw, such as a 404 or a TLS error.

### 6.3 Check that unauthenticated requests are rejected
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -H 'Content-Type: application/json' -d '{"update_id":1}' \
  "https://hermes-me.fly.dev$WEBHOOK_PATH"
```
A 4xx (401 or 403) means the secret header check works ✅. A 200 means the check isn't being enforced, so stop and investigate. A 502 or 503 means nothing is listening on 8443; check `fly logs`.

### 6.4 Say hi
DM the bot. It should reply. If no model is configured yet, the reply may be an error asking you to set one up.

---

## 7. First-run configuration (inside the machine)

### 7.1 Shell and helper
`fly ssh console` logs you in as **root**. Run `hermes` as the `hermes` user, or it will create root-owned files the gateway can't read.
```bash
fly ssh console -a hermes-me

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
fly apps restart hermes-me
```

---

## 8. Dashboard access (private network only)

```bash
fly proxy 9119:9119 -a hermes-me
# open http://localhost:9119 and log in as chris / DASH_PASS
```
- Port 9119 isn't listed in `[[services]]`, so it can't be reached through `hermes-me.fly.dev`. To confirm, `curl -m 5 https://hermes-me.fly.dev:9119` should fail.
- **If the proxy connects but the page hangs:** run `ss -ltnp | grep 9119` in `fly ssh console`. If it shows only `0.0.0.0`, set `HERMES_DASHBOARD_HOST = "fly-local-6pn"` and redeploy.
- On your phone, use Telegram. Reaching the dashboard from a phone would need Tailscale or a Cloudflare Tunnel with Access via a custom image. Never add 9119 to `[[services]]`.

---

## 9. Private skills repo (read-only, synced on push)

### 9.1 Repo layout
```
hermes-skills/
├── research-brief/SKILL.md
├── itinerary/SKILL.md
├── code-review/SKILL.md
└── .github/workflows/sync.yml
```
```yaml
---
name: research-brief
description: "Use when asked for a daily research brief. Searches, dedupes, cites sources."
version: 1.0.0
---
# Research brief
1. ...
```

### 9.2 Deploy key (read-only, one repo)
```bash
ssh-keygen -t ed25519 -C "hermes-skills-deploy" -f ~/.ssh/hermes_skills_deploy -N ""
cat ~/.ssh/hermes_skills_deploy.pub
```
Then in GitHub: `hermes-skills` → Settings → Deploy keys → Add. **Leave "Allow write access" unchecked.**

### 9.3 Put the key on the volume (root-only); keep the sync script OFF the volume

> **Security rule (see [SECURITY_REVIEW.md](SECURITY_REVIEW.md) H1):** `/opt/data` is owned by the
> agent (UID 10000), so the agent can rename or replace anything inside it, including root-owned
> subdirectories. Anything that **root executes or trusts** must therefore not live on the volume.
> Earlier drafts kept `bin/sync-skills.sh` and a persistent `.git/` on the volume. A prompt-injected
> agent could swap the script, or add `core.fsmonitor` to `.git/config`, and get root on the next sync.
> The script below runs from the skills repo, clones fresh into root-only temp space every time, and
> publishes a **root-owned, read-only** copy with no `.git/`.

```bash
fly ssh console -a hermes-me -C "mkdir -p /opt/data/.ssh"
fly ssh sftp shell -a hermes-me
» put /Users/<you>/.ssh/hermes_skills_deploy /opt/data/.ssh/skills_deploy
» exit
fly ssh console -a hermes-me -C "sh -c 'chown -R root:root /opt/data/.ssh && chmod 700 /opt/data/.ssh && chmod 600 /opt/data/.ssh/skills_deploy'"

# The key now exists only on the server; remove the local copy (or move it into your password manager)
rm -P ~/.ssh/hermes_skills_deploy
```
`which git ssh` inside `fly ssh console` must show both; otherwise use the HTTPS fallback below.

Commit this as `scripts/sync-skills.sh` **in the `hermes-skills` repo**:
```sh
#!/bin/sh
# Runs as root, streamed in via `fly ssh console` (never stored on the volume).
# Trusts nothing under /opt/data except the key file, which it validates first.
set -eu
umask 077
REPO=git@github.com:<YOUR_GH_USER>/hermes-skills.git
KEY=/opt/data/.ssh/skills_deploy
DEST=/opt/data/skills-repo

# The key must be a root-owned regular file, not a symlink, with mode 600.
[ -f "$KEY" ] && [ ! -L "$KEY" ] || { echo "bad key path" >&2; exit 1; }
[ "$(stat -c '%u %a' "$KEY")" = "0 600" ] || { echo "bad key perms" >&2; exit 1; }

WORK=$(mktemp -d /root/skills.XXXXXX)          # root-only, outside the agent's reach
trap 'rm -rf "$WORK"' EXIT
# Pinned GitHub host key: verify at docs.github.com → "GitHub's SSH key fingerprints"
echo 'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl' > "$WORK/known_hosts"
export GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o UserKnownHostsFile=$WORK/known_hosts -o StrictHostKeyChecking=yes"

git -c core.symlinks=false -c core.hooksPath=/dev/null \
  clone --quiet --depth 1 --branch main "$REPO" "$WORK/repo"
REV=$(git -C "$WORK/repo" rev-parse --short HEAD)
rm -rf "$WORK/repo/.git" "$WORK/repo/.github" "$WORK/repo/scripts"

# Stage on the same filesystem, then swap in with an atomic rename
STAGE=$(mktemp -d /opt/data/.skills-stage.XXXXXX)
cp -R "$WORK/repo/." "$STAGE/"
chown -R root:root "$STAGE"
chmod -R u=rwX,go=rX "$STAGE"                   # the agent can read but never write
rm -rf -- "$DEST"
mv -T "$STAGE" "$DEST"
echo "skills synced @ $REV"
```
Run it manually the first time:
```bash
fly ssh console -a hermes-me -C "sh -c \"echo $(base64 < scripts/sync-skills.sh | tr -d '\n') | base64 -d | sh\""
```
Register the directory in `hx config edit` (define `hx` as in §7.1 first):
```yaml
skills:
  external_dirs:
    - /opt/data/skills-repo
```
Then run `fly apps restart hermes-me` and check with `hx skills list`.

**HTTPS fallback (if the image has no `ssh`):** create a fine-grained GitHub PAT with *Contents: read-only* on this one repo. Store it at `/opt/data/.ssh/gh_pat` (root-owned, mode 600, validated the same way as `KEY`). Pass it with `git -c http.extraHeader="Authorization: Basic $(printf 'x-access-token:%s' "$(cat …)" | base64 -w0)"` instead of putting it in the URL, so it never appears in `ps` output or in `.git/config`.

### 9.4 Auto-sync on push
This token can SSH into the machine as root, so treat it as the most sensitive credential you have.
```bash
fly tokens create deploy -a hermes-me -x 2160h   # 90 days; put a rotation reminder in your calendar
```
- In GitHub, add it as a secret on a **`production` environment** (Settings → Environments), not as a plain repo secret, and limit that environment to the `main` branch.
- Protect `main`: require PRs, block force-pushes. Anyone who can push to `main` controls both the agent's skills and a root shell.
- Pin every action to a full commit SHA. A `@master` ref lets whoever controls upstream run code next to your token.

`.github/workflows/sync.yml`:
```yaml
name: sync-skills-to-hermes
on:
  push:
    branches: [main]
permissions:
  contents: read
concurrency: sync-skills
jobs:
  sync:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@<FULL_COMMIT_SHA>          # vX.Y.Z
        with: { persist-credentials: false }
      - uses: superfly/flyctl-actions/setup-flyctl@<FULL_COMMIT_SHA>   # vX.Y.Z
      - name: Sync skills (script is streamed in, never stored on the volume)
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
        run: |
          B64=$(base64 -w0 scripts/sync-skills.sh)
          flyctl ssh console -a hermes-me -C "sh -c \"echo $B64 | base64 -d | sh\""
```
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
fly secrets set GH_PAT="$GHP" -a hermes-me; unset GHP
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
  API_SERVER_KEY="$(openssl rand -hex 32)" -a hermes-me
```
Reach it only through `fly proxy 8642:8642`. Never add it to `[[services]]`.

---

## 12. Friends: a separate app

**Don't add friends to `hermes-me`.** Sessions are per user, but one gateway shares memory, skills, the terminal and the filesystem.

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
| `hermes-me`: shared-cpu-1x, 2 GB, always on | about $12.70 at the Ashburn rate; Singapore is higher |
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
  TELEGRAM_WEBHOOK_URL="https://hermes-me.fly.dev/tg-$(openssl rand -hex 12)" -a hermes-me
```
Hermes re-registers the webhook on restart. Confirm with `getWebhookInfo` (§6.2).

**Rotate the bot token:** revoke it in BotFather, then `fly secrets set TELEGRAM_BOT_TOKEN=…`.

**Backups**
- Daily Fly snapshots: run `fly volumes list -a hermes-me`, then `fly volumes snapshots list <vol-id>`.
- Monthly off-site copy. It holds your memories, sessions and `/opt/data/.env`, so it is a **secret** and must be encrypted before it touches disk (`brew install age`; keep the age identity in your password manager):
  ```bash
  # On the server: write to a root-only temp file
  fly ssh console -a hermes-me -C "sh -c 'umask 077; tar czf /root/hermes-backup.tgz -C /opt/data --exclude=./installs --exclude=./.ssh --exclude=./.skills-stage.* .'"
  # Download into a 0700 directory OUTSIDE this repo, encrypt it, then shred the plaintext
  mkdir -m 700 -p ~/hermes-backups && cd ~/hermes-backups
  fly ssh sftp get /root/hermes-backup.tgz ./plain.tgz -a hermes-me
  age -r <YOUR_AGE_PUBLIC_KEY> -o hermes-backup-$(date +%F).tgz.age plain.tgz && rm -P plain.tgz
  fly ssh console -a hermes-me -C "rm -f /root/hermes-backup.tgz"
  ```

---

## 15. Security checklist

- [ ] Old bot token revoked; the new one lives only in Fly secrets and your password manager
- [ ] `TELEGRAM_WEBHOOK_SECRET` set (32-byte hex); the unauthenticated `curl` in §6.3 returns 4xx
- [ ] Random webhook path, stored as a secret
- [ ] `TELEGRAM_ALLOWED_USERS` contains only your ID; no `*_ALLOW_ALL_USERS` flags
- [ ] Group allowlist, if used, contains only groups whose members you trust with the agent
- [ ] The only `[[services]]` route is 443→8443; `https://hermes-me.fly.dev:9119` is unreachable
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
| Skill missing | Re-run the sync workflow (or the manual command in §9.3), check `external_dirs`, run `hx skills list`, then start a new session. |
| State gone after deploy | The volume isn't mounted at `/opt/data`. |

---

## Appendix: verify these on your first deploy

1. `[processes] app = "gateway run"` starts the gateway through the image's s6 entrypoint, and the dashboard also comes up.
2. The entrypoint handles a fresh root-owned volume at `/opt/data`. If it doesn't, run the `chown` fix from §16 once.
3. The Telegram webhook server listens on `0.0.0.0:8443`, so Fly's edge can reach it.
4. Hermes registers the webhook itself on startup (`getWebhookInfo` shows your URL).
5. Unauthenticated POSTs to the webhook path return 4xx (§6.3).
6. `HERMES_DASHBOARD_HOST = "::"` is reachable through `fly proxy`.
7. `git` and `ssh` exist in the image.
8. `fly ssh console` from GitHub Actions works with an app-scoped deploy token.

**References:** Hermes docs (hermes-agent.nousresearch.com/docs): Telegram, Docker, Security, Skills, Cron · fly.io/pricing · core.telegram.org/bots/api (setWebhook, getWebhookInfo) · OpenRouter provider-routing docs.
