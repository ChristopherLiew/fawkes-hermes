# Common commands for the fawkes-hermes Fly.io deployment.
# Run `make` (or `make help`) to list targets. See docs/CICD.md for the release flow.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c   # GNU make >= 3.82 only; macOS make 3.81 ignores it, so chained recipes set -e themselves
.DEFAULT_GOAL := help

APP          ?= fawkes-hermes
FLY          ?= fly
# Skills sync: repo URL as the deploy key sees it, and the ref to publish
SKILLS_GIT   ?= $(shell git remote get-url origin 2>/dev/null | sed -E 's|^https://github.com/|git@github.com:|; s|(\.git)?$$|.git|')
REF          ?= main
BACKUP_DIR   ?= $(HOME)/hermes-backups
AGE_RECIPIENT ?=

# Local runs use the same pinned image as production (read from fly.toml)
HERMES_IMAGE ?= $(shell sed -nE 's/^[[:space:]]*image[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' fly.toml 2>/dev/null)
export HERMES_IMAGE
COMPOSE      ?= docker compose
HX_LOCAL      = $(COMPOSE) exec -u hermes -e HERMES_HOME=/opt/data hermes hermes

.PHONY: help setup lint scan check-image deploy status logs ssh dashboard restart \
        image-digest releases secrets-init secrets skill-secrets webhook-info webhook-test skills-check test test-live sync-skills snapshots backup \
        adopt-pr local-check local-up local-down local-logs local-shell local-hx local-doctor local-reset

help: ## List targets
	@awk 'BEGIN{FS=":.*## "} /^[a-zA-Z_-]+:.*## /{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}' $(MAKEFILE_LIST)

## ---- Local -------------------------------------------------------------

setup: ## Install pre-commit + pre-push hooks (needs: brew install pre-commit gitleaks)
	@command -v gitleaks >/dev/null || { echo "brew install gitleaks"; exit 1; }
	@command -v pre-commit >/dev/null || { echo "brew install pre-commit"; exit 1; }
	pre-commit install --install-hooks

lint: ## Run all pre-commit hooks on every file
	pre-commit run --all-files

scan: ## Secret scan: git history + working tree including untracked/ignored files (redacted)
	gitleaks git --redact --no-banner --config .gitleaks.toml .
	gitleaks dir --redact --no-banner --config .gitleaks.toml .

check-image: ## Ensure fly.toml pins the image by tag AND digest (never latest)
	@test -f fly.toml || { echo "fly.toml not found (see docs/DESIGN.md §4)"; exit 1; }
	@grep -Eq '^[[:space:]]*image[[:space:]]*=[[:space:]]*"nousresearch/hermes-agent:v?[0-9]+\.[0-9]+\.[0-9]+@sha256:[a-f0-9]{64}"' fly.toml \
	  || { echo "fly.toml image must be nousresearch/hermes-agent:vX.Y.Z@sha256:<digest> (see: make image-digest VERSION=vX.Y.Z)"; exit 1; }
	@echo "image pin OK"

image-digest: ## Look up the digest for VERSION=vX.Y.Z from Docker Hub (no Docker needed)
	@test -n "$(VERSION)" || { echo "usage: make image-digest VERSION=vX.Y.Z"; exit 1; }
	@TOKEN=$$(curl -fsS "https://auth.docker.io/token?service=registry.docker.io&scope=repository:nousresearch/hermes-agent:pull" \
	    | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])'); \
	  D=$$(curl -fsSI -H "Authorization: Bearer $$TOKEN" \
	    -H 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json' \
	    "https://registry-1.docker.io/v2/nousresearch/hermes-agent/manifests/$(VERSION)" \
	    | awk 'tolower($$1)=="docker-content-digest:"{print $$2}' | tr -d '\r'); \
	  test -n "$$D" || { echo "tag $(VERSION) not found"; exit 1; }; \
	  echo "image = \"nousresearch/hermes-agent:$(VERSION)@$$D\""

## ---- Local (Docker) --------------------------------------------------

local-check: ## Preflight: Docker running, image pinned, .env.local safe
	@docker info >/dev/null 2>&1 || { echo "Docker daemon not running (start Docker Desktop)"; exit 1; }
	@test -n "$(HERMES_IMAGE)" || { echo "No image: create fly.toml (DESIGN §4) or pass HERMES_IMAGE=..."; exit 1; }
	@case "$(HERMES_IMAGE)" in *:latest|*hermes-agent) echo "Refusing unpinned image $(HERMES_IMAGE)"; exit 1;; esac
	@test -f .env.local || { echo "cp .env.local.example .env.local and fill in a DEV bot token"; exit 1; }
	@! grep -Eq '^[[:space:]]*TELEGRAM_WEBHOOK_URL=.+' .env.local \
	  || { echo "Remove TELEGRAM_WEBHOOK_URL from .env.local (local must poll, not take over the webhook)"; exit 1; }
	@echo "local preflight OK ($(HERMES_IMAGE))"

