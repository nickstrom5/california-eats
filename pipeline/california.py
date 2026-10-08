"""Stage 2: the California list -> site/ca_meta.json + one columnar file per region (site/ca_<region>.json, ca_<region>_detail.json)

Adapted from wi-eats/pipeline/wisconsin.py. Statewide base: Overture Maps listings (stage1.pkl), kept by the rule calibrate.py
measured against official lists (LA County's food facility inventory, San Diego County's permits, ABC's licenses statewide).
Official records:
  - county food-facility records where they're published in bulk (LA County, San Francisco, Santa Clara, Sacramento, San Diego):
    a listing that matches one is marked official; LA County, San Francisco and Sacramento restaurants the map data doesn't have
    are added from the record (those lists have coordinates);
  - ABC on-sale licenses statewide: a match confirms the place and says it serves alcohol (beer, beer & wine, or a full bar);
  - inspections: each jurisdiction's own official result as recorded (LA County's score and letter grade, San Francisco's,
    Santa Clara's and Sacramento's placards). Never blended into one statewide number and never re-graded by us.
Ratings, reviews and price level (the web leaderboard only): Google, Sep 2021 snapshot (UCSD Google Local).
CA_APP=1 builds the App Store data set instead (no Google-derived data at all): see the APP branches.
"""
import os, re, sys, json, math, hashlib, unicodedata, collections, html, urllib.parse
import numpy as np, pandas as pd
from shapely.geometry import shape, Point, Polygon
from shapely.prepared import prep
from shapely.ops import unary_union
from rapidfuzz import fuzz
from common import (norm_name, nice, name_sim, cuisine, CUISINE_RULES, FOOD_COST, MARGIN, MARGIN_CUISINE, SPEND, GENERIC, _stems, DATA, CA,
                    ROOT, canon_city, town_key, street_key, street_nums)
from brands import brand_of
import official
from listings_util import official_match, _close_words

APP = os.environ.get("CA_APP") == "1"
SITE = os.environ.get("CA_SITE") or (os.path.join(ROOT, "data", "app") if APP else os.path.join(ROOT, "site"))
FETCHED = pd.Timestamp("2026-10-07")
GOOD_SOURCES = {"meta", "AllThePlaces", "DAC"}
BASE = {1: 600_000, 2: 1_000_000, 3: 2_200_000, 4: 3_500_000}   # typical yearly sales by price tier (same as Chicago)
B_FIT = 0.764   # review-volume exponent fit on Chicago's published sales (chi-eats meta.model.b)
OWN_HD = {"Pasadena", "Long Beach", "Vernon"}   # their own health departments, not on LA County's list
REGIONS = [
    ("la", "Los Angeles", ["Los Angeles County"]),
    ("oc", "Orange County", ["Orange County"]),
    ("sd", "San Diego & Imperial", ["San Diego County", "Imperial County"]),
    ("ie", "Inland Empire & Desert", ["Riverside County", "San Bernardino County"]),
    ("cc", "Central Coast", ["Ventura County", "Santa Barbara County", "San Luis Obispo County", "Monterey County", "Santa Cruz County", "San Benito County"]),
    ("bay", "Bay Area", ["San Francisco", "San Mateo County", "Santa Clara County", "Alameda County", "Contra Costa County", "Marin County",
                         "Napa County", "Sonoma County", "Solano County"]),
    ("sac", "Sacramento Region", ["Sacramento County", "Placer County", "El Dorado County", "Yolo County", "Sutter County", "Yuba County"]),
    ("cv", "Central Valley", ["San Joaquin County", "Stanislaus County", "Merced County", "Madera County", "Fresno County", "Kings County",
                              "Tulare County", "Kern County"]),
    ("north", "North State & Sierra", None),   # every other county
]
# inspection jurisdictions: (code, label, agency, the official result scale in display order, the ones that aren't a pass)
JURS = [("lac", "Los Angeles County", "LA County Department of Public Health, Environmental Health", ["A", "B", "C"], ("B", "C")),
        ("sf", "San Francisco", "San Francisco Department of Public Health", ["Pass", "Conditional Pass", "Closure"], ("Conditional Pass", "Closure")),
        ("scc", "Santa Clara County", "Santa Clara County Department of Environmental Health", ["G", "Y", "R"], ("Y", "R")),
        ("sac", "Sacramento County", "Sacramento County Environmental Management Department", ["PASS", "CONDITIONAL PASS", "CLOSED"], ("CONDITIONAL PASS", "CLOSED"))]
# LA County cities that never adopted letter-grade cards: the county's file still fills in a grade, but none is posted there
LA_NO_CARD = {"Avalon", "Bradbury", "Hidden Hills", "La Habra Heights", "San Marino", "Sierra Madre", "Signal Hill"}
TAX_CUISINE = {
    "pizza_restaurant": "Pizza", "mexican_restaurant": "Mexican", "taco_restaurant": "Mexican", "texmex_restaurant": "Mexican",
    "sandwich_shop": "Sandwiches & Deli", "delicatessen": "Sandwiches & Deli", "bakery": "Bakery & Sweets", "donut_shop": "Bakery & Sweets",
    "dessert_shop": "Bakery & Sweets", "ice_cream_shop": "Bakery & Sweets", "bagel_shop": "Bakery & Sweets", "cupcake_shop": "Bakery & Sweets",
    "frozen_yogurt_shop": "Bakery & Sweets", "chocolatier": "Bakery & Sweets", "popcorn_shop": "Bakery & Sweets",
    "bar_and_grill_restaurant": "Bar & Pub", "gastropub": "Bar & Pub", "bar": "Bar & Pub", "brewery": "Bar & Pub", "pub": "Bar & Pub",
    "sports_bar": "Bar & Pub", "cocktail_bar": "Bar & Pub", "wine_bar": "Bar & Pub", "dive_bar": "Bar & Pub", "beer_bar": "Bar & Pub",
    "irish_pub": "Bar & Pub", "tiki_bar": "Bar & Pub", "speakeasy": "Bar & Pub", "hookah_bar": "Bar & Pub", "gay_bar": "Bar & Pub",
    "chinese_restaurant": "Chinese", "italian_restaurant": "Italian", "burger_restaurant": "Burgers",
    "breakfast_and_brunch_restaurant": "Breakfast & Diner", "diner": "Breakfast & Diner", "barbecue_restaurant": "BBQ",
    "chicken_restaurant": "Chicken & Wings", "chicken_wings_restaurant": "Chicken & Wings", "sushi_restaurant": "Japanese & Sushi",
    "japanese_restaurant": "Japanese & Sushi", "ramen_restaurant": "Japanese & Sushi", "seafood_restaurant": "Seafood", "poke_restaurant": "Seafood",
    "steakhouse": "Steakhouse", "indian_restaurant": "South Asian", "pakistani_restaurant": "South Asian", "thai_restaurant": "Thai",
    "hot_dog_restaurant": "Hot Dogs", "mediterranean_restaurant": "Mediterranean & Middle Eastern",
    "greek_restaurant": "Mediterranean & Middle Eastern", "middle_eastern_restaurant": "Mediterranean & Middle Eastern",
    "korean_restaurant": "Korean", "vietnamese_restaurant": "Vietnamese", "salad_bar": "Healthy & Vegan", "vegan_restaurant": "Healthy & Vegan",
    "vegetarian_restaurant": "Healthy & Vegan", "health_food_restaurant": "Healthy & Vegan", "coffee_shop": "Coffee & Café", "cafe": "Coffee & Café",
    "coffee_roastery": "Coffee & Café", "smoothie_juice_bar": "Healthy & Vegan", "juice_bar": "Healthy & Vegan", "bubble_tea_shop": "Coffee & Café",
    "tea_room": "Coffee & Café", "soul_food": "Soul & Southern", "southern_american_restaurant": "Soul & Southern",
    "cajun_and_creole_restaurant": "Seafood", "caribbean_restaurant": "Latin & Caribbean", "jamaican_restaurant": "Latin & Caribbean",
    "latin_american_restaurant": "Latin & Caribbean", "cuban_restaurant": "Latin & Caribbean", "puerto_rican_restaurant": "Latin & Caribbean",
    "peruvian_restaurant": "Latin & Caribbean", "salvadoran_restaurant": "Latin & Caribbean", "brazilian_restaurant": "Latin & Caribbean",
    "african_restaurant": "African", "ethiopian_restaurant": "African", "filipino_restaurant": "Filipino", "hawaiian_restaurant": "Hawaiian",
    "french_restaurant": "European", "german_restaurant": "European", "polish_restaurant": "European",
    "spanish_restaurant": "European", "tapas_bar": "European", "noodles_restaurant": "Chinese", "dim_sum_restaurant": "Chinese",
    "taiwanese_restaurant": "Chinese", "cantonese_restaurant": "Chinese", "szechuan_restaurant": "Chinese", "hot_pot_restaurant": "Chinese",
    "dumpling_restaurant": "Chinese", "armenian_restaurant": "Mediterranean & Middle Eastern", "persian_restaurant": "Mediterranean & Middle Eastern",
    "afghan_restaurant": "South Asian", "lebanese_restaurant": "Mediterranean & Middle Eastern", "turkish_restaurant": "Mediterranean & Middle Eastern",
    "belgian_restaurant": "European", "russian_restaurant": "European", "fondue_restaurant": "European",
    "scandinavian_restaurant": "European", "european_restaurant": "European", "eastern_european_restaurant": "European",
    "hungarian_restaurant": "European", "british_restaurant": "European", "dutch_restaurant": "European", "basque_restaurant": "European",
}


def pct(s):
    return (s.rank(pct=True) * 100).round(1)


def curated_matcher(frame):
    """A researched place -> row of frame: same street number and street with a similar name; else a near-exact name in the same town;
    else a near-exact name statewide, but only within 30 km of the researched town (wi-eats learned this the hard way)."""
    from rapidfuzz import process
    from common import undir, street_eq
    by_key = {}
    for i, a in enumerate(frame.street):
        sk = street_key(a)[1]
        for n in street_nums(a):
            if sk:
                by_key.setdefault((n, undir(sk)), []).append(i)
    towns = [canon_city(c).lower() if isinstance(c, str) else "" for c in frame.city]
    ks = list(frame.k.fillna(""))
    lat, lon, streets = list(frame.lat), list(frame.lon), list(frame.street)
    tc, by_town = {}, {}
    for i, (t, a, b) in enumerate(zip(towns, lat, lon)):
        if t:
            by_town.setdefault(t, []).append(i)
            if a == a:
                tc.setdefault(t, []).append((a, b))
    center = {t: (float(np.median([x[0] for x in v])), float(np.median([x[1] for x in v]))) for t, v in tc.items()}

    def near_town(i, town, km=30):
        if town not in center or lat[i] != lat[i]:
            return False
        return hav_km(center[town][0], center[town][1], lat[i], lon[i]) <= km

    def match(c):
        keys = {norm_name(m) for m in (c.get("match_names") or [])} | {norm_name(c["name"])}
        keys.discard("")
        addr = c.get("address") or ""
        _, sk = street_key(addr)
        cands = set()
        for n in street_nums(addr):
            cands.update(i for i in by_key.get((n, undir(sk)), []) if street_eq(sk, street_key(streets[i])[1]))
        best, bs = None, 0
        for i in cands:
            s_ = max((fuzz.token_set_ratio(m, ks[i]) for m in keys), default=0)
            if s_ >= 60 and s_ > bs:
                best, bs = i, s_
        if best is None and not c.get("chain"):
            ctown = (canon_city(c.get("city") or "") or "").lower()
            hits = [i for i in by_town.get(ctown, []) if ks[i] and max(fuzz.ratio(m, ks[i]) for m in keys) >= 90]
            if not hits:
                for m in keys:
                    hits += [j for _, sc_, j in process.extract(m, ks, scorer=fuzz.ratio, score_cutoff=95, limit=8) if near_town(j, ctown)]
                hits = sorted(set(hits))
            if len(hits) == 1:
                best = hits[0]
        return best
    return match


def street_part(a):
    """'Fairmont Grand Del Mar, 5200 Grand Del Mar Way, San Diego, 92130' -> '5200 Grand Del Mar Way'."""
    parts = [p.strip() for p in (a or "").split(",")]
    return next((p for p in parts if re.match(r"\d", p)), parts[0] if parts else None)


GUIDE_BITS = {"taqueria": 1, "burrito": 2, "fishtaco": 4, "dimsum": 8, "kbbq": 16, "burgerstand": 32, "winecountry": 64, "oldest": 128}


