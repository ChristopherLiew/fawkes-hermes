"""weather: NEA and Open-Meteo parsing/formatting from recorded fixtures, WMO table sync, errors. No network."""
from __future__ import annotations

import copy
import io
import os
import re
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest import mock

from support import SKILLS, fixture, live, load_script

wx = load_script("weather", "weather")


class TwoHour(unittest.TestCase):
    data = fixture("nea_two_hr.json")["data"]

    def test_parse(self):
        p = wx.parse_two_hr(self.data)
        self.assertEqual(len(p["forecasts"]), 47)
        self.assertEqual(p["valid_from"], "2026-11-09T00:00:00+08:00")

    def test_area_match(self):
        areas = list(wx.parse_two_hr(self.data)["forecasts"])
        self.assertEqual(wx.match_area("tampines", areas), "Tampines")
        self.assertEqual(wx.match_area("Tampenis", areas), "Tampines")   # typo → fuzzy
        self.assertEqual(wx.match_area("ang mo", areas), "Ang Mo Kio")    # unique partial
        self.assertIsNone(wx.match_area("Kyoto", areas))
        self.assertIsNone(wx.match_area("jurong", areas))              # ambiguous: East / West / Island

    def test_format_area(self):
        p = wx.parse_two_hr(self.data)
        self.assertEqual(wx.format_two_hr(p, "Tampines"),
                         "Tampines: Cloudy\n(NEA 2-h forecast 00:00–02:00, issued 00:06)")

    def test_format_summary_lists_exceptions(self):
        data = copy.deepcopy(self.data)
        for f in data["items"][0]["forecasts"]:
            if f["area"] in ("Tuas", "Jurong West"):
                f["forecast"] = "Showers"
        line = wx.format_two_hr(wx.parse_two_hr(data)).splitlines()[0]
        self.assertEqual(line, "Mostly cloudy; showers in Jurong West, Tuas")


class DailyNea(unittest.TestCase):
    def test_today(self):
        t = wx.parse_today(fixture("nea_24hr.json")["data"])
        out = wx.format_today(t)
        self.assertTrue(out.startswith("Thundery Showers, 24–33°C"))
        self.assertIn("6 am to Midday 09 Nov: Partly Cloudy (Day) islandwide", out)
        self.assertIn("east Thundery Showers, west Cloudy", out)

    def test_outlook_four_days(self):
        out = wx.format_outlook(wx.parse_outlook(fixture("nea_4day.json")["data"])).splitlines()
        self.assertEqual(len(out), 5)
        self.assertEqual(out[0], "Mon 11-09  24–33°C  Early hours and Afternoon thundery showers")


class OpenMeteo(unittest.TestCase):
    def setUp(self):
        self.place = fixture("om_geocode_kyoto.json")["results"][0]
        self.f = wx.parse_forecast(self.place, fixture("om_forecast_kyoto.json"))

    def test_daily(self):
        out = wx.format_forecast({**self.f, "hours": []}).splitlines()
        self.assertEqual(out[0], "Kyoto, Japan (Asia/Tokyo)")
        self.assertEqual(out[1:4], ["  Mon 09 Nov  Light rain, 10–18°C, rain 24%",
                                    "  Tue 10 Nov  Light rain, 8–15°C, rain 76%",
                                    "  Wed 11 Nov  Mainly clear, 7–16°C, rain 0%"])

    def test_hourly_three_hourly_rows(self):
        out = wx.format_forecast(self.f)
        self.assertEqual(len(re.findall(r"^    \d\d:00 ", out, flags=re.M)), 8)

    def test_null_hourly_values(self):
        data = fixture("om_forecast_kyoto.json")
        data["hourly"]["temperature_2m"][0] = None
        data["hourly"]["precipitation_probability"][0] = None
        self.assertIn("?°C  rain ?", wx.format_forecast(wx.parse_forecast(self.place, data)))

    def test_unknown_wmo_code(self):
        data = fixture("om_forecast_kyoto.json")
        data["daily"]["weather_code"][0] = 42
        self.assertEqual(wx.parse_forecast(self.place, data)["days"][0]["weather"], "code 42")

    def test_lat_lon_skips_geocoding(self):
        with mock.patch.object(wx, "http_json") as m:
            p = wx.resolve_place("35.02, 135.75")
        m.assert_not_called()
        self.assertEqual((p["latitude"], p["longitude"]), (35.02, 135.75))


class WmoTableInSync(unittest.TestCase):
    def test_reference_matches_script(self):
        text = (SKILLS / "weather" / "references" / "wmo-codes.md").read_text(encoding="utf-8")
        table = {int(c): t.strip() for c, t in re.findall(r"^\| (\d+) \| ([^|]+)\|$", text, flags=re.M)}
        self.assertEqual(table, wx.WMO)


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.invalid", code, "err", {}, None)


class Errors(unittest.TestCase):
    def nea_error(self, code: int) -> str:
        with mock.patch.object(wx.urllib.request, "urlopen", side_effect=http_error(code)), \
             mock.patch.object(wx.time, "sleep"):
            with self.assertRaises(wx.ApiError) as ctx:
                wx.nea("two-hr-forecast")
        return str(ctx.exception)

    def test_429(self):
        self.assertEqual(self.nea_error(429), "rate limited by data.gov.sg; set DATA_GOV_SG_API_KEY for higher limits")

    def test_401(self):
        self.assertIn("DATA_GOV_SG_API_KEY invalid", self.nea_error(401))

    def test_key_header_only_when_set(self):
        seen = []

        def fake(req, timeout):
            seen.append(req.get_header("X-api-key"))
            raise http_error(429)

        for value in ("", "SENTINEL"):
            with mock.patch.dict(os.environ, {"DATA_GOV_SG_API_KEY": value}), \
                 mock.patch.object(wx.urllib.request, "urlopen", side_effect=fake):
                with self.assertRaises(wx.ApiError) as ctx:
                    wx.nea("two-hr-forecast")
            self.assertNotIn("SENTINEL", str(ctx.exception))
        self.assertEqual(seen, [None, "SENTINEL"])


@live()
class Live(unittest.TestCase):
    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = wx.main(list(args))
        return code, out.getvalue()

    def test_sg_now_tampines(self):
        code, out = self.run_cli("sg", "now", "--area", "Tampines")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("Tampines: "))

    def test_forecast_kyoto(self):
        code, out = self.run_cli("forecast", "Kyoto", "--days", "3")
        self.assertEqual(code, 0)
        self.assertIn("Japan", out)
        self.assertEqual(len(re.findall(r"°C, rain", out)), 3)


if __name__ == "__main__":
    unittest.main()