local-up: local-check ## Start local Hermes (dev bot, polling) + dashboard on 127.0.0.1:9120
	$(COMPOSE) up -d
	@echo "LOCAL dashboard: http://127.0.0.1:9120   (prod is make dashboard → :9119)   logs: make local-logs"

local-down: ## Stop local Hermes (keeps local state)
	$(COMPOSE) down

local-logs: ## Tail local logs
	$(COMPOSE) logs -f hermes

local-shell: ## Shell in the local container as the hermes user
	$(COMPOSE) exec -u hermes hermes sh

local-hx: ## Run a hermes CLI command locally, e.g. make local-hx ARGS="model"
	$(HX_LOCAL) $(ARGS)

local-doctor: ## hermes doctor on the local instance
	$(HX_LOCAL) doctor

local-reset: ## DESTROY local state volume (asks first)
	@read -rp "Delete local Hermes state volume? [y/N] " a; [ "$$a" = y ] || exit 1
	$(COMPOSE) down -v

## ---- Fly -------------------------------------------------------------

deploy: lint check-image ## Scan, verify image pin, deploy (single machine)
	$(FLY) deploy --ha=false -a $(APP)
	$(FLY) status -a $(APP)

status: ## Machine and release status
	$(FLY) status -a $(APP)

logs: ## Tail logs
	$(FLY) logs -a $(APP)

ssh: ## Root shell on the machine with a system-only PATH (use `hx`, DESIGN §7.1)
	@# The image PATH includes agent-writable /opt/data/.local/bin; a root shell must never resolve commands there.
	$(FLY) ssh console -a $(APP) --pty -C "/usr/bin/env PATH=/usr/sbin:/usr/bin:/sbin:/bin /bin/bash"

dashboard: ## PROD dashboard (fawkes-hermes on Fly) via private tunnel → http://localhost:9119
	$(FLY) proxy 9119:9119 -a $(APP)

restart: ## Restart the app (applies config / re-registers webhook)
	$(FLY) apps restart $(APP)

releases: ## List releases (for rollback)
	$(FLY) releases -a $(APP)

secrets-init: ## Set all runtime secrets via hidden prompts (run in YOUR terminal; values never echoed/stored)
	@echo "Values are read silently, sent straight to Fly and never echoed, logged or written to disk."
	@set -euo pipefail; \
	  read -rsp "Telegram bot token (NEW, never pasted anywhere): " BOT; echo; \
	  read -rsp "OpenRouter API key: " ORK; echo; \
	  read -rsp "Telegram user ID(s), comma-separated: " TGID; echo; \
	  read -rsp "Dashboard username: " DU; echo; \
	  read -rsp "Dashboard password (blank = generate): " DP; echo; \
	  [ -n "$$DP" ] || { DP=$$(openssl rand -base64 24); echo "Generated a dashboard password; it will be shown once at the end."; GEN=1; }; \
	  case "$$BOT" in *:*) ;; *) echo "bot token looks wrong"; exit 1;; esac; \
	  case "$$TGID" in *[!0-9,]*|"") echo "user ID must be numeric"; exit 1;; esac; \
	  WPATH="/tg-$$(openssl rand -hex 12)"; \
	  printf '%s\n' \
	    "TELEGRAM_BOT_TOKEN=$$BOT" "TELEGRAM_ALLOWED_USERS=$$TGID" \
	    "TELEGRAM_WEBHOOK_URL=https://$(APP).fly.dev$$WPATH" "TELEGRAM_WEBHOOK_SECRET=$$(openssl rand -hex 32)" \
	    "OPENROUTER_API_KEY=$$ORK" \
	    "HERMES_DASHBOARD_BASIC_AUTH_USERNAME=$$DU" "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=$$DP" \
	    "HERMES_DASHBOARD_BASIC_AUTH_SECRET=$$(openssl rand -hex 32)" \
	  | $(FLY) secrets import --stage -a $(APP) >/dev/null \
	  || { echo "FAILED: secrets were NOT staged (nothing to save)"; exit 1; }; \
	  echo "Staged 8 secrets on $(APP) (applied on next deploy)."; \
	  echo "Save to your password manager NOW: webhook path = $$WPATH"; \
	  [ -z "$${GEN:-}" ] || echo "Save to your password manager NOW: dashboard password = $$DP"; \
	  unset BOT ORK TGID DU DP WPATH

secrets: ## List secret NAMES and digests (never values)
	$(FLY) secrets list -a $(APP)

## ---- Verification ----------------------------------------------------

webhook-info: ## Show Telegram getWebhookInfo (prompts for bot token, hidden)
	@read -rsp "Bot token: " T; echo; \
	  curl -fsS "https://api.telegram.org/bot$$T/getWebhookInfo" | python3 -m json.tool

