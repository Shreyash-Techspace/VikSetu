import json
import urllib.parse
import urllib.request
from collections import Counter

q = """
[out:json][timeout:90];
area["ISO3166-2"="IN-MH"][admin_level=4]->.mh;
area["name"="Palghar"][admin_level=5](area.mh)->.a;
(
  node["amenity"~"school|hospital|clinic|pharmacy|police|post_office|townhall|community_centre"](area.a);
);
out tags center;
""".strip()

req = urllib.request.Request(
    "https://overpass.kumi.systems/api/interpreter",
    data=q.encode("utf-8"),
    method="POST",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
with urllib.request.urlopen(req, timeout=120) as resp:
    data = json.loads(resp.read().decode())

els = data.get("elements", [])
c = Counter(e.get("tags", {}).get("amenity", "?") for e in els)
print("POI nodes in Palghar (OSM):", len(els))
for k, v in c.most_common(15):
    print(f"  {k}: {v}")
