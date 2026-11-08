# LTA DataMall notes (sg-bus)

Source: LTA DataMall API User Guide v6.11 (30 Oct 2026), §2.1 Bus Arrival, §2.4 Bus Stops, §2.11 Train Service Alerts. Every call sends the header `AccountKey: $LTA_DATAMALL_KEY`, plus `accept: application/json`.

## Endpoints used

| Command | Endpoint | Notes |
|---|---|---|
| `arrivals` | `GET /ltaodataservice/v3/BusArrival?BusStopCode=&ServiceNo=` | Updated every 20 s. `ServiceNo` is optional. |
| `stops` | `GET /ltaodataservice/BusStops?$skip=N` | 500 records per page; keep requesting until a page comes back empty. Updated ad hoc. |
| `train-alerts` | `GET /ltaodataservice/TrainServiceAlerts` | Updated ad hoc. |

## Bus arrival fields (per `NextBus`, `NextBus2`, `NextBus3`)

| Field | Meaning | Script output |
|---|---|---|
| `EstimatedArrival` | ISO time, +08:00. Empty when no further bus is known. | minutes from now, rounded down; `Arr` at 0; `—` when empty |
| `Monitored` | `1` = estimated from bus location; `0` = from the timetable | `(sched)` when 0 |
| `Load` | `SEA` seats available, `SDA` standing available, `LSD` limited standing | seats / standing / packed |
| `Type` | `SD` single deck, `DD` double deck, `BD` bendy | shown only for DD and BD |
| `Feature` | `WAB` = wheelchair accessible; blank = not | `no WAB` when blank |
| `Latitude`/`Longitude` | Current bus position. `0.0` when unmonitored. | not shown |
| `VisitNumber` | 1st or 2nd visit of this bus at the stop (loop services) | not shown |

When a service has no buses on the road, it's missing from `Services` entirely. During maintenance the whole response can be empty.

## Bus stop fields
`BusStopCode` (5-digit string), `RoadName`, `Description` (nearby landmark), `Latitude`, `Longitude`.

## Train service alert fields
- `Status`: `1` = normal service or minor delays; `2` = disrupted service or major delays.
- `AffectedSegments[]`: `Line` (EWL, NSL, NEL, CCL, DTL, TEL, BPL, STL, PTL), `Direction` (`Both` or towards a station), `Stations` (codes), `FreePublicBus`, `FreeMRTShuttle`, `MRTShuttleDirection`.
- `Message[]`: `Content` (LTA's advisory text) and `CreatedDate`.

A normal response looks like `{"value": {"Status": 1, "AffectedSegments": [], "Message": []}}`.
