# hermes

Personal [Hermes Agent](https://hermes-agent.nousresearch.com/docs) deployment on Fly.io
(Telegram webhook + private dashboard, always on, Singapore region).

- **Design / runbook:** [docs/DESIGN.md](docs/DESIGN.md)
- **Security review:** [docs/SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md)

## Setup (per clone)

```bash
pre-commit install          # gitleaks + private-key scan on every commit
pre-commit run --all-files
```

## Ground rules

- **No secrets in this repo.** Tokens, keys and passwords live in Fly secrets
  (`fly secrets set ...`) and a password manager only. `.gitignore` blocks the
  common offenders, but don't rely on it.
- **Pin the image tag** in `fly.toml`; never deploy `latest`.
- **Only 443 → 8443 is public.** Never add the dashboard (9119) or API server
  (8642) to `[[services]]`.
- Private skills live in a separate `hermes-skills` repo (see DESIGN §9).
- Secret **names** are listed in `.env.example`; values never go in git.
- Treat the agent as potentially hostile: root never executes anything under `/opt/data`.

## Layout

```
.
├── README.md
├── docs/
│   ├── DESIGN.md           # architecture, setup, security checklist, troubleshooting
│   └── SECURITY_REVIEW.md  # threat model, findings, implementation gate
├── .env.example            # secret names only
├── .gitleaks.toml          # custom secret rules
├── .pre-commit-config.yaml
└── (fly.toml)         # add when deploying — see DESIGN §4
```
