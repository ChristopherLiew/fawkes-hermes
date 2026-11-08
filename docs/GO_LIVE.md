# Go-live runbook: initialization and CI/CD

A one-time, ordered path from this repo to a running `hermes-me` with CI/CD wired up. Each step says what to do and how to confirm it worked. Reference material: [DESIGN.md](DESIGN.md) (the why and the details), [CICD.md](CICD.md) (day-to-day flow), [SECURITY_REVIEW.md](SECURITY_REVIEW.md) (the gate).

Steps marked 👤 need you, because they involve a browser login, BotFather or a password manager. Everything else can be pasted as-is.

---

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
gh repo create hermes --private --source . --push
```
Then in GitHub → **Settings**:
1. **Code security**: turn on *Secret scanning* and *Push protection*.
2. **Actions → General**: set *Workflow permissions* to **Read repository contents**.
3. Wait for the first `ci` run on `main` to go green (**Actions** tab).
4. **Branches → Add rule** (or **Rules → Rulesets**) for `main`:
   - Require a pull request before merging. Set approvals to **0**, since you're the only reviewer.
   - Require these status checks: `secret scan + hooks`, `validate skills`, `fly.toml image pin`.
   - Block force pushes and deletions.
5. **Environments → New environment** named `production`. Under *Deployment branches*, choose **Selected branches** and add `main`.

> 🔎 **Plan check:** for a **private** repo on GitHub Free, branch protection, rulesets and environment secrets may be unavailable; they need GitHub Pro. If you hit that limit:
> - Remove the `environment: production` line from `deploy-skills.yml`.
> - Store `FLY_API_TOKEN` as a plain repo secret (`gh secret set FLY_API_TOKEN`).
>
> The job's `if: github.ref == 'refs/heads/main'` still keeps it to `main`, and only people with push access (just you) can create branches. Record this decision in SECURITY_REVIEW M1.

✅ The repo is private, `ci` is green, and pushing straight to `main` is rejected (or you've accepted the Free-plan fallback).

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
fly apps create hermes-me
fly volumes create hermes_data --app hermes-me --region sin --size 3 --yes
make image-digest VERSION=v0.23.0      # use the newest plain vX.Y.Z tag
```
Create `fly.toml` from DESIGN §4 and paste in the `image = "…@sha256:…"` line. Then:
```bash
git switch -c fly-toml && make check-image
git add fly.toml && git commit -m "Add fly.toml pinned to vX.Y.Z" && git push -u origin fly-toml
gh pr create --fill && gh pr merge --squash --auto
git switch main && git pull
```
✅ `ci` passes, including `fly.toml image pin`, and `fly volumes list -a hermes-me` shows `hermes_data` in `sin`.

## 5. Secrets 👤 (DESIGN §5)

Run the `read -rsp …` / `fly secrets set --stage …` block from DESIGN §5 exactly as written. **Save `WEBHOOK_PATH` in your password manager**; you'll need it for `make webhook-test`.

✅ `make secrets` lists all eight names. Values are never shown.

## 6. First deploy and verification (DESIGN §6)

```bash
make deploy                 # lint → check-image → fly deploy --ha=false → status
fly scale count 1 --yes -a hermes-me
make logs                   # wait for: [telegram] Connected to Telegram (webhook mode)
make webhook-info           # url = https://hermes-me.fly.dev/tg-…, no last_error_message
make webhook-test           # must print "OK: 4xx"
curl -m 5 https://hermes-me.fly.dev:9119 || echo "dashboard not public ✅"
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
gh repo deploy-key add ~/.ssh/hermes_skills_deploy.pub --title hermes-me-skills   # read-only by default
fly ssh console -a hermes-me -C "mkdir -p /opt/data/.ssh"
fly ssh sftp shell -a hermes-me        # » put ~/.ssh/hermes_skills_deploy /opt/data/.ssh/skills_deploy
fly ssh console -a hermes-me -C "sh -c 'chown -R root:root /opt/data/.ssh && chmod 700 /opt/data/.ssh && chmod 600 /opt/data/.ssh/skills_deploy'"
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
fly tokens create deploy -a hermes-me -x 2160h | gh secret set FLY_API_TOKEN --env production
```
Add a calendar reminder to rotate it in about 85 days.

**8.4 Prove CD end-to-end:**
```bash
gh workflow run deploy-skills && gh run watch
```
✅ The `deploy` job's *Verify published revision* step prints `published=<sha> expected=<sha>`.

## 9. Operations setup

- Cron jobs: `/cron add …` in Telegram (DESIGN §10).
- Backups: create an age key with `age-keygen -o ~/hermes-backups/age.key` and move it into your password manager. Then run `make backup AGE_RECIPIENT=age1…` once, and add a monthly reminder.
- Calendar reminders: `FLY_API_TOKEN` expiry, monthly backup, monthly check of the Hermes release notes.
- After a week: size the budget from OpenRouter → Activity.

## 10. Go-live sign-off

- [ ] Every item in DESIGN **§15 Security checklist** is ticked
- [ ] Every item in the SECURITY_REVIEW **Implementation gate** is ticked
- [ ] Appendix items 1–8 in DESIGN verified; 🔎 notes resolved or recorded
- [ ] `ci` is required on `main`; `deploy-skills` has succeeded at least once
- [ ] Rollback rehearsed once: `make sync-skills REF=<previous-sha>`, then back to `main`
