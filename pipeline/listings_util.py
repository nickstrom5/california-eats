"""Matching map listings to official records (used by calibrate.py and california.py).

Adapted from wa-eats/pipeline/listings_util.py. California's statewide ABC licenses and San Diego's permits carry no coordinates,
so a record without a location matches only at the same street address AND the same zip code: "1200 Main St" exists in dozens
of California towns.
"""
import math
from rapidfuzz import fuzz
from common import name_sim, _stems, GENERIC, street_key, street_nums, undir, street_eq


def _close_words(a, b):
    """A distinctive word in common, allowing a spelling slip ("HIMAL CHULI" / "HIMALI CHULO")."""
    return any(x == y or (len(x) >= 5 and len(y) >= 5 and fuzz.ratio(x, y) >= 85) for x in a for y in b)


def official_match(L, R, one_to_one=False, town_words=frozenset(), street_col="street"):
    """L: listings with k (name key), street, zip, lat, lon. R: official records with keys, num, street, addr, zip, lat, lon.
    Returns {listing index: official index}. A match needs the same business name nearby, or the same street address
    (and zip, when the record has no location) with a distinctive (non-generic, non-town) name word in common."""
    by_addr, grid = {}, {}
    for j, (a, st) in enumerate(zip(R.addr, R.street)):
        for n in street_nums(a):
            if st:
                by_addr.setdefault((n, undir(st)), []).append(j)
    for j, (la, lo) in enumerate(zip(R.lat, R.lon)):
        if la == la and lo == lo:
            grid.setdefault((round(la / 0.0015), round(lo / 0.002)), []).append(j)
    rstems = [set().union(*[(_stems(k) - GENERIC - town_words) for k in ks]) if ks else set() for ks in R["keys"]]
    rnums = [street_nums(a) for a in R.addr]
    rzip = list(R["zip"]) if "zip" in R else [None] * len(R)
    lzip = list(L["zip"]) if "zip" in L else [None] * len(L)
    pairs = []
    for i, (k, street, la, lo) in enumerate(zip(L.k, L[street_col], L.lat, L.lon)):
        if not k:
            continue
        _, st = street_key(street)
        nums = street_nums(street)
        z = (str(lzip[i])[:5] if isinstance(lzip[i], str) else None)
        cand = set()
        for n in nums:
            cand.update(j for j in by_addr.get((n, undir(st)), []) if street_eq(st, R.street.iat[j]))
        if la == la:
            gy, gx = round(la / 0.0015), round(lo / 0.002)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    cand.update(grid.get((gy + dy, gx + dx), []))
        mine = _stems(k) - GENERIC - town_words
        for j in cand:
            same_addr = bool(st and street_eq(R.street.iat[j], st) and nums & rnums[j])
            rl, ro = R.lat.iat[j], R.lon.iat[j]
            located = rl == rl and la == la
            if same_addr and not located and not (z and rzip[j] and z == rzip[j]):
                continue   # no location to check against: the zip has to agree
            dist = math.hypot((rl - la) * 111000, (ro - lo) * 92000) if located else (40 if same_addr else 9999)
            s = max((name_sim(k, rk) for rk in R["keys"].iat[j]), default=0)
            shared = bool(mine & rstems[j]) or _close_words(mine, rstems[j])
            if (same_addr and (s >= 75 or shared)) or (dist <= 150 and s >= 88) or (dist <= 60 and s >= 80 and shared):
                pairs.append((s + (15 if same_addr else 0) - dist / 20, i, j))
    out, taken_l, taken_r = {}, set(), set()
    for sc, i, j in sorted(pairs, key=lambda t: -t[0]):
        if i in taken_l or (one_to_one and j in taken_r):
            continue
        taken_l.add(i); taken_r.add(j); out[i] = j
    return out
