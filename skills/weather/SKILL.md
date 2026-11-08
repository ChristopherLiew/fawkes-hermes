---
name: weather
description: "Forecasts: NEA for Singapore, Open-Meteo elsewhere."
version: 1.0.0
author: owner
license: MIT
platforms: [linux, macos]
required_environment_variables:
  - name: DATA_GOV_SG_API_KEY
    prompt: "data.gov.sg API key (optional)"
    help: "https://data.gov.sg (sign in, then API keys); without it the free tier applies"
    required_for: "Higher rate limits on NEA forecasts (optional)"
metadata:
  hermes:
    category: travel
    tags: [weather, forecast, rain, singapore, nea, open-meteo]
    related_skills: [itinerary, sg-bus, maps]
    requires_toolsets: [terminal]
---
# Weather

Official NEA forecasts for Singapore (data.gov.sg) and Open-Meteo forecasts for anywhere else, through one stdlib Python script. Neither source needs a key; `DATA_GOV_SG_API_KEY` only raises the rate limit.

## When to Use
- "Will it rain in Tampines this afternoon?", "weather now", "is it raining in the east?"
- "Weather in Kyoto next week?", "packing for Seoul on Friday", or forecasts for an itinerary
- Don't use for: historical weather, climate averages ("what's March like in Tokyo": use web search), or severe-weather warnings (point the user to the national met service).

## Commands
Run each through the `terminal` tool:
```bash
python3 ${HERMES_SKILL_DIR}/scripts/weather.py sg now --area Tampines
python3 ${HERMES_SKILL_DIR}/scripts/weather.py sg now
python3 ${HERMES_SKILL_DIR}/scripts/weather.py sg today
python3 ${HERMES_SKILL_DIR}/scripts/weather.py sg outlook
python3 ${HERMES_SKILL_DIR}/scripts/weather.py forecast "Kyoto" --days 3
python3 ${HERMES_SKILL_DIR}/scripts/weather.py forecast "35.02,135.75" --days 1 --hourly
```
Add `--json` before the subcommand to chain results.

Example output:
```
Tampines: Thundery Showers
(NEA 2-h forecast 14:00–16:00, issued 14:06)
```
```
Mostly cloudy; showers in Jurong West, Tuas
(NEA 2-h forecast 14:00–16:00, issued 14:06)
```
```
Kyoto, Japan (Asia/Tokyo)
  Mon 09 Nov  Light rain, 10–18°C, rain 24%
  Tue 10 Nov  Light rain, 8–15°C, rain 76%
  Wed 11 Nov  Mainly clear, 7–16°C, rain 0%
(Open-Meteo, local time)
```
Weather codes map to text as listed in `references/wmo-codes.md`.

## Procedure
1. **Route by place and horizon:**
   - In Singapore, next 2 hours or a named area → `sg now [--area <area>]`.
   - Singapore today/tonight → `sg today`. Singapore within 4 days → `sg outlook`.
   - Anywhere else, or Singapore beyond 4 days → `forecast <place> --days N` (max 7). Add `--hourly` for "this afternoon" or "at 3pm" questions.

   Done when exactly one command fits the question.
2. **Resolve the place.** If the user said "home" or "here", use their saved location from memory, or a lat,lon from a Telegram pin. A Singapore estate or town goes to `--area`; the script fuzzy-matches the 47 NEA area names. Done when the script echoes a place or area you expected. If the echo looks wrong (wrong country), retry with "City, Country" or lat,lon.
3. **Answer in one or two lines, then the source.** Always state the source and its time, e.g. "(NEA, issued 13:30)" or "(Open-Meteo)". Give the rain chance as a probability, never as certainty ("60% chance of rain", not "it will rain").
4. **Beyond 7 days:** say forecasts don't reach that far, and offer climate norms from web search instead, clearly labelled as averages.

## Pitfalls
- Singapore afternoon showers are very local. When the user names an area, give that area's line, not the islandwide "mostly" summary.
- NEA's 2-hour forecast covers only the current 2-hour window. For later today, use `sg today` (6-hour periods by region).
- Open-Meteo's rain % is the day's maximum hourly probability, not the chance of rain all day.
- Geocoding takes the first match: "Paris" could be Paris, Texas. Check the echoed country.
- A `429` means data.gov.sg rate limiting. Wait a minute, or the owner sets `DATA_GOV_SG_API_KEY`. Relay the script's one-line error; never make up a forecast.

## Verification
- `sg now --area Tampines` prints `Tampines: <forecast>` and an NEA validity window.
- `forecast "Kyoto" --days 3` prints "Kyoto, Japan" and exactly 3 day lines.
- Your reply names the source and issue time, and every figure in it came from script output in this turn.
