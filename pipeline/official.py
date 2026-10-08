"""Official records for California: county food-facility permits and inspections, and the state's ABC alcohol licenses.

load() returns one table of official food/alcohol records with a normalized name key, street number and street key, the zip,
coordinates where the source has them, the jurisdiction and the record kind (restaurant, bar, retail, other). Sources (see
data/raw/official/SOURCES_*.md for URLs, terms and cadence):
  - lac  Los Angeles County DEH restaurant and market inventory (coordinates) + inspections with the official score and grade
  - sd   San Diego County DEHQ food facility permits (no coordinates, no inspections or grades in bulk)
  - abc  California ABC daily license export, active on-sale licenses statewide (no coordinates)
  - sf   San Francisco DPH health inspections 2024-present (official placard: Pass / Conditional Pass / Closure)
  - scc  Santa Clara County DEH businesses + inspections (official placard G/Y/R and score)
  - sac  Sacramento County EMD food facilities + inspection history (official placard PASS / CONDITIONAL PASS / CLOSED)
California has no statewide inspection list: each county (and Berkeley, Long Beach, Pasadena, Vernon) inspects on its own.
"""
import os, re, csv
import numpy as np, pandas as pd
from common import norm_name, RAW, street_key, street_nums, name_sim, _stems, GENERIC

OFF = os.path.join(RAW, "official")


def _names(*vals):
    out = []
    for v in vals:
        if not isinstance(v, str):
            continue
        for part in re.split(r"\s*/\s*|\s+\bdba\b\s+|\s+\baka\b\s+|\s+&\s+(?=[A-Z][a-z])", v, flags=re.I):
            part = re.sub(r"\s*#\s*\d+\w*\s*$", "", part)   # "CHRIS & PITTS BBQ #6"
            k = norm_name(re.sub(r"\b(?:LLC|INC|CORP|CORPORATION|LTD|CO)\b\.?", "", part, flags=re.I))
            if k and k not in out:
                out.append(k)
    return out


def _zip5(z):
    m = re.match(r"\s*(\d{5})", str(z or ""))
    return m.group(1) if m else None


def _read(path, **kw):
    """County files mix UTF-8 and Windows-1252 (LA County's apostrophes are 0x92)."""
    try:
        return pd.read_csv(path, dtype=str, **kw)
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype=str, encoding="cp1252", **kw)


def la_kind(pe):
    pe = (pe or "").upper()
    return "restaurant" if pe.startswith("RESTAURANT") else "retail" if pe.startswith("FOOD MKT") else "other"


def sd_kind(t):
    t = (t or "")
    if t == "Restaurant Food Facility":
        return "restaurant"
    if t in ("Retail Market with Deli", "Pre-Packaged Retail Market", "Retail Food Processing"):
        return "retail"
    return "other"


def sf_kind(t):
    t = (t or "").upper()
    if re.match(r"H2[4-6]R? |H28 ", t):
        return "restaurant"
    if re.match(r"H8[67] ", t):
        return "bar"
    if re.match(r"H0[37] |H88 ", t):
        return "retail"
    return "other"


def sac_kind(t):
    t = (t or "").strip().upper()
    return {"RESTAURANT": "restaurant", "RESTAURANT WITH BAR": "restaurant", "BAR": "bar", "FOOD PREP ESTAB": "food"}.get(t,
            "retail" if t.startswith("RETAIL MARKET") else "other")


ABC_KIND = {"restaurant": "restaurant", "restaurant (brewpub)": "restaurant", "restaurant (seasonal)": "restaurant", "restaurant (SF special)": "restaurant",
            "bar": "bar", "bar/other (seasonal)": "bar", "music venue": "bar", "brewery/taproom (manufacturer)": "taproom",
            "winery tasting room (manufacturer)": "winery", "distillery (manufacturer)": "other", "club": "club", "club/organization": "club",
            "hotel guests only": "other", "caterer": "other", "special use": "other"}
# on-sale license types that let a restaurant or bar serve: 41/59 beer & wine eating place, 47/49/87 general eating place, 75 brewpub,
# 40/42/48/60/61 bars and taverns, 90 music venue
ABC_SERVES = {"41": "beer & wine", "59": "beer & wine", "47": "full bar", "49": "full bar", "87": "full bar", "75": "beer & wine (brewpub)",
              "40": "beer", "60": "beer", "61": "beer", "42": "beer & wine", "48": "full bar", "90": "full bar"}


ALL = ("lac", "sd", "abc", "sf", "scc", "sac")


def load(jurs=ALL):
    """Cached in data/ca/official_<jurs>.pkl until a source file changes (building it takes minutes)."""
    import glob, pickle
    from common import CA
    srcs = sorted(glob.glob(f"{OFF}/*/*.csv"))
    sig = [(f, os.path.getmtime(f)) for f in srcs]
    cache = f"{CA}/official_{'_'.join(jurs)}.pkl"
    if os.path.exists(cache):
        got = pickle.load(open(cache, "rb"))
        if got["sig"] == sig:
            return got["df"]
    df = _load(jurs)
    pickle.dump({"sig": sig, "df": df}, open(cache, "wb"))
    return df


