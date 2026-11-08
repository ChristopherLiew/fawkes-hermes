#!/usr/bin/env python3
"""Singapore bus arrivals, stop lookup and MRT alerts from LTA DataMall. Standard library only.

  sg_bus.py arrivals <stop_code> [--service <no>]
  sg_bus.py stops search <query> [--limit 5]
  sg_bus.py stops near <lat> <lon> [--radius 400] [--limit 5]
  sg_bus.py nearby <lat> <lon> [--radius 400] [--stops 3] [--service <no>]
  sg_bus.py train-alerts
Add --json for structured output. Needs LTA_DATAMALL_KEY. Never prints the key.
Field meanings: references/datamall-notes.md
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://datamall2.mytransport.sg/ltaodataservice"
SGT = timezone(timedelta(hours=8), "SGT")
UA = "fawkes-hermes-skills/1.0"
STOPS_TTL = 7 * 24 * 3600
LOAD = {"SEA": "seats", "SDA": "standing", "LSD": "packed"}


class ApiError(Exception):
    """One actionable line for stderr."""


# ---------------------------------------------------------------- HTTP + cache

def http_json(url: str, headers: dict[str, str]) -> dict:
    """GET JSON: 10 s timeout, one retry on 5xx or timeout."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **headers})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 401 or e.code == 403:
                raise ApiError("LTA_DATAMALL_KEY missing or invalid (set it as a Fly secret)") from None
            if e.code == 429:
                raise ApiError("rate limited by LTA DataMall; wait a minute and retry") from None
            if e.code < 500 or attempt == 2:
                raise ApiError(f"LTA DataMall returned HTTP {e.code}; try again shortly") from None
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise ApiError("LTA DataMall unreachable (timeout); try again shortly") from None
        time.sleep(1)
    raise AssertionError("unreachable")


def lta(path: str, **params: str) -> dict:
    key = os.environ.get("LTA_DATAMALL_KEY", "").strip()
    if not key:
        raise ApiError("LTA_DATAMALL_KEY missing or invalid (set it as a Fly secret)")
    query = ("?" + urllib.parse.urlencode(params, safe="$")) if params else ""
    return http_json(f"{BASE}/{path}{query}", {"AccountKey": key, "accept": "application/json"})


def cache_dir() -> Path:
    root = os.environ.get("SKILLS_CACHE_DIR") or os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    d = Path(root) / "fawkes" / "sg-bus"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_stops(refresh: bool = False) -> list[dict]:
    """All bus stops, cached for 7 days (the dataset is ~5,200 stops over ~11 pages)."""
    path = cache_dir() / "bus_stops.json"
    if not refresh and path.is_file() and time.time() - path.stat().st_mtime < STOPS_TTL:
        try:
            return json.loads(path.read_text())
        except ValueError:
            pass  # unreadable cache: download again
    stops: list[dict] = []
    while True:
        page = lta("BusStops", **({"$skip": str(len(stops))} if stops else {})).get("value", [])
        if not page:
            break
        stops.extend(page)
    if not stops:
        raise ApiError("LTA DataMall returned no bus stops; try again shortly")
    # Unique temp file per process, then an atomic rename: concurrent runs never leave half a file.
    with tempfile.NamedTemporaryFile("w", dir=path.parent, suffix=".tmp", delete=False) as tmp:
        json.dump(stops, tmp)
    Path(tmp.name).replace(path)
    return stops


def cached_stop_name(code: str) -> str | None:
    """Stop description from the cache only; arrivals never trigger the full download."""
    try:
        path = cache_dir() / "bus_stops.json"
        for s in json.loads(path.read_text()):
            if s.get("BusStopCode") == code:
                return s.get("Description")
    except (OSError, ValueError):
        pass
    return None


# ---------------------------------------------------------------- arrivals

def natural_key(service: str) -> tuple[int, str]:
    m = re.match(r"(\d+)(.*)", service)
    return (int(m.group(1)), m.group(2)) if m else (10**6, service)


