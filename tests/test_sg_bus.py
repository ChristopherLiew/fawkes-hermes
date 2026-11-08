"""sg-bus: parsing and formatting from recorded fixtures, error messages, cache, read-only skill dir. No network."""
from __future__ import annotations

import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest import mock

from support import SKILLS, fixture, live, load_script

bus = load_script("sg-bus", "sg_bus")
T = datetime.fromisoformat


class Arrivals(unittest.TestCase):
    def test_live_fixture_minutes_and_blank_third_bus(self):
        services = bus.parse_arrivals(fixture("lta_bus_arrival_83139.json"), T("2026-11-09T00:25:00+08:00"))
        self.assertEqual([s["service"] for s in services], ["155"])
        first, second, third = services[0]["buses"]
        self.assertEqual(first["minutes"], 2)      # 00:27:40 → 2 min 40 s → rounds down
        self.assertEqual(second["minutes"], 21)
        self.assertIsNone(third)                   # empty EstimatedArrival
        self.assertEqual(bus.format_bus(third), "—")

    def test_guide_fixture_format(self):
        now = T("2024-08-14T16:41:30+08:00")
        out = bus.format_arrivals("83139", bus.parse_arrivals(fixture("lta_bus_arrival_guide.json"), now), now)
        self.assertEqual(out.splitlines(), [
            "Stop 83139 · 16:41 SGT",
            "  15   Arr (seats) · 7 min (seats) · 24 min (seats)",
            "  150  13 min (sched) · 33 min (sched) · —",
            "  155  3 min (standing, DD) · 12 min (packed, BD, no WAB) · —",
        ])

    def test_monitored_zero_is_sched_and_hides_load(self):
        b = bus.parse_bus({"EstimatedArrival": "2024-08-14T16:55:22+08:00", "Monitored": 0, "Load": "SEA"},
                          T("2024-08-14T16:50:00+08:00"))
        self.assertFalse(b["live"])
        self.assertEqual(bus.format_bus(b), "5 min (sched)")

    def test_minute_rounding(self):
        now = T("2026-01-01T12:00:00+08:00")
        eta = lambda s: bus.parse_bus({"EstimatedArrival": s, "Monitored": 1}, now)["minutes"]
        self.assertEqual(eta("2026-01-01T12:00:59+08:00"), 0)
        self.assertEqual(eta("2026-01-01T12:01:00+08:00"), 1)
        self.assertEqual(eta("2026-01-01T11:59:00+08:00"), 0)   # already due → Arr, never negative

    def test_natural_sort(self):
        self.assertEqual(sorted(["NR1", "133", "10e", "2", "10"], key=bus.natural_key), ["2", "10", "10e", "133", "NR1"])

    def test_empty_services(self):
        out = bus.format_arrivals("01012", [], T("2026-01-01T02:00:00+08:00"))
        self.assertIn("No buses in service", out)

    def test_empty_for_named_service(self):
        out = bus.format_arrivals("01012", [], T("2026-01-01T12:00:00+08:00"), service="999")
        self.assertIn("Service 999: no arrivals at this stop", out)


class Stops(unittest.TestCase):
    stops = fixture("lta_bus_stops_sample.json")["value"]

    def test_search_by_words(self):
        codes = [s["BusStopCode"] for s in bus.search_stops(self.stops, "bugis exit c")]
        self.assertEqual(codes, ["01112", "01119"])

    def test_search_by_short_code_keeps_leading_zero(self):
        self.assertEqual([s["BusStopCode"] for s in bus.search_stops(self.stops, "1012")], ["01012"])

    def test_search_no_match(self):
        self.assertEqual(bus.search_stops(self.stops, "xyzzy"), [])

    def test_near_bugis(self):
        near = bus.near_stops(self.stops, 1.3006, 103.8559, radius=150, limit=5)
        self.assertEqual([s["BusStopCode"] for s in near], ["01059", "01113", "01112", "01119", "01139"])
        self.assertEqual(near[0]["distance_m"], 29)
        self.assertIn("01059  Bugis Stn Exit B, Victoria St · 29 m", bus.format_stops(near))

    def test_near_none_in_radius(self):
        self.assertEqual(bus.near_stops(self.stops, 1.3006, 103.8559, radius=10), [])


