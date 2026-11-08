# Go-live runbook: initialization and CI/CD

A one-time, ordered path from this repo to a running `fawkes-hermes` with CI/CD wired up. Each step says what to do and how to confirm it worked. Reference material: [DESIGN.md](DESIGN.md) (the why and the details), [CICD.md](CICD.md) (day-to-day flow), [SECURITY_REVIEW.md](SECURITY_REVIEW.md) (the gate).

Steps marked 👤 need you, because they involve a browser login, BotFather or a password manager. Everything else can be pasted as-is.

---

## Credentials inventory (all of them)

**Never paste a value into chat, a doc or a commit.** Each one goes from its source straight into your password manager, then into Fly or GitHub using the commands in the step listed.

| # | Credential | Required? | Create it at | Stored in | Step |
|---|---|---|---|---|---|
| 1 | Fly account login | ✅ | `fly auth login` (browser) | Laptop keychain | 0 |
| 2 | GitHub CLI login | ✅ (done) | `gh auth login` | Laptop keychain | 0 |
| 3 | `TELEGRAM_BOT_TOKEN`, a **new** prod token | ✅ | @BotFather (revoke the v1 token) | Fly secret | 2, 5 |
| 4 | `TELEGRAM_ALLOWED_USERS`, your numeric ID | ✅ | @userinfobot | Fly secret | 2, 5 |
| 5 | `TELEGRAM_WEBHOOK_SECRET` | ✅ | Generated: `openssl rand -hex 32` | Fly secret | 5 |
| 6 | Webhook path (inside `TELEGRAM_WEBHOOK_URL`) | ✅ | Generated: `/tg-$(openssl rand -hex 12)` | Fly secret + password manager | 5 |
| 7 | `OPENROUTER_API_KEY`, with a credit limit | ✅ | openrouter.ai → Keys | Fly secret | 3, 5 |
| 8 | Dashboard `…_BASIC_AUTH_USERNAME` / `…_PASSWORD` / `…_SECRET` | ✅ | You choose / `openssl rand` | Fly secrets | 5 |
| 9 | `FLY_API_TOKEN`, deploy scope, 90 days | ✅ | `fly tokens create deploy -a fawkes-hermes -x 2160h` | GitHub → env `production` (piped, never shown) | 8.3 |
| 10 | Skills deploy key (ed25519, read-only) | ✅ | `ssh-keygen`; public half via `gh repo deploy-key add` | Private half: `/opt/data/.ssh` (root, mode 600) only | 8.1 |
| 11 | Backup age key pair | ✅ | `age-keygen` | Password manager (public key in `make backup`) | 9 |
| 12 | Web-search backend key | Depends | Whatever `hx tools` asks for (e.g. Nous Portal) | Fly secret / `hx` | 7 |
| 13 | `TELEGRAM_GROUP_ALLOWED_CHATS` | Optional | Group ID (starts with `-`) | Fly secret | 5 |
| 14 | `GH_PAT` for the GitHub MCP (fine-grained, read-only) | Optional | github.com → Settings → Developer settings | Fly secret | DESIGN §11 |
| 15 | Dev bot token + dev OpenRouter key | Optional | @BotFather / OpenRouter | `.env.local` (gitignored) | `make local-up` |
| 16 | `MODAL_TOKEN_ID` / `_SECRET` | Optional (friends app) | modal.com | Fly secret on the friends app | DESIGN §12 |
| 17 | `LTA_DATAMALL_KEY` (`sg-bus` skill) | For `sg-bus` | datamall.lta.gov.sg → Request for API Access | `.env.local` → Fly secret via `make skill-secrets` | [TRAVEL_SKILLS](TRAVEL_SKILLS.md) |
| 18 | `DATA_GOV_SG_API_KEY` (`weather` skill) | Optional | data.gov.sg → API keys | `.env.local` → Fly secret via `make skill-secrets` | [TRAVEL_SKILLS](TRAVEL_SKILLS.md) |