def load_research():
    """data/research/app/*.json: hand-checked guide places (facts with 2025-26 sources), and data/research/closed_*.json."""
    import glob
    out, by = [], {}
    for f in sorted(glob.glob(f"{DATA}/research/app/*.json")):
        for e in json.load(open(f)):
            if e.get("open") is False or not e.get("name"):
                continue
            key = (norm_name(e["name"]), (canon_city(e.get("city")) or "").lower(), (street_key(e.get("address") or "")[0] or ""))
            c = by.get(key)
            if c is None:
                c = {"name": e["name"], "address": e.get("address"), "city": e.get("city"), "zip": e.get("zip"), "chain": bool(e.get("chain")),
                     "match_names": [e["name"]], "kinds": [], "dishes": [], "opened": None, "opened_note": None, "brand_founded": None,
                     "note": None, "website": None, "sources": [], "file": os.path.basename(f)}
                by[key] = c; out.append(c)
            c["kinds"] = list(dict.fromkeys(c["kinds"] + [k for k in (e.get("kinds") or []) if k in GUIDE_BITS]))
            c["dishes"] = list(dict.fromkeys(c["dishes"] + [d for d in (e.get("dishes") or []) if isinstance(d, str)]))
            for k in ("opened", "opened_note", "note", "website"):
                c[k] = c[k] or e.get(k)
            # a founding year from somewhere else (an earlier address, or the brand's first store): "1919", "1946 in Inglewood"
            by_ = re.search(r"\b(1[789]\d\d|20[0-2]\d)\b", str(e.get("brand_founded") or ""))
            if by_ and not c["brand_founded"]:
                first = e.get("brand_first_city")
                c["brand_founded"] = by_.group(1) + (f" in {first}" if isinstance(first, str) and first.strip() else "")
            # the display note states what the menu shows, never reputation ("known for X" -> "serving X")
            if c["note"]:
                c["note"] = re.sub(r"\bknown for\b", "serving", c["note"], flags=re.I)
            c["sources"] += e.get("sources") or []
            # a live site with no 2025-26 date (or an old copyright footer) can outlive the restaurant: such an entry needs a
            # dated source elsewhere, or (checked at matching time) an official 2025-26 inspection of the place
            c["weak"] = bool(c["sources"]) and all(re.search(r"no 2025|(?:\u00a9|\(c\)|copyright)\s*(?:19\d\d|20(?:[01]\d|2[0-4]))",
                                                             x.get("what") or "", re.I) and not re.match(r"202[56]", str(x.get("date") or ""))
                                                   for x in c["sources"])
    for c in out:
        # the Oldest guide is places open at this address since 1960 or earlier; a year without the address history isn't enough
        if "oldest" in c["kinds"] and not (isinstance(c["opened"], int) and c["opened"] <= 1960):
            c["kinds"] = [k for k in c["kinds"] if k != "oldest"]
        if c["brand_founded"] and c["opened"] and c["brand_founded"] == str(c["opened"]):
            c["brand_founded"] = None
    closed = []
    for f in sorted(glob.glob(f"{DATA}/research/closed_*.json")):
        for e in json.load(open(f)):
            if e.get("name"):
                closed.append({"name": e["name"], "address": e.get("address"), "city": e.get("city"), "source": e.get("source_url"), "why": e.get("why")})
    return out, closed


MI_LEVEL = {"Recommended": 1, "Bib Gourmand": 2, "1 Star": 3, "2 Stars": 4, "3 Stars": 5}


def load_honors():
    """MICHELIN Guide California 2026 and James Beard (2023-26 + America's Classics), from data/research (facts with sources).
    Returns curated-style entries and the closed list."""
    by, out, closed = {}, [], []
    def entry(name, city, addr):
        key = (norm_name(name), (canon_city(city) or "").lower())
        if key not in by:
            by[key] = {"name": name, "city": city, "address": street_part(addr), "mi": 0, "green": False, "mi_new": False, "jbf": [], "flags": 0,
                       "match_names": [name]}
            out.append(by[key])
        e = by[key]
        if not e.get("address") and addr:
            e["address"] = street_part(addr)
        return e
    m = json.load(open(f"{DATA}/research/michelin_ca.json"))
    for r_ in m["restaurants"]:
        e = entry(r_["name"], r_["city"], r_.get("address"))
        e["mi"] = max(e["mi"], MI_LEVEL.get(r_["distinction"], 0)); e["green"] |= bool(r_.get("green_star")); e["mi_new"] |= bool(r_.get("new_this_edition"))
        e["mi_note"] = r_.get("status_note")
    j = json.load(open(f"{DATA}/research/jbf_ca.json"))
    LV = {"America's Classic": 1, "winner": 2, "finalist": 4, "semifinalist": 8}
    for r_ in j["entries"]:
        if not r_.get("address") and r_.get("category") == "Outstanding Restaurateur":
            continue   # a restaurant group, not one place
        e = entry(html.unescape(r_["restaurant"]), r_["city"], r_.get("address"))
        lvl = r_["level"]
        e["flags"] |= LV.get(lvl, 0)
        txt = "America's Classics" + (f" {r_['year']}" if r_.get("year") else "") if lvl == "America's Classic" else \
            f"{r_['category']} {r_['year']}: {lvl}" + (f" ({r_['person']})" if r_.get("person") else "")
        # one line per award: a winner was also a finalist and a semifinalist that year, so show only the furthest stage
        award = (r_.get("category"), r_.get("year"), r_.get("person"), lvl == "America's Classic")
        rank = {"winner": 3, "finalist": 2, "semifinalist": 1}.get(lvl, 0)
        best = e.setdefault("jbf_rank", {})
        if award in best and best[award][0] >= rank:
            continue
        if award in best:
            e["jbf"][e["jbf"].index(best[award][1])] = txt
        elif txt not in e["jbf"]:
            e["jbf"].append(txt)
        best[award] = (rank, txt)
    for c in m.get("closed", []) + j.get("closed", []):
        if re.search(r"temporarily closed|is moving|moving to|relocat", c.get("why", ""), re.I) and not re.search(r"closed (?:its .* )?(?:location )?permanently|closed for good", c.get("why", ""), re.I):
            continue   # temporary closures and moves aren't removals
        closed.append({"name": c["name"].split(" (")[0], "city": c.get("city"), "address": None, "source": c.get("source_url"), "why": c.get("why")})
    return out, closed


def hav_km(la1, lo1, la2, lo2):
    return 6371 * 2 * math.asin(math.sqrt(math.sin(math.radians(la2 - la1) / 2) ** 2
                                          + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(math.radians(lo2 - lo1) / 2) ** 2))


o = pd.read_pickle(f"{CA}/stage1.pkl")
# name keys with the current norm_name (accents folded since 2026-10-07), whatever stage 1 stored
o["k"] = o.name.map(norm_name)
o["st"] = o.k.map(lambda k: _stems(k) - GENERIC if k else set())
o["brand_n"] = [brand_of(k, norm_name(b) if isinstance(b, str) else None) for k, b in zip(o.k, o.brand)]
G = pd.read_pickle(f"{CA}/google21.pkl")
if APP:   # the App Store build ignores every Google 2021 match
    o["in21"] = False; o["closed21"] = False; o["gi"] = np.nan
calib = json.load(open(f"{CA}/calibration.json")) if os.path.exists(f"{CA}/calibration.json") else {}

# ---------------------------------------------------------------- counties and regions
SH = json.load(open(f"{CA}/ca_shapes.json"))
# exact county outlines (valid, from Overture divisions), not the simplified map rings, which can self-intersect
CTY = [(c["name"], prep(shape(json.load(open(f"{CA}/county_{c['name'].replace(' ', '_')}.geojson"))).buffer(0.0005))) for c in SH["counties"]]
# exact county outlines for the official-record areas (the simplified map outlines are too coarse along shared lines)
EXACT = {n: prep(shape(json.load(open(f"{CA}/county_{n.replace(' ', '_')}.geojson"))).buffer(0.0005)) for n in
         ("Los Angeles County", "San Diego County", "San Francisco", "Santa Clara County", "Sacramento County")}


def county_of(la, lo):
    if la != la:
        return None
    p = Point(lo, la)
    for n, pr in EXACT.items():
        if pr.contains(p):
            return n
    return next((n for n, pr in CTY if pr.contains(p)), None)


o["county"] = [county_of(la, lo) for la, lo in zip(o.lat, o.lon)]
print("listings without a county (offshore or across the line):", int(o.county.isna().sum()), flush=True)
AREA_OF = {"Los Angeles County": "lac", "San Diego County": "sd", "San Francisco": "sf", "Santa Clara County": "scc", "Sacramento County": "sac"}
o["area"] = o.county.map(AREA_OF)
o.loc[(o.area == "lac") & o.city.isin(OWN_HD), "area"] = None

# ---------------------------------------------------------------- official records
F = official.load()
F = F[F.active].reset_index(drop=True)
OFFJ = ["lac", "sd", "sf", "scc", "sac", "abc"]
# the matching takes most of a run, so it's cached until the listings, the records or the matching code change
# keyed on what the matching reads (names, streets, zips, points, areas), the records file and the matching code itself
_sig = [hashlib.md5(pd.util.hash_pandas_object(o[["id", "k", "street", "zip", "lat", "lon", "area", "county"]].astype(str), index=False).values).hexdigest(),
        os.path.getmtime(f"{CA}/official_{'_'.join(official.ALL)}.pkl"), os.path.getmtime(os.path.join(os.path.dirname(__file__), "listings_util.py"))]
_cache = f"{CA}/official_match.pkl"
_hit = pd.read_pickle(_cache) if os.path.exists(_cache) else None
if _hit is not None and _hit["sig"] == _sig and len(_hit["df"]) == len(o):
    for jur in OFFJ:
        o["off_" + jur] = _hit["df"]["off_" + jur].values
    print("official matches: cached", {j: int(o["off_" + j].notna().sum()) for j in OFFJ}, flush=True)
else:
    for jur in OFFJ:
        o["off_" + jur] = np.nan
        sel = o.index[(o.area == jur) if jur != "abc" else o.county.notna()]
        L = o.loc[sel].reset_index(drop=True)
        R = F[F.jur == jur]
        m = official_match(L, R.reset_index(drop=True))
        for i, j in m.items():
            o.at[sel[i], "off_" + jur] = R.index[j]
        print(f"listings matched to {jur} records:", len(m), flush=True)
    pd.to_pickle({"sig": _sig, "df": o[["id"] + [f"off_{j}" for j in OFFJ]].copy()}, _cache)
o["off"] = o[[f"off_{j}" for j in OFFJ if j != "abc"]].bfill(axis=1).iloc[:, 0]   # the county record, if any
o["official"] = o.off.notna() | o.off_abc.notna()
print("listings matched to an official record:", int(o.official.sum()), "| a county record:", int(o.off.notna().sum()), flush=True)

# ---------------------------------------------------------------- keep rule (see calibrate.py / calibration.json)
base_ok = ~o.j_junk & ~o.j_closedname & ~o.j_outside & ~o.j_far & ~o.ov_closed & ~(o.nowhere & ~o.in21) & o.county.notna()
verified = pd.Series(False, index=o.index)   # hand-checked research (data/research/app) joins here in a later pass
keep = base_ok & (~o.closed21 | o.official | verified) & (o.src.isin(GOOD_SOURCES) | o.official | verified)
if APP:
    conf = o.confidence.fillna(0)
    keep = base_ok & (o.official | verified | ((o.src == "meta") & (conf >= 0.9)) | o.src.isin(["AllThePlaces", "DAC"]))
print("kept listings:", int(keep.sum()), "of", len(o), "| dropped single-source (Foursquare/BrightQuery/Microsoft):",
      int((base_ok & ~o.src.isin(GOOD_SOURCES) & ~o.official).sum()), "| closed per Google 2021:", int((base_ok & o.closed21 & ~o.official).sum()), flush=True)
o = o[keep].reset_index(drop=True)

# ---------------------------------------------------------------- duplicate listings of one place
bizof = lambda j: F.biz.iat[int(j)] if j == j else np.nan
o["biz"] = o.off.map(bizof)
o["biz_abc"] = o.off_abc.map(bizof)
o["rank"] = o.off.notna().astype(int) * 8 + o.in21.astype(int) * 4 + o.src.isin(GOOD_SOURCES).astype(int) * 2 + o.confidence.fillna(0) \
    + o.off_abc.notna().astype(int)
o = o.sort_values("rank", ascending=False).reset_index(drop=True)
cell, drop = {}, set()
for i, r in enumerate(o.itertuples()):
    key = (round(r.lat / 0.001), round(r.lon / 0.0013))
    hit = False
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in cell.get((key[0] + dy, key[1] + dx), []):
                d_ = math.hypot((o.lat.iat[j] - r.lat) * 111000, (o.lon.iat[j] - r.lon) * 92000)
                same_biz = (r.biz == r.biz and r.biz == o.biz.iat[j]) or (r.biz_abc == r.biz_abc and r.biz_abc == o.biz_abc.iat[j])
                if (same_biz and name_sim(r.k, o.k.iat[j]) >= 80) or (d_ < 80 and (r.k == o.k.iat[j] or (fuzz.token_set_ratio(r.k, o.k.iat[j]) >= 92 and r.st & o.st.iat[j]))) or (
                        d_ < 150 and isinstance(r.brand_n, str) and r.brand_n == o.brand_n.iat[j]):
                    hit = True; break
            if hit: break
        if hit: break
    if hit:
        drop.add(i)
    else:
        cell.setdefault(key, []).append(i)
