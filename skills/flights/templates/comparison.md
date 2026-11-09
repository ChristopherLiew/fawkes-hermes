# Flight comparison layout (Telegram first)

Write normal Markdown. The Telegram gateway converts `**bold**`, `*italic*`, `` `code` ``, links and `>` quote lines, but not tables. One message, under about 1,800 characters.

```
✈️ **{ORIGIN} → {DEST}** · {dates} · {pax}, {cabin}
*Checked {date} {time} {tz} · fares change · assumed {defaults, e.g. 1 checked bag}*

🏷 **{ccy} {total}** · cheapest sensible
{carriers} · `{dep}` → `{arr}`{+1} · {h m} · {n} stop ({layover city} {h m})
{bags · self-transfer? · redeye?} · [Book]({bookingUrl})

⭐ **{ccy} {total}** · best value
{carriers} · `{dep}` → `{arr}` · {h m} · nonstop
{notes} · [Book]({bookingUrl})

⚡ **{ccy} {total}** · fastest
{carriers} · `{dep}` → `{arr}` · {h m} · nonstop
{notes} · [Book]({bookingUrl})

👉 **Pick {⭐}:** {one-line reason}
> 📅 **Cheaper dates:** {±N-day finds, or "none cheaper in the window"}
> 🔎 Cheapest found on Kiwi, cross-checked with {source}. Nothing has been booked.
```

## Rules
- One block per option: line 1 is the price + label, line 2 is the schedule, line 3 is the catches + link. Put a blank line between options.
- Labels: 🏷 cheapest sensible · ⭐ best value · ⚡ fastest · 🛋 most comfortable (only if comfort matters). At most 4 options.
- Times are local, in inline code. `+1` marks next-day arrival.
- For a return trip, give line 2 twice: `Out` then `Back`.
- No tables, no `#` headings, no bare URLs.
