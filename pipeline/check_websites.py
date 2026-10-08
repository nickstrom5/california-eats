"""Checks every website link the app ships before it ships, because map listings carry stale and hijacked domains.

Chicago found about 3% of its listing websites redirected to gambling, betting or adult sites, including a starred restaurant's.
A link survives only if:
  - the final response is 2xx,
  - it stays on the same registered domain (or the page plainly belongs to the place),
  - the page mentions a distinctive word of the place's name,
  - and nothing looks like gambling spam, adult content, a parked or for-sale domain, an expired account or "coming soon".
A site that blocks the check, times out or errors is dropped too: no link beats a wrong link. The one exception is a chain's own
domain (mcdonalds.com for McDonald's): when its sample pages refuse the check (403, 429, connection refused), the links stay, because
the domain plainly belongs to the brand.

Polite by design: an honest user agent, one request at a time per host, and three sample pages for a chain's own domain (5+ places,
80%+ one brand). Shared hosts (Square, Wix, Linktree, Instagram) carry many unrelated places, so every link there is checked on its own.
Never bypasses bot protection.

Usage: ../.venv/bin/python check_websites.py   (reads data/ca/website_candidates.json) → data/ca/website_check.json ({url: {"ok": bool, "why": str, "final": str}})
The app export (california.py, CA_APP=1) drops every link that isn't ok. Re-run before each App Store submission.
"""
import collections
import json
import os
import re
import threading
import time
import sys
import unicodedata
import zlib
import glob
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = f"{ROOT}/data/ca/website_check.json"
# --shard i/n: check only the registered domains that hash to i (n processes side by side, each domain still in one process, one
# request at a time); writes website_check.shard<i>.json. --merge folds the shard files into website_check.json.
_arg = dict(zip(sys.argv[1::2], sys.argv[2::2])) if len(sys.argv) > 2 else {}
SHARD = tuple(map(int, _arg["--shard"].split("/"))) if "--shard" in _arg else None


def shard_file(i, n):
    return OUT.replace(".json", f".shard{i}of{n}.json")