o = o.drop(index=list(drop)).reset_index(drop=True)
akey = [(b if isinstance(b, str) else k, n, c) if n and isinstance(c, str) else None for b, k, n, c in zip(o.brand_n, o.k, o.num, o.city)]
seen, dup = set(), []
for a in akey:   # o is sorted best-first, so the better-sourced copy survives
    dup.append(a is not None and a in seen)
    if a is not None:
        seen.add(a)
has_addr = o.num.notna()
for b, grp in o[o.brand_n.notna()].groupby("brand_n"):
    with_a, without = grp[has_addr[grp.index]], grp[~has_addr[grp.index]]
    for i, r in without.iterrows():
        if len(with_a) and (np.hypot((with_a.lat - r.lat) * 111, (with_a.lon - r.lon) * 92) < 1.5).any():
            dup[i] = True
o = o[~np.array(dup)].reset_index(drop=True)
near_dup = set()
conf_row = o.in21 | o.official
for (k, c), grp in o[o.brand_n.isna() & o.k.fillna("").str.len().ge(4) & o.city.notna()].groupby(["k", "city"]):
    if len(grp) < 2 or not (_stems(k) - GENERIC):
        continue
    idx = list(grp.index)   # already best-first
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            if idx[b] in near_dup or idx[a] in near_dup:
                continue
            if math.hypot((o.lat[idx[a]] - o.lat[idx[b]]) * 111000, (o.lon[idx[a]] - o.lon[idx[b]]) * 92000) < 500 and not (o.off.notna()[idx[a]] and o.off.notna()[idx[b]]):
                near_dup.add(idx[b])
    good = grp[conf_row[grp.index]]
    for i in grp.index[~conf_row[grp.index]]:
        if len(good) and i not in good.index and (np.hypot((good.lat - o.lat[i]) * 111, (good.lon - o.lon[i]) * 92) < 1.5).any():
            near_dup.add(i)
o = o.drop(index=list(near_dup)).reset_index(drop=True)
print("after merging duplicate listings:", len(o), "(dropped", len(drop) + sum(dup) + len(near_dup), "; same name within 500 m:", len(near_dup), ")", flush=True)
confirmed = ((o.src == "meta") & (o.confidence.fillna(0) >= 0.95)) if APP else o.in21
o["tier"] = np.where(o.official, "official", np.where(confirmed, "both", "listing"))

# ---------------------------------------------------------------- licensed restaurants the map listings don't have (lists with coordinates)
found = set(o.biz.dropna())
add = F[F.jur.isin(["lac", "sf", "sac"]) & F.kind.isin(["restaurant", "bar"]) & ~F.biz.isin(found) & F.lat.notna()].copy()
add["pri"] = add.kind.map({"restaurant": 0, "bar": 1})
add = add.sort_values("pri").drop_duplicates("biz")
print("county-listed restaurants/bars not in the map listings:", len(add), add.jur.value_counts().to_dict(), flush=True)


def clean_official(n):
    n = re.split(r"\s*;\s*", n or "")[0]
    n = re.sub(r"\s*#\s*\d+\w*.*$|\s*\(#?[A-Z]?\d+\)|\s+\d{3,}\s*$", "", n or "")
    n = re.sub(r",?\s+(?:INC|LLC|L\.L\.C|CORP|CORPORATION|LTD)\.?\s*$", "", n, flags=re.I)
    n = re.split(r"\s*/\s*", n)[0] if len(n) > 34 and "/" in n else n
    n = n.strip(" -,&/")
    return nice(n) if n.isupper() or n.islower() else n


rows = []
for _, f in add.iterrows():
    rows.append({"id": f.lic, "name": clean_official(f["name"]), "street": f.addr, "city": canon_city(f.city), "zip": f.zip, "lat": f.lat, "lon": f.lon,
                 "cat": "bar" if f.kind == "bar" else "restaurant", "tax": None, "confidence": np.nan, "brand": None, "src": "official",
                 "official": True, "off": f.name, "off_" + f.jur: f.name, "biz": f.biz, "tier": "official", "in21": False, "closed21": False,
                 "dom": None, "area": f.jur, "county": county_of(f.lat, f.lon)})
A = pd.DataFrame(rows)
A["k"] = A.name.map(norm_name)
A["st"] = A.k.map(lambda k: _stems(k) - GENERIC if k else set())
A["num"] = A.street.map(lambda a: (re.match(r"\s*(\d+)", a or "") or [None, None])[1])
A["brand_n"] = A.k.map(brand_of)
# a licensed place the address match missed can sit on top of its own map listing under a slightly different name: merge it in
kgrid = {}
for j, (la, lo) in enumerate(zip(o.lat, o.lon)):
    kgrid.setdefault((round(la / 0.0015), round(lo / 0.002)), []).append(j)
merge, same_lic, taken = {}, set(), set()
for ai, r in A.iterrows():
    if not r.k:
        continue
    best, bs = None, -1
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in kgrid.get((round(r.lat / 0.0015) + dy, round(r.lon / 0.002) + dx), []):
                if j in taken:
                    continue
                dist = math.hypot((o.lat.iat[j] - r.lat) * 111000, (o.lon.iat[j] - r.lon) * 92000)
                s = name_sim(r.k, o.k.iat[j]) if o.k.iat[j] else 0
                if o.off.notna().iat[j]:   # a listing with its own county record: only the same business's second record
                    if dist <= 80 and s >= 95:
                        same_lic.add(ai)
                    continue
                shared = bool(r.st & o.st.iat[j]) or _close_words(r.st, o.st.iat[j])
                if (dist <= 60 and (s >= 88 or (shared and s >= 60))) or (dist <= 25 and s >= 75):
                    if s - dist / 10 > bs:
                        best, bs = j, s - dist / 10
    if best is not None:
        merge[ai] = best; taken.add(best)
for ai, j in merge.items():
    jur = A.at[ai, "area"]
    for c in ("off", "biz", "area"):
        o.at[o.index[j], c] = A.at[ai, c]
    o.at[o.index[j], "off_" + jur] = A.at[ai, "off"]
    o.at[o.index[j], "official"] = True; o.at[o.index[j], "tier"] = "official"
A = A.drop(index=list(set(merge) | same_lic)).reset_index(drop=True)
print("county rows merged into a map listing on the second pass:", len(merge), "| second records of listed places:", len(same_lic - set(merge)),
      "| county rows added:", len(A), flush=True)

# Google 2021 listings for the added rows (leaderboard only)
A["gi"] = np.nan
if not APP and len(A):
    gtaken = set(o.gi.dropna().astype(int))
    grid = {}
    for i, (la, lo) in enumerate(zip(G.latitude, G.longitude)):
        grid.setdefault((round(la / 0.0015), round(lo / 0.002)), []).append(i)
    pairs = []
    for ai, r in A.iterrows():
        if not r.k:
            continue
        gy, gx = round(r.lat / 0.0015), round(r.lon / 0.002)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for gi in grid.get((gy + dy, gx + dx), []):
                    if gi in gtaken or not G.k.iat[gi] or G.closed21.iat[gi]:
                        continue
                    dist = math.hypot((G.latitude.iat[gi] - r.lat) * 111000, (G.longitude.iat[gi] - r.lon) * 92000)
                    if dist > 200:
                        continue
                    s = name_sim(r.k, G.k.iat[gi])
                    same_num = r.num is not None and G.num.iat[gi] == r.num
                    if same_num and r.st & G.st.iat[gi]:
                        s = max(s, 80)
                    if s < 95 and not r.st & G.st2.iat[gi]:
                        continue
                    if (s >= 88 and dist < 150) or (s >= 75 and same_num):
                        pairs.append((s + (10 if same_num else 0) - dist / 25, ai, gi))
    ta, tg = set(), set()
    for sc, ai, gi in sorted(pairs, key=lambda t: -t[0]):
        if ai in ta or gi in tg:
            continue
        ta.add(ai); tg.add(gi); A.at[ai, "gi"] = gi
A["in21"] = A.gi.notna()
print("added rows matched to Google 2021:", int(A.in21.sum()), flush=True)
# food trucks and caterers licensed at a shared kitchen: 5+ record-only places at one address
akey = [(n, st) for n, st in zip(A.num, A.street.map(lambda a: street_key(a)[1]))]
shared_n = collections.Counter(akey)
A["lic_shared"] = [shared_n[k] >= 5 and not g for k, g in zip(akey, A.in21)]
o = pd.concat([o, A], ignore_index=True)
o["city"] = o.city.map(canon_city)
main = o.city.dropna().groupby(o.city.dropna().map(town_key)).agg(lambda x: x.mode().iat[0])
o["city"] = o.city.map(lambda c: main.get(town_key(c), c) if isinstance(c, str) else c)
o["official"] = o.official.fillna(False).astype(bool)
reg_of = {c: rid for rid, _, cs in REGIONS if cs for c in cs}
o["region"] = o.county.map(lambda c: reg_of.get(c, "north") if isinstance(c, str) else None)

# ---------------------------------------------------------------- fields
gi = [int(v) if v == v and v is not None else None for v in o.gi]
o["rating"] = [G.avg_rating.iat[i] if i is not None else np.nan for i in gi]
o["reviews"] = [G.num_of_reviews.iat[i] if i is not None else np.nan for i in gi]
o["gprice"] = [len(G.price.iat[i]) if i is not None and isinstance(G.price.iat[i], str) else np.nan for i in gi]
o["gcats"] = ["|".join(G.category.iat[i] or []) if i is not None else "" for i in gi]
o["gmap_id"] = [G.gmap_id.iat[i] if i is not None else None for i in gi]
o["name_out"] = [b if isinstance(b, str) and fuzz.ratio(norm_name(n), norm_name(b)) >= 88 else nice(n) if n.isupper() or n.islower() else n
                 for n, b in zip(o.name, o.brand_n)]


def pick_cuisine(tax, k, gcats, raw):
    for c, pat in CUISINE_RULES[:-1]:          # a specific word in the name wins ("Taqueria El Gordo", "Philz Coffee")
        if pat.search(k or ""):
            return c
    if isinstance(tax, str) and tax in TAX_CUISINE:
        return TAX_CUISINE[tax]
    return cuisine(k, gcats, raw)              # "bar"-type names, then Google's categories


o["cuisine"] = [pick_cuisine(t, k, gc, n) for t, k, gc, n in zip(o.tax, o.k, o.gcats, o.name)]
first_cat = o.gcats.str.split("|").str[0].fillna("")
cafe_tax = o.tax.isin(["cafe", "coffee_shop"]) & o.cuisine.eq("Coffee & Café") & first_cat.ne("") & ~first_cat.str.contains(r"Coffee|Cafe|Café|Espresso|Tea|Bakery|Donut|Dessert|Ice cream|Juice|Breakfast")
o.loc[cafe_tax, "cuisine"] = [cuisine(k, g, "") for k, g in zip(o.loc[cafe_tax, "k"], o.loc[cafe_tax, "gcats"])]
o.loc[o.cat.isin(["bar", "brewery"]) & (o.cuisine == "American & Other"), "cuisine"] = "Bar & Pub"
o.loc[o.cat.isin(["coffee_shop", "cafe"]) & (o.cuisine == "American & Other"), "cuisine"] = "Coffee & Café"
o.loc[o.city.fillna("") == "", "city"] = None


# brand sanity: a brand rule that matched a name prefix must agree with the listing's website, Overture's brand feed, or its kind of food
def mode(x):
    return x.mode().iat[0]


bdom = {}
for b, grp in o[o.brand_n.notna()].groupby("brand_n"):
    d = grp.dom.dropna()
    if len(d) >= 3:
        top, n = collections.Counter(d).most_common(1)[0]
        if n >= 0.5 * len(d):
            bdom[b] = top
FAMILY = {"Chicken & Wings": "quick", "Burgers": "quick", "Hot Dogs": "quick", "Sandwiches & Deli": "cafe", "Pizza": "pizza",
          "Mexican": "mex", "Latin & Caribbean": "mex", "Coffee & Café": "cafe", "Bakery & Sweets": "cafe",
          "Breakfast & Diner": "cafe", "Healthy & Vegan": "cafe", "Steakhouse": "sitdown", "Seafood": "sea",
          "Bar & Pub": "bar", "Italian": "italian", "Chinese": "asian", "Japanese & Sushi": "asian", "Thai": "asian", "Korean": "asian",
          "Vietnamese": "asian", "Filipino": "asian", "Hawaiian": "asian", "South Asian": "sasian", "Mediterranean & Middle Eastern": "med",
          "European": "sitdown", "BBQ": "bbq", "Soul & Southern": "soul", "African": "african"}
brand_cuisine = o[o.brand_n.notna()].groupby("brand_n").cuisine.agg(mode)


