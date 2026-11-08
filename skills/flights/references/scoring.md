# Scoring rubric and defaults (flights)

## Generic defaults
Use these only when neither the message nor this user's memory says otherwise, and always state them as assumptions.
- Origin: **ask**. Never assume an airport.
- Cabin: economy (`M`). Passengers: 1 adult. Bags: 1 checked bag (`adults_hold_bags: [1]`) and 1 cabin bag.
- Currency: SGD. This is the instance's base currency; change it here for a deployment elsewhere.
- No airline or loyalty preferences.

## Normalise each option
| Field | How |
|---|---|
| Total cost | Kiwi `price` (it includes the bags passed in the search), plus known seat fees, in the user's currency. If bags weren't passed or priced, write "bags not included". |
| Total time | `outbound.durationSeconds` (and `inbound`), shown as `Xh Ym` |
| Stops / longest layover | `stops`; layover = next segment departure − segment arrival (same airport, local times) |
| Overnight layover | the layover crosses 00:00–05:00 local |
| Redeye | departure 23:00–05:00 local |
| Late arrival | arrival 23:00–05:00 local (00:55 the next day counts), or a conflict with hotel check-in or the itinerary's first fixed time |
| Possible self-transfer | the carrier changes between consecutive segments, or the arrival and next departure airports differ. List it only if the layover is ≥ 3 h. |
| Carrier type | full-service vs low-cost (bags/meals included or not) |

## Rubric (lower score = better)
Score = **total cost in SGD**, plus these penalties (convert roughly for another currency):

| Condition | Penalty |
|---|---|
| Each hour of travel time over the fastest option | +S$40 |
| Each extra stop | +S$80 |
| Redeye departure | +S$120 |
| Late arrival (23:00–05:00) | +S$100 |
| Possible self-transfer | +S$150 |
| Low-cost carrier with no included checked bag when the user needs one | +S$60 |

- Adjust for explicit preferences in this user's memory. For example, "hates redeyes" doubles the redeye penalty, and "only cares about price" halves the time penalty.
- Show the penalty breakdown only on request.
- The weights are tunable preferences, not facts. Say so if the user questions a ranking.

## Picks
- 🏷 **Cheapest sensible**: the lowest total that isn't a self-transfer with a layover under 3 h.
- ⭐ **Best value**: the lowest score.
- ⚡ **Fastest**: the lowest total travel time.
- 🛋 **Most comfortable**: full-service, sensible times, fewest stops. Include it only when the user cares about comfort.

When one option wins several picks, show it once with all its badges, and fill the table from the next-best options.