def save(obj, path, **kw):
    """Write to a temp file, then rename: a run stopped mid-save once left a truncated website_check.json (24,000 checks lost)."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, **kw)
    os.replace(tmp, path)


def mine(dom, shard=None):
    shard = shard or SHARD
    return shard is None or zlib.crc32(dom.encode()) % shard[1] == shard[0]
UA = "CaliforniaEatsLinkCheck/1.0 (+https://nickstrom5.github.io/california-eats/)"
GENERIC = set("""the and of a an at on in restaurant restaurants bar bars grill grille cafe caffe coffee pizza pizzeria pub tavern house
supper club inn lounge kitchen bistro eatery diner bakery deli market express food foods co company inc llc ltd corp
family original new old north south east west st saint mt sports place spot shop shoppe taproom brewing brewery
tap taps bbq barbecue burger burgers chicken subs sub sandwich sandwiches tacos taco mexican chinese thai sushi asian italian
american cuisine catering events ca california los angeles san francisco diego jose sacramento
fresno oakland la sf""".split())
# Hijacked domains carry Indonesian slot and lottery spam, Turkish betting pages or porn links: any of these marks a page.
SPAM = re.compile(r"slot ?gacor|situs (?:slot|judi|togel)|slot online|\bslot ?88\b|\btogel\b|judi (?:online|bola|slot|qq|poker)|perjudian|"
                  r"bandar ?(?:slot|qq|togel)|\bmaxwin\b|\brtp slot|\bsbobet\b|\bbahis|casino siteleri|\b1win\b|watch porn|free porn|"
                  r"porn videos?|\bpornhub\b|\bxvideos\b|\bxnxx\b|escort service|adult dating|sex cam|camgirl", re.I)
BLOBS = re.compile(r"[A-Za-z0-9+/=_-]{100,}")   # base64 images and tokens: random letters spell anything
# Words a real casino's restaurant or a brewery near the sportsbook uses too: they count only in the page title or description,
# or repeated in the body, and never on a casino's own page.
BETTING = re.compile(r"online casino|casino online|deposit bonus|sportsbook|\bbaccarat\b|bet365|no deposit", re.I)
HEAD = re.compile(r"<title[^>]*>(.*?)</title>|<meta[^>]+name=.description.[^>]+content=\"([^\"]*)", re.S)
CASINO_PLACE = re.compile(r"casino|gaming|potawatomi|ho-?chunk|oneida|menominee|mohican|north ?star|lake of the torches|"
                          r"st\.? ?croix|bad river|legendary waters|isle vista|grindstone", re.I)
PARKED = re.compile(r"domain (?:is|may be) for sale|buy this domain|this domain is parked|parked free|sedoparking|hugedomains|"
                    r"afternic|domain has expired|this domain name has expired|account (?:has been )?suspended|website coming soon|"
                    r"site (?:is )?coming soon|future home of|launching soon|godaddy\.com/domainsearch|dan\.com", re.I)
# directories, listings, review sites, shorteners and fundraisers: not the place's own page
BAD_HOSTS = ("business.site", "negocio.site", "google.", "goo.gl", "g.co/", "share.google", "yelp.", "tripadvisor.",   # "google." = google.com.mx too
             "facebook.com/pages", "doordash.com", "grubhub.com", "ubereats.com", "seamless.com", "allmenus.com", "menupix.com",
             "zmenu.com", "restaurantji.com", "yellowpages.com", "superpages.com", "whitepages.com", "chamberofcommerce.com",
             "cortera.com", "dandb.com", "bizapedia.com", "city-data.com", "mapquest.com", "citysearch.com", "yahoo.com", "hub.biz",
             "edan.io", "poi.place", "placeweb.site", "jany.io", "lany.io", "keeq.io", "restoguides.com", "dinehere.us", "foodspot.com",
             "gastrobars.com", "indulgery.com", "clubplanet.com", "restaurant.com", "groupon.com", "seatgeek.com", "opentable.com",
             "menuism.com", "barfinder.com", "friendseat.com", "local.com", "usplaces.com", "foodeist.com", "jmaps.net", "kwickmenu.com",
             "tinyurl.com", "bit.ly", "forms.gle", "gofund.me", "gofundme.com", "cash.app", "tiktok.com", "reverbnation.com",
             "yesware.com", "mailtrack.io", "list-manage.com", "ct.sendgrid.net", "click.mailchimp.com")   # mail trackers
SHADY = re.compile(r"(?:^|\.)food\d+\.com$|\.top$")   # food73.com-style listing farms, .top redirect farms
# a brand that moved its stores to a short domain
ALIASES = {"burgerking.com": "bk.com"}
BLOCKED = re.compile(r"^(?:http 40[39]|http 429|error: (?:ConnectionError|ConnectTimeout|ReadTimeout))$")


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s.replace("'", "")).strip()


def regdom(host):
    parts = host.lower().removeprefix("www.").split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def bad_host(url):
    """Matches a listed site by its host, not as a substring: "restaurant.com" must not catch madersrestaurant.com
    (that bug dropped 171 restaurants' own links). Entries with a path ("facebook.com/pages", "g.co/") match host + path."""
    u = urllib.parse.urlparse(url if "//" in url else "https://" + url)
    host = u.netloc.lower().split("@")[-1].split(":")[0].removeprefix("www.")
    for b in BAD_HOSTS:
        if "/" in b:
            bh, bp = b.split("/", 1)
            if (host == bh or host.endswith("." + bh)) and u.path.lower().lstrip("/").startswith(bp):
                return True
        elif b.endswith("."):   # "tripadvisor." = any tripadvisor domain
            if host.startswith(b) or ("." + b) in ("." + host):
                return True
        elif host == b or host.endswith("." + b):
            return True
    # a tracker or wrapper whose path carries a directory page (t.yesware.com/tt/…/www.yelp.com/reservations/…)
    if re.search(r"/(?:www\.)?(?:google|yelp|tripadvisor|doordash|grubhub|ubereats)\.[a-z.]+/", u.path, re.I):
        return True
    return bool(SHADY.search(regdom(host)))


def words(name):
    return [w for w in norm(name).split() if len(w) >= 4 and w not in GENERIC]


host_locks = collections.defaultdict(threading.Lock)
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "text/html,*/*;q=0.5", "Accept-Language": "en-US"})


def check(url, name):
    u = url if url.startswith("http") else "https://" + url
    host = urllib.parse.urlparse(u).netloc.lower()
    if bad_host(u):
        return {"ok": False, "why": "directory or Google link", "final": u}
    with host_locks[regdom(host)]:
        try:
            r = session.get(u, timeout=(8, 15), allow_redirects=True, stream=True)
            body = r.raw.read(400_000, decode_content=True).decode(r.encoding or "utf-8", "ignore") if r.ok else ""
            final = r.url
            r.close()
        except Exception as e:
            return {"ok": False, "why": "error: " + type(e).__name__, "final": u}
        finally:
            time.sleep(0.3)
    if not r.ok:
        return {"ok": False, "why": f"http {r.status_code}", "final": final}
    text = BLOBS.sub(" ", body).lower()
    head = " ".join(a or b for a, b in HEAD.findall(text[:60_000]))
    casino = CASINO_PLACE.search(name) or CASINO_PLACE.search(urllib.parse.urlparse(final).netloc)
    if SPAM.search(text) or SPAM.search(final) or (not casino and (BETTING.search(head) or len(BETTING.findall(text)) >= 2)):
        return {"ok": False, "why": "gambling or adult content", "final": final}
    if PARKED.search(text[:60_000]):
        return {"ok": False, "why": "parked, expired or coming soon", "final": final}
    if bad_host(final):
        return {"ok": False, "why": "redirects to a directory", "final": final}
    ws = words(name)
    page = norm(re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S)) + " " + norm(final)
    mentions = not ws or any(w in page for w in ws)
    same = regdom(urllib.parse.urlparse(final).netloc) in (regdom(host), ALIASES.get(regdom(host)))
    if not mentions:
        return {"ok": False, "why": "page doesn't mention the place", "final": final}
    if not same and not any(w in norm(urllib.parse.urlparse(final).netloc) for w in ws):
        return {"ok": False, "why": "moved to another domain", "final": final}
    return {"ok": True, "why": "ok", "final": final}


