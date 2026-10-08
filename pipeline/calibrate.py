"""How often is a map listing a real, licensed restaurant? Measured where official lists exist -> data/ca/calibration*.json

Adapted from wi-eats/pipeline/calibrate.py. Every Overture eating/drinking listing inside an area is checked against the official
list for that area (same business name nearby, or the same street address with a distinctive name word in common; records without
coordinates also need the same zip):
  - lac  Los Angeles County DEH food facility inventory (restaurants and markets), outside Pasadena, Long Beach and Vernon,
         which run their own health departments
  - sd   San Diego County DEHQ food facility permits (all 18 cities and the unincorporated county)
  - abc  California ABC active on-sale licenses, statewide. Only places that serve alcohol hold one, so this is a floor: a
         coffee shop or taqueria without a license counts as a miss.
Reported by where the listing came from (the same breakdown as Chicago and Wisconsin), and the other direction: how much of
each official restaurant list the map listings cover.
"""
import json, sys
import numpy as np, pandas as pd
from shapely.geometry import shape, Point
from shapely.prepared import prep
from common import CA
import official
from listings_util import official_match

o = pd.read_pickle(f"{CA}/stage1.pkl")
F = official.load()
county = lambda n: prep(shape(json.load(open(f"{CA}/county_{n}.geojson"))).buffer(0.0005))
LA, SD = county("Los_Angeles_County"), county("San_Diego_County")
OWN_HD = {"Pasadena", "Long Beach", "Vernon"}   # their own health departments: not on LA County's list
o["area"] = [("lac" if LA.contains(Point(x, y)) else "sd" if SD.contains(Point(x, y)) else None) for x, y in zip(o.lon, o.lat)]
o.loc[(o.area == "lac") & o.city.isin(OWN_HD), "area"] = None
base = ~o.j_junk & ~o.j_outside
print("listings inside LA County DEH's area:", int(((o.area == "lac") & base).sum()), "| San Diego County:", int(((o.area == "sd") & base).sum()),
      "| statewide:", int(base.sum()), flush=True)

AREAS = {"lac": (o.area == "lac", F.jur == "lac", ["restaurant"]), "sd": (o.area == "sd", F.jur == "sd", ["restaurant"]),
         "abc": (pd.Series(True, index=o.index), F.jur == "abc", ["restaurant", "bar", "taproom", "winery"])}
only = sys.argv[1:] or list(AREAS)


def groups_google(L):
    s = L.src.fillna("none")
    return np.select([L.closed21, L.ov_closed, (s == "meta") & L.in21, s == "meta", s.isin(["AllThePlaces", "DAC"]) & L.in21,
                      s.isin(["AllThePlaces", "DAC"]), L.in21, s == "Foursquare", s == "BrightQuery", s == "Microsoft"],
                     ["Google 2021 says closed", "Overture says closed", "Meta + open in Google 2021", "Meta only",
                      "brand feed + Google 2021", "brand feed only", "Foursquare/BrightQuery/Microsoft + Google 2021",
                      "Foursquare only", "BrightQuery only", "Microsoft only"], "other")


def groups_app(L):
    conf, s2 = L.confidence.fillna(0), L.src.fillna("none")
    return np.select([L.ov_closed, (s2 == "meta") & (conf >= 0.95), (s2 == "meta") & (conf >= 0.9), s2.isin(["AllThePlaces", "DAC"]),
                      (s2 == "BrightQuery") & (conf >= 0.95), s2 == "meta", s2 == "Foursquare", s2 == "BrightQuery", s2 == "Microsoft"],
                     ["closed (Overture)", "meta_high (>=0.95)", "meta_mid (0.90-0.95)", "brand_feed", "bq_high (>=0.95)", "meta_low (<0.90)",
                      "foursquare", "brightquery", "microsoft"], "other")


res, app = {}, {}
for jur in only:
    lsel, rsel, kinds = AREAS[jur]
    L = o[lsel & base & ~o.j_closedname & ~o.nowhere].reset_index(drop=True)
    R = F[rsel & F.active].reset_index(drop=True)
    m = official_match(L, R)          # listing index -> official index
    L["off_any"] = L.index.map(lambda i: i in m)
    L["off_rest"] = L.index.map(lambda i: i in m and R.kind.iat[m[i]] in kinds)
    for name, fn, out in (("google", groups_google, res), ("app", groups_app, app)):
        L["grp"] = fn(L)
        t = L.groupby("grp").agg(n=("id", "size"), official=("off_any", "mean"), rest=("off_rest", "mean")).sort_values("n", ascending=False)
        print(f"\n== {jur} ({name} grouping): {len(L)} listings, {len(R)} active records ({int(R.kind.isin(kinds).sum())} {'/'.join(kinds)})")
        print(t.assign(official=(t.official * 100).round(1), rest=(t.rest * 100).round(1)).to_string(), flush=True)
        out[jur] = {"listings": int(len(L)), "records": int(len(R)),
                    "groups": {g: {"n": int(r.n), "official": round(float(r.official), 3), "rest": round(float(r.rest), 3)} for g, r in t.iterrows()}}
    # the other direction: how much of the official restaurant list do the map listings cover (one per business)?
    got = set(R.biz.iloc[list(m.values())])
    Rr = R[R.kind.isin(kinds)].drop_duplicates("biz")
    cover = float(np.mean([b in got for b in Rr.biz])) if len(Rr) else None
    # and only the listings the app would keep (Meta >= 0.90, chain feeds)
    keep_app = L.grp.isin(["meta_high (>=0.95)", "meta_mid (0.90-0.95)", "brand_feed"])
    got_app = set(R.biz.iloc[[m[i] for i in L.index[keep_app] if i in m]])
    cover_app = float(np.mean([b in got_app for b in Rr.biz])) if len(Rr) else None
    print(f"official {'/'.join(kinds)} (one per business) found among map listings: {cover*100:.1f}% of {len(Rr)};"
          f" among the app's kept listings: {cover_app*100:.1f}%", flush=True)
    res[jur]["coverage"] = round(cover, 3); app[jur]["coverage"] = round(cover_app, 3); app[jur]["official_rest"] = int(len(Rr))
    res[jur]["official_rest"] = int(len(Rr))

prev = lambda f: json.load(open(f)) if __import__("os").path.exists(f) else {}
cal, cal_app = prev(f"{CA}/calibration.json"), prev(f"{CA}/calibration_app.json")
cal.update(res); cal_app.update(app)
json.dump(cal, open(f"{CA}/calibration.json", "w"), indent=1)
json.dump(cal_app, open(f"{CA}/calibration_app.json", "w"), indent=1)
