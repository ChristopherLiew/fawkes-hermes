# Research shapes (Telegram first)

Write normal Markdown; the gateway converts `**bold**`, `*italic*`, `` `code` ``, links and `>` quote lines. No tables, `#` headings or `---`. One message stays under about 3,500 characters. Examples show layout only. Their facts are made up, so never reuse them. Cite inline with superscripts (`¹ ² ³`) that match the collapsed sources line, which is **one line** from `**> ` to `||` with no other `**` on it.

## 1. Research answer
```
🔎 **Yes: the JR Pass no longer pays off for Osaka–Kyoto–Uji.**

• **Price:** 7-day pass is ¥50,000 since the 2023 rise¹
• **Your trips:** ≈ ¥9,000 in single fares over 8 days²
• **Uji:** Keihan line, which the pass doesn't cover³
• **Better buy:** ICOCA top-ups; the Kansai one-day passes only win on 3+ rides

> 🎯 **Confidence:** high on prices, medium on your exact routing

**> 🔗 Sources: [¹ japanrailpass.net](https://example.com) · [² jorudan](https://example.com) · [³ keihan.co.jp](https://example.com)||
```
- Line 1 is the verdict, not the question restated. 3–5 findings, one line each, each with a citation.
- The confidence line says what's solid and what's a guess.

## 2. Compare options
```
🔎 **Pick the Sony WH-1000XM6** unless you need it to fold flat.

**Sony WH-1000XM6** · S$549¹
Best ANC tested · 30 h battery · folds
*Catch: heavier than the rest*

**Bose QC Ultra** · S$499²
Most comfortable · 24 h · folds
*Catch: weaker app*

**AirPods Max** · S$799³
Best with iPhone · 20 h
*Catch: no fold, priciest*

👉 **Sony** for travel, **Bose** for all-day comfort.
**> 🔗 Sources: [¹ rtings](https://example.com) · [² rtings](https://example.com) · [³ apple.com](https://example.com)||
```
- 2–4 options. Each block is a bold name with a price, then strengths joined by ` · `, then one italic catch.
- End with one 👉 pick line, never a table.

## 3. News or daily brief
```
📰 **Brief · Mon 9 Nov**

**AI**
• Anthropic shipped X, which does Y. [Reuters](https://example.com)
• Z raised $40M for agent tooling. [TechCrunch](https://example.com)

**Markets**
• No significant updates.
```
- Matches the `research-brief` template: a bold topic line (the gateway turns its `##` into bold), at most 5 one-sentence bullets per topic, and **exactly one link per bullet**. Brief bullets use inline links, not superscripts.
- A quiet topic gets "No significant updates". Never pad.

## 4. Deep dive (too long for one message)
```
🔎 **Summary: EV road tax rises in 2026; buying now saves ≈ S$1,200/yr.**

1. **Tax change:** what rises, and when¹
2. **Your car:** cost now vs. after 2026
3. **Options:** buy now, wait, or lease

> Full write-up is about 2,000 words.
Reply **1**, **2** or **3** for a section, or **all**.
**> 🔗 Sources: [¹ lta.gov.sg](https://example.com)||
```
- Send the summary and a numbered menu, then wait. Each section you send later is its own message, under 3,500 characters.
- In a cron run, nobody can reply. Send the summary plus the most important section instead.

## 5. Numbers or data snapshot
~~~
📊 **SGD→JPY is up 2.1% this month.**

```
Pair      Rate     1M
SGD/JPY   112.40   +2.1%
SGD/USD     0.77   -0.4%
SGD/EUR     0.71   +0.3%
```
*As of 9 Nov 14:00 SGT · [MAS](https://example.com)*
~~~
- Figures go in a fenced block with padded, right-aligned columns of 3–4 rows. Labels go outside the block.
- Always add an as-of time and the source. Never show a number without both.

## 6. Couldn't confirm, or sources disagree
```
⚠️ **I couldn't confirm Taihoan's tea ceremony hours.**

• **Official site:** no hours listed for 2026¹
• **Blogs:** say 10:00–16:00, but those posts are from 2023²

> 👉 Call ahead, or swap in Ito Kyuemon, which has confirmed hours³.

**> 🔗 Sources: [¹ city.uji.kyoto.jp](https://example.com) · [² blog](https://example.com) · [³ itohkyuemon.co.jp](https://example.com)||
```
- Line 1 says what's unconfirmed. Then list what each source says, with its date, and give one next step.
- Never average conflicting sources into a confident answer, and never fill a gap with a guess.