webhook-test: ## Unauthenticated POST must return 4xx (prompts for webhook path)
	@read -rsp "Webhook path (/tg-...): " P; echo; \
	  code=$$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' \
	    -d '{"update_id":1}' "https://$(APP).fly.dev$$P"); \
	  case $$code in 4??) echo "OK: $$code (secret check enforced)";; \
	    200) echo "FAIL: 200 — secret header NOT enforced"; exit 1;; \
	    *) echo "FAIL: $$code — check fly logs"; exit 1;; esac

## ---- Dependencies ----------------------------------------------------

adopt-pr: ## Re-apply a Dependabot PR as YOUR commit on main, push, close the PR (PR=<n>)
	@test -n "$(PR)" || { echo "usage: make adopt-pr PR=<number>"; exit 1; }
	@git diff --quiet && git diff --cached --quiet || { echo "working tree not clean"; exit 1; }
	@author=$$(gh pr view $(PR) --json author --jq .author.login); \
	  case "$$author" in *dependabot*) ;; *) echo "PR $(PR) is by $$author, not Dependabot; merge it normally"; exit 1;; esac
	git switch main && git pull --ff-only
	gh pr diff $(PR) | git apply --index
	git commit -m "$$(gh pr view $(PR) --json title --jq .title) (adopted from #$(PR))"
	git push
	gh pr close $(PR) --delete-branch --comment "Applied as $$(git rev-parse --short HEAD) under the sole-author policy (AGENTS.md)."

## ---- Skills & backups -----------------------------------------------

skills-check: ## Validate skills/ (frontmatter, names, no symlinks) + skill tests + shellcheck the sync script
	python3 scripts/validate_skills.py skills
	python3 -m unittest discover -s tests
	@if command -v shellcheck >/dev/null; then shellcheck scripts/sync-skills.sh scripts/require-merged-pr.sh; else echo "shellcheck not installed (brew install shellcheck); CI runs it"; fi

test: ## Skill script tests against recorded fixtures (stdlib unittest, no network)
	python3 -m unittest discover -s tests -v

test-live: ## Same, plus live API calls (keys from gitignored .env.local; never printed)
	SKILLS_LIVE=1 python3 -m unittest discover -s tests -v

skill-secrets: ## Push LTA_DATAMALL_KEY + DATA_GOV_SG_API_KEY from .env.local to Fly via stdin (restarts the machine)
	@test -f .env.local || { echo "no .env.local (see .env.local.example)"; exit 1; }
	@grep -Eq '^(LTA_DATAMALL_KEY|DATA_GOV_SG_API_KEY)=.+' .env.local || { echo "no skill keys set in .env.local"; exit 1; }
	@set -euo pipefail; grep -E '^(LTA_DATAMALL_KEY|DATA_GOV_SG_API_KEY)=.+' .env.local | $(FLY) secrets import -a $(APP)
	@$(FLY) secrets list -a $(APP) | grep -E 'LTA_DATAMALL_KEY|DATA_GOV_SG_API_KEY'

sync-skills: skills-check ## Manually publish skills/ at REF (default main; must be pushed) to the Fly machine
	@test -n "$(SKILLS_GIT)" || { echo "no git remote 'origin' (or pass SKILLS_GIT=git@github.com:<owner>/<repo>.git)"; exit 1; }
	@echo "publishing $(SKILLS_GIT) @ $(REF)"
	@set -euo pipefail; B64=$$( { printf 'REPO=%s\nREF=%s\n' "$(SKILLS_GIT)" "$(REF)"; cat scripts/sync-skills.sh; } | base64 | tr -d '\n'); \
	  $(FLY) ssh console -a $(APP) -C "/bin/sh -c \"echo $$B64 | /usr/bin/base64 -d | /bin/sh\""

snapshots: ## List volume snapshots
	@for v in $$($(FLY) volumes list -a $(APP) --json | python3 -c 'import json,sys;[print(v["id"]) for v in json.load(sys.stdin)]'); do \
	  echo "== $$v"; $(FLY) volumes snapshots list $$v; done

backup: ## Encrypted off-site backup to $(BACKUP_DIR) (needs AGE_RECIPIENT=age1...)
	@test -n "$(AGE_RECIPIENT)" || { echo "set AGE_RECIPIENT=age1..."; exit 1; }
	@command -v age >/dev/null || { echo "brew install age"; exit 1; }
	@mkdir -m 700 -p "$(BACKUP_DIR)"
	$(FLY) ssh console -a $(APP) -C "/bin/sh -c 'umask 077; /bin/tar czf /root/hermes-backup.tgz -C /opt/data --exclude=./installs --exclude=./.ssh --exclude=./.skills-stage.* .'"
	@cd "$(BACKUP_DIR)" && umask 077 && \
	  $(FLY) ssh sftp get /root/hermes-backup.tgz ./plain.tgz -a $(APP) && \
	  age -r "$(AGE_RECIPIENT)" -o "hermes-backup-$$(date +%F).tgz.age" plain.tgz && rm -P plain.tgz
	$(FLY) ssh console -a $(APP) -C "/bin/rm -f /root/hermes-backup.tgz"
	@echo "backup written to $(BACKUP_DIR)"