class Nearby(unittest.TestCase):
    stops = fixture("lta_bus_stops_sample.json")["value"]

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(bus, "load_stops", return_value=self.stops), \
             mock.patch.object(bus, "lta", return_value=fixture("lta_bus_arrival_83139.json")), \
             redirect_stdout(out), redirect_stderr(err):
            code = bus.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_nearby_prints_arrivals_per_stop_with_distance(self):
        code, out, _ = self.run_main("nearby", "1.3006", "103.8559", "--radius", "150", "--stops", "2")
        self.assertEqual(code, 0)
        self.assertIn("Stop 01059 Bugis Stn Exit B (29 m)", out)
        self.assertEqual(out.count("Stop 0"), 2)

    def test_outside_singapore_is_one_line_error(self):
        for cmd in (("nearby",), ("stops", "near")):
            code, out, err = self.run_main(*cmd, "35.68", "139.69")
            self.assertEqual((code, out), (1, ""))
            self.assertIn("not in Singapore", err)

    def test_no_stops_in_radius(self):
        code, _, err = self.run_main("nearby", "1.3006", "103.8559", "--radius", "5")
        self.assertEqual(code, 1)
        self.assertIn("no stops within", err)


class TrainAlerts(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(bus.format_train_alerts(bus.parse_train_alerts(fixture("lta_train_alerts_normal.json"))),
                         "All lines normal")

    def test_disrupted(self):
        out = bus.format_train_alerts(bus.parse_train_alerts(fixture("lta_train_alerts_disrupted.json")))
        self.assertTrue(out.startswith("Train disruption"))
        self.assertIn("NEL towards Punggol: NE1,NE3,NE4,NE5,NE6", out)
        self.assertIn("signalling fault", out)


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.invalid", code, "err", {}, None)


class Errors(unittest.TestCase):
    SENTINEL = "SENTINEL-KEY-0123456789abcdef"

    def call(self, exc):
        with mock.patch.dict(os.environ, {"LTA_DATAMALL_KEY": self.SENTINEL}), \
             mock.patch.object(bus.urllib.request, "urlopen", side_effect=exc), \
             mock.patch.object(bus.time, "sleep"):
            with self.assertRaises(bus.ApiError) as ctx:
                bus.lta("v3/BusArrival", BusStopCode="83139")
        self.assertNotIn(self.SENTINEL, str(ctx.exception))
        return str(ctx.exception)

    def test_401(self):
        self.assertEqual(self.call(http_error(401)), "LTA_DATAMALL_KEY missing or invalid (set it as a Fly secret)")

    def test_429(self):
        self.assertIn("rate limited", self.call(http_error(429)))

    def test_5xx_retries_once(self):
        with mock.patch.dict(os.environ, {"LTA_DATAMALL_KEY": self.SENTINEL}), \
             mock.patch.object(bus.urllib.request, "urlopen", side_effect=http_error(503)) as m, \
             mock.patch.object(bus.time, "sleep"):
            with self.assertRaises(bus.ApiError):
                bus.lta("TrainServiceAlerts")
        self.assertEqual(m.call_count, 2)

    def test_missing_key(self):
        with mock.patch.dict(os.environ, {"LTA_DATAMALL_KEY": ""}):
            with self.assertRaises(bus.ApiError) as ctx:
                bus.lta("TrainServiceAlerts")
        self.assertIn("LTA_DATAMALL_KEY missing", str(ctx.exception))

    def test_key_sent_as_header_never_in_url(self):
        seen = {}

        def fake(req, timeout):
            seen["url"], seen["key"] = req.full_url, req.get_header("Accountkey")
            raise http_error(401)

        with mock.patch.dict(os.environ, {"LTA_DATAMALL_KEY": self.SENTINEL}), \
             mock.patch.object(bus.urllib.request, "urlopen", side_effect=fake):
            with self.assertRaises(bus.ApiError):
                bus.lta("v3/BusArrival", BusStopCode="83139")
        self.assertEqual(seen["key"], self.SENTINEL)
        self.assertNotIn(self.SENTINEL, seen["url"])

    def test_cli_bad_stop_code(self):
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(bus.main(["arrivals", "bugis"]), 1)
        self.assertIn("try: sg_bus.py stops search", err.getvalue())

    def test_cli_unknown_stop_name(self):
        err = io.StringIO()
        with mock.patch.object(bus, "load_stops", return_value=Stops.stops), redirect_stderr(err):
            self.assertEqual(bus.main(["stops", "search", "xyzzy"]), 1)
        self.assertIn('no stop matches "xyzzy"', err.getvalue())


class Cache(unittest.TestCase):
    def test_paginates_until_empty_and_caches(self):
        pages = [{"value": [{"BusStopCode": f"{i:05d}"} for i in range(500)]},
                 {"value": [{"BusStopCode": "99999"}]}, {"value": []}]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"SKILLS_CACHE_DIR": tmp}), \
             mock.patch.object(bus, "lta", side_effect=pages) as m:
            self.assertEqual(len(bus.load_stops()), 501)
            self.assertEqual([c.kwargs for c in m.call_args_list], [{}, {"$skip": "500"}, {"$skip": "501"}])
            self.assertTrue((Path(tmp) / "fawkes" / "sg-bus" / "bus_stops.json").is_file())
            self.assertEqual(len(bus.load_stops()), 501)   # second call served from cache
            self.assertEqual(m.call_count, 3)
            self.assertEqual(bus.cached_stop_name("99999"), None)
            self.assertEqual(list((Path(tmp) / "fawkes" / "sg-bus").glob("*.tmp")), [])

    def test_corrupt_cache_is_refetched(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"SKILLS_CACHE_DIR": tmp}):
            (bus.cache_dir() / "bus_stops.json").write_text('[{"BusStopCode": "0')   # half-written file
            with mock.patch.object(bus, "lta", side_effect=[{"value": [{"BusStopCode": "01012"}]}, {"value": []}]):
                self.assertEqual(bus.load_stops(), [{"BusStopCode": "01012"}])


