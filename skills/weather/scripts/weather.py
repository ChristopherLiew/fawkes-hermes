#!/usr/bin/env python3
"""Weather: NEA forecasts for Singapore (data.gov.sg), Open-Meteo for anywhere else. Standard library only.

  weather.py sg now [--area <name>]       NEA 2-hour forecast, per area
  weather.py sg today                     NEA 24-hour forecast, by region
  weather.py sg outlook                   NEA 4-day outlook
  weather.py forecast <place | lat,lon> [--days 1-7] [--hourly]
Add --json for structured output. DATA_GOV_SG_API_KEY is optional (higher rate limits); never printed.
WMO code table: references/wmo-codes.md
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

NEA = "https://api-open.data.gov.sg/v2/real-time/api"
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
UA = "fawkes-hermes-skills/1.0"

# Mirrors references/wmo-codes.md (WMO 4677 subset used by Open-Meteo).
WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Heavy freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Violent showers", 85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm, hail", 99: "Thunderstorm, heavy hail",
}


class ApiError(Exception):
    """One actionable line for stderr."""


def http_json(url: str, headers: dict[str, str] | None = None, source: str = "data.gov.sg") -> dict:
    """GET JSON: 10 s timeout, one retry on 5xx or timeout."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                hint = "; set DATA_GOV_SG_API_KEY for higher limits" if source == "data.gov.sg" else "; retry in a minute"
                raise ApiError(f"rate limited by {source}{hint}") from None
            if e.code in (401, 403) and source == "data.gov.sg":
                raise ApiError("DATA_GOV_SG_API_KEY invalid (fix the Fly secret, or unset it to use the free tier)") from None
            if e.code < 500 or attempt == 2:
                raise ApiError(f"{source} returned HTTP {e.code}; try again shortly") from None
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise ApiError(f"{source} unreachable (timeout); try again shortly") from None
        time.sleep(1)
    raise AssertionError("unreachable")


def nea(endpoint: str) -> dict:
    key = os.environ.get("DATA_GOV_SG_API_KEY", "").strip()
    data = http_json(f"{NEA}/{endpoint}", {"x-api-key": key} if key else {})
    if data.get("code") not in (0, None):
        raise ApiError(f"data.gov.sg error: {data.get('errorMsg') or data.get('code')}")
    return data.get("data") or {}


