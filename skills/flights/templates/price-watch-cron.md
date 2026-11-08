# Price watch (cron)

Cron runs start a fresh session with no chat history, and they may not see the user's memory. So the prompt must spell out **every** personal parameter. Hermes suppresses delivery when the reply is exactly `[SILENT]`. Cron also gives each run the job's most recent non-silent output, which is how "dropped since the last run" is judged.

Fill in the braces and send this as one message:

```
/cron add "every day at 9am" "Load the flights skill. Search {ORIGIN}→{DEST} departing {dd/mm/yyyy} ±{N} days, returning {dd/mm/yyyy} ±{N} days, {adults} adult(s), cabin {economy|business}, {bags} checked bag(s), currency {ccy}. Only message me if the best-value total is below {ccy} {threshold}, or is more than 10% lower than the previous run's best-value total; otherwise reply with exactly [SILENT]. When you do message, include the comparison table, the 'checked …; fares change' line and links. Never book." --skill flights
```

- One route per job. List jobs with `/cron list`, and remove one with `/cron remove <id>`.
- If the Kiwi tool isn't connected, the run should say so once rather than reply `[SILENT]`.
- A run that fails outright posts a failure notice to the job's delivery target. That's separate from `[SILENT]`.
