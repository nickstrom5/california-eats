"""Download the Overture Maps extracts that the California pipeline reads -> data/ca/

- overture_ca_bbox.parquet     every place in California's bounding box (name, category, address, point)
- overture_ca_sources.parquet  which datasets each California eating/drinking listing came from (Meta, Foursquare, ...)
- ca_state_detail.geojson      the state's land outline (for the in-state test)
- ca_shapes.json               simplified state and county outlines for the map

Adapted from wi-eats/pipeline/fetch_overture.py. Reads the public Overture bucket over S3 with DuckDB (no account needed).
"""
import os, json, time
import duckdb

RELEASE = "2026-09-23.1"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "ca")
# California, including the Channel Islands, plus a margin for border towns (Lake Tahoe, the Colorado River, Tijuana line)
BBOX = "bbox.xmin BETWEEN -124.7 AND -114.0 AND bbox.ymin BETWEEN 32.4 AND 42.1"
EAT = "('restaurant','casual_eatery','bar','fast_food_restaurant','coffee_shop','cafe','smoothie_juice_bar','brewery','food_court')"
os.makedirs(OUT, exist_ok=True)

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
places = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=places/type=place/*.parquet"

t = time.time()
if not os.path.exists(f"{OUT}/overture_ca_sources.parquet"):
    con.execute(f"""
COPY (
  SELECT id, names.primary AS name, basic_category AS cat, taxonomy.primary AS tax, taxonomy.hierarchy AS hier, confidence,
         operating_status AS status, brand.names.primary AS brand, addresses[1].freeform AS street, addresses[1].locality AS city,
         addresses[1].postcode AS zip, addresses[1].region AS region, ST_Y(geometry) AS lat, ST_X(geometry) AS lon, websites[1] AS web,
         phones[1] AS phone
  FROM read_parquet('{places}', hive_partitioning=1) WHERE {BBOX}
) TO '{OUT}/overture_ca_bbox.parquet' (FORMAT PARQUET)""")
    print("places in bbox", round(time.time() - t), "s", flush=True)
    con.execute(f"""
COPY (
  SELECT id, list_transform(sources, x -> x.dataset) AS ds, list_transform(sources, x -> x.update_time) AS ut,
         len(socials) AS n_soc, len(websites) AS n_web, len(phones) AS n_ph
  FROM read_parquet('{places}', hive_partitioning=1)
  WHERE {BBOX} AND addresses[1].region = 'CA' AND basic_category IN {EAT}
) TO '{OUT}/overture_ca_sources.parquet' (FORMAT PARQUET)""")
    print("sources", round(time.time() - t), "s", flush=True)

areas = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=divisions/type=division_area/*.parquet"
from shapely import wkb
from shapely.geometry import mapping, Polygon
rows = con.execute(f"""
  SELECT subtype, names.primary AS name, ST_AsWKB(geometry) AS g
  FROM read_parquet('{areas}', hive_partitioning=1)
  WHERE country = 'US' AND region = 'US-CA' AND subtype IN ('region', 'county') AND class = 'land'
    AND bbox.xmin > -125.5 AND bbox.xmax < -113.5 AND bbox.ymin > 32 AND bbox.ymax < 42.5""").fetchall()
print("division areas:", len(rows), round(time.time() - t), "s", flush=True)


def rings(geom, tol, min_area, holes=False):
    """Outer rings, or with holes=True one list per polygon: [outer, hole, hole...] (the page fills even-odd, so lakes stay water)."""
    geom = geom.simplify(tol, preserve_topology=True)
    polys = [p for p in getattr(geom, "geoms", [geom]) if p.geom_type == "Polygon" and p.area >= min_area]
    r = lambda ring: [[round(x, 3), round(y, 3)] for x, y in ring.coords]
    if holes:
        return [[r(p.exterior)] + [r(h) for h in p.interiors if abs(Polygon(h).area) >= min_area] for p in polys]
    return [r(p.exterior) for p in polys]


out = {"state": None, "counties": []}
for sub, name, g in rows:
    geom = wkb.loads(bytes(g)).buffer(0)
    if sub == "region":
        json.dump(mapping(geom.simplify(0.0005, preserve_topology=True)), open(f"{OUT}/ca_state_detail.geojson", "w"))
        out["state"] = rings(geom, 0.004, 0.0004, holes=True)
    else:
        out["counties"].append({"name": name, "c": rings(geom, 0.008, 0.001)})
        json.dump(mapping(geom.simplify(0.0005, preserve_topology=True)), open(f"{OUT}/county_{name.replace(' ', '_')}.geojson", "w"))
json.dump(out, open(f"{OUT}/ca_shapes.json", "w"), separators=(",", ":"))
print("outlines: state", len(out["state"] or []), "rings +", len(out["counties"]), "counties;", round(time.time() - t), "s total",
      os.path.getsize(f"{OUT}/ca_shapes.json") // 1024, "KB")
