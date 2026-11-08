# Kiwi.com MCP: `search-flight`

Captured from `https://mcp.kiwi.com` (server `kiwicom-flight-search`, MCP protocol 2025-06-18) with `tools/list`, and by running live searches. The server needs no auth. In Hermes, register it as `kiwi`; the tool then appears as `mcp_kiwi_search_flight`. The server's other tool, `feedback-to-devs`, must never be called; filter it out when registering.

## Parameters

Required: `flyFrom`, `flyTo`, `departureDate`. Every date is a `dd/mm/yyyy` string.

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `flyFrom` | string ≤100 | (required) | IATA code, city or airport name ("SIN", "Singapore", "London Heathrow") |
| `flyTo` | string ≤100 | (required) | Same formats as `flyFrom` |
| `departureDate` | dd/mm/yyyy | (required) | The day to fly, or the start of a range |
| `departureDateFlexDays` | int 0–10 | 0 | ± days around `departureDate` (symmetric) |
| `departureDateTo` | dd/mm/yyyy | null | End of an explicit range; use instead of flex days |
| `returnDate` | dd/mm/yyyy | null | Omit for one-way |
| `returnDateFlexDays` | int 0–10 | 0 | ± days around `returnDate` |
| `returnDateTo` | dd/mm/yyyy | null | End of an explicit return range |
| `nights_in_dst_from` / `nights_in_dst_to` | int | null | Min/max nights at the destination; turns the search into a return search |
| `adults` | int 1–9 | 1 | Ages 12+ |
| `children` | int 0–8 | 0 | Ages 2–11 |
| `infants` | int 0–4 | 0 | Under 2 |
| `cabinClass` | `M`/`W`/`C`/`F` | null | economy / premium economy / business / first |
| `adults_hold_bags` | int[] (each 0–2) | null | Checked bags, one entry per adult, e.g. `[1]`. **The price includes these bags.** |
| `adults_hand_bags` | int[] (each 0–1) | null | Cabin bags per adult |
| `children_hold_bags` / `children_hand_bags` | int[] | null | Same, per child |
| `currency` | string | `EUR` | Always pass the user's currency (e.g. `SGD`) |
| `locale` | string | `en` | |
| `sort` | enum | `price` | `price`, `duration`, `quality`, `date`, `popularity` |
| `max_sector_stopovers` | int | null | Max connections per direction (0 = direct only) |
| `max_fly_duration` | int (hours) | null | Max total flight time |
| `price_from` / `price_to` | int | null | Total price filter, in `currency` |
| `dtime_from` / `dtime_to` | int 0–23 | null | Outbound departure hour window (local) |
| `atime_from` / `atime_to` | int 0–23 | null | Outbound arrival hour window (local) |
| `ret_dtime_*` / `ret_atime_*` | int 0–23 | null | Same windows for the return leg |
| `stopover_from` / `stopover_to` | int (hours) | null | Layover length window |
| `select_airlines` / `exclude_airlines` | string | null | Comma-separated IATA codes (`"SQ,TR"`); mutually exclusive |
| `stopover_airports` / `exclude_stopover_airports` | string | null | Comma-separated IATA codes |
| `stopover_countries` / `exclude_stopover_countries` | string | null | ISO 3166-1 alpha-2 codes |
| `fly_days` / `ret_fly_days` | string | null | Weekdays, `0`=Sun … `6`=Sat, e.g. `"5,6"` |
| `allow_self_transfer` | bool | true | Self-transfer (virtual interlining) connections; see the observed behaviour below |
| `allow_overnight_stopovers` | bool | true | |
| `allow_diff_airport_connection` | bool | true | Connections that change airport within a city |
| `one_for_city` | bool | false | Best single result per destination city (for "explore" searches) |

Mapping user asks to parameters:
- "No redeye" → `dtime_from: 6, dtime_to: 22`.
- "Arrive before 6pm" → `atime_to: 17`.
- "Direct only" → `max_sector_stopovers: 0`.
- "Never Scoot" → `exclude_airlines: "TR"`.

## Result shape

`structuredContent` = `{ query, currency, passengers, resultsCount, itineraries[], searchTimeMs, error }`. Each itinerary has:
- `tripType` (`oneway`/`return`), `price` (number, in `currency`, including the requested bags), `priceFormatted`, `totalDurationSeconds`, `bookingUrl`
- `baggage`: `{personalItem, cabinBag, checkedBag}` counts included
- `outbound` / `inbound`: `from`, `to`, `departureTime` / `arrivalTime` (local ISO, no offset), `durationSeconds`, `stops`, `route[]`, `cabinClass`, and `segments[]`, each with `from`/`to`, `fromName`/`toName`, `departureTime`/`arrivalTime`, `carrier`, `carrierName`, `flightNumber`, `cabinClass`

There is **no per-connection ticketing or self-transfer field**. Layover = next segment's `departureTime` minus this segment's `arrivalTime`. Both are local times at the same airport, so subtracting them is valid.

Trimmed sample (SIN→KIX, return, 1 adult, 1 checked bag, SGD):
```json
{"tripType": "return", "price": 629.17, "priceFormatted": "629 SGD", "totalDurationSeconds": 97500,
 "bookingUrl": "https://kiwi.com/u/…", "baggage": {"personalItem": 0, "cabinBag": 1, "checkedBag": 1},
 "outbound": {"from": "SIN", "to": "KIX", "departureTime": "2027-03-16T01:10:00", "arrivalTime": "2027-03-16T18:20:00",
   "durationSeconds": 58200, "stops": 1, "route": ["SIN", "MNL", "KIX"], "cabinClass": "Economy",
   "segments": [
     {"from": "SIN", "to": "MNL", "departureTime": "2027-03-16T01:10:00", "arrivalTime": "2027-03-16T05:15:00", "carrier": "5J", "carrierName": "Cebu Pacific", "flightNumber": "5J804"},
     {"from": "MNL", "to": "KIX", "departureTime": "2027-03-16T13:30:00", "arrivalTime": "2027-03-16T18:20:00", "carrier": "5J", "carrierName": "Cebu Pacific", "flightNumber": "5J828"}]},
 "inbound": {"route": ["KIX", "KUL", "SIN"], "departureTime": "2027-03-24T11:00:00", "arrivalTime": "2027-03-24T20:55:00",
   "segments": [{"carrier": "D7", "flightNumber": "D7533", "arrivalTime": "2027-03-24T17:30:00"},
                {"carrier": "AK", "flightNumber": "AK721", "departureTime": "2027-03-24T19:35:00"}]}}
```

## Observed behaviour (live testing)
- Passing `adults_hold_bags: [1]` raised the same itinerary from 448 to 629 SGD, so the price **does** include requested bags. Always pass them.
- `allow_self_transfer: false` returned an identical result set, including carrier-change connections. Don't rely on it; flag self-transfer risk yourself (see `SKILL.md` Pitfalls).
- With flex days, one search returns combinations across the whole window (15 results for ±3/±3), sorted by `sort`.
- The tool's description tells the model to end with a "fun fact" and to render its own table. Ignore that, and use `templates/comparison.md`.