def core(k):
    w = [x for x in k.split() if x not in GENERIC and x not in ("RESTAURANT", "RESTAURANTS", "CAFE", "STORE")]
    return " ".join(w) or k


def brand_ok(b, dm, cu, tax, obrand, name, src):
    if not isinstance(b, str):
        return None
    dm = dm if isinstance(dm, str) else None
    nk, bk = norm_name(name), norm_name(b)
    if src not in ("AllThePlaces", "DAC") and brand_of(nk) != b:
        return None                                 # only Overture's label says so
    ob = norm_name(obrand) if isinstance(obrand, str) else ""
    brand_feed = src in ("AllThePlaces", "DAC")
    label = bool(ob) and fuzz.token_set_ratio(ob, bk) >= 80
    related = brand_feed or fuzz.partial_ratio(bk, nk) >= 60 or (label and fuzz.partial_ratio(ob, nk) >= 60)
    if not related:
        return None
    squashed = re.sub(r"[^a-z]", "", b.lower())
    own_site = dm and (bdom.get(b) == dm or dm.split(".")[0].replace("-", "") in (squashed, squashed + "s"))
    exact = fuzz.ratio(core(nk), core(bk)) >= 90 or (label and fuzz.ratio(core(nk), core(ob)) >= 90) \
        or (len(bk) >= 6 and (nk == bk or nk.startswith(bk + " ")))
    if exact or own_site or (label and brand_feed):
        return b
    if dm and b in bdom and src != "BrightQuery":
        return None
    want = brand_cuisine.get(b)
    if isinstance(tax, str) and tax in TAX_CUISINE and want and FAMILY.get(cu) and FAMILY.get(want) and FAMILY[cu] != FAMILY[want]:
        return None
    return b


old_brand = o.brand_n.copy()
o["brand_n"] = [brand_ok(b, dm, cu, t, ob, n, sr) for b, dm, cu, t, ob, n, sr in zip(o.brand_n, o.dom, o.cuisine, o.tax, o.brand, o.name, o.src)]
rej = o[old_brand.notna() & o.brand_n.isna()]
print("brand matches rejected:", len(rej), collections.Counter(old_brand[rej.index]).most_common(10), flush=True)
o.loc[o.brand_n.notna(), "name_out"] = [b if fuzz.ratio(norm_name(n), norm_name(b)) >= 80 or len(norm_name(n)) <= len(norm_name(b)) + 2 else n
                                        for n, b in zip(o.loc[o.brand_n.notna(), "name_out"], o.loc[o.brand_n.notna(), "brand_n"])]


def chain_mode(x):
    real = x[x != "American & Other"]
    return (real if len(real) else x).mode().iat[0]


CHAIN_CUISINE = {"In-N-Out Burger": "Burgers", "Jack in the Box": "Burgers", "Carl's Jr.": "Burgers", "Del Taco": "Mexican", "El Pollo Loco": "Mexican",
                 "Rubio's": "Mexican", "Rubio's Coastal Grill": "Mexican", "Baja Fresh": "Mexican", "Wahoo's Fish Taco": "Mexican",
                 "Panera Bread": "Sandwiches & Deli", "Starbucks": "Coffee & Café", "Dunkin'": "Coffee & Café", "Peet's Coffee": "Coffee & Café",
                 "Coffee Bean & Tea Leaf": "Coffee & Café", "Philz Coffee": "Coffee & Café", "Dutch Bros": "Coffee & Café",
                 "Dairy Queen": "Bakery & Sweets", "Cold Stone Creamery": "Bakery & Sweets", "Baskin-Robbins": "Bakery & Sweets",
                 "Yogurtland": "Bakery & Sweets", "Pinkberry": "Bakery & Sweets", "Einstein Bros. Bagels": "Bakery & Sweets",
                 "Porto's Bakery": "Bakery & Sweets", "85°C Bakery Cafe": "Bakery & Sweets", "Taco Bell": "Mexican", "Chipotle": "Mexican",
                 "Jamba": "Healthy & Vegan", "Smoothie King": "Healthy & Vegan", "Tropical Smoothie Cafe": "Healthy & Vegan", "Sweetgreen": "Healthy & Vegan",
                 "Panda Express": "Chinese", "Yoshinoya": "Japanese & Sushi", "Wienerschnitzel": "Hot Dogs", "Dog Haus": "Hot Dogs",
                 "Zankou Chicken": "Mediterranean & Middle Eastern", "Habit Burger Grill": "Burgers", "Farmer Boys": "Burgers",
                 "Black Bear Diner": "Breakfast & Diner", "Denny's": "Breakfast & Diner", "IHOP": "Breakfast & Diner", "Norms": "Breakfast & Diner",
                 "Cheesecake Factory": "American & Other", "BJ's Restaurant & Brewhouse": "American & Other", "Islands": "Burgers",
                 "Togo's": "Sandwiches & Deli", "Subway": "Sandwiches & Deli", "Jersey Mike's": "Sandwiches & Deli", "Jollibee": "Filipino",
                 "L&L Hawaiian Barbecue": "Hawaiian", "Ono Hawaiian BBQ": "Hawaiian", "Boiling Crab": "Seafood", "Din Tai Fung": "Chinese"}
allc = o.loc[o.brand_n.notna(), ["brand_n", "cuisine"]]
all_brand_cuisine = allc.groupby("brand_n").cuisine.agg(chain_mode)
o.loc[o.brand_n.notna(), "cuisine"] = o.loc[o.brand_n.notna(), "brand_n"].map(lambda b: CHAIN_CUISINE.get(b) or all_brand_cuisine.get(b))

# price: Google price level, else the chain's usual level, else the cuisine's usual level (both from California's own Google data)
o["price"] = o.gprice
o["price_est"] = o.price.isna().astype(int)
bp = o[o.gprice.notna()].groupby("brand_n").gprice.median()
o.loc[o.price.isna() & o.brand_n.notna(), "price"] = o.brand_n.map(bp)
cp = o[o.gprice.notna()].groupby("cuisine").gprice.median()
o.loc[o.price.isna(), "price"] = o.cuisine.map(cp)
o["price"] = o.price.fillna(2).round().clip(1, 4).astype(int)

# chain size statewide. Unbranded same-name places count as one chain only when they share a website
bc = o.brand_n.value_counts()
o["chain_n"] = o.brand_n.map(lambda b: int(bc.get(b, 0)) if isinstance(b, str) else 1)
STORE_DOMS_ALL = {"7-eleven.com", "circlek.com", "ampm.com", "arco.com", "chevron.com", "shell.com", "walmart.com", "samsclub.com", "target.com",
                  "costco.com", "safeway.com", "vons.com", "ralphs.com", "albertsons.com", "raleys.com", "savemart.com", "food4less.com",
                  "smartandfinal.com", "staterbros.com", "groceryoutlet.com", "traderjoes.com", "wholefoodsmarket.com", "sprouts.com",
                  "wincofoods.com", "luckysupermarkets.com", "gelsons.com", "bristolfarms.com", "elsuper.com", "vallartasupermarkets.com",
                  "northgatemarket.com", "99ranch.com", "hmart.com", "seafoodcity.com", "erewhon.com"}
first_stem = o.k.fillna("").map(lambda k: next((w for w in k.split() if w not in GENERIC and len(w) >= 3), None))
grpkey = pd.Series([(d, s) if isinstance(d, str) and isinstance(s, str) and not isinstance(b, str) and d not in STORE_DOMS_ALL else None
                    for d, s, b in zip(o.dom, first_stem, o.brand_n)], index=o.index)
gsize = grpkey.dropna().value_counts()
member = [g is not None and gsize.get(g, 0) >= 2 for g in grpkey]
o.loc[member, "chain_n"] = [int(gsize[g]) for g, m in zip(grpkey, member) if m]
o["ckey"] = grpkey.map(lambda g: "|".join(g) if g else None)
grp_cuisine = o[member].groupby("ckey").cuisine.agg(chain_mode)
o.loc[member, "cuisine"] = [grp_cuisine.get(k) for k in o.loc[member, "ckey"]]
sib = o.gprice.notna()
for key, sel in (("brand_n", o.brand_n.notna()), ("ckey", pd.Series(member, index=o.index))):
    med = o[sel & sib].groupby(key).gprice.median()
    fill = sel & (o.price_est == 1) & o[key].isin(med.index)
    o.loc[fill, "price"] = o.loc[fill, key].map(med).round().clip(1, 4).astype(int)
print("name-based chains:", o.ckey[member].nunique(), "|", int(sum(member)), "locations", flush=True)

o["bar"] = o.cat.isin(["bar", "brewery"]) | (o.cuisine == "Bar & Pub")
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]+")
CJK = r"[぀-ヿ㐀-鿿가-힯豈-﫿＀-￯]"
TAILWORDS = re.compile(r"^(?:best|award|voted|magazine|official|order|delivery|takeout|take out|catering|now open|open|to go|curbside|franchise|inside .*|"
                       r"(?:(?:ice cream|chocolates?|fudge|coffee|cafe|café|restaurant|bar|grill|pizza|shawarma|hookah lounge|juicy seafood|latin tavern|"
                       r"bakery|deli|sandwiches|tacos|gifts?|shopping|treats|sweets|full bar|food|game room|drinks|spirits|live music|events|patio|"
                       r"lodging|rooms|resort|motel|campground|cocktails|beer|wine|burgers|wings|craft beer|sports bar|and|&|,|-|\s)+))$", re.I)


def tidy(n, brand):
    """Emoji and non-Latin duplicates of an English name, LLC in the middle, marketing tails, notes in parentheses."""
    n = unicodedata.normalize("NFKC", n)
    if re.search(r"[ÃÂâð][\u0080-¿ŒœŠšŸŽžƒˆ˜–-›€™]", n):
        for enc in ("cp1252", "latin-1"):
            try:
                n = n.encode(enc).decode("utf-8"); break
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    n = re.sub(r"[®™©]", "", EMOJI.sub("", n))
    if re.search(r"[A-Za-z]{3,}", re.sub(CJK, "", n)):
        n = re.sub(r"\s*\([^()]*" + CJK + r"[^()]*\)", "", n)
    latin = re.sub(CJK + "+", " ", n)
    if re.search(r"[A-Za-z]{3,}", latin) and re.search(CJK, n):
        n = re.sub(r"\(\s*\)", "", latin)
    m = re.match(r"^(.*?)[,\s]+(?:LLC|Inc)\.?\s*-{1,2}\s*(.+)$", n, flags=re.I)
    if m:
        n = m.group(2) if len(m.group(2).split()) >= 2 and len(m.group(1).split()) <= 2 else m.group(1)
    n = re.sub(r"[,\s]+(?:LLC|L\.L\.C|LLP|L\.L\.P|Inc|Corp)\.?(?=\s|$|,)", "", n, flags=re.I)
    n = re.sub(r"\s*\([^()]*\)\s*$", "", n) if re.sub(r"\s*\([^()]*\)\s*$", "", n).strip() else n
    n = re.sub(r",?\s+(?:CA|Calif\.?|California)\s*$", "", n)
    parts = re.split(r"\s+[-–]{1,2}\s+|--", n)
    if len(parts) > 1:
        tail = " ".join(parts[1:])
        if TAILWORDS.match(tail.strip()) or re.search(r"\b(?:Best|Award|Magazine|Voted|20\d\d)\b", tail):
            n = parts[0]
    if isinstance(brand, str):
        n = re.sub(r"\s*#\s*\d+\s*$", "", n)
    n = re.sub(r"\s+", " ", n).strip(" -–,") or n
    return nice(n) if n.isupper() and len(n) > 4 else n


o["name_out"] = [tidy(n, b) for n, b in zip(o.name_out, o.brand_n)]
o.loc[o.brand_n.notna(), "name_out"] = [b if norm_name(n).startswith(norm_name(b)) and len(norm_name(b)) >= 3 else n
                                        for n, b in zip(o.loc[o.brand_n.notna(), "name_out"], o.loc[o.brand_n.notna(), "brand_n"])]
o["spell"] = o.name_out.map(lambda n: re.sub(r"[^a-z0-9]", "", n.lower()))
o["name_out"] = o.groupby("spell").name_out.transform(lambda s: s.mode().iat[0] if len(s) > 1 else s.iat[0])
towns_l = set(o.city.dropna().str.lower())
nm = o.name_out.fillna("")
junk = (nm.str.match(r"(?i)^\d+\s+(?:[NSEW]\.?\s+)?[\w.' ]+?\b(?:St|Street|Ave|Avenue|Dr|Drive|Rd|Road|Blvd|Ln|Lane|Way|Ct|Pl|Hwy|Pkwy|Trl)\b\.?(?:\s*#\s*\w+)?(?:\s*,.*|\s+[A-Z][a-z]+,\s*CA\b.*)?$")
        | nm.str.contains(r"(?i)(?:\bclosed|\bretired)\s*\)?\s*$") | (nm.str.lower().str.strip().isin(towns_l) & o.brand_n.isna())
        | nm.str.match(r"(?i)^(?:city|town) of ") | nm.str.strip().str.lower().isin(["kitchen", "bar", "pub", "tavern", "grill", "deli", "pizza", "bakery", "coffee", "diner", "restaurant", "cafe", "café", "taqueria", "tacos"])
        | ~nm.str.contains(r"[A-Za-z]"))