OUT_W = shard_file(*SHARD) if SHARD else OUT


def merge():
    """Each shard file holds the old results plus its own new ones: take a URL from the shard that owns its domain."""
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    files = sorted(glob.glob(OUT.replace(".json", ".shard*.json")))
    for f in files:
        i, n = map(int, re.search(r"shard(\d+)of(\d+)", f).groups())
        for u, v in json.load(open(f)).items():
            dom = regdom(urllib.parse.urlparse(u if u.startswith("http") else "https://" + u).netloc)
            if mine(dom, (i, n)) or u not in out:
                out[u] = v
    save(out, OUT, indent=0)
    for f in files:
        os.remove(f)
    print(f"merged {len(files)} shard files: {len(out)} links")


def main():
    # every link the export considered (written by california.py, CA_APP=1), so a link dropped last time gets another chance
    cands = json.load(open(f"{ROOT}/data/ca/website_candidates.json"))
    jobs = collections.defaultdict(list)   # registered domain -> [(url, name)]
    for w, name in cands.items():
        u = w if w.startswith("http") else "https://" + w
        jobs[regdom(urllib.parse.urlparse(u).netloc)].append((w, name))
    prev = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for f in sorted(glob.glob(OUT.replace(".json", ".shard*.json"))):   # an unmerged sharded run counts as done too
        prev.update(json.load(open(f)))
    # chain verdicts are recomputed every run; host rules may have grown since a page was fetched
    prev = {u: v for u, v in prev.items() if not v["why"].startswith(("chain domain", "brand's own"))
            and v["why"] not in ("moved to another domain", "gambling or adult content", "directory or Google link", "redirects to a directory")}
    todo, chain_hosts, brand_of = [], {}, {}
    for dom, items in jobs.items():
        if not mine(dom):
            continue
        uniq = list(dict.fromkeys(items))
        top, n = collections.Counter(name for _, name in uniq).most_common(1)[0]
        if len(uniq) >= 5 and n >= 0.8 * len(uniq):   # a chain's own domain: three samples stand for all
            chain_hosts[dom] = [u for u, _ in uniq]
            brand_of[dom] = top
            todo += uniq[:3]
        else:
            todo += uniq
    for u, v in prev.items():   # host rules apply to cached pages too, no request needed
        if v["ok"] and (bad_host(u) or bad_host(v["final"])):
            prev[u] = {"ok": False, "why": "redirects to a directory", "final": v["final"]}
    todo = [(u, n) for u, n in todo if u not in prev]
    print(f"{sum(len(v) for v in jobs.values())} links, {len(jobs)} domains, {len(chain_hosts)} chain domains; checking {len(todo)}")
    results, done = dict(prev), 0
    lock = threading.Lock()

    def run(item):
        nonlocal done
        res = check(*item)
        with lock:
            results[item[0]] = res
            done += 1
            if done % 500 == 0:
                print(f"  {done}/{len(todo)}", flush=True)
                save(results, OUT_W)

    with ThreadPoolExecutor(max_workers=96 // (SHARD[1] if SHARD else 1)) as ex:   # one request per registered domain at a time either way (host_locks)
        list(ex.map(run, todo))
    for dom, urls in chain_hosts.items():
        samples = [results.get(u) for u in urls[:3] if results.get(u)]
        verdict = bool(samples) and sum(s["ok"] for s in samples) >= 2
        why = "chain domain " + ("ok" if verdict else "failed its samples")
        own = any(w in norm(dom) for w in words(brand_of[dom]))
        if not verdict and own and samples and all(s["ok"] or BLOCKED.match(s["why"]) for s in samples):
            verdict, why = True, "brand's own site (blocked the check)"
            for u in urls[:3]:
                results[u] = {**results[u], "ok": True, "why": why}
        for u in urls[3:]:
            results[u] = {"ok": verdict, "why": why, "final": u}
    save(results, OUT_W, indent=0)
    c = collections.Counter(v["why"] if not v["ok"] else "ok" for v in results.values())
    print("results:", c.most_common())


if __name__ == "__main__":
    merge() if "--merge" in sys.argv else main()
