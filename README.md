# hermes

Personal [Hermes Agent](https://hermes-agent.nousresearch.com/docs) deployment on Fly.io
(Telegram webhook + private dashboard, always on, Singapore region).

- **Design / runbook:** [docs/DESIGN.md](docs/DESIGN.md)

## Ground rules

- **No secrets in this repo.** Tokens, keys and passwords live in Fly secrets
  (`fly secrets set ...`) and a password manager only. `.gitignore` blocks the
  common offenders, but don't rely on it.
- **Pin the image tag** in `fly.toml`; never deploy `latest`.
- **Only 443 → 8443 is public.** Never add the dashboard (9119) or API server
  (8642) to `[[services]]`.
- Private skills live in a separate `hermes-skills` repo (see DESIGN §9).

## Layout

```
.
├── README.md
├── docs/
│   └── DESIGN.md      # architecture, setup, security checklist, troubleshooting
└── (fly.toml)         # add when deploying — see DESIGN §4
```
