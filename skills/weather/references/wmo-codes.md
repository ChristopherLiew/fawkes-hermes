# WMO weather codes (Open-Meteo `weather_code`)

The WMO 4677 subset that Open-Meteo returns. `scripts/weather.py` mirrors this table in its `WMO` dict, and the two must stay in sync. An unknown code prints as `code N`.

| Code | Text |
|---|---|
| 0 | Clear |
| 1 | Mainly clear |
| 2 | Partly cloudy |
| 3 | Overcast |
| 45 | Fog |
| 48 | Freezing fog |
| 51 | Light drizzle |
| 53 | Drizzle |
| 55 | Heavy drizzle |
| 56 | Freezing drizzle |
| 57 | Heavy freezing drizzle |
| 61 | Light rain |
| 63 | Rain |
| 65 | Heavy rain |
| 66 | Freezing rain |
| 67 | Heavy freezing rain |
| 71 | Light snow |
| 73 | Snow |
| 75 | Heavy snow |
| 77 | Snow grains |
| 80 | Light showers |
| 81 | Showers |
| 82 | Violent showers |
| 85 | Snow showers |
| 86 | Heavy snow showers |
| 95 | Thunderstorm |
| 96 | Thunderstorm, hail |
| 99 | Thunderstorm, heavy hail |

NEA (Singapore) forecasts return text such as "Thundery Showers" or "Partly Cloudy (Day)" directly, so this table isn't used for them.