print("junk names dropped:", int(junk.sum()), nm[junk].head(12).tolist(), flush=True)
o = o[~junk].reset_index(drop=True)

# ---------------------------------------------------------------- not restaurants (hidden unless "include non-restaurants" is on)
STORE = re.compile(r"^(?:7 ELEVEN|CIRCLE K|AM ?PM|ARCO(?: AM ?PM)?|CHEVRON|SHELL|76|MOBIL|VALERO|EXXON|SPEEDWAY|UNITED OIL|ROTTEN ROBBIE|"
                   r"WALMART\b.*|COSTCO\b.*|TARGET|SAFEWAY|VONS|RALPHS|ALBERTSONS|RALEYS|SAVE MART|FOOD 4 LESS|FOOD MAXX|FOODMAXX|SMART AND FINAL|"
                   r"STATER BROS(?: MARKETS)?|GROCERY OUTLET|TRADER JOES|WHOLE FOODS(?: MARKET)?|SPROUTS(?: FARMERS MARKET)?|WINCO(?: FOODS)?|"
                   r"LUCKY(?: SUPERMARKETS?)?|NOB HILL(?: FOODS)?|GELSONS|BRISTOL FARMS|EL SUPER|VALLARTA(?: SUPERMARKETS?)?|NORTHGATE(?: MARKET| GONZALEZ)?|"
                   r"CARDENAS(?: MARKETS?)?|SUPERIOR GROCERS|99 RANCH(?: MARKET)?|H MART|SEAFOOD CITY|MITSUWA(?: MARKETPLACE)?|TOKYO CENTRAL|"
                   r"MARUKAI|EREWHON|ALDI|DASHMART|CVS|WALGREENS|RITE AID|DOLLAR TREE|DOLLAR GENERAL)$|"
                   r"\b(?:SAMS CLUB|HUNT BROTHERS|KRISPY KRUNCHY|CHESTERS (?:FRIED )?CHICKEN|GAS STATION|TRAVEL (?:CENTER|PLAZA)|TRUCK STOP|TRUCKSTOP|"
                   r"FARMERS FRIDGE|MRBEAST|MR BEAST|ITS JUST WINGS|WOW BAO|GHOST KITCHEN|VIRTUAL KITCHEN|BANDA BURRITO|LAREDO TACO|"
                   r"TENDERFIX|PARDON MY CHEESESTEAK|THE MELTDOWN|BURGER DEN|HOT DOG HEAVEN|PASTA LA VISTA|LIQUORS? (?:STORE|MART|DEPOT|OUTLET)|LIQUORS?$|"
                   r"GENTLEM[AE]NS CLUB|SHOWGIRLS|HUSTLER|SPEARMINT RHINO|DEJA VU|STRIP CLUB|TRAMPOLINE|INDOOR PLAYGROUND|"
                   r"MEAT MARKET|MEATS$|BUTCHER|CARNICERIA|VENDING|COMMISSARY|FOOD PANTRY|FOOD BANK|SMOKE SHOP|VAPE|DISPENSARY|CANNABIS|"
                   r"WINE (?:MERCHANTS?|SHOP|STORE|DEPOT|OUTLET)|WINE AND SPIRITS|AND SPIRITS$|BEVMO|TOTAL WINE|JELLY BELLY|LINDT|SEES CANDIES|"
                   r"ROCKY MOUNTAIN CHOCOLATE)\b")
REALFOOD = re.compile(r"\b(?:RESTAURANT|GRILL|BAR|PUB|TAVERN|PIZZA|CAFE|KITCHEN|STEAK|BISTRO|DINER|BREWING|BREWERY|TAP|SALOON|TAQUERIA|"
                      r"TAPROOM|LOUNGE|INN|EATERY|BURGERS?|BBQ|TACOS?|DRIVE IN|DELI|COFFEE|ICE CREAM|CREAMERY|BAKERY|DONUTS?|SUSHI|PHO|BOBA|TEA)\b")
CANDY = re.compile(r"\b(?:CANDY|CANDIES|FUDGE|POPCORN|CONFECTION\w*|CHOCOLATES?|CHOCOLATIER|TRUFFLES?|SWEETS? SHOPPE?|KETTLE CORN|NUTRITION)\b")
HARD = re.compile(r"\b(?:AIRPORT|TERMINAL|CONCOURSE|LAX|SFO|DODGER STADIUM|SOFI STADIUM|LEVIS STADIUM|ORACLE PARK|CHASE CENTER|CRYPTO COM ARENA|"
                  r"PETCO PARK|ANGEL STADIUM|ROSE BOWL|GOLDEN 1 CENTER|SAP CENTER|INTUIT DOME|FAIRGROUNDS?|LEVY|AVIANDS|SODEXO|ARAMARK|"
                  r"DELAWARE NORTH|CENTERPLATE|COMPASS GROUP|CHARTWELLS|BON APPETIT|HMSHOST|EUREST|GUCKENHEIMER|SSP AMERICA|DELTA SKY CLUB|"
                  r"COMMISSARY|DINING HALL|UNIVERSITY DINING|CORRECTIONAL|PRISON|STATE PRISON|DETENTION|CAREERS)\b")
SOFT = re.compile(r"\b(?:STADIUM|ARENA|FESTIVAL|CONCESSIONS?|FOOD ?SERVICES?|UNIVERSITY|COLLEGE|SCHOOL|ACADEMY|ELEMENTARY|STUDENT|CAMPUS|"
                  r"HOSPITAL|MEDICAL CENTER|CLINIC|HEALTH CENTER|SENIOR|RETIREMENT|ASSISTED LIVING|NURSING|CARE CENTER|REHAB|CHURCH|PARISH|"
                  r"CONGREGATION|TEMPLE|SYNAGOGUE|MOSQUE|MINISTR(?:Y|IES)|VFW|AMERICAN LEGION|AMVETS|EAGLES|FRATERNAL ORDER|ELKS LODGE|"
                  r"MOOSE LODGE|KNIGHTS OF COLUMBUS|COUNTRY CLUB|GOLF CLUB|GOLF COURSE|YACHT CLUB|ATHLETIC CLUB|SOCIAL CLUB|"
                  r"CATERING|CATERERS?|BANQUETS?|BANQUET HALL|EVENT (?:CENTER|VENUE|SPACE)|CONVENTION CENTER|CONFERENCE CENTER|MUSEUM|ZOO|"
                  r"THEATER|THEATRE|CINEMAS?|AMC|REGAL|BOWLING|LANES|CASINO|HOTEL|MOTEL|INN AND SUITES|SUITES|MARRIOTT|HILTON|HYATT|SHERATON|WESTIN|"
                  r"HOLIDAY INN|HAMPTON INN|FAIRFIELD INN|RESIDENCE INN|COURTYARD|SPRINGHILL|RADISSON|BEST WESTERN|COMFORT INN|SUPER 8|"
                  r"RED ROOF|DAYS INN|CORPORATE|EMPLOYEE|CAFETERIA|MOBILE|FOOD TRUCK|KIOSK|GYM|FITNESS|YMCA|YWCA|BOYS AND GIRLS CLUB|DAYCARE|"
                  r"DAY CARE|CHILD CARE|CHILDCARE|LEARNING CENTER|JAIL|MILITARY|NATIONAL GUARD|BUILDING)\b")
kd = o.name_out.map(norm_name).fillna("")
k_ = o.k.fillna("")
busy = o.reviews.fillna(0) >= 200
gfirst = o.gcats.fillna("").str.split("|").str[0]
plainly_food = kd.str.contains(REALFOOD) | o.cat.isin(["bar", "brewery", "coffee_shop", "cafe"]) \
    | gfirst.str.contains(r"\b(?:Bar|Pub|Restaurant|Cafe|Café|Coffee|Tavern|Grill|Brewery|Diner|Bakery)\b", regex=True)
brand_store = o.brand_n.isin(["7-Eleven", "Circle K", "AM/PM", "Hunt Brothers Pizza", "Krispy Krunchy Chicken", "Chester's Chicken", "Farmer's Fridge",
                              "MrBeast Burger", "It's Just Wings", "Wow Bao"])
store = kd.str.contains(STORE) | k_.str.contains(r"\b(?:GAS STATION)\b") | brand_store | (o.dom.isin(STORE_DOMS_ALL) & ~plainly_food) \
    | (kd.str.contains(CANDY) & ~kd.str.contains(REALFOOD) & ~busy)
venue = kd.str.contains(HARD) | k_.str.contains(HARD) | o.name.fillna("").str.upper().str.contains(r"\(T-?\d|\bGATE [A-Z]?\d", regex=True) \
    | (kd.str.contains(SOFT) & ~(busy | plainly_food))
LICENSE_ONLY_NONREST = re.compile(r"\b(?:APARTMENTS?|POOLS?|SWIM|AQUATIC|ASSOCIATION|ATTN|C O|EVENTS?|STUDIOS?|SPORTS CENTER|HOSPITALITY GROUP|"
                                  r"KNIGHTS|HEALTH|CONDOMINIUMS?|HOMEOWNERS|NEIGHBORHOOD|COMMUNITY|PARKS AND REC|RECREATION|CAMP|BIBLE|FOUNDATION|"
                                  r"SOCIETY|COUNCIL|LEAGUE|UNION|INSTITUTE|CENTER$|FARMS?|AMUSEMENT|PREP|EDUCATIONAL|ENTERTAINMENT|CORPORATION|"
                                  r"HOLDINGS|MANAGEMENT|VENTURES|FIELD|SWAP ?MEET)\b")
lic_only = o.src.eq("official")
club = kd.str.contains(r"\bCLUB\b") & ~kd.str.contains(r"NIGHT ?CLUB|SUPPER ?CLUB")
venue |= lic_only & (kd.str.contains(LICENSE_ONLY_NONREST) | club) & ~busy
o["venue"] = store | venue | o.get("lic_shared", pd.Series(False, index=o.index)).fillna(False).astype(bool)
print("non-restaurants flagged:", int(o.venue.sum()), "| stores:", int(store.sum()), "| venues:", int((venue & ~store).sum()), flush=True)
adult = o.name_out.str.contains(r"gentlem[ae]n'?s club|exotic dancer|strip club|adult entertainment|spearmint rhino|deja vu showgirls|hustler club", case=False, regex=True)
print("adult clubs removed:", int(adult.sum()), o.name_out[adult].head(10).tolist(), flush=True)
o = o[~adult].reset_index(drop=True)

# ---------------------------------------------------------------- California boards by name and category (leaderboard v1; the app's guides are hand-checked)
TAGS = ["taqueria", "burrito", "dimsum", "kbbq", "seafood", "winecountry"]
k2 = o.name_out.map(norm_name).fillna("") + " " + o.k.fillna("")
gc = o.gcats.fillna("")
o["t_taqueria"] = (k2.str.contains(r"\bTAQUERIAS?\b") | o.tax.eq("taco_restaurant") | gc.str.contains(r"\bTaco restaurant\b")) & ~o.brand_n.isin(["Taco Bell", "Del Taco", "Chipotle"])
o["t_burrito"] = (k2.str.contains(r"\bBURRITOS?\b") | gc.str.contains(r"\bBurrito restaurant\b")) & ~o.brand_n.notna()
o["t_dimsum"] = k2.str.contains(r"\bDIM SUM\b|\bDIMSUM\b|\bYUM CHA\b") | o.tax.eq("dim_sum_restaurant") | gc.str.contains(r"\bDim sum restaurant\b")
o["t_kbbq"] = k2.str.contains(r"\bKOREAN (?:BBQ|BARBECUE|BARBEQUE|GRILL)\b|\bKBBQ\b|\bK BBQ\b|\bGALBI\b|\bKALBI\b") | gc.str.contains(r"\bKorean barbecue restaurant\b")
o["t_seafood"] = (o.cuisine == "Seafood") & ~o.brand_n.notna()
WINE_TOWNS = {"Napa", "Yountville", "St. Helena", "Calistoga", "Rutherford", "Oakville", "Sonoma", "Glen Ellen", "Kenwood", "Healdsburg",
              "Geyserville", "Windsor", "Sebastopol", "Guerneville", "Forestville", "Paso Robles", "Templeton", "Los Olivos", "Solvang",
              "Buellton", "Santa Ynez", "Los Alamos", "Temecula", "Murphys", "Plymouth", "Sutter Creek", "Lodi", "Livermore", "Carmel Valley",
              "Boonville", "Philo", "Hopland", "Amador City", "Fair Play", "Somerset", "Saratoga"}
