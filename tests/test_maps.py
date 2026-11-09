"""maps: vendored OSM client — offline parsing, CLI wiring, and one live geocode behind SKILLS_LIVE=1."""
from __future__ import annotations

import subprocess
import sys
import unittest

from support import SKILLS, live, load_script

maps = load_script("maps", "maps_client")
SCRIPT = SKILLS / "maps" / "scripts" / "maps_client.py"


class Offline(unittest.TestCase):
    def test_parse_overpass_sorts_by_distance_and_links(self):
        elements = [
            {"type": "node", "id": 2, "lat": 1.3020, "lon": 103.8559, "tags": {"name": "Far", "amenity": "cafe"}},
            {"type": "way", "id": 1, "center": {"lat": 1.3007, "lon": 103.8559},
             "tags": {"name": "Near", "amenity": "cafe", "opening_hours": "Mo-Su 08:00-22:00"}},
            {"type": "node", "id": 3, "tags": {"name": "No coords"}},
        ]
        places = maps.parse_overpass_elements(elements, 1.3006, 103.8559)
        self.assertEqual([p["name"] for p in places], ["Near", "Far"])
        self.assertLess(places[0]["distance_m"], places[1]["distance_m"])
        self.assertEqual(places[0]["maps_url"], "https://www.google.com/maps/search/?api=1&query=1.3007,103.8559")
        self.assertEqual(places[0]["hours"], "Mo-Su 08:00-22:00")

    def test_haversine(self):
        self.assertAlmostEqual(maps.haversine_m(1.3006, 103.8559, 1.3096, 103.8559), 1000, delta=10)

    def test_cli_runs_from_any_cwd(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "nearby", "--help"], capture_output=True, text=True, cwd="/")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("restaurant", r.stdout)


class Live(unittest.TestCase):
    @live()
    def test_search_merlion(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "search", "Merlion Park, Singapore"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1.28", r.stdout)


if __name__ == "__main__":
    unittest.main()
