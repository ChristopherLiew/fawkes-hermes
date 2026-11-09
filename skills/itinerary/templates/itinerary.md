# Itinerary layout (Telegram first)

Write normal Markdown. The Telegram gateway converts it: `**bold**`, `*italic*`, `` `code` ``, `[label](url)` and `>` quote lines render; tables do not. Send the overview first, then **one message per day**. Each message stays under about 1,800 characters.

## Message 1: trip overview

```
✈️ **{Trip title}** · {N} days
{Mon 26 Jan} → {Mon 2 Feb} · base {area} · {relaxed|normal|packed} pace

**At a glance**
`D1` {Mon 26} · {theme, e.g. Arrival + Dotonbori}
`D2` {Tue 27} · {theme}
`D3` {Wed 28} · {theme}

{weather emoji} {high}° / {low}° · rain {x}% · sunset {hh:mm}
🎟 **Book ahead:** {timed tickets, restaurants, or "nothing"}
*Assumed: {defaults used, e.g. mid budget, SGD}*
```

## Messages 2…n: one day each

```
**📍 Day {n} · {Wed 28 Jan} · {area or theme}**
{weather emoji} {high}° / {low}° · rain {x}% · sunset {hh:mm}

`10:00` 🚆 **{From} → {To}** · {line} · ≈{mins} min
`11:15` ⛩ **{Stop}** · {price}¹ · {duration}
{one short reason or tip, only if it earns its line}
↓ *🚶 {mins} min*
`12:30` 🍵 **{Lunch spot}** · {dish, price band}²
↓ *🚕 {mins} min · ≈{fare}*
`14:00` 🌳 **{Stop}** · free · {duration}
`17:00` 🚆 **Back to {base}** · ≈{mins} min

> ☔ **Rain:** {outdoor stop} → {indoor alternative}
> 🔁 **If closed:** {stop} → {fallback}
> 💴 **Cost:** {local amount} (≈ {home ccy} {amount})
> 🎟 **Book:** {what to reserve, or "nothing"}

**> 🔗 Sources: [¹ {site}]({url}) · [² {site}]({url}) · † unverified||
```

## Rules
- One row per stop: `` `HH:MM` `` + one type emoji + **name** + up to three ` · ` facts. A second line is optional and is plain text, one sentence.
- Legs go on their own line: `↓ *{mode emoji} {mins} min*`. Transit is `≈` and cites a source, or "check a transit app".
- Type emoji, one per row and never mid-sentence: 🚆 train · 🚌 bus · 🚶 walk · 🚕 taxi · ✈️ flight · 🏨 hotel · ⛩ temple/shrine · 🏯 castle · 🏛 museum · 🌳 park/nature · 📸 viewpoint · 🛍 shopping · 🍜 meal · ☕ café · 🍡 sweets · 🍻 drinks.
- Weather emoji: ☀️ clear · 🌤 mostly sunny · ⛅ cloudy · 🌧 rain ≥50% · ⛈ storms.
- Prices and opening hours carry a superscript source (`¹ ² ³`) or `†` for unverified. The sources line explains both.
- The sources line must be **one line** that starts with `**>` and ends with `||`. That's what makes it a collapsed quote. Put no other `**` on that line.
- At most 12 stop rows per day. For a longer day, send Morning and Afternoon as two messages with the same header.
- No `#` headings, no tables, no `---` rules, no nested bullets.