o["t_winecountry"] = o.city.isin(WINE_TOWNS) & ~o.venue & o.brand_n.isna()
print("boards:", {t: int(o["t_" + t].sum()) for t in TAGS}, flush=True)

# ---------------------------------------------------------------- ABC: serves alcohol (beer / beer & wine / full bar), statewide
LIQT = ["", "beer", "beer & wine", "full bar"]
lic_type = o.off_abc.map(lambda j: F.pe.iat[int(j)] if j == j else None)
serves = lic_type.map(lambda t: official.ABC_SERVES.get(t) if isinstance(t, str) else None)
o["liq"] = serves.map(lambda s: 0 if not isinstance(s, str) else 3 if s == "full bar" else 1 if s == "beer" else 2).astype(int)
o["abc_lic"] = o.off_abc.map(lambda j: F.lic.iat[int(j)] if j == j else None)
o["abc_type"] = lic_type
print("matched to an ABC on-sale license:", int(o.off_abc.notna().sum()), "| full bar:", int((o.liq == 3).sum()), flush=True)

# ---------------------------------------------------------------- inspections: each jurisdiction's own official result
THROUGH = {}
for jur in ("lac", "sf", "scc", "sac"):
    THROUGH[jur] = FETCHED - pd.Timedelta(days=7)   # at least a week of publication lag, never past the fetch
INS = official.inspections(THROUGH)
o["in_j"] = None
for col in ("in_res", "in_score", "in_date", "in_n", "in_bad", "in_first", "in_mean", "in_lic"):
    o[col] = None
for jx, (jur, label, agency, scale, bad) in enumerate(JURS):
    S_ = INS[jur]
    offc = o["off_" + jur] if "off_" + jur in o else pd.Series(np.nan, index=o.index)
    lic = offc.map(lambda j: F.lic.iat[int(j)] if j == j else None)
    biz = offc.map(lambda j: F.biz.iat[int(j)] if j == j else None)
    n_hit = 0
    for i in o.index[lic.notna()]:
        cand = [lic[i]] if lic[i] in S_.index else []
        if not cand and biz[i] is not None:   # a sibling record of the same business (LA County: the restaurant program, not the market's)
            sib_ = F[(F.biz == biz[i]) & (F.jur == jur)]
            cand = [x for x, kd_ in zip(sib_.lic, sib_.kind) if x in S_.index and kd_ in ("restaurant", "bar", "food")] or [x for x in sib_.lic if x in S_.index]
        if not cand:
            continue
        rec = S_.loc[cand].sort_values("last_date").iloc[-1]
        res = rec.last_result
        if jur == "lac" and o.at[i, "city"] in LA_NO_CARD:
            res = None   # the score is official; a letter card isn't posted in these cities
        o.at[i, "in_j"] = jx; o.at[i, "in_res"] = res; o.at[i, "in_date"] = rec.last_date; o.at[i, "in_n"] = int(rec.n_insp)
        o.at[i, "in_bad"] = int(rec.n_bad); o.at[i, "in_first"] = rec.first_date; o.at[i, "in_lic"] = rec.name
        if "last_score" in rec and rec.last_score == rec.last_score:
            o.at[i, "in_score"] = int(rec.last_score); o.at[i, "in_mean"] = float(rec.mean_score)
        n_hit += 1
    print(f"{label}: places with an official inspection result:", n_hit, flush=True)

# ---------------------------------------------------------------- honors: MICHELIN Guide California 2026, James Beard 2023-26 + America's Classics
for col in ("jbf", "honors", "icon", "founded", "rev_reported", "rev_year", "rev_label", "mi_note"):
    o[col] = None
o["mi"] = 0; o["green"] = False; o["hon_flags"] = 0
o["honored"] = False
o["hc"] = False
HON, CLOSED_V = load_honors()
# Yank Sing's Rincon Center location closed (2026-09-20); its Stevenson St location is open: match the closure by address
for c in CLOSED_V:
    if c["name"] == "Yank Sing":
        c["address"] = "101 Spear St"
mh = curated_matcher(o)
unmatched_h = []
for c in HON:
    b = mh(c)
    if b is None:
        unmatched_h.append(f"{c['name']} ({c['city']})"); continue
    i = o.index[b]
    o.at[i, "mi"] = max(int(o.at[i, "mi"]), c["mi"]); o.at[i, "green"] = bool(o.at[i, "green"]) or c["green"]
    o.at[i, "hon_flags"] = int(o.at[i, "hon_flags"]) | c["flags"]
    if c["jbf"]:
        o.at[i, "jbf"] = "; ".join(([o.at[i, "jbf"]] if isinstance(o.at[i, "jbf"], str) else []) + c["jbf"])
    if c.get("mi_note"):
        o.at[i, "mi_note"] = c["mi_note"]
    # the guide's own name when the listing only adds to it ("SingleThread Farm - Restaurant - Inn" is SingleThread)
    hk, lk = norm_name(c["name"]), norm_name(o.at[i, "name_out"])
    if hk and lk != hk and lk.startswith(hk + " ") and not isinstance(o.at[i, "brand_n"], str):
        o.at[i, "name_out"] = c["name"]
    o.at[i, "honored"] = True
def overture_spots(entries):
    """Researched or honored places the eating listings lack (a hotel dining room, an inn): Overture's own listing of the business in
    any category, a near-exact name in the same town. Returns {entry index: (lat, lon, zip, street)}."""
    import duckdb
    towns = sorted({(canon_city(c.get("city")) or "").lower() for c in entries if c.get("city")})
    if not towns:
        return {}
    OV = duckdb.connect().execute(f"""SELECT name, street, city, zip, lat, lon FROM '{CA}/overture_ca_bbox.parquet'
        WHERE region = 'CA' AND name IS NOT NULL AND lower(city) IN ({",".join("?" * len(towns))})""", towns).df()
    OV["k"] = OV.name.map(norm_name); OV["town"] = OV.city.map(lambda c: (canon_city(c) or "").lower())
    out = {}
    for n, c in enumerate(entries):
        g = OV[OV.town == (canon_city(c.get("city")) or "").lower()]
        if not len(g):
            continue
        keys = {norm_name(m) for m in (c.get("match_names") or [])} | {norm_name(c["name"])}
        sims = [max(fuzz.ratio(m, k) for m in keys) if isinstance(k, str) and k else 0 for k in g.k]
        j = int(np.argmax(sims))
        if sims[j] >= 88:
            h = g.iloc[j]
            out[n] = (h["lat"], h["lon"], (h["zip"] or "")[:5] or None, c.get("address") or h["street"])
    return out


closed_keys = {(norm_name(c["name"]), (canon_city(c.get("city")) or "").lower()) for c in CLOSED_V}
miss_h = [c for c in HON if mh(c) is None and (norm_name(c["name"]), (canon_city(c.get("city")) or "").lower()) not in closed_keys]
spots = overture_spots(miss_h)
add_h = []
for n, (la, lo, zp, st) in spots.items():
    c = miss_h[n]
    add_h.append({"id": "honors-" + c["name"], "name": c["name"], "name_out": c["name"], "street": st, "city": canon_city(c.get("city")), "zip": zp,
                  "lat": la, "lon": lo, "cat": "restaurant", "tax": None, "confidence": np.nan, "brand": None, "brand_n": None, "src": "research",
                  "official": False, "off": np.nan, "tier": "both", "in21": False, "closed21": False, "dom": None, "area": None, "k": norm_name(c["name"]),
                  "num": (re.match(r"\s*(\d+)", st or "") or [None, None])[1], "venue": False, "bar": False, "county": county_of(la, lo), "chain_n": 1,
                  "cuisine": pick_cuisine(None, norm_name(c["name"]), "", c["name"]), "price": 4 if c["mi"] >= 3 else 2, "price_est": 1, "liq": 0,
                  "mi": c["mi"], "green": c["green"], "hon_flags": c["flags"], "honored": True, "jbf": "; ".join(c["jbf"]) or None, "in_j": None, "gcats": "",
                  "rating": np.nan, "reviews": np.nan, "gprice": np.nan, "abc_lic": None, "abc_type": None, "web": None, "phone": None, "hc": False,
                  "mi_note": c.get("mi_note")})
if add_h:
    A3 = pd.DataFrame(add_h)
    A3["region"] = A3.county.map(lambda c: reg_of.get(c, "north") if isinstance(c, str) else None)
    for t in TAGS:
        A3["t_" + t] = False
    o = pd.concat([o, A3], ignore_index=True)
    mh = curated_matcher(o)
unmatched_h = [u for u in unmatched_h if not any(u.startswith(a["name"] + " (") for a in add_h)]
print(f"honored places matched: {len(HON) - len(unmatched_h)}/{len(HON)} ({len(add_h)} placed on Overture's listing in another category);"
      f" not placed ({len(unmatched_h)}):", unmatched_h[:40], flush=True)
gone = []
for c in CLOSED_V:
    b = mh({"name": c["name"], "city": c["city"], "address": c.get("address")}) if c.get("address") else mh({"name": c["name"], "city": c["city"]})
    if b is not None:
        gone.append((c["name"], o.name_out.iat[b], o.street.iat[b]))
        o = o.drop(index=o.index[b]).reset_index(drop=True)
        mh = curated_matcher(o)
print("verified closed, removed:", gone, flush=True)
o.loc[o.honored, "venue"] = False   # a starred hotel dining room is a restaurant

# ---------------------------------------------------------------- hand-checked guides (data/research/app): open with a 2025-26 source
RES, RES_CLOSED = load_research()
for col in ("dishes", "opened_note", "rnote", "rsite", "brand_founded"):
    o[col] = None
o["gbits"] = 0
gone_r = []
for c in RES_CLOSED:
    b = curated_matcher(o)(c)
    if b is not None:
        gone_r.append((c["name"], o.name_out.iat[b], o.street.iat[b]))
        o = o.drop(index=o.index[b]).reset_index(drop=True)
print("research: verified closed, removed:", len(gone_r), gone_r[:12], flush=True)
mr = curated_matcher(o)
unplaced, weak_skipped = [], []
for c in RES:
    b = mr(c)
    if b is None:
        if not c.get("weak"):
            unplaced.append(c)
        else:
            weak_skipped.append(c["name"])
        continue
    i = o.index[b]
    if c.get("weak") and not (isinstance(o.at[i, "in_date"], str) and o.at[i, "in_date"] >= "2025-01-01"):
        weak_skipped.append(c["name"]); continue
    o.at[i, "hc"] = True
    o.at[i, "gbits"] = int(o.at[i, "gbits"]) | sum(GUIDE_BITS[k] for k in c["kinds"])
    for col, v in (("dishes", ", ".join(c["dishes"]) or None), ("opened_note", c.get("opened_note")), ("rnote", c.get("note")),
                   ("rsite", c.get("website")), ("brand_founded", c.get("brand_founded"))):
        if v and not isinstance(o.at[i, col], str):
            o.at[i, col] = str(v)
    if c.get("opened") and not o.at[i, "founded"]:
        o.at[i, "founded"] = int(c["opened"])
# verified places the map listings don't have: placed on the US Census geocoder's match for the verified address
# (pipeline/geocode_research.py fills data/research/geocode_census.json from data/research/geocode_todo.json)
GEOCACHE = json.load(open(f"{DATA}/research/geocode_census.json")) if os.path.exists(f"{DATA}/research/geocode_census.json") else {}
todo, added_r = [], []
for c in unplaced:
    a, t = (c.get("address") or "").strip(), (c.get("city") or "").strip()
    gq = f"{a}, {t}, CA {c.get('zip') or ''}".strip() if re.match(r"\s*\d", a) and t else None
    hit = GEOCACHE.get(gq) if gq else None
    if not hit:
        if gq: todo.append(gq)
        continue
    added_r.append({"id": "research-" + c["name"], "name": c["name"], "name_out": c["name"], "street": a, "city": canon_city(t), "zip": hit.get("zip") or c.get("zip"),
                    "lat": hit["lat"], "lon": hit["lon"], "cat": "restaurant", "tax": None, "confidence": np.nan, "brand": None, "brand_n": None,
                    "src": "research", "official": False, "off": np.nan, "tier": "both", "in21": False, "closed21": False, "dom": None, "area": None,
                    "k": norm_name(c["name"]), "num": (re.match(r"\s*(\d+)", a) or [None, None])[1], "venue": False, "bar": False, "hc": True,
                    "gbits": sum(GUIDE_BITS[k] for k in c["kinds"]), "dishes": ", ".join(c["dishes"]) or None, "opened_note": c.get("opened_note"),
                    "rnote": c.get("note"), "rsite": c.get("website"), "brand_founded": c.get("brand_founded"), "founded": c.get("opened"),
                    "county": county_of(hit["lat"], hit["lon"]), "chain_n": 1, "cuisine": pick_cuisine(None, norm_name(c["name"]), "", c["name"]),
                    "price": 2, "price_est": 1, "liq": 0, "mi": 0, "green": False, "hon_flags": 0, "honored": False, "in_j": None, "gcats": "",
                    "rating": np.nan, "reviews": np.nan, "gprice": np.nan, "abc_lic": None, "abc_type": None, "web": c.get("website"), "phone": None})