class ReadOnlySkillDir(unittest.TestCase):
    def test_runs_from_read_only_copy_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "sg-bus"
            shutil.copytree(SKILLS / "sg-bus", skill)
            before = sorted(p.relative_to(skill) for p in skill.rglob("*"))
            for p in [skill, *skill.rglob("*")]:
                p.chmod(p.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            try:
                env = {**os.environ, "SKILLS_CACHE_DIR": str(Path(tmp) / "cache")}
                script = str(skill / "scripts" / "sg_bus.py")
                ok = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True, env=env)
                bad = subprocess.run([sys.executable, script, "arrivals", "abc"], capture_output=True, text=True, env=env)
                self.assertEqual(ok.returncode, 0, ok.stderr)
                self.assertEqual(bad.returncode, 1)
                self.assertEqual(sorted(p.relative_to(skill) for p in skill.rglob("*")), before)
            finally:
                for p in [skill, *skill.rglob("*")]:
                    p.chmod(p.stat().st_mode | stat.S_IWUSR)


@live("LTA_DATAMALL_KEY")
class Live(unittest.TestCase):
    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = bus.main(list(args))
        return code, out.getvalue()

    def test_arrivals(self):
        code, out = self.run_cli("arrivals", "83139")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"^Stop 83139.* · \d\d:\d\d SGT")
        self.assertNotIn(os.environ["LTA_DATAMALL_KEY"], out)

    def test_near_bugis(self):
        code, out = self.run_cli("stops", "near", "1.3006", "103.8559")
        self.assertEqual(code, 0)
        self.assertIn("Bugis", out)

    def test_train_alerts(self):
        self.assertEqual(self.run_cli("train-alerts")[0], 0)


if __name__ == "__main__":
    unittest.main()