def parse_bus(bus: dict, now: datetime) -> dict | None:
    eta = (bus or {}).get("EstimatedArrival") or ""
    if not eta:
        return None
    mins = math.floor((datetime.fromisoformat(eta) - now).total_seconds() / 60)
    return {
        "minutes": max(mins, 0),
        "eta": eta,
        "live": str(bus.get("Monitored")) == "1",
        "load": LOAD.get(bus.get("Load", ""), ""),
        "type": bus.get("Type", ""),
        "wheelchair": bus.get("Feature") == "WAB",
    }


def parse_arrivals(data: dict, now: datetime) -> list[dict]:
    services = []
    for svc in data.get("Services", []):
        buses = [parse_bus(svc.get(k), now) for k in ("NextBus", "NextBus2", "NextBus3")]
        services.append({"service": svc.get("ServiceNo", "?"), "operator": svc.get("Operator", ""), "buses": buses})
    return sorted(services, key=lambda s: natural_key(s["service"]))


def format_bus(b: dict | None) -> str:
    if b is None:
        return "—"
    when = "Arr" if b["minutes"] <= 0 else f"{b['minutes']} min"
    if not b["live"]:
        return f"{when} (sched)"
    notes = [b["load"]] if b["load"] else []
    if b["type"] in ("DD", "BD"):
        notes.append(b["type"])
    if not b["wheelchair"]:
        notes.append("no WAB")
    return f"{when} ({', '.join(notes)})" if notes else when


def format_arrivals(code: str, services: list[dict], now: datetime, name: str | None = None,
                    service: str | None = None) -> str:
    head = f"Stop {code}{' ' + name if name else ''} · {now:%H:%M} SGT"
    if not services and service:
        return head + f"\n  Service {service}: no arrivals at this stop (not running now, or doesn't stop here)."
    if not services:
        return head + "\n  No buses in service right now (normal late at night)."
    return "\n".join([head] + [f"  {s['service']:<4} " + " · ".join(format_bus(b) for b in s["buses"]) for s in services])


# ---------------------------------------------------------------- stops

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def search_stops(stops: list[dict], query: str, limit: int = 5) -> list[dict]:
    q = query.strip().lower()
    if q.isdigit():
        exact = [s for s in stops if s["BusStopCode"] == q.zfill(5)]
        if exact:
            return exact
    words = re.findall(r"[\w']+", q)

    def matches(s: dict) -> bool:  # every query word starts some word of the code, name or road
        tokens = re.findall(r"[\w']+", f"{s['BusStopCode']} {s['Description']} {s['RoadName']}".lower())
        return all(any(t.startswith(w) for t in tokens) for w in words)

    hits = [s for s in stops if matches(s)]
    # Prefer matches on the stop name over road-only matches.
    hits.sort(key=lambda s: (q not in s["Description"].lower(), s["BusStopCode"]))
    return hits[:limit]


def near_stops(stops: list[dict], lat: float, lon: float, radius: float = 400, limit: int = 5) -> list[dict]:
    out = []
    for s in stops:
        d = haversine_m(lat, lon, float(s["Latitude"]), float(s["Longitude"]))
        if d <= radius:
            out.append({**s, "distance_m": round(d)})
    return sorted(out, key=lambda s: s["distance_m"])[:limit]


def check_in_singapore(lat: float, lon: float) -> None:
    if not (1.15 <= lat <= 1.50 and 103.55 <= lon <= 104.15):
        raise ApiError(f"{lat}, {lon} is not in Singapore; ask for a Singapore stop code, road or landmark")


def format_stops(stops: list[dict]) -> str:
    return "\n".join(
        f"{s['BusStopCode']}  {s['Description']}, {s['RoadName']}" + (f" · {s['distance_m']} m" if "distance_m" in s else "")
        for s in stops)


# ---------------------------------------------------------------- train alerts

def parse_train_alerts(data: dict) -> dict:
    v = data.get("value") or {}
    if isinstance(v, list):  # tolerate an OData list wrapper
        v = v[0] if v else {}
    return {
        "status": int(v.get("Status") or 1),
        "segments": v.get("AffectedSegments") or [],
        "messages": [m.get("Content", "") for m in v.get("Message") or [] if m.get("Content")],
    }