def hhmm(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%H:%M") if iso else "?"


# ---------------------------------------------------------------- NEA 2-hour

def parse_two_hr(data: dict) -> dict:
    item = (data.get("items") or [{}])[-1]
    vp = item.get("valid_period") or {}
    return {
        "issued": item.get("update_timestamp") or item.get("timestamp", ""),
        "valid_from": vp.get("start", ""),
        "valid_to": vp.get("end", ""),
        "forecasts": {f["area"]: f["forecast"] for f in item.get("forecasts", [])},
    }


def match_area(query: str, areas: list[str]) -> str | None:
    q = query.strip().lower()
    by_lower = {a.lower(): a for a in areas}
    if q in by_lower:
        return by_lower[q]
    partial = [a for a in areas if q in a.lower()]
    if len(partial) == 1:
        return partial[0]
    if partial:  # ambiguous ("jurong"): never guess which one
        return None
    close = difflib.get_close_matches(q, list(by_lower), n=1, cutoff=0.6)
    return by_lower[close[0]] if close else None


def format_two_hr(p: dict, area: str | None = None) -> str:
    stamp = f"NEA 2-h forecast {hhmm(p['valid_from'])}–{hhmm(p['valid_to'])}, issued {hhmm(p['issued'])}"
    if area:
        return f"{area}: {p['forecasts'][area]}\n({stamp})"
    counts: dict[str, list[str]] = {}
    for a, f in p["forecasts"].items():
        counts.setdefault(f, []).append(a)
    if not counts:
        return f"No areas in the NEA response ({stamp})"
    main = max(counts, key=lambda f: len(counts[f]))
    parts = [f"Mostly {main.lower()}"]
    for f, areas in sorted(counts.items(), key=lambda kv: -len(kv[1])):
        if f != main:
            shown = ", ".join(areas[:6]) + (f" +{len(areas) - 6} more" if len(areas) > 6 else "")
            parts.append(f"{f.lower()} in {shown}")
    return "; ".join(parts) + f"\n({stamp})"


# ---------------------------------------------------------------- NEA 24-hour + 4-day

def parse_today(data: dict) -> dict:
    rec = (data.get("records") or [{}])[0]
    g = rec.get("general") or {}
    return {
        "issued": rec.get("updatedTimestamp") or rec.get("timestamp", ""),
        "valid": (g.get("validPeriod") or {}).get("text", ""),
        "forecast": (g.get("forecast") or {}).get("text", ""),
        "low": (g.get("temperature") or {}).get("low"),
        "high": (g.get("temperature") or {}).get("high"),
        "periods": [
            {"period": (pd.get("timePeriod") or {}).get("text", ""),
             "regions": {r: v.get("text", "") for r, v in (pd.get("regions") or {}).items()}}
            for pd in rec.get("periods", [])
        ],
    }


def format_today(t: dict) -> str:
    lines = [f"{t['forecast']}, {t['low']}–{t['high']}°C ({t['valid']})"]
    for pd in t["periods"]:
        texts = set(pd["regions"].values())
        if len(texts) == 1:
            lines.append(f"  {pd['period']}: {texts.pop()} islandwide")
        else:
            lines.append(f"  {pd['period']}: " + ", ".join(f"{r} {v}" for r, v in pd["regions"].items()))
    lines.append(f"(NEA 24-h forecast, issued {hhmm(t['issued'])})")
    return "\n".join(lines)


def parse_outlook(data: dict) -> dict:
    rec = (data.get("records") or [{}])[0]
    return {
        "issued": rec.get("updatedTimestamp") or rec.get("timestamp", ""),
        "days": [
            {"date": f.get("timestamp", "")[:10], "day": f.get("day", ""),
             "forecast": (f.get("forecast") or {}).get("summary") or (f.get("forecast") or {}).get("text", ""),
             "low": (f.get("temperature") or {}).get("low"), "high": (f.get("temperature") or {}).get("high")}
            for f in rec.get("forecasts", [])
        ],
    }


def format_outlook(o: dict) -> str:
    lines = [f"{d['day'][:3]} {d['date'][5:]}  {d['low']}–{d['high']}°C  {d['forecast']}" for d in o["days"]]
    return "\n".join(lines + [f"(NEA 4-day outlook, issued {hhmm(o['issued'])})"])


# ---------------------------------------------------------------- Open-Meteo

def resolve_place(place: str) -> dict:
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", place)
    if m:
        return {"name": f"{float(m.group(1)):.4f},{float(m.group(2)):.4f}", "country": "",
                "latitude": float(m.group(1)), "longitude": float(m.group(2))}
    q = urllib.parse.urlencode({"name": place, "count": 1, "language": "en", "format": "json"})
    hits = http_json(f"{GEOCODE}?{q}", source="Open-Meteo").get("results") or []
    if not hits:
        raise ApiError(f'no place matches "{place}"; try "City, Country" or lat,lon')
    return hits[0]


def parse_forecast(place: dict, data: dict) -> dict:
    d = data.get("daily") or {}
    days = [
        {"date": t, "weather": WMO.get(code, f"code {code}"),
         "min": d["temperature_2m_min"][i], "max": d["temperature_2m_max"][i],
         "rain_pct": d["precipitation_probability_max"][i]}
        for i, (t, code) in enumerate(zip(d.get("time", []), d.get("weather_code", [])))
    ]
    h = data.get("hourly") or {}
    hours = [
        {"time": t, "temp": h["temperature_2m"][i], "rain_pct": h["precipitation_probability"][i],
         "weather": WMO.get(h["weather_code"][i], "")}
        for i, t in enumerate(h.get("time", []))
    ]
    label = ", ".join(dict.fromkeys(x for x in (place.get("name"), place.get("admin1"), place.get("country")) if x))
    return {"place": label, "timezone": data.get("timezone", ""), "days": days, "hours": hours}


def format_forecast(f: dict) -> str:
    lines = [f"{f['place']} ({f['timezone']})"]
    for d in f["days"]:
        day = datetime.fromisoformat(d["date"]).strftime("%a %d %b")
        rain = "?" if d["rain_pct"] is None else f"{d['rain_pct']}%"
        lines.append(f"  {day}  {d['weather']}, {d['min']:.0f}–{d['max']:.0f}°C, rain {rain}")
    if f["hours"]:
        lines.append("  Next 24 h (3-hourly):")
        for hr in f["hours"][:24:3]:
            temp = "?" if hr["temp"] is None else f"{hr['temp']:.0f}"
            rain = "?" if hr["rain_pct"] is None else f"{hr['rain_pct']}%"
            lines.append(f"    {hr['time'][11:16]}  {temp}°C  rain {rain}  {hr['weather']}")
    lines.append("(Open-Meteo, local time)")
    return "\n".join(lines)


def open_meteo(place: dict, days: int, hourly: bool) -> dict:
    params = {
        "latitude": place["latitude"], "longitude": place["longitude"], "timezone": "auto", "forecast_days": days,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    }
    if hourly:
        params["hourly"] = "temperature_2m,precipitation_probability,weather_code"
        params["forecast_hours"] = 24  # starts at the current local hour
    return http_json(f"{FORECAST}?{urllib.parse.urlencode(params)}", source="Open-Meteo")


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="weather.py", description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true", help="structured JSON output")
    sub = p.add_subparsers(dest="cmd", required=True)
    sg = sub.add_parser("sg").add_subparsers(dest="sg_cmd", required=True)
    now = sg.add_parser("now")
    now.add_argument("--area")
    sg.add_parser("today")
    sg.add_parser("outlook")
    fc = sub.add_parser("forecast")
    fc.add_argument("place", nargs="+")
    fc.add_argument("--days", type=int, default=3, choices=range(1, 8), metavar="1-7")
    fc.add_argument("--hourly", action="store_true")
    args = p.parse_args(argv)

    try:
        if args.cmd == "sg" and args.sg_cmd == "now":
            parsed = parse_two_hr(nea("two-hr-forecast"))
            area = None
            if args.area:
                area = match_area(args.area, list(parsed["forecasts"]))
                if not area:
                    q = args.area.strip().lower()
                    options = [a for a in parsed["forecasts"] if q in a.lower()] or sorted(parsed["forecasts"])
                    raise ApiError(f'no single NEA area matches "{args.area}"; pick one of: ' + ", ".join(options))
            out = ({**parsed, "area": area} if args.json else format_two_hr(parsed, area))
        elif args.cmd == "sg" and args.sg_cmd == "today":
            parsed = parse_today(nea("twenty-four-hr-forecast"))
            out = parsed if args.json else format_today(parsed)
        elif args.cmd == "sg":
            parsed = parse_outlook(nea("four-day-outlook"))
            out = parsed if args.json else format_outlook(parsed)
        else:
            place = resolve_place(" ".join(args.place))
            parsed = parse_forecast(place, open_meteo(place, args.days, args.hourly))
            out = parsed if args.json else format_forecast(parsed)
    except ApiError as e:
        print(e, file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=1) if args.json else out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