Claude (or any agent working in this repo) needs **none** of these values. It only needs you to have run the logins in #1–2. You type secrets at hidden `read -s` prompts or pipe them between CLIs.

## 0. Tools and logins 👤

```bash
brew install flyctl age shellcheck     # pre-commit is already installed via brew
gh auth login                          # GitHub: browser flow, scopes repo + workflow
fly auth login
```
✅ `gh auth status` and `fly auth whoami` both show your accounts.

## 1. GitHub repository

```bash
cd ~/Desktop/hermes
make setup && make lint                # first run downloads gitleaks; all hooks must pass
git add -A && git commit -m "..."      # if anything is uncommitted
gh repo create fawkes-hermes --private --source . --push
```
Repository settings (✅ = already applied on 2026-11-08 through `gh api`):
1. ✅ **Actions → General:** workflow token is **read-only**, and Actions can't approve PRs.
2. ✅ **Environments → `production`:** deployment branches limited to `main`. `FLY_API_TOKEN` goes here in step 8.3.
3. ✅ First `ci` run on `main` is green.

**Not available on GitHub Free for private repos** (confirmed: the API returned "Upgrade to GitHub Pro"):
- *Branch protection / rulesets:* `main` accepts direct pushes, so use PRs by habit (CICD "Local gate").
- *Environment required reviewers:* there's no approval click, so `deploy-infra` is manual-dispatch only, with a typed version check.
- *GitHub secret scanning / push protection:* replaced by gitleaks on commit, on push and in CI.

If you upgrade to Pro later: add branch protection on `main` requiring `secret scan + hooks`, `validate skills` and `fly.toml image pin`, plus yourself as a required reviewer on `production`. Then `deploy-infra` can be switched to trigger on merge.

✅ The repo is private, the environment exists, and `ci` is green.

## 2. Telegram 👤 (DESIGN §1.1, §2)

1. BotFather: **revoke the old v1 token**, then save the new one in your password manager.
2. If you'll use groups: *Group Privacy → Off*, then remove and re-add the bot to each group.
3. Collect `MY_TG_ID` from @userinfobot.
4. Optional: create a **second, dev bot** for `make local-up`.

✅ The old token returns `401` from `getMe`; the new one works.

## 3. OpenRouter 👤

Create a dedicated key with a **credit limit** (for example $15/month). Create a separate, smaller one for local dev.

## 4. Fly app, volume and `fly.toml` (DESIGN §3–4)

```bash
fly apps create fawkes-hermes
fly volumes create hermes_data --app fawkes-hermes --region sin --size 3 --yes
make image-digest VERSION=v0.23.0      # use the newest plain vX.Y.Z tag
```
Create `fly.toml` from DESIGN §4 and paste in the `image = "…@sha256:…"` line. Then:
```bash
git switch -c fly-toml && make check-image
git add fly.toml && git commit -m "Add fly.toml pinned to vX.Y.Z" && git push -u origin fly-toml
gh pr create --fill && gh pr merge --squash --auto
git switch main && git pull
```
✅ `ci` passes, including `fly.toml image pin`, and `fly volumes list -a fawkes-hermes` shows `hermes_data` in `sin`.

## 5. Secrets 👤 (DESIGN §5)

Run the `read -rsp …` / `fly secrets set --stage …` block from DESIGN §5 exactly as written. **Save `WEBHOOK_PATH` in your password manager**; you'll need it for `make webhook-test`.

✅ `make secrets` lists all eight names. Values are never shown.

## 6. First deploy and verification (DESIGN §6)

```bash
make deploy                 # lint → check-image → fly deploy --ha=false → status
fly scale count 1 --yes -a fawkes-hermes
make logs                   # wait for: [telegram] Connected to Telegram (webhook mode)
make webhook-info           # url = https://fawkes-hermes.fly.dev/tg-…, no last_error_message
make webhook-test           # must print "OK: 4xx"
curl -m 5 https://fawkes-hermes.fly.dev:9119 || echo "dashboard not public ✅"
make dashboard              # then open http://localhost:9119 (DESIGN §8: how access is secured)
```
✅ All of the above pass, and the bot replies to your DM. A "set up a model" error is fine at this point.

