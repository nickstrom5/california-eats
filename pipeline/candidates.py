"""Research candidates for the app's hand-checked guides -> data/research/candidates/<guide>_<region>.json

Built only from map listings (Overture: name, category, address, website, phone) and county records, never from Google data, so
what the guides include doesn't depend on Google. A candidate is a lead, not a guide entry: a researcher confirms each one open with
a 2025-26 source (data/research/BRIEF.md). Places with their own website come first, since that's where the check starts.
"""
import os, re, json
import numpy as np, pandas as pd
from shapely.geometry import shape, Point, Polygon
from shapely.prepared import prep
from shapely.ops import unary_union
from common import CA, DATA, norm_name

o = pd.read_pickle(f"{CA}/stage1.pkl")
conf = o.confidence.fillna(0)
o = o[~o.j_junk & ~o.j_closedname & ~o.j_outside & ~o.ov_closed & (((o.src == "meta") & (conf >= 0.9)) | o.src.isin(["AllThePlaces", "DAC"]))].copy()
SH = json.load(open(f"{CA}/ca_shapes.json"))
# exact county outlines (valid, from Overture divisions), not the simplified map rings, which can self-intersect
CTY = [(c["name"], prep(shape(json.load(open(f"{CA}/county_{c['name'].replace(' ', '_')}.geojson"))).buffer(0.0005))) for c in SH["counties"]]
o["county"] = [next((n for n, p in CTY if p.contains(Point(x, y))), None) for x, y in zip(o.lon, o.lat)]
REG = {"la": ["Los Angeles County"], "oc": ["Orange County"], "sd": ["San Diego County", "Imperial County"], "ie": ["Riverside County", "San Bernardino County"],
       "cc": ["Ventura County", "Santa Barbara County", "San Luis Obispo County", "Monterey County", "Santa Cruz County", "San Benito County"],
       "bay": ["San Francisco", "San Mateo County", "Santa Clara County", "Alameda County", "Contra Costa County", "Marin County", "Napa County", "Sonoma County", "Solano County"],
       "sac": ["Sacramento County", "Placer County", "El Dorado County", "Yolo County", "Sutter County", "Yuba County"],
       "cv": ["San Joaquin County", "Stanislaus County", "Merced County", "Madera County", "Fresno County", "Kings County", "Tulare County", "Kern County"]}
reg_of = {c: r for r, cs in REG.items() for c in cs}
o["region"] = o.county.map(lambda c: reg_of.get(c, "north") if isinstance(c, str) else None)
k = o.name.map(norm_name).fillna("")
CHAINS = r"^(?:TACO BELL|DEL TACO|CHIPOTLE|QDOBA|RUBIOS|BAJA FRESH|EL POLLO LOCO|CHRONIC TACOS|WAHOOS|TACO JOHN|TACO CABANA|CAFE RIO|COSTA VIDA|PANDA EXPRESS|PF CHANG|MCDONALDS|BURGER KING|JACK IN THE BOX|CARLS JR|WENDYS|SONIC|HABIT|FIVE GUYS|SHAKE SHACK|SMASHBURGER|RED ROBIN|FATBURGER|JOHNNY ROCKETS|FARMER BOYS|ISLANDS|ORIGINAL TOMMYS|TOMMYS)\b"
GUIDES = {
    "taqueria": (k.str.contains(r"\bTAQUERIAS?\b|\bTACOS?\b|\bTACO SHOP\b|\bTACOS Y\b") | o.tax.eq("taco_restaurant")) & ~k.str.contains(CHAINS),
    "burrito": k.str.contains(r"\bBURRITOS?\b|\bTAQUERIA\b") & o.region.isin(["bay", "sd"]) & ~k.str.contains(CHAINS),
    "fishtaco": (k.str.contains(r"\bFISH TACOS?\b|\bMARISCOS\b|\bBAJA\b") | (o.tax.eq("seafood_restaurant") & k.str.contains(r"\bTACOS?\b"))) & o.region.isin(["sd", "oc", "la"]) & ~k.str.contains(CHAINS),
    "dimsum": k.str.contains(r"\bDIM SUM\b|\bDIMSUM\b|\bYUM CHA\b|\bDUMPLINGS?\b|\bSEAFOOD RESTAURANT\b.*|\bBAO\b") & (o.tax.isin(["chinese_restaurant", "dim_sum_restaurant", "cantonese_restaurant", "seafood_restaurant", "dumpling_restaurant"]) | k.str.contains(r"\bDIM SUM\b|\bDIMSUM\b|\bYUM CHA\b")),
    "kbbq": k.str.contains(r"\bKOREAN (?:BBQ|BARBECUE|BARBEQUE|GRILL)\b|\bKBBQ\b|\bK BBQ\b|\bGALBI\b|\bKALBI\b|\bGOGI\b|\bSAMGYUPSAL\b|\bSAMGYEOPSAL\b|\bKOREAN B B Q\b") | (o.tax.eq("korean_restaurant") & k.str.contains(r"\bBBQ\b|\bBARBECUE\b|\bGRILL\b")),
    "burgerstand": k.str.contains(r"^IN N OUT\b|\bDRIVE IN\b|\bDRIVE INN\b|\bBURGER STAND\b|\bHAMBURGER STAND\b|\bBURGER SHACK\b|\bFREEZE\b") & ~k.str.contains(r"^(?:MCDONALDS|BURGER KING|JACK IN THE BOX|CARLS JR|SONIC)\b"),
}
out = os.path.join(DATA, "research", "candidates")
os.makedirs(out, exist_ok=True)
summary = {}
for g, sel in GUIDES.items():
    d = o[sel & o.region.notna()].copy()
    d["own_site"] = d.dom.notna()
    d = d.sort_values(["region", "own_site", "name"], ascending=[True, False, True])
    for rid, grp in d.groupby("region"):
        recs = [{"name": r.name, "address": r.street, "city": r.city, "zip": (str(r.zip)[:5] if isinstance(r.zip, str) else None), "county": r.county,
                 "website": r.web if isinstance(r.web, str) and isinstance(r.dom, str) else None, "phone": r.phone if isinstance(r.phone, str) else None,
                 "brand": r.brand if isinstance(r.brand, str) else None, "category": r.tax}
                for r in grp.itertuples()]
        json.dump(recs, open(f"{out}/{g}_{rid}.json", "w"), indent=0, ensure_ascii=False)
        summary.setdefault(g, {})[rid] = [len(recs), int(grp.own_site.sum())]
print(json.dumps(summary, indent=0))