def format_train_alerts(a: dict) -> str:
    if a["status"] == 1 and not a["segments"]:
        lines = ["All lines normal"]
    else:
        lines = ["Train disruption" if a["status"] == 2 else "Minor delays"]
        for s in a["segments"]:
            lines.append(f"  {s.get('Line', '?')} towards {s.get('Direction', '?')}: {s.get('Stations', '')}")
            if s.get("FreePublicBus"):
                lines.append(f"    free bus: {s['FreePublicBus']}")
            if s.get("FreeMRTShuttle"):
                lines.append(f"    free shuttle: {s['FreeMRTShuttle']}")
    lines += [f"  {m}" for m in a["messages"]]
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sg_bus.py", description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true", help="structured JSON output")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("arrivals")
    a.add_argument("stop_code")
    a.add_argument("--service")
    s = sub.add_parser("stops").add_subparsers(dest="stops_cmd", required=True)
    ss = s.add_parser("search")
    ss.add_argument("query", nargs="+")
    ss.add_argument("--limit", type=int, default=5)
    sn = s.add_parser("near")
    sn.add_argument("lat", type=float)
    sn.add_argument("lon", type=float)
    sn.add_argument("--radius", type=float, default=400)
    sn.add_argument("--limit", type=int, default=5)
    n = sub.add_parser("nearby")
    n.add_argument("lat", type=float)
    n.add_argument("lon", type=float)
    n.add_argument("--radius", type=float, default=400)
    n.add_argument("--stops", type=int, default=3)
    n.add_argument("--service")
    sub.add_parser("train-alerts")
    args = p.parse_args(argv)

    try:
        if args.cmd == "arrivals":
            code = args.stop_code.strip()
            if not re.fullmatch(r"\d{1,5}", code):
                raise ApiError(f'"{code}" is not a stop code; try: sg_bus.py stops search <name>')
            code = code.zfill(5)
            params = {"BusStopCode": code, **({"ServiceNo": args.service} if args.service else {})}
            now = datetime.now(SGT)
            services = parse_arrivals(lta("v3/BusArrival", **params), now)
            out = ({"stop": code, "time": now.isoformat(), "services": services} if args.json
                   else format_arrivals(code, services, now, cached_stop_name(code), args.service))
        elif args.cmd == "nearby":
            check_in_singapore(args.lat, args.lon)
            found = near_stops(load_stops(), args.lat, args.lon, args.radius, args.stops)
            if not found:
                raise ApiError(f"no stops within {args.radius:.0f} m; try --radius 800")
            now = datetime.now(SGT)
            results = []
            for st in found:
                params = {"BusStopCode": st["BusStopCode"], **({"ServiceNo": args.service} if args.service else {})}
                results.append((st, parse_arrivals(lta("v3/BusArrival", **params), now)))
            out = ([{**st, "services": svcs} for st, svcs in results] if args.json else "\n".join(
                format_arrivals(st["BusStopCode"], svcs, now, f"{st['Description']} ({st['distance_m']} m)", args.service)
                for st, svcs in results))
        elif args.cmd == "stops":
            stops = load_stops()
            if args.stops_cmd == "search":
                query = " ".join(args.query)
                found = search_stops(stops, query, args.limit)
                if not found:
                    raise ApiError(f'no stop matches "{query}"; try a road name, landmark or: sg_bus.py stops near <lat> <lon>')
            else:
                check_in_singapore(args.lat, args.lon)
                found = near_stops(stops, args.lat, args.lon, args.radius, args.limit)
                if not found:
                    raise ApiError(f"no stops within {args.radius:.0f} m; try --radius 800")
            out = found if args.json else format_stops(found)
        else:
            alerts = parse_train_alerts(lta("TrainServiceAlerts"))
            out = alerts if args.json else format_train_alerts(alerts)
    except ApiError as e:
        print(e, file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=1) if args.json else out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