if added_r:
    A2 = pd.DataFrame(added_r)
    A2["region"] = A2.county.map(lambda c: reg_of.get(c, "north") if isinstance(c, str) else None)
    for t in TAGS:
        A2["t_" + t] = False
    o = pd.concat([o, A2], ignore_index=True)
json.dump(sorted(set(todo)), open(f"{DATA}/research/geocode_todo.json", "w"), indent=1)
print("research: undated-website-only entries without a 2025-26 inspection, left as leads:", weak_skipped, flush=True)
print(f"research: {len(RES)} hand-checked places; matched {len(RES) - len(unplaced) - len(weak_skipped)}, added {len(added_r)}, waiting for the geocoder {len(set(todo))}",
      {k: int((o.gbits & b > 0).sum()) for k, b in GUIDE_BITS.items()}, flush=True)

# ---------------------------------------------------------------- sales / profit: the Chicago model
auv = {a["brand"]: a for a in json.load(open(f"{DATA}/chain_auv.json")) if a.get("auv_usd")} if os.path.exists(f"{DATA}/chain_auv.json") else {}
ALIAS = {"In-N-Out Burger": "In-N-Out Burger", "Jack in the Box": "Jack in the Box", "Carl's Jr.": "Carl's Jr.", "Del Taco": "Del Taco",
         "El Pollo Loco": "El Pollo Loco", "Habit Burger Grill": "The Habit Burger Grill"}
for mine, theirs in ALIAS.items():
    if theirs and theirs in auv and mine not in auv:
        auv[mine] = auv[theirs]
med_rev = o[o.reviews.notna() & (o.chain_n < 5)].groupby("price").reviews.median()
rel = (o.reviews + 10) / (o.price.map(med_rev) + 10)
bump = np.where(o.bar, 1.15, 1.0)
o["rev"] = (o.price.map(BASE) * bump * rel.fillna(0.6) ** B_FIT).clip(100_000, 40_000_000)
o["rev_src"] = np.where(o.reviews.notna(), "model", "model-low")
n_auv = 0
for b, a in auv.items():
    sel = o.brand_n == b
    if not sel.any():
        continue
    n_auv += 1
    med = o.loc[sel, "reviews"].median()
    r_ = (o.loc[sel, "reviews"] / med) ** 0.35 if med == med else pd.Series(np.nan, index=o.index[sel])
    o.loc[sel, "rev"] = a["auv_usd"] * r_.fillna(0.85).clip(0.6, 1.5)
    o.loc[sel, "rev_src"] = "chain"
o.loc[o.venue & o.rev_src.isin(["model", "model-low"]), "rev_src"] = "venue"
m_rat = o.rating.mean()
o["bayes"] = (o.reviews * o.rating + 40 * m_rat) / (o.reviews + 40)
margin = o.price.map(MARGIN)
margin = o.cuisine.map(MARGIN_CUISINE).fillna(margin) * (0.8 + 0.4 * pct(o.bayes).fillna(40) / 100)
o["margin"] = margin.round(4)
o["profit"] = o.rev * o.margin
o["food_cost"] = o.cuisine.map(FOOD_COST).fillna(30)
o["value_raw"] = o.bayes - 0.18 * (o.price - 1)
# honors points: MICHELIN distinction, James Beard level, America's Classics, plus how many people know the place (2021 reviews)
mi_pts = o.mi.map({0: 0, 1: 8, 2: 22, 3: 34, 4: 42, 5: 50}).fillna(0) + o.green.astype(int) * 6
hf = o.hon_flags.fillna(0).astype(int)
jb_pts = np.select([hf & 1 > 0, hf & 2 > 0, hf & 4 > 0, hf & 8 > 0], [32, 22, 12, 5], 0)
o["s_icon"] = np.where(o.honored, (np.minimum(mi_pts + jb_pts, 70) + pct(np.log1p(o.reviews)).fillna(0) / 100 * 30).clip(upper=100), np.nan)


# ---------------------------------------------------------------- export
def r(x, n=0):
    if x is None or (isinstance(x, float) and x != x):
        return None
    return int(round(float(x))) if n == 0 else round(float(x), n)


o = o[o.lat.notna() & o.region.notna()].reset_index(drop=True)
# statewide percentiles, computed once here so every region file ranks against all of California (the page's pctRank, ported)
def pct_rank(s):
    return (s.rank(method="average", pct=True) * 1000).round().where(s.notna())


o["i_rating"], o["i_pop"], o["i_value"], o["i_profit"] = pct_rank(o.bayes), pct_rank(o.reviews), pct_rank(o.value_raw), pct_rank(o.profit)
nv = o[~o.venue]
os.makedirs(SITE, exist_ok=True)


def phone_e164(ph):
    """+1 and ten digits, or nothing (wi-eats: "+608..." dialed Malaysia; placeholders like 555-5555 aren't numbers)."""
    if not isinstance(ph, str):
        return None
    d = re.sub(r"\D", "", ph)
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    if len(d) != 10 or d[0] in "01" or re.search(r"(\d)\1{6}$|5555555$|1234567$", d):
        return None
    return "+1" + d


def clean_url(u):
    """Website links without tracking parameters, Facebook's mobile host swapped for the main one."""
    base, _, q = u.partition("?")
    base = re.sub(r"^(https?://)(?:m|mobile)\.facebook\.com", r"\1www.facebook.com", base)
    keep = [kv for kv in q.split("&") if kv and not re.match(
        r"(rwg_token|utm_[a-z]+|fbclid|gclid|msclkid|igshid|y_source|mc_[a-z]+|hsa_[a-z]+|_ga|_rdr)(=|$)|cid=.*(YXT|GMB|RF:|RF%3A)", kv)]
    return base + ("?" + "&".join(keep) if keep else "")