def _load(jurs):
    rows = []
    if "lac" in jurs:
        f = _read(f"{OFF}/lacounty/inventory.csv")
        f = f.rename(columns=lambda c: re.sub(r"\s+", "_", c.strip()).lower())
        for _, r in f.iterrows():
            num, st = street_key(r.facility_address)
            la, lo = pd.to_numeric(r.facility_latitude, errors="coerce"), pd.to_numeric(r.facility_longitude, errors="coerce")
            rows.append({"jur": "lac", "lic": r.record_id, "fac": r.facility_id, "name": r.facility_name, "keys": _names(r.facility_name, r.program_name),
                         "addr": r.facility_address, "city": r.facility_city, "zip": _zip5(r.facility_zip), "num": num, "street": st,
                         "lat": la if la and la == la and la > 30 else np.nan, "lon": lo if lo and lo == lo and lo < -100 else np.nan,
                         "kind": la_kind(r.pe_description), "pe": r.pe_description, "active": True, "since": None})
    if "sd" in jurs:
        f = _read(f"{OFF}/sandiego/food_facility_permits.csv").drop_duplicates("record_id")
        for _, r in f.iterrows():
            num, st = street_key(r.address)
            rows.append({"jur": "sd", "lic": r.record_id, "fac": r.record_id, "name": r.record_name, "keys": _names(r.record_name),
                         "addr": r.address, "city": r.city, "zip": _zip5(r.zip), "num": num, "street": st, "lat": np.nan, "lon": np.nan,
                         "kind": sd_kind(r.business_type), "pe": r.business_type, "active": r.permit_status != "Expired", "since": None})
    if "abc" in jurs:
        f = _read(f"{OFF}/abc/abc_onsale_active.csv")
        for _, r in f.iterrows():
            addr = r.prem_addr_1
            num, st = street_key(addr)
            rows.append({"jur": "abc", "lic": "ABC-" + r.file_number, "fac": "ABC-" + r.file_number, "name": r.dba_name if isinstance(r.dba_name, str) else None,
                         # the licensee's own name can be a person's: it only helps matching, it is never shown
                         "keys": _names(r.dba_name) or _names(r.primary_name), "addr": addr, "city": r.prem_city, "zip": _zip5(r.prem_zip),
                         "num": num, "street": st, "lat": np.nan, "lon": np.nan, "kind": ABC_KIND.get(r.our_bucket, "other"),
                         "pe": r.license_type, "active": True, "since": r.orig_iss_date, "county": r.prem_county})
    if "sf" in jurs:
        f = _read(f"{OFF}/sf/inspections_2024_present_tvy3-wexg.csv")
        f = f[f.permit_number.notna()].sort_values("inspection_date").drop_duplicates("permit_number", keep="last")
        for _, r in f.iterrows():
            num, st = street_key(r.street_address_clean if isinstance(r.street_address_clean, str) else r.street_address)
            la, lo = pd.to_numeric(r.latitude, errors="coerce"), pd.to_numeric(r.longitude, errors="coerce")
            rows.append({"jur": "sf", "lic": "SF-" + r.permit_number, "fac": "SF-" + r.permit_number, "name": r.dba, "keys": _names(r.dba),
                         "addr": re.sub(r"\s+", " ", r.street_address or ""), "city": "San Francisco", "zip": None, "num": num, "street": st,
                         "lat": la, "lon": lo, "kind": sf_kind(r.permit_type), "pe": r.permit_type, "active": True, "since": None})
    if "scc" in jurs:
        f = _read(f"{OFF}/santaclara/businesses_vuw7-jmjk.csv")
        for _, r in f.iterrows():
            num, st = street_key(r.address)
            la, lo = pd.to_numeric(r.latitude, errors="coerce"), pd.to_numeric(r.longitude, errors="coerce")
            rows.append({"jur": "scc", "lic": r.business_id, "fac": r.business_id, "name": r["name"], "keys": _names(r["name"]),
                         "addr": r.address, "city": r.city, "zip": _zip5(r.postal_code), "num": num, "street": st,
                         "lat": la if la == la and la > 30 else np.nan, "lon": lo if lo == lo and lo < -100 else np.nan,
                         "kind": "food", "pe": None, "active": True, "since": None})   # the county's file has no facility type
    if "sac" in jurs:
        f = _read(f"{OFF}/sacramento/facilities_layer0.csv").drop_duplicates("Facility_ID")
        for _, r in f.iterrows():
            a = r.Facility_Address or ""
            m = re.match(r"^(.*?),\s*([A-Za-z .']+?)\s+(\d{5})", a)
            street, city, z = (m.group(1), m.group(2), m.group(3)) if m else (a, None, None)
            num, st = street_key(street)
            la, lo = pd.to_numeric(r.latitude, errors="coerce"), pd.to_numeric(r.longitude, errors="coerce")
            rows.append({"jur": "sac", "lic": r.Facility_ID, "fac": r.Facility_ID, "name": r.Facility_Name, "keys": _names(r.Facility_Name),
                         "addr": street, "city": city, "zip": z, "num": num, "street": st, "lat": la, "lon": lo,
                         "kind": sac_kind(r.Description), "pe": (r.Description or "").strip(), "active": True, "since": None})
    df = pd.DataFrame(rows)
    # one business can hold several records (LA County: a restaurant program and a market program; ABC: duplicate licenses):
    # same jurisdiction, same address and a name in common
    df["biz"] = np.arange(len(df))
    for (jur, num, st), g in df[df.num.notna() & df.street.notna()].groupby(["jur", "num", "street"]):
        idx = list(g.index)
        if len(idx) < 2:
            continue
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                if df.at[idx[a], "zip"] != df.at[idx[b], "zip"]:
                    continue
                ka, kb = df.at[idx[a], "keys"], df.at[idx[b], "keys"]
                same = any(name_sim(x, y) >= 85 or ((_stems(x) - GENERIC) & (_stems(y) - GENERIC)) for x in ka for y in kb)
                if same:
                    old, new = df.at[idx[b], "biz"], df.at[idx[a], "biz"]
                    df.loc[df.biz == old, "biz"] = new
    return df


