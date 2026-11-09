---
name: sg-bus
description: "Singapore bus arrivals, stops and MRT alerts (LTA)."
version: 1.2.0
author: owner
license: MIT
platforms: [linux, macos]
required_environment_variables:
  - name: LTA_DATAMALL_KEY
    prompt: "LTA DataMall AccountKey"
    help: "https://datamall.lta.gov.sg (Request for API Access)"
    required_for: "Live bus arrivals, stop lookup and train alerts"
metadata:
  hermes:
    category: travel
    tags: [singapore, bus, mrt, transit, lta, datamall]
    related_skills: [maps, weather, itinerary]
    requires_toolsets: [terminal]
---
# Singapore bus

Live bus arrivals, bus stop lookup and MRT disruption alerts from LTA DataMall, through one stdlib Python script. It never guesses times: if the API fails, it says so.

## When to Use
- "When's the next 10 at my stop?", "buses at 83139", "is the 155 coming?"
- "Which stops are near Bugis?", "bus stop at Victoria St", "buses near me", "what's coming near me", a Telegram location pin plus "bus"
- "Is the MRT down?", "any train delays?", a same-day itinerary leg in Singapore
- Don't use for: routes between two places (use `maps`), or anywhere outside Singapore.

## Commands
Run each through the `terminal` tool:
```bash
python3 ${HERMES_SKILL_DIR}/scripts/sg_bus.py arrivals 83139
python3 ${HERMES_SKILL_DIR}/scripts/sg_bus.py arrivals 83139 --service 155
python3 ${HERMES_SKILL_DIR}/scripts/sg_bus.py stops search "bugis stn"
python3 ${HERMES_SKILL_DIR}/scripts/sg_bus.py stops near 1.3006 103.8559 --radius 400
python3 ${HERMES_SKILL_DIR}/scripts/sg_bus.py nearby 1.3006 103.8559 --stops 3
python3 ${HERMES_SKILL_DIR}/scripts/sg_bus.py train-alerts
```
`nearby` lists the closest stops (default within 400 m) with live arrivals for each, in one call.
Add `--json` before the subcommand (`sg_bus.py --json arrivals 83139`) to chain results.

Example output:
```
Stop 01059 Bugis Stn Exit B · 14:02 SGT
  2    5 min (seats, DD) · 17 min (standing) · —
  12   Arr (seats) · 10 min (packed, DD) · 24 min (sched)
```
```
01059  Bugis Stn Exit B, Victoria St · 29 m
01113  Bugis Stn Exit A, Victoria St · 68 m
```
- `Arr`: arriving now. `—`: no further bus reported. `(sched)`: a timetable time, not a live one.
- Load: seats / standing / packed. `DD` double deck, `BD` bendy. `no WAB`: not wheelchair accessible.
- For field meanings and API limits, read `references/datamall-notes.md`.

## Procedure
1. **Start from a place.** Work through these in order:
   1. A location pin: the message reads `[The user shared a location pin.] latitude: … longitude: …` (a venue pin adds its name). Run `nearby <lat> <lon>` and go to step 3.
   2. A stop code in this message: use it as a 5-digit string, keeping leading zeros.
   3. A place name, road or landmark: `stops search <words>`; if that finds nothing, geocode it with the `maps` skill (`search`) and run `nearby <lat> <lon>`.
   4. "My stop", "home" or "office": use this user's saved stop from memory and echo it ("Home: 83139 Aft Joo Chiat Pl").
   5. "Near me" with no pin, or nothing above resolves: don't guess. Ask: "Share your location (📎 → Location), or give me a bus stop code, road or landmark."
   6. The script says no stops nearby or the place is outside Singapore, or the landmark can't be found: say sorry in one line, then ask the same question. Offer a wider radius (`--radius 800`) only when the pin looked right.

   Never invent a stop code. Done when you have one code, up to 3 nearby stops with arrivals, or up to 5 candidates for the user to pick from.
2. **Get the arrivals** with `arrivals <code>`. Add `--service <no>` when the user named a bus. Done when the script prints the stop header.
3. **Reply** with a bold header built from the script's stop line, then its service lines as-is in a fenced block (for `nearby`, one header and block per stop, nearest first, with its distance). The shape is "Bus arrivals" in the `telegram-format` skill. Mention `(sched)` times as estimates. If the list is empty, say no buses are running at that stop right now.
4. **MRT questions:** run `train-alerts`. Quote any affected lines, stations and free bus/shuttle info word for word.
5. **Remember (optional):** when the user names a personal anchor ("my home stop is 83139"), offer to save it to memory labelled with their name or handle, e.g. "Alex: home bus stop 83139". Several people can share this gateway's memory, so never save or reuse an unlabelled stop or another user's stop.

## Pitfalls
- A shared pin is the user's position: use it for this request only. Never save it to memory or repeat the coordinates unless the user asks. A stale pin (a forwarded or old live location) can be wrong; if the user says it's not where they are, ask for a fresh one.
- Stop codes are strings: `01012`, not `1012`. The script pads short numbers, but always show the 5-digit form.
- The arrival API returns nothing for services that aren't on the road. An empty result late at night (about 00:30–05:30) is normal, not an error.
- `(sched)` (Monitored = 0) means no GPS fix. That time comes from the timetable and can be off by several minutes.
- The first `stops` call downloads all ~5,200 stops (about 11 requests) and caches them for 7 days. Later calls are instant.
- On an error, relay the script's one-line message and give the stop code so the user can check another app. Never fill in times yourself.
- Stop names are short LTA labels ("Aft", "Opp", "Stn"). Expand them in prose if needed, but keep the code.

## Verification
- `arrivals 83139` prints a `Stop 83139 … SGT` header followed by service lines, or the "no buses" line.
- `stops near 1.3006 103.8559` lists Bugis stops, each with a distance in metres.
- `nearby 1.3006 103.8559` prints a `Stop … (N m) … SGT` block per nearby stop. Coordinates outside Singapore give a one-line error, and you ask for a stop or landmark.
- Every time in your reply came from script output in this turn, and the stop code is shown.
