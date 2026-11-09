# Telegram message shapes

Copy the shape that fits. Delete sections that have nothing in them.

## 1. Quick answer (1–3 sentences)
Plain text. No bullets, no bold unless there is one key value.

> Yes, the deploy finished. The machine is on **v0.23.0** and healthy.

## 2. Digest or brief (news, cron summaries)
```
📰 **Morning brief** · 9 Nov

**AI**
• One-sentence item. [Source](url)
• One-sentence item. [Source](url)

**Markets**
• No significant updates.
```
Max about 5 bullets per section. One link per bullet.

## 3. Comparison (replaces a table)
```
**Option A** · cheaper
• Cost: $12/mo
• Catch: slower cold start

**Option B** · faster
• Cost: $20/mo
• Catch: more setup

👉 **Pick B** if latency matters, otherwise A.
```
For three or more numeric columns, use a fenced block:
````
```
Region  Latency  Cost
sin     12 ms    $12
nrt     68 ms    $12
```
````

## 4. Status or alert
```
⚠️ **Disk at 91%** on `fawkes-hermes`
Since: 14:05 SGT
Likely cause: `/opt/data/sessions` growth
Next step: prune old sessions, or tell me to.
```
Status icons: ✅ ok · ⚠️ needs attention · ❌ failed · ⏳ in progress.

## 5. How-to steps
```
**Rotate the webhook secret**
1. Generate a new value.
2. Set it with `fly secrets set`.
3. Check `getWebhookInfo` for errors.

⚠️ The bot is silent until step 2 finishes.
```
One action per step. Commands in inline code.

## 6. Code or command
Say what it does in one line, then one fenced block, then one line on how to confirm it worked. Name the language after the opening fence.

## 7. Failure report
```
❌ **Could not fetch the report**
What happened: the site returned 403.
What I tried: two retries, one alternate source.
What I need: a different source, or skip it?
```
State the failure first. Never bury it under what went well.

## 8. Long result
```
**Summary**: three findings, one needs action.

1. **Key finding.** One sentence.
2. **Second finding.** One sentence.
3. **Third finding.** One sentence.

Full detail is about 2,000 words. Want it, or a specific section?
```

## 9. Confirmation before a risky action
```
❓ **Delete 14 old sessions?**
Frees about 300 MB. Not reversible.

Reply **yes** to proceed.
```

## 10. Schedule or plan (a day, an agenda)
```
**📍 Sat 14 Nov · Joo Chiat**
⛅ 31° / 26° · rain 40% after 3pm

`09:30` ☕ **Chin Mee Chin** · kaya toast · 45 min
↓ *🚶 8 min*
`10:30` 📸 **Koon Seng Road** · Peranakan houses · free
`12:00` 🍜 **Lunch** · laksa, ~S$8

> ☔ **Rain:** Koon Seng → Peranakan Museum
> 💴 **Cost:** ≈ S$40

**> 🔗 Sources: [¹ site](https://example.com)||
```
Times in inline code, one emoji and a bold name per row, legs on `↓` lines, extras in a quote, sources collapsed.