def la_inspections():
    """LA County routine and owner-initiated inspections (Oct 2023 on), with the official score and letter grade as recorded."""
    i = _read(f"{OFF}/lacounty/inspections.csv")
    i.columns = [re.sub(r"\s+", "_", c.strip()).lower() for c in i.columns]
    i["d"] = pd.to_datetime(i.activity_date.str.strip(), format="%m/%d/%Y", errors="coerce")
    i["score"] = pd.to_numeric(i.score, errors="coerce")
    return i


def la_violations():
    v = _read(f"{OFF}/lacounty/violations.csv")
    v.columns = [re.sub(r"\s+", "_", c.strip()).lower() for c in v.columns]
    v["points"] = pd.to_numeric(v.points, errors="coerce")
    return v


# ---------------------------------------------------------------- inspections: each jurisdiction's own official result, never blended
def _routine_summary(d, key, date, result, score=None, bad=()):
    """Per facility: visits in the window, the latest result (grade or placard) with its date and score, and how many visits
    ended in one of the `bad` results. Results are what the agency recorded; nothing is computed from violations."""
    d = d[d[date].notna()].sort_values(date)
    g = d.groupby(key)
    out = pd.DataFrame({"n_insp": g.size(), "n_bad": g[result].agg(lambda x: int(x.isin(bad).sum()))})
    last = g.tail(1).set_index(key)
    out["last_date"] = last[date].dt.strftime("%Y-%m-%d").reindex(out.index)
    out["last_result"] = last[result].reindex(out.index)
    if score:
        out["last_score"] = last[score].reindex(out.index)
        out["mean_score"] = g[score].mean().round(1)
    first = g.head(1).set_index(key)
    out["first_date"] = first[date].dt.strftime("%Y-%m-%d").reindex(out.index)
    return out


def inspections(through):
    """{jur: per-facility summary}. `through`: {jur: last date to count} (publication lag: at least 7 days before the fetch)."""
    out = {}
    i = la_inspections()
    i = i[(i.d <= through["lac"]) & i.score.notna()]
    i["grade"] = i.grade.fillna("").str.strip().replace("", None)
    out["lac"] = _routine_summary(i, "record_id", "d", "grade", "score", bad=("B", "C"))
    f = _read(f"{OFF}/sf/inspections_2024_present_tvy3-wexg.csv")
    f["d"] = pd.to_datetime(f.inspection_date, errors="coerce")
    f = f[(f.d <= through["sf"]) & f.facility_rating_status.notna() & f.permit_number.notna()]
    f["key"] = "SF-" + f.permit_number
    f = f.drop_duplicates(["key", "d", "facility_rating_status"])
    out["sf"] = _routine_summary(f, "key", "d", "facility_rating_status", bad=("Conditional Pass", "Closure"))
    c = _read(f"{OFF}/santaclara/inspections_2u2d-8jej.csv")
    c["d"] = pd.to_datetime(c.date, format="%Y%m%d", errors="coerce")
    c["score"] = pd.to_numeric(c.score, errors="coerce")
    c = c[(c.d <= through["scc"]) & c.result.isin(["G", "Y", "R"])]
    out["scc"] = _routine_summary(c, "business_id", "d", "result", "score", bad=("Y", "R"))
    h = _read(f"{OFF}/sacramento/inspection_violation_history_table1.csv")
    h["d"] = pd.to_datetime(h.Inspection_Date_utc_date, errors="coerce")
    # only the three values that are placards; IN COMPLIANCE, MINOR/CRITICAL VIOLATIONS and NOT APPLICABLE are not
    h = h[(h.d <= through["sac"]) & h.Inspection_Result.isin(["PASS", "CONDITIONAL PASS", "CLOSED"])]
    h = h.drop_duplicates(["Facility_ID", "d", "Inspection_Result"])
    out["sac"] = _routine_summary(h, "Facility_ID", "d", "Inspection_Result", bad=("CONDITIONAL PASS", "CLOSED"))
    return out