if APP:
    # ---- App Store data set: no Google-derived data. Overture places, county records, ABC licenses, official inspections
    # (LA County, San Francisco, Sacramento; Santa Clara's has no stated license, so it stays in the private leaderboard: Nick, 2026-10-07),
    # MICHELIN and James Beard facts, and our hand-checked research.
    APP_JURS = ["lac", "sf", "sac"]
    CUIS = sorted(o.cuisine.unique().tolist()); BRANDS = sorted(o.brand_n.dropna().unique().tolist())
    cu, br = {c: i for i, c in enumerate(CUIS)}, {c: i for i, c in enumerate(BRANDS)}
    TIERS = {"listing": 0, "both": 1, "official": 2}
    SRCS_A = ["official", "meta", "AllThePlaces", "DAC", "research"]
    LINKS = json.load(open(f"{CA}/website_check.json")) if os.path.exists(f"{CA}/website_check.json") else {}
    link_drops, link_cands = collections.Counter(), {}
    # the same place twice: same name at the same street address, or (not a chain) same name in one town within 400 m;
    # the kept copy inherits what the dropped one knew (a hand check, honors, facts)
    rank_ = o.tier.map(TIERS).fillna(0) * 10 + o.hc.astype(int) * 5 + o.honored.astype(int) * 3 + o.web.notna().astype(int)
    keyname = o.name_out.map(norm_name)
    keyaddr = ["|".join(k) if all(k := street_key(s_)) else None for s_ in o.street]
    drop, merged, seen = set(), [], {}
    for pos, i in enumerate(o.index):
        if keyaddr[pos] and keyname[i]:
            k = (keyname[i], keyaddr[pos], o.at[i, "city"])
            if k in seen:
                j = seen[k]; lose = i if rank_[i] <= rank_[j] else j; keep_ = j if lose == i else i
                drop.add(lose); seen[k] = keep_; merged.append((keep_, lose))
            else:
                seen[k] = i
    single = o[(o.chain_n.fillna(1) < 2) & ~o.index.isin(drop)]
    for (nm, town), g in single.groupby([keyname[single.index], single.city]):
        if len(g) < 2 or not nm:
            continue
        idx = list(g.index)
        for a_ in range(len(idx)):
            for b_ in range(a_ + 1, len(idx)):
                i, j = idx[a_], idx[b_]
                if i in drop or j in drop:
                    continue
                if hav_km(o.at[i, "lat"], o.at[i, "lon"], o.at[j, "lat"], o.at[j, "lon"]) < 0.4:
                    lose = i if rank_[i] <= rank_[j] else j
                    drop.add(lose); merged.append((j if lose == i else i, lose))
    for keep_, lose in merged:
        for col in ("hc", "honored"):
            if bool(o.at[lose, col]) and not bool(o.at[keep_, col]):
                o.at[keep_, col] = o.at[lose, col]
        for col in ("gbits", "hon_flags", "mi"):
            o.at[keep_, col] = int(o.at[keep_, col] or 0) | int(o.at[lose, col] or 0) if col != "mi" else max(int(o.at[keep_, col] or 0), int(o.at[lose, col] or 0))
        for col in ("dishes", "opened_note", "rnote", "rsite", "brand_founded", "founded", "jbf", "s_icon", "web", "phone", "liq", "abc_lic", "abc_type",
                    "in_j", "in_res", "in_score", "in_date", "in_n", "in_bad"):
            if col in o.columns and (o.at[keep_, col] is None or (isinstance(o.at[keep_, col], float) and o.at[keep_, col] != o.at[keep_, col]) or o.at[keep_, col] == 0) \
                    and not (o.at[lose, col] is None or (isinstance(o.at[lose, col], float) and o.at[lose, col] != o.at[lose, col])):
                o.at[keep_, col] = o.at[lose, col]
    print("duplicates removed for the app:", len(drop), flush=True)
    o = o.drop(index=list(drop)).reset_index(drop=True)
    smoke = o.name_out.str.contains(r"\bvape\b|smoke shop|\btobacco\b|cigar lounge|\bcbd\b|dispensary|head shop|hookah lounge", case=False, regex=True)
    o.loc[smoke, "venue"] = True
    COUNTIES_A = sorted(o.county.dropna().unique().tolist()); cty_a = {c: i for i, c in enumerate(COUNTIES_A)}
    files, nv_a = [], o[~o.venue]
    seen_ids = set()
    for rid, rname, _ in REGIONS:
        sub = o[o.region == rid]
        CITIES = sorted(sub.city.dropna().unique().tolist()); ci = {c: i for i, c in enumerate(CITIES)}
        places = []
        for _, x in sub.iterrows():
            idsrc = f"{norm_name(x.name_out)}|{round(float(x.lat), 3)}|{round(float(x.lon), 3)}"
            p_ = {"id": hashlib.md5(idsrc.encode()).hexdigest()[:12], "n": x.name_out, "cu": cu[x.cuisine], "t": TIERS[x.tier],
                  "s": SRCS_A.index(x.src) if x.src in SRCS_A else 1}
            while p_["id"] in seen_ids:   # two same-name places in one ~100 m cell
                p_["id"] += "x"
            seen_ids.add(p_["id"])
            if isinstance(x.city, str): p_["c"] = ci[x.city]
            if isinstance(x.street, str): p_["a"] = nice(x.street, addr=True)
            if isinstance(x.zip, str) and re.match(r"^9[0-6]\d{3}", x.zip): p_["z"] = x.zip[:5]
            p_["la"], p_["lo"] = round(float(x.lat), 5), round(float(x.lon), 5)
            if isinstance(x.county, str): p_["ct"] = cty_a[x.county]
            if isinstance(x.brand_n, str): p_["b"] = br[x.brand_n]
            if x.chain_n and int(x.chain_n) > 1: p_["ch"] = int(x.chain_n)
            if x.venue: p_["v"] = 1
            if x.bar: p_["bar"] = 1
            if int(x.gbits or 0): p_["g"] = int(x.gbits)
            if x.hc: p_["hc"] = 1
            if int(x.liq or 0): p_["liq"] = int(x.liq)
            if x.honored:
                p_["h"] = int(x.hon_flags or 0)
                if int(x.mi or 0): p_["mi"] = int(x.mi)
                if x.green: p_["gs"] = 1
                if x.s_icon == x.s_icon and x.s_icon is not None: p_["ip"] = round(float(x.s_icon), 1)
                if isinstance(x.jbf, str): p_["jbf"] = x.jbf
            if x.founded == x.founded and x.founded is not None: p_["f"] = int(float(x.founded))
            for k_, col in (("on", "opened_note"), ("bf", "brand_founded"), ("note", "rnote"), ("di", "dishes")):
                if isinstance(x[col], str) and x[col]: p_[k_] = x[col]
            web = x.rsite if isinstance(x.rsite, str) else (x.web if isinstance(x.web, str) and isinstance(x.dom, str) else None)
            if isinstance(web, str) and ("\u2026" in web or "..." in web):
                web = None
            if web:
                w_ = clean_url(web)
                link_cands[w_] = x.brand_n if isinstance(x.brand_n, str) else x.name_out
                scheme = re.match(r"^([a-z][a-z0-9+.-]*):", w_, re.I)
                if scheme and scheme.group(1).lower() not in ("http", "https"):
                    link_drops["not a web link"] += 1
                elif re.search(r"^(?:[a-z]+://)?(?:[^/]*\.)?(?:google|yelp|tripadvisor)\.[a-z.]+(?:/|$)|business\.site|goo\.gl|"
                               r"/(?:www\.)?(?:google|yelp|tripadvisor)\.[a-z.]+/", w_ + " " + (LINKS.get(w_, {}).get("final") or ""), re.I):
                    link_drops["directory or Google link"] += 1   # a second guard: never a map or review page, whatever the check said
                elif LINKS.get(w_, {}).get("ok"):   # only links pipeline/check_websites.py verified; without its file, none ship
                    p_["w"] = w_ if scheme else "https://" + w_
                    # a link that passed by redirecting to another site (a mail tracker, a shortener) ships as where it lands
                    fin = LINKS[w_].get("final") or ""
                    site_of = lambda u: ".".join(urllib.parse.urlparse(u if "//" in u else "https://" + u).netloc.lower().split(":")[0].split(".")[-2:])
                    if fin.startswith(("http://", "https://")) and site_of(fin) != site_of(p_["w"]):
                        p_["w"] = clean_url(fin)
                else:
                    link_drops[LINKS.get(w_, {}).get("why", "not checked yet")] += 1
            if (ph := phone_e164(x.phone)): p_["ph"] = ph
            if x.in_j is not None and x.in_j == x.in_j and JURS[int(x.in_j)][0] in APP_JURS:
                jx = int(x.in_j); jid = JURS[jx][0]; scale = JURS[jx][3]
                ins = {"j": APP_JURS.index(jid), "d": x.in_date, "n": r(x.in_n), "b": r(x.in_bad)}
                if x.in_res in scale: ins["r"] = scale.index(x.in_res)
                if x.in_score is not None and x.in_score == x.in_score: ins["s"] = r(x.in_score)
                p_["in"] = ins
            places.append(p_)
        fn = f"places-{rid}.json"
        json.dump({"region": rid, "cities": CITIES, "places": places}, open(f"{SITE}/{fn}", "w"), separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)
        sv = sub[~sub.venue]
        files.append({"id": rid, "name": rname, "file": fn, "counties": sorted(sub.county.dropna().unique().tolist()), "count": len(places),
                      "count_restaurants": int(len(sv)), "bytes": os.path.getsize(f"{SITE}/{fn}")})
        print(f"APP region {rid}: {len(places)} places, {os.path.getsize(f'{SITE}/{fn}') // 1024} KB", flush=True)
    json.dump(link_cands, open(f"{CA}/website_candidates.json", "w"), indent=0, ensure_ascii=False)
    print("website links dropped:", sum(link_drops.values()), link_drops.most_common(8), flush=True)
    calib_app = json.load(open(f"{CA}/calibration_app.json")) if os.path.exists(f"{CA}/calibration_app.json") else {}
    index = {"v": 1, "generated": str(pd.Timestamp.now().date()), "regions": files, "cuisines": CUIS, "brands": BRANDS, "sources": SRCS_A,
             "counties": COUNTIES_A, "guides": GUIDE_BITS, "liqt": LIQT,
             "jurs": [{"id": j, "name": n, "agency": a, "scale": sc, "through": str(THROUGH[j].date()),
                       "newest": gmeta_newest.get(j) if (gmeta_newest := {JURS[jx][0]: max(d for d, jj in zip(o.in_date, o.in_j) if jj == jx and isinstance(d, str))
                                                                          for jx in range(len(JURS)) if any(jj == jx for jj in o.in_j)}) else None}
                      for j, n, a, sc, _ in JURS if j in APP_JURS],
             "count": int(len(o)), "count_restaurants": int(len(nv_a)), "count_hc": int(nv_a.hc.sum()),
             "calibration": {k: v for k, v in calib_app.items() if k in ("lac", "sd")},
             "michelin": {"edition": "2026", "ceremony": "2026-06-24"}, "overture_release": "2026-09-23.1"}
    json.dump(index, open(f"{SITE}/index.json", "w"), separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)
    print("APP: wrote", len(o), "places (", len(nv_a), "restaurants ) in", len(files), "region files |",
          sum(f_["bytes"] for f_ in files) // 1024, "KB | hand-checked:", int(nv_a.hc.sum()), "| honored:", int(nv_a.honored.sum()), flush=True)
    sys.exit(0)
SRC = {"model": 0, "model-low": 1, "chain": 2, "reported": 3, "venue": 4}
TIER = {"listing": 0, "both": 1, "official": 2}
OJ = {None: 0, "lac": 1, "sd": 2, "sf": 3, "scc": 4, "sac": 5}
SCALE = {"lat": 10000, "lon": 10000, "rating": 10, "margin": 1000, "value_raw": 1000}
SRCS = ["official", "meta", "AllThePlaces", "DAC", "research", "BrightQuery", "Foursquare", "Microsoft"]
COUNTIES = sorted(o.county.dropna().unique().tolist())
cty = {c: i for i, c in enumerate(COUNTIES)}
ins_dates = [d for d in o.in_date.dropna()]
region_meta = []
for rid, rname, _ in REGIONS:
    sub = o[o.region == rid].reset_index(drop=True)
    CITIES = sorted(sub.city.dropna().unique().tolist()); CUIS = sorted(sub.cuisine.unique().tolist()); BRANDS = sorted(sub.brand_n.dropna().unique().tolist())
    ci, cu, br = {c: i for i, c in enumerate(CITIES)}, {c: i for i, c in enumerate(CUIS)}, {c: i for i, c in enumerate(BRANDS)}
    C = collections.OrderedDict((c, []) for c in ["name", "addr", "city", "zip", "lat", "lon", "cuisine", "brand", "chain_n", "rating", "reviews", "price",
                                                   "price_est", "rev_k", "rev_src", "margin", "value_raw", "tier", "jur", "bar", "venue", "tags", "src",
                                                   "liq", "county", "i_rating", "i_pop", "i_value", "i_profit"])
    SP = {"insp": [], "hon": []}
    extra = {}
    for i, x in sub.iterrows():
        tags = sum(1 << b for b, t in enumerate(TAGS) if bool(x["t_" + t]))
        z = int(x.zip[:5]) if isinstance(x.zip, str) and re.match(r"^9[0-6]\d{3}", x.zip) else None
        vals = {"name": x.name_out, "addr": nice(x.street, addr=True) if isinstance(x.street, str) else None,
                "city": ci.get(x.city) if isinstance(x.city, str) else None, "zip": z, "lat": x.lat, "lon": x.lon, "cuisine": cu[x.cuisine],
                "brand": br.get(x.brand_n) if isinstance(x.brand_n, str) else None, "chain_n": int(x.chain_n), "rating": x.rating, "reviews": r(x.reviews),
                "price": int(x.price), "price_est": int(x.price_est), "rev_k": int(round(x.rev / 1000)), "rev_src": SRC[x.rev_src], "margin": x.margin,
                "value_raw": x.value_raw, "tier": TIER[x.tier], "jur": OJ.get(x.area if isinstance(x.area, str) and x.off == x.off else None, 0),
                "bar": int(bool(x.bar)), "venue": int(bool(x.venue)), "tags": tags, "src": SRCS.index(x.src) if x.src in SRCS else 1,
                "liq": int(x.liq), "county": cty.get(x.county), "i_rating": r(x.i_rating), "i_pop": r(x.i_pop), "i_value": r(x.i_value), "i_profit": r(x.i_profit)}
        for c_, v in vals.items():
            if c_ in SCALE:
                v = None if v is None or v != v else int(round(float(v) * SCALE[c_]))
            elif isinstance(v, float):
                v = None if v != v else v
            C[c_].append(v.item() if hasattr(v, "item") else v)
        if x.honored:
            SP["hon"].append([i, int(round(x.s_icon * 10)), int(x.hon_flags), int(x.mi), int(bool(x.green))])
        if x.in_j is not None and x.in_j == x.in_j:
            jx = int(x.in_j); scale = JURS[jx][3]
            SP["insp"].append([i, jx, scale.index(x.in_res) if x.in_res in scale else None, r(x.in_score), x.in_date, r(x.in_n), r(x.in_bad)])
        e = {}
        if isinstance(x.abc_lic, str):
            e["abc"] = [x.abc_lic.split("-", 1)[1], x.abc_type]
        if x.in_j is not None and x.in_j == x.in_j:
            e["insp"] = {"lic": x.in_lic, "first": x.in_first, "mean": x.in_mean}
        if x.tier == "official" and x.off == x.off:
            e["rec"] = [x.area, F.lic.iat[int(x.off)], "list" if x.src == "official" else "match"]
        if x.honored:
            hl = []
            if x.mi:
                hl.append(["", "MICHELIN Guide California 2026: Recommended", "Bib Gourmand", "1 MICHELIN Star", "2 MICHELIN Stars", "3 MICHELIN Stars"][int(x.mi)]
                          + (" (MICHELIN Guide California 2026)" if x.mi > 1 else ""))
            if x.green:
                hl.append("MICHELIN Green Star (2026)")
            if isinstance(x.mi_note, str):
                hl.append("MICHELIN note: " + x.mi_note)
            if isinstance(x.jbf, str):
                hl += ["James Beard: " + v for v in x.jbf.split("; ")]
            e["honors"] = hl
        e = {k: v for k, v in e.items() if v is not None}
        if e:
            extra[i] = e
    snv = sub[~sub.venue]
    meta = {"region": rid, "region_name": rname, "cities": CITIES, "cuisines": CUIS, "brands": BRANDS, "count": len(sub), "count_restaurants": int(len(snv))}
    json.dump({"n": len(sub), "scale": SCALE, "cols": C, "sparse": SP, "meta": meta},
              open(f"{SITE}/ca_{rid}.json", "w"), separators=(",", ":"), allow_nan=False, default=str)
    json.dump({"n": len(sub), "extra": {str(k): v for k, v in extra.items()}}, open(f"{SITE}/ca_{rid}_detail.json", "w"), separators=(",", ":"), allow_nan=False, default=str)
    region_meta.append({"id": rid, "name": rname, "counties": sorted(sub.county.dropna().unique().tolist()), "count": len(sub),
                        "count_restaurants": int(len(snv)), "n_cities": int(snv.city.nunique()),
                        "bytes": os.path.getsize(f"{SITE}/ca_{rid}.json"), "detail_bytes": os.path.getsize(f"{SITE}/ca_{rid}_detail.json")})
    print(f"region {rid}: {len(sub)} places ({len(snv)} restaurants), {os.path.getsize(f'{SITE}/ca_{rid}.json') // 1024} KB", flush=True)

gmeta = {"generated": str(pd.Timestamp.now().date()), "regions": region_meta, "counties": COUNTIES, "src": list(SRC), "tiers": list(TIER), "tags": TAGS,
         "srcs": SRCS, "jurs": [{"id": j, "name": n, "agency": a, "scale": sc} for j, n, a, sc, _ in JURS],
         "rec_jurs": [None, "Los Angeles County", "San Diego County", "San Francisco", "Santa Clara County", "Sacramento County"],
         "liqt": LIQT, "la_no_card": sorted(LA_NO_CARD),
         "inspections_through": {j: str(THROUGH[j].date()) for j in THROUGH},
         "inspections_newest": {JURS[jx][0]: max(d for d, jj in zip(o.in_date, o.in_j) if jj == jx and isinstance(d, str)) for jx in range(len(JURS))
                                if any(jj == jx for jj in o.in_j)},
         "food_cost": dict(FOOD_COST), "spend": SPEND, "count": len(o), "count_restaurants": int(len(nv)),
         "count_official": int(nv.official.sum()), "count_both": int((nv.tier == "both").sum()), "count_listing": int((nv.tier == "listing").sum()),
         "count_abc": int(nv.off_abc.notna().sum()), "count_insp": int(nv.in_j.notna().sum()),
         "n_cities": int(nv.city.nunique()), "overture_release": "2026-09-23.1", "rating_mean": round(float(m_rat), 3),
         "model": {"b": B_FIT, "n_chains": n_auv}, "calibration": calib}
json.dump(gmeta, open(f"{SITE}/ca_meta.json", "w"), separators=(",", ":"), allow_nan=False, default=str)
json.dump(SH, open(f"{SITE}/ca_shapes.json", "w"), separators=(",", ":"))
o.drop(columns=["st"], errors="ignore").to_pickle(f"{CA}/stage2.pkl")
print("wrote", len(o), "places (", int(len(nv)), "restaurants ) in", nv.city.nunique(), "towns | tiers:", nv.tier.value_counts().to_dict(),
      "| regions:", {m_["id"]: m_["count"] for m_ in region_meta}, flush=True)