## 7. First-run configuration (DESIGN §7)

`make ssh`, define `hx` (§7.1), then:
```bash
hx doctor
hx model                    # OpenRouter → your chosen model
hx tools                    # web search backend enabled
hx config edit              # confirm §7.5 safety defaults; add skills.external_dirs: [/opt/data/skills-repo]
exit
make restart
```
**H2 check (required):** DM the bot: *"Run `env | cut -d= -f1` and list the variable names."* If you see `TELEGRAM_*`, `OPENROUTER_*` or `GH_PAT`, decide now: disable the terminal and code toolsets, or accept the risk with the credit limit. Record the decision in SECURITY_REVIEW H2.

✅ `hx doctor` is clean, the bot answers a real question, and the H2 decision is recorded.

## 8. Skills CI/CD

**8.1 Deploy key** (DESIGN §9.2–9.3):
```bash
ssh-keygen -t ed25519 -C "hermes-skills-deploy" -f ~/.ssh/hermes_skills_deploy -N ""
gh repo deploy-key add ~/.ssh/hermes_skills_deploy.pub --title fawkes-hermes-skills   # read-only by default
fly ssh console -a fawkes-hermes -C "mkdir -p /opt/data/.ssh"
fly ssh sftp shell -a fawkes-hermes        # » put ~/.ssh/hermes_skills_deploy /opt/data/.ssh/skills_deploy
fly ssh console -a fawkes-hermes -C "sh -c 'chown -R root:root /opt/data/.ssh && chmod 700 /opt/data/.ssh && chmod 600 /opt/data/.ssh/skills_deploy'"
rm -P ~/.ssh/hermes_skills_deploy ~/.ssh/hermes_skills_deploy.pub
```

**8.2 First sync by hand**, to prove the path before giving CI a token:
```bash
make sync-skills            # → "skills synced @ <sha> (1 skills)"
make restart
```
Then confirm inside `make ssh`: `hx skills list` shows `research-brief`, and `ls -la /opt/data/skills-repo` shows owner `root` and no write bit for others.

**8.3 Give CI its token.** The token is piped straight into GitHub and never shown:
```bash
fly tokens create deploy -a fawkes-hermes -x 2160h | gh secret set FLY_API_TOKEN --env production
```
Add a calendar reminder to rotate it in about 85 days.

**8.4 Prove CD end-to-end:**
```bash
gh workflow run deploy-skills && gh run watch
```
✅ The `deploy` job's *Verify published revision* step prints `published=<sha> expected=<sha>`.

**8.5 Prove infra CD.** This redeploys the version that's already running, so it's harmless:
```bash
gh workflow run deploy-infra -f version=<vX.Y.Z in fly.toml> && gh run watch
make webhook-info && make webhook-test
```
✅ The *Verify exactly one started machine running the pinned digest* step passes, and the bot still replies.

## 9. Operations setup

- Cron jobs: `/cron add …` in Telegram (DESIGN §10).
- Backups: create an age key with `age-keygen -o ~/hermes-backups/age.key` and move it into your password manager. Then run `make backup AGE_RECIPIENT=age1…` once, and add a monthly reminder.
- Calendar reminders: `FLY_API_TOKEN` expiry, monthly backup, monthly check of the Hermes release notes.
- After a week: size the budget from OpenRouter → Activity.

## 10. Go-live sign-off

- [ ] Every item in DESIGN **§15 Security checklist** is ticked
- [ ] Every item in the SECURITY_REVIEW **Implementation gate** is ticked
- [ ] Appendix items 1–8 in DESIGN verified; 🔎 notes resolved or recorded
- [ ] `ci` green on `main`; `deploy-skills` and `deploy-infra` have each succeeded at least once
- [ ] Rollback rehearsed once: `make sync-skills REF=<previous-sha>`, then back to `main`
