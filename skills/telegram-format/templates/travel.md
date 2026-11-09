# Telegram travel shapes

Shapes for replies about transport and travel on the go. They follow the conventions in [cases.md](cases.md):
- **Bold** names, with times and codes in inline code.
- One leading emoji per row, and ` · ` between facts.
- Asides go in a `>` quote, and sources in a single-line `**> …||` collapsed quote.
- No tables, `#` headings or `---` rules.

Examples show layout only. Their facts are made up, so never reuse them.
Where an example holds a code block, the outer `~~~` fence only marks where the example starts and ends. Don't send it.

## 1. Bus arrivals (sg-bus)
~~~
🚌 **Bugis Stn Exit B** · `01059` · 14:02
```
2    5 min (seats, DD) · 17 min (standing)
12   Arr (seats) · 10 min (packed, DD) · 24 min (sched)
```
> (sched) = timetable estimate, no live GPS
~~~
- Build the bold header from the script's first line (stop name, code, time). Put its service lines in a fenced block, verbatim, so the columns stay aligned. Never retype or round the times.
- Add the quote line only when a `(sched)` time appears.

**Near me / location pin:** one header per stop, nearest first, with its distance and its own fenced block. At most 3 stops.
~~~
📍 **3 stops near you**

🚌 **Bugis Stn Exit B** · `01059` · 29 m
```
2    5 min (seats, DD) · 17 min (standing)
```

🚌 **Bugis Stn Exit A** · `01113` · 68 m
```
7    3 min (seats) · 11 min (seats)
```
~~~

## 2. MRT / train alerts
```
✅ **MRT running normally** · 08:15
```
```
⚠️ **EWL disrupted** · Tanah Merah ↔ Pasir Ris
Towards Pasir Ris · since 07:40
> 🚌 **Free bus:** Tanah Merah, Simei, Tampines, Pasir Ris
> 🚐 **Shuttle:** Tanah Merah ↔ Pasir Ris every 5 min
Add 25–30 min. Next update when LTA posts one.
```
- The status is the first line. Quote affected stations and free bus/shuttle info word for word from `train-alerts`.
- "All clear" is one line. Don't send an empty template.

## 3. Getting from A to B
```
👉 **Take the MRT** · 24 min · S$1.79
**Bugis → Botanic Gardens**

🚇 **MRT** · 24 min · S$1.79 · no transfer
Downtown Line, Bugis → Botanic Gardens, 5 stops
↓ *🚶 4 min to the gate*

🚌 **Bus 7** · 32 min · S$1.69 · no transfer
Stop `01059` → `40189`

🚕 **Taxi / Grab** · 15 min · ≈S$14–18
Surge likely 17:30–19:30

> 🚶 Walking is 55 min. Not in this heat.

**> 🔗 Sources: [¹ maps](https://example.com) · † fares unverified||
```
- The pick and its headline numbers come first. Each option gets 2 lines: `mode emoji **mode** · time · cost · transfers`, then one line of detail.
- 2–3 options maximum. A transit time from the web is `≈` and cites a source. `maps` only routes driving, walking and cycling.

## 4. Nearby places (from a pin)
```
📍 **Cafés near you** · within 500 m

1. ☕ **Chye Seng Huat Hardware** · 120 m · open till 22:00 · [Map](https://example.com)
2. ☕ **Apartment Coffee** · 260 m · specialty pour-over · [Map](https://example.com)
3. ☕ **Tiong Hoe Specialty** · 410 m · hours unknown† · [Map](https://example.com)

> OSM data: check hours before you go. † unverified
```
- Number the list, nearest first, up to 5 places. Each row is name · distance · one useful fact · a `[Map](maps_url)` link.
- Never show raw coordinates. If `hours` is missing, say "hours unknown" rather than guessing.

## 5. Weather
**Now / today:**
```
🌧 **Tampines: thundery showers** till 16:00
Take an umbrella; it eases by evening.

> NEA 2-h forecast, issued 14:06
```
**Multi-day outlook:** a bold header, then the days in a fenced block so the columns align.
~~~
⛅ **Kyoto · next 3 days**
```
Mon 09 Nov  10–18°C  rain 24%  light rain
Tue 10 Nov   8–15°C  rain 76%  light rain
Wed 11 Nov   7–16°C  rain  0%  clear
```
> Open-Meteo, local time. Tue is the wet one; plan indoors.
~~~
- The first line answers the question: the verdict for the place and time asked. Give rain as a percentage, never a certainty.
- Always end with the source and its issue time.

## 6. Flight recap (status or trip summary; never a booking)
```
✈️ **SQ 618 · SIN → KIX** · Wed 28 Jan
`08:55` T3 → `16:20` T1 · 6 h 25 · on time

🧳 Check-in opens `05:55` · bag drop closes `07:55`
🔗 [Check in](https://example.com) · [Flight status](https://example.com)
> Status as of 06:10 SGT. Check the airline app before you leave.
```
- Line 1: flight · route · date. Line 2: times in inline code, terminals, duration and status.
- Status is a snapshot: always give its time. Never say anything is booked or checked in.
