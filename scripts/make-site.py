"""Writes the public website in docs/ from the same data the app ships (data/app/index.json + places-<region>.json).

Pages: the landing page, the hand-checked statewide guides (taquerías, dim sum, burritos, fish tacos, Korean barbecue, burger stands,
wine country, the oldest places), MICHELIN & James Beard honors, one page per big city, the web app (/explore/), privacy, terms, 404,
plus sitemap.xml, robots.txt and site.webmanifest. Everything listed is hand-checked research or licensed open data (Overture Maps, county
food-facility and inspection records, California ABC licenses); nothing comes from Google, Yelp or any ratings site, and nothing is
ranked by ratings. Adapted from wa-eats/scripts/make-site.py (itself from wi-eats).

Usage (from the repo root): .venv/bin/python scripts/make-site.py
Re-run it after every data rebuild, then check the pages: .venv/bin/python scripts/qa-site.py
"""
import base64
import datetime
import hashlib
import html
import json
import math
import os
import re
import urllib.parse
import struct
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = f"{ROOT}/docs"
# Where the site lives. Until Nick's Cloudflare record `california CNAME nickstrom5.github.io` (DNS only) resolves, the site is served at
# the GitHub Pages project address. Then set CUSTOM_DOMAIN = "california.eatsranked.com", re-run, push (with Nick's OK), and GitHub
# forwards the old github.io links (the ones inside shipped app builds) to it.
CUSTOM_DOMAIN = ""
DOMAIN = f"https://{CUSTOM_DOMAIN}" if CUSTOM_DOMAIN else "https://nickstrom5.github.io/california-eats"
BASE = "" if CUSTOM_DOMAIN else "/california-eats"     # path prefix for root-relative links
BRAND = "California Eats"
TAGLINE = "Taquería & dim sum guide"
EMAIL = "nick@eatsranked.com"      # Nick, 2026-10-12: the public site's contact address (Cloudflare Email Routing); the app follows next build
CHECKED = "October 2026"

IDX = json.load(open(f"{ROOT}/data/app/index.json"))
# Website links the site must never publish (hacked sites, listing farms, another business's page): pipeline/website_blocklist.json,
# [{"domain": ..., "match": "domain" | "url", ...}]. "domain" covers the domain and every subdomain; "url" that one address. The place
# stays; only its link goes, everywhere this script writes one (static pages and every web-app data file). Add entries there, not here.
BLOCKLIST = json.load(open(f"{ROOT}/pipeline/website_blocklist.json"))
BLOCK_DOMAINS = {b["domain"].lower().removeprefix("www.") for b in BLOCKLIST if b.get("match", "domain") == "domain"}
_url_key = lambda u: re.sub(r"^https?://(www\.)?", "", (u or "").strip().lower()).rstrip("/")
BLOCK_URLS = {_url_key(b.get("url") or b["domain"]) for b in BLOCKLIST if b.get("match") == "url"}


def site_blocked(u):
    if not u:
        return False
    host = urllib.parse.urlsplit(u.strip() if "://" in u else "http://" + u.strip()).hostname or ""
    return any(host == d or host.endswith("." + d) for d in BLOCK_DOMAINS) or _url_key(u) in BLOCK_URLS


def region_file(rf):
    """One region's places from data/app, with blocklisted website links removed."""
    R = json.load(open(f"{ROOT}/data/app/{rf['file']}"))
    for r in R["places"]:
        if site_blocked(r.get("w")):
            del r["w"]
    return R


TODAY = IDX["generated"][:10]
# the day the site's own text last changed (bump it with the copy, the privacy policy or the terms); pages and the sitemap show the later
# of this and the data's date
SITE_UPDATED = "2026-10-12"
LASTMOD = max(TODAY, SITE_UPDATED)


def nice_date(iso):
    d = datetime.date.fromisoformat(iso[:10])
    return f"{d:%B} {d.day}, {d.year}"

CUISINES, BRANDS, COUNTIES, JURS = IDX["cuisines"], IDX["brands"], IDX["counties"], IDX["jurs"]
GB = IDX["guides"]   # guide bits: taqueria 1, burrito 2, fishtaco 4, dimsum 8, kbbq 16, burgerstand 32, winecountry 64, oldest 128
MI = {5: "3 MICHELIN Stars", 4: "2 MICHELIN Stars", 3: "1 MICHELIN Star", 2: "Bib Gourmand", 1: "MICHELIN Recommended"}


class P:
    """One place, with the same meaning the app gives each field (CaliforniaEats/Models/Place.swift)."""

    def __init__(self, r, cities, region):
        self.r = r
        self.id = r["id"]
        self.name = r["n"]
        self.city = cities[r["c"]] if r.get("c") is not None else ""
        self.county = COUNTIES[r["ct"]] if r.get("ct") is not None else None
        self.region = region["name"]
        self.region_id = region["id"]
        self.cuisine = CUISINES[r["cu"]] if r.get("cu") is not None else ""
        self.brand = BRANDS[r["b"]] if r.get("b") is not None else None
        self.addr = r.get("a") or ""
        self.zip = r.get("z") or ""
        self.lat, self.lon = r.get("la"), r.get("lo")
        self.g = r.get("g") or 0
        self.hc = r.get("hc") == 1
        self.chain = (r.get("ch") or 0) >= 5
        self.ch = r.get("ch") or 1
        self.venue = r.get("v") == 1
        self.ip = r.get("ip")
        self.mi = r.get("mi") or 0
        self.gs = r.get("gs") == 1
        self.h = r.get("h") or 0
        self.jbf = r.get("jbf") or ""
        self.founded = r.get("f")
        self.opened_note = r.get("on") or ""
        self.brand_founded = r.get("bf") or ""
        self.dishes = r.get("di") or ""
        self.note = r.get("note") or ""
        self.site = r.get("w") or ""
        self.insp = r.get("in")
        self.honored = bool(self.h or self.mi or self.gs)

    def key(self):
        return (self.city, self.name.lower())

    def guide(self, bit):
        return self.hc and bool(self.g & bit)


PLACES = []
for rf in IDX["regions"]:
    R = region_file(rf)
    PLACES += [P(r, R["cities"], rf) for r in R["places"]]
REST = [p for p in PLACES if not p.venue]
REGIONS = [rf["name"] for rf in IDX["regions"]]
TAQ = [p for p in PLACES if p.guide(GB["taqueria"])]
BURR = [p for p in PLACES if p.guide(GB["burrito"])]
FISH = [p for p in PLACES if p.guide(GB["fishtaco"])]
DIM = [p for p in PLACES if p.guide(GB["dimsum"])]
KBBQ = [p for p in PLACES if p.guide(GB["kbbq"])]
BURG = [p for p in PLACES if p.guide(GB["burgerstand"])]
WINE = [p for p in PLACES if p.guide(GB["winecountry"])]
# open at this address since 1960 or earlier, as in the app's Oldest guide
OLD = sorted([p for p in PLACES if p.founded and p.founded <= 1960 and (p.guide(GB["oldest"]) or p.honored)], key=lambda p: (p.founded, p.name.lower()))
HON = sorted([p for p in PLACES if p.honored], key=lambda p: (-(p.ip or 0), p.name.lower()))
INSPECTED = [p for p in REST if p.insp]
N_REST = len(REST)
N_TOWNS = len({p.city for p in REST if p.city})


def miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


# ---------------------------------------------------------------- html helpers
e = html.escape


def slug(s):
    s = s.lower().replace("'", "").replace("í", "i").replace("é", "e").replace("ñ", "n")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


APPLE = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M16.4 12.6c0-2.5 2-3.7 2.1-3.8-1.2-1.7-3-1.9-3.6-2-1.5-.2-3 .9-3.8.9-.8 0-2-.9-3.3-.9-1.7 0-3.3 1-4.1 2.5-1.8 3.1-.5 7.6 1.3 10.1.9 1.2 1.9 2.6 3.2 2.6 1.3-.1 1.8-.8 3.3-.8 1.6 0 2 .8 3.3.8 1.4 0 2.3-1.3 3.1-2.5 1-1.4 1.4-2.8 1.4-2.9 0 0-2.7-1-2.9-4zM14 5.2c.7-.8 1.2-2 1-3.2-1 0-2.2.7-2.9 1.5-.6.7-1.2 1.9-1.1 3.1 1.1.1 2.3-.6 3-1.4z"/></svg>'
# the app icon in miniature (scripts/make-brand.swift's avocado at 64 units, Eats Ranked style 2026-10-09): a flat upright avocado
# half on Pacific blue: skin rim outside the outline, bright-green ring clipped inside it, pale flesh, one flat pit
AVO = ("M32 9.96 C40.78 9.96 41.44 21.73 45.35 27.59 C49.96 34.51 49.56 36.49 49.56 41.28 C49.56 48.43 41.83 54.04 32 54.04 "
       "C22.17 54.04 14.44 48.43 14.44 41.28 C14.44 36.49 14.04 34.51 18.65 27.59 C22.56 21.73 23.22 9.96 32 9.96 Z")
LOGO = ('<svg viewBox="0 0 64 64" width="30" height="30" aria-hidden="true"><rect width="64" height="64" rx="14" fill="#003262"/>'
        f'<clipPath id="ca-fruit"><path d="{AVO}"/></clipPath>'
        f'<path d="{AVO}" fill="none" stroke="#2F4F1C" stroke-width="2" stroke-linejoin="round"/>'
        f'<path d="{AVO}" fill="#E4EC9A"/>'
        f'<path d="{AVO}" fill="none" stroke="#9CC94F" stroke-width="5" clip-path="url(#ca-fruit)"/>'
        '<circle cx="32" cy="39.68" r="7.04" fill="#7A4A26"/></svg>')
FAVICON = "data:image/svg+xml," + LOGO.replace('width="30" height="30" ', "").replace(' aria-hidden="true"', "").replace("<svg ", "<svg xmlns='http://www.w3.org/2000/svg' ").replace('"', "'").replace("#", "%23").replace("<", "%3C").replace(">", "%3E")

CSS = """
  :root {
    --bg: #f8fafc; --surface: #fff; --surface2: #eef3f8; --rule: #dce3ec;
    --ink: #0e1b2c; --ink2: #283a52; --muted: #4a5a72;
    --blue: #003262; --blue2: #1a4b80; --sea: #5582b4; --seasoft: #e3ecf5;
    --gold: #fdb515; --goldsoft: #fee7b0; --poppy: #e35b1e;
    --radius: 16px;
    --display: "Avenir Next Condensed", "HelveticaNeue-CondensedBold", "Arial Narrow", system-ui, sans-serif;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #0b1420; --surface: #111d2c; --surface2: #172638; --rule: #24364b; --ink: #edf2f8; --ink2: #ccd8e6; --muted: #a2b2c6; --blue: #9cc3ec; --blue2: #7fb0e3; --sea: #8cb6df; --seasoft: #16304a; }
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  @media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.55 -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
  a { color: var(--blue); text-underline-offset: 2px; }
  a:focus-visible, summary:focus-visible, button:focus-visible { outline: 3px solid var(--gold); outline-offset: 3px; border-radius: 6px; }
  .skip { position: absolute; left: -9999px; top: 0; background: var(--gold); color: #0e1b2c; padding: 10px 14px; font-weight: 700; z-index: 10; }
  .skip:focus { left: 8px; top: 8px; }
  .wrap { max-width: 760px; margin: 0 auto; padding: 0 20px; }
  .band { display: block; width: 100%; height: 22px; margin-top: 8px; }
  header.site { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 0 18px; border-bottom: 4px solid var(--gold); }
  .logo { display: inline-flex; align-items: center; gap: 10px; min-height: 44px; font: 800 22px/1 var(--display); text-transform: uppercase; letter-spacing: .01em; color: var(--blue); text-decoration: none; }
  header.site nav { display: flex; flex-wrap: wrap; gap: 4px 16px; justify-content: flex-end; }
  header.site nav a { color: var(--ink2); text-decoration: none; font-size: 15px; }
  header.site nav a, footer nav a, nav.crumbs a { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; }
  header.site nav a:hover { color: var(--blue); text-decoration: underline; }
  h1, h2 { font-family: var(--display); font-weight: 800; color: var(--blue); letter-spacing: -.005em; }
  h1 { font-size: clamp(36px, 7.5vw, 56px); line-height: 1.02; margin: 0 0 16px; text-transform: uppercase; text-wrap: balance; }
  h1 .kicker { display: block; font: 700 15px/1.4 -apple-system, system-ui, sans-serif; letter-spacing: .06em; color: var(--muted); margin-bottom: 12px; }
  h2 { font-size: 32px; line-height: 1.1; margin: 0 0 10px; text-wrap: balance; }
  h3 { font-size: 18px; margin: 0; line-height: 1.3; }
  .lede { font-size: 19px; color: var(--ink2); margin: 0 0 26px; }
  .hero { padding: 44px 0 28px; }
  section { padding: 36px 0; border-top: 1px solid var(--rule); }
  section.hero { border: 0; }
  .sub { color: var(--ink2); margin: 0 0 22px; }
  .cta-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .btn { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; gap: 10px; background: var(--gold); color: #0e1b2c; font-weight: 700; padding: 14px 20px; border-radius: 14px; text-decoration: none; font-size: 17px; }
  .btn svg { width: 22px; height: 22px; }
  .btn-ghost { background: transparent; color: var(--blue); border: 2px solid var(--blue); }
  .pill { font-size: 14px; color: var(--muted); }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 28px 0 0; padding: 0; list-style: none; }
  .stats li { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 14px; }
  .stats b { display: block; font: 800 30px/1 var(--display); color: var(--blue); font-variant-numeric: tabular-nums; }
  .stats span { font-size: 14px; color: var(--muted); }
  .steps { display: grid; gap: 12px; list-style: none; margin: 0; padding: 0; }
  .step { display: flex; gap: 14px; background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); padding: 18px; }
  .step .n { flex: 0 0 32px; height: 32px; border-radius: 50%; background: var(--gold); color: #0e1b2c; font-weight: 800; display: grid; place-items: center; }
  .step p { margin: 4px 0 0; color: var(--ink2); }
  .shots { display: flex; gap: 14px; overflow-x: auto; margin: 0 -20px; padding: 4px 20px 14px; scroll-snap-type: x proximity; list-style: none; }
  .shots li { flex: 0 0 auto; width: 210px; scroll-snap-align: start; }
  .shots img { display: block; width: 210px; height: auto; border-radius: 24px; border: 1px solid var(--rule); background: var(--surface2); }
  .shots p { font-size: 14px; color: var(--muted); margin: 8px 2px 0; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .card { background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); padding: 18px; }
  .card p { margin: 6px 0 0; color: var(--ink2); }
  a.card { display: block; text-decoration: none; color: var(--ink); }
  a.card:hover h3 { text-decoration: underline; color: var(--blue); }
  .card.lead { border-color: var(--gold); background: var(--goldsoft); }
  @media (prefers-color-scheme: dark) { .card.lead { background: var(--surface); } }
  .cities { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; padding: 0; margin: 0; }
  .cities a { display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 8px 14px; border-radius: 999px; border: 1px solid var(--rule); background: var(--surface); text-decoration: none; color: var(--ink); font-size: 15px; }
  .cities a:hover { border-color: var(--blue); }
  details { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 2px 18px; margin-bottom: 10px; }
  summary { cursor: pointer; padding: 14px 0; font-weight: 600; list-style: none; display: flex; justify-content: space-between; gap: 12px; }
  summary::-webkit-details-marker { display: none; }
  summary::after { content: "+"; color: var(--blue); font-weight: 800; }
  details[open] summary::after { content: "\\2013"; }
  details p { margin: 0 0 16px; color: var(--ink2); }
  .final { text-align: center; }
  .final .cta-row { justify-content: center; }
  nav.crumbs { font-size: 14px; color: var(--muted); padding: 16px 0 0; }
  nav.crumbs ol { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 6px; }
  nav.crumbs li + li::before { content: "/"; margin-right: 6px; color: var(--rule); }
  nav.crumbs a { color: var(--muted); }
  nav.crumbs li { display: inline-flex; align-items: center; min-height: 44px; }
  .places { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
  .places li { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 14px 16px; min-width: 0; overflow-wrap: anywhere; }
  .places .where { margin: 2px 0 0; font-size: 15px; color: var(--muted); }
  .places .facts { margin: 8px 0 0; font-size: 15px; color: var(--ink2); }
  .places .facts b { color: var(--ink); font-weight: 600; }
  .places .note { margin: 6px 0 0; font-size: 15px; color: var(--ink2); }
  .places .link { font-size: 14px; }
  .places .link a, .places h3 a, .toc a, td a { display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; }
  .tag { display: inline-block; font-size: 12px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; background: var(--goldsoft); color: #0e1b2c; border-radius: 6px; padding: 1px 6px; margin-right: 4px; }
  .tag-sea { background: var(--seasoft); color: var(--blue); }
  .tag-mi { background: #003262; color: #fff; }
  .toc { columns: 2; padding-left: 20px; margin: 0; }
  table { border-collapse: collapse; width: 100%; font-size: 15px; }
  th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--rule); }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
  .tablewrap { overflow-x: auto; }
  .fine { font-size: 14px; color: var(--muted); }
  .legal h2 { font-size: 26px; margin-top: 28px; }
  .legal p, .legal li { color: var(--ink2); }
  footer { padding: 32px 0 56px; color: var(--muted); font-size: 14px; border-top: 1px solid var(--rule); margin-top: 20px; }
  footer nav { display: flex; flex-wrap: wrap; gap: 8px 16px; }
  footer a { color: var(--muted); }
  footer p { margin: 12px 0 0; }
  @media (max-width: 600px) {
    .grid2 { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
    .toc { columns: 1; }
    header.site { flex-direction: column; align-items: flex-start; }
    header.site nav { justify-content: flex-start; }
  }
"""
# the one California element: a low gold sun over two Pacific swells
BAND = ('<svg class="band" viewBox="0 0 760 22" preserveAspectRatio="none" aria-hidden="true">'
        '<path d="M40 22 A22 22 0 0 1 84 22 Z" fill="#fdb515"/>'
        '<path d="M0 22 V14 Q24 9 48 14 T96 14 T144 14 T192 14 T240 14 T288 14 T336 14 T384 14 T432 14 T480 14 T528 14 T576 14 T624 14 T672 14 T720 14 T760 14 V22 Z" fill="#5582b4"/>'
        '<path d="M0 22 V18 Q24 14 48 18 T96 18 T144 18 T192 18 T240 18 T288 18 T336 18 T384 18 T432 18 T480 18 T528 18 T576 18 T624 18 T672 18 T720 18 T760 18 V22 Z" fill="#003262"/></svg>')


def jsonld(obj):
    big = obj.get("@type") == "ItemList"
    # < > & escaped as JSON unicode escapes, so no value from open data can close the <script> element early
    js = json.dumps(obj, ensure_ascii=False, indent=None if big else 1, separators=(",", ":") if big else None)
    return '<script type="application/ld+json">\n' + js.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") + "\n</script>"


def web_link(u):
    """Only http(s) links become hrefs (the export allows nothing else; this guards the page if that ever changes)."""
    return u if re.match(r"(?i)^https?://", u or "") else ""


def csp(doc):
    """Content-Security-Policy for one page (GitHub Pages can't send headers, so it's a meta tag): this page's own inline scripts and
    styles by hash, same-origin data, images and manifest, nothing from anywhere else."""
    h = lambda t: "'sha256-" + base64.b64encode(hashlib.sha256(t.encode()).digest()).decode() + "'"
    scripts = " ".join(h(t) for t in re.findall(r"<script>(.*?)</script>", doc, re.S)) or "'none'"
    styles = " ".join(h(t) for t in re.findall(r"<style>(.*?)</style>", doc, re.S)) or "'none'"
    return (f"default-src 'none'; script-src {scripts}; style-src {styles}; img-src 'self' data:; connect-src 'self'; manifest-src 'self'; "
            "base-uri 'none'; form-action 'none'; object-src 'none'")


def crumbs(trail):
    """trail: [(name, url)] ending with the current page."""
    items = "".join(f'<li><a href="{u}">{e(n)}</a></li>' if i < len(trail) - 1 else f'<li aria-current="page">{e(n)}</li>'
                    for i, (n, u) in enumerate(trail))
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": DOMAIN + u} for i, (n, u) in enumerate(trail)]}
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{items}</ol></nav>', ld


def store_button(label="Get early access"):
    return (f'<a class="btn store-btn" href="mailto:{EMAIL}?subject=California%20Eats%20early%20access&amp;body=Send%20me%20the%20TestFlight%20link.">'
            f'{APPLE}<span class="store-label">{label}</span></a>')


GUIDE_PAGES = [   # (bit, page, nav label, guide title, noun, nouns, list, blurb)
    ("taqueria", "california-taquerias.html", "Taquerías", "California taquerías", "taquería", "taquerías", TAQ,
     "Taquerías and taco shops with a fixed address, from East LA and the Mission to Fresno and San Diego, with the tacos on each menu."),
    ("dimsum", "california-dim-sum.html", "Dim sum", "California dim sum", "dim sum house", "dim sum houses", DIM,
     "Dim sum houses and bakeries in the San Gabriel Valley, Chinatowns, the Peninsula and beyond, with headline dishes."),
    ("burrito", "california-burritos.html", "Burritos", "Mission & California burritos", "burrito shop", "burrito shops", BURR,
     "Mission-style burritos in the Bay Area and California burritos (carne asada and fries) in San Diego."),
    ("fishtaco", "california-fish-tacos.html", "Fish tacos", "California fish tacos", "fish taco spot", "fish taco spots", FISH,
     "Baja-style fried and grilled fish tacos, mostly in San Diego County."),
    ("kbbq", "california-korean-bbq.html", "Korean BBQ", "California Korean barbecue", "Korean barbecue restaurant", "Korean barbecue restaurants", KBBQ,
     "Tabletop-grill Korean barbecue in Los Angeles' Koreatown and across the state."),
    ("burgerstand", "california-burger-stands.html", "Burger stands", "California burger stands", "burger stand", "burger stands", BURG,
     "Walk-up burger stands and drive-ins, each checked open by hand, from Los Angeles to the Central Coast and the desert."),
    ("winecountry", "california-wine-country-restaurants.html", "Wine country", "Wine-country restaurants", "restaurant", "restaurants", WINE,
     "Restaurants with a kitchen in Napa Valley, Sonoma County, Paso Robles, the Santa Ynez Valley, Temecula and other wine towns."),
]
GUIDE_PAGES = [g for g in GUIDE_PAGES if g[6]]   # a guide page only once its research has places


def nav_links():
    links = [(p, lbl) for _, p, lbl, *_ in GUIDE_PAGES[:4]] + [("california-michelin-james-beard.html", "Honors"), ("/#cities", "Cities"), ("explore/", "Search")]
    return "".join(f'<a href="{u if u.startswith("/") else "/" + u}">{e(l)}</a>' for u, l in links)


def page(path, title, desc, body, lds=(), robots="index,follow,max-image-preview:large", og_alt=None, extra_css="", after=""):
    assert 50 <= len(title) <= 60 or path == "404.html", (path, len(title), title)
    assert 140 <= len(desc) <= 160 or path == "404.html", (path, len(desc), desc)
    assert body.count("<h1") == 1, path
    url = DOMAIN + "/" + ("" if path == "index.html" else path.removesuffix("index.html"))
    og_alt = og_alt or f"{BRAND}: {TAGLINE}. California restaurants, with hand-checked taquerías, dim sum, burritos and more."
    ld = "\n".join(jsonld(x) for x in lds)
    doc = f"""<!DOCTYPE html>
<html lang="en" data-base="{BASE}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- <meta name="apple-itunes-app" content="app-id=APP_ID"> fill in once the App Store record exists -->
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="{robots}">
<meta name="theme-color" content="#003262">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="{'website' if path == 'index.html' else 'article'}">
<meta property="og:site_name" content="{BRAND}">
<meta property="og:locale" content="en_US">
<meta property="og:image" content="{DOMAIN}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(og_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{DOMAIN}/og.png">
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<style>{CSS}{extra_css}</style>
{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="wrap">
  {BAND}
  <header class="site">
    <a class="logo" href="/" aria-label="{BRAND} home">{LOGO}{BRAND}</a>
    <nav aria-label="Main">{nav_links()}</nav>
  </header>
{body}
  <footer>
    <nav aria-label="Footer">
      <a href="/">{BRAND} app</a>
      <a href="/explore/">Search California restaurants</a>
      {"".join(f'<a href="/{p}">{e(t)}</a>' for _, p, _, t, *_ in GUIDE_PAGES)}
      <a href="/california-michelin-james-beard.html">MICHELIN &amp; James Beard</a>
      <a href="/privacy.html">Privacy policy</a>
      <a href="/terms.html">Terms of use</a>
      <a href="mailto:{EMAIL}">Email us</a>
    </nav>
    <p>Place data: hand-checked research by {BRAND} ({CHECKED}); Overture Maps Foundation (CDLA Permissive 2.0); County of Los Angeles, City and County of San Francisco, Sacramento County and San Diego County food-facility and inspection records; California Department of Alcoholic Beverage Control license data. Not affiliated with or endorsed by any restaurant, chain or government agency. MICHELIN and the MICHELIN Guide are trademarks of Michelin; James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. Places open and close, so check before you go.</p>
    <p>© {TODAY[:4]} {BRAND}. Part of <a href="https://eatsranked.com/">Eats Ranked</a>, restaurant apps state by state.</p>
  </footer>
</div>
{after}<script>
  // Once the App Store listing exists, paste its URL here (looks like https://apps.apple.com/app/id123456789).
  // Every button switches from "Get early access" to "Download on the App Store" automatically.
  var APP_STORE_URL = "";
  if (APP_STORE_URL) {{
    document.querySelectorAll(".store-btn").forEach(function (b) {{ b.href = APP_STORE_URL; b.rel = "noopener"; }});
    document.querySelectorAll(".store-label").forEach(function (l) {{ l.textContent = "Download on the App Store"; }});
    document.querySelectorAll(".store-note").forEach(function (n) {{ n.textContent = "Free for iPhone and iPad."; }});
  }}
</script>
</body>
</html>
"""
    if path == "404.html" or "noindex" in robots:   # a 404 is served at any URL; a noindexed page names no address for search either
        doc = re.sub(r'<link rel="canonical"[^>]*>\n|<meta property="og:url"[^>]*>\n', "", doc)
    if BASE:   # served under /california-eats/: every root-relative link and asset gets the prefix
        doc = re.sub(r'(href|src|srcset)="/', rf'\1="{BASE}/', doc)
    doc = doc.replace('<meta charset="utf-8">\n', '<meta charset="utf-8">\n'
                      f'<meta http-equiv="Content-Security-Policy" content="{csp(doc)}">\n'
                      '<meta name="referrer" content="strict-origin-when-cross-origin">\n', 1)
    os.makedirs(os.path.dirname(f"{DOCS}/{path}"), exist_ok=True)
    open(f"{DOCS}/{path}", "w").write(doc)
    return path


def honor_tags(p):
    t = []
    if p.mi:
        t.append((MI[p.mi], " tag-mi"))
    if p.gs:
        t.append(("MICHELIN Green Star", " tag-mi"))
    jb = "America's Classic" if p.h & 1 else "James Beard winner" if p.h & 2 else "James Beard finalist" if p.h & 4 else "James Beard semifinalist" if p.h & 8 else None
    if jb:
        t.append((jb, " tag-sea"))
    return t


def place_item(p, show_town=True, extra=None):
    facts = []
    if p.dishes:
        facts.append(f"<b>On the menu:</b> {e(p.dishes)}")
    if p.founded:
        facts.append(f"<b>Opened</b> {p.founded}")
    elif p.brand_founded:
        facts.append(f"<b>Founded</b> {e(p.brand_founded)}")
    kinds = [(lbl, "") for k, lbl in (("taqueria", "Taquería"), ("burrito", "Burritos"), ("fishtaco", "Fish tacos"), ("dimsum", "Dim sum"),
                                      ("kbbq", "Korean BBQ"), ("burgerstand", "Burger stand"), ("winecountry", "Wine country")) if p.guide(GB[k])]
    kinds = honor_tags(p) + kinds
    where = ", ".join(x for x in (p.addr, p.city) if x)
    if extra:
        where += f" · {extra}"
    out = [f"<li><h3>{e(p.name)}</h3>", f'<p class="where">{e(where)}</p>']
    if kinds or facts:
        out.append('<p class="facts">' + "".join(f'<span class="tag{cls}">{e(k)}</span>' for k, cls in kinds) + (" " + " · ".join(facts) if facts else "") + "</p>")
    if p.note:
        out.append(f'<p class="note">{e(p.note)}</p>')
    if web_link(p.site):
        host = re.sub(r"^https?://(www\.)?", "", p.site, flags=re.I).split("/")[0]
        out.append(f'<p class="link"><a href="{e(p.site)}" rel="noopener nofollow">{e(host)}</a></p>')
    out.append("</li>")
    return "".join(out)


def dish_list(text):
    """A menu line split into dishes at the commas outside parentheses: "super burrito (rice, beans, cheese), carnitas" is two dishes,
    not "super burrito (rice" and "beans"."""
    out, depth, cur = [], 0, ""
    for ch in text or "":
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth <= 0:
            out.append(cur); cur = ""
        else:
            cur += ch
    return [d.strip().lower() for d in out + [cur] if d.strip()]


def restaurant_ld(p):
    x = {"@type": "Restaurant", "name": p.name,
         "address": {"@type": "PostalAddress", "streetAddress": p.addr, "addressLocality": p.city, "addressRegion": "CA", "addressCountry": "US"}}
    if not p.addr:     # a stand with no street number: no empty property
        del x["address"]["streetAddress"]
    if p.zip:
        x["address"]["postalCode"] = p.zip
    if web_link(p.site):
        x["url"] = p.site
    if p.founded:
        x["foundingDate"] = str(p.founded)
    if p.cuisine and p.cuisine not in ("American & Other",):
        x["servesCuisine"] = p.cuisine
    return x


def item_list(name, places, url):
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name, "url": url, "numberOfItems": len(places),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": restaurant_ld(p)} for i, p in enumerate(places)]}


def article_ld(url, headline, desc):
    return {"@context": "https://schema.org", "@type": "Article", "headline": headline, "description": desc,
            "datePublished": TODAY, "dateModified": LASTMOD, "inLanguage": "en", "mainEntityOfPage": url,
            "image": f"{DOMAIN}/og.png", "author": {"@type": "Organization", "name": BRAND, "url": DOMAIN + "/"},
            "publisher": {"@type": "Organization", "name": BRAND, "url": DOMAIN + "/", "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/icon-512.png"}}}


def fit(options, lo, hi):
    for o in options:
        if lo <= len(o) <= hi:
            return o
    raise ValueError(f"nothing fits {lo}-{hi}: {[(len(o), o) for o in options]}")


def by_region(places):
    groups = defaultdict(list)
    for p in places:
        groups[p.region].append(p)
    return [(r, sorted(groups[r], key=P.key)) for r in REGIONS if groups.get(r)]


def region_sections(places, noun, plural=None):
    plural = plural or noun + "s"
    toc = '<ul class="toc">' + "".join(f'<li><a href="#{slug(r)}">{e(r)}</a> ({len(ps)})</li>' for r, ps in by_region(places)) + "</ul>"
    secs = []
    for r, ps in by_region(places):
        secs.append(f'<section id="{slug(r)}" aria-labelledby="h-{slug(r)}"><h2 id="h-{slug(r)}">{e(r)}</h2>'
                    f'<p class="sub">{len(ps)} {noun if len(ps) == 1 else plural}, by town.</p><ol class="places">'
                    + "".join(place_item(p) for p in ps) + "</ol></section>")
    return toc, "\n".join(secs)


CITY_CANDIDATES = ["Los Angeles", "San Francisco", "San Diego", "San Jose", "Sacramento", "Oakland", "Fresno", "Long Beach", "Pasadena",
                   "Santa Barbara", "Berkeley", "Santa Monica", "Irvine", "Anaheim", "Riverside", "Bakersfield", "Santa Cruz", "Napa",
                   "Palm Springs", "Monterey", "San Luis Obispo", "Stockton", "Glendale", "San Gabriel"]
town_n = Counter(p.city for p in REST if p.city)
CITY_PAGES = [c for c in CITY_CANDIDATES if town_n.get(c, 0) >= 60]


def city_url(c):
    return f"/cities/{slug(c)}.html"


def city_links(skip=None):
    return '<ul class="cities">' + "".join(f'<li><a href="{city_url(c)}">{e(c)}</a></li>' for c in CITY_PAGES if c != skip) + "</ul>"


def guide_cta():
    return f'<div class="cta-row">{store_button()}<span class="pill store-note">Free for iPhone and iPad, arriving on the App Store soon.</span></div>'


written, noindexed = [], []    # sitemap pages; pages kept out of search (thin towns)

# ---------------------------------------------------------------- the hand-checked guides
HOW = (f"Our method: for every place we found a 2025 or 2026 source of its own, such as the menu on its website, an ordering page it runs, or a "
       f"dated story in the local press, and read it in {CHECKED}. A listing that only carries the word in its name, or whose website has gone "
       "dark, stays in the app's directory and off this page. No review site fed this list, and it runs by region and town, never by score.")
for bit, path, lbl, gtitle, noun, nouns, places, blurb in GUIDE_PAGES:
    url = f"{DOMAIN}/{path}"
    n = len(places)
    regions_n = len(by_region(places))
    title = fit([f"{gtitle}: {n} Checked Places | {BRAND}", f"{gtitle}: {n} Hand-Checked Places", f"{gtitle}: {n} Places Checked Open",
                 f"{gtitle} Guide | {BRAND}", f"{gtitle}, Checked Open | {BRAND} App", f"{gtitle}: A Hand-Checked Guide | California Eats"], 50, 60)
    desc = fit([f"{n} {nouns} across California, each checked open in {CHECKED} against a 2025 or 2026 source, with what they serve, by region and town. Free, no ads.",
                f"{n} {nouns} in California, each checked open in {CHECKED}, listed by region and town with what's on the menu. Free app, no ads, no ratings.",
                f"{n} California {nouns}, checked open in {CHECKED} and listed by region and town with what they serve. Free, no ratings, no ads.",
                f"{n} {nouns} statewide, checked open in {CHECKED} with what they serve. Free California guide for iPhone, iPad and the web, no ratings."], 140, 160)
    toc, secs = region_sections(places, noun, nouns)
    dish = Counter()
    for p in places:
        for d in dict.fromkeys(dish_list(p.dishes)):
            dish[d] += 1
    # most common first, ties by name: the page is the same on every run (a set's order changed it from run to run)
    # "most often" means on at least three menus; a guide whose dishes rarely repeat (wine country) skips the sentence
    common = [d for d, k in sorted(dish.items(), key=lambda x: (-x[1], x[0])) if k >= 3][:8]
    top = ", ".join(common) if len(common) >= 3 else ""
    nav, bc = crumbs([("Home", "/"), (gtitle, "/" + path)])
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <h1><span class="kicker">{BRAND} guide · checked {CHECKED}</span>{e(gtitle)}</h1>
    <p class="lede">{n} {e(nouns)} {f"across all {len(REGIONS)} of California's regions" if regions_n == len(REGIONS) else f"across {regions_n} of California's {len(REGIONS)} regions"}, each checked open in {CHECKED} against its own website, menu or ordering page, or a dated local news story. {e(blurb)}</p>
    {guide_cta()}
  </section>
  <section id="about">
    <h2>About this list</h2>
    {f"<p>What's on the menus, most often: {e(top)}. Each place lists what its own menu shows.</p>" if top else ""}
    <p>{HOW}</p>
    <p>The app sorts the same {e(nouns)} by how far each one is from you, and tapping one brings up its Apple Maps card, hours and photos included.</p>
    <h2>Jump to a region</h2>
    {toc}
    <p class="fine">City pages: {", ".join(f'<a href="{city_url(c)}">{e(c)}</a>' for c in CITY_PAGES)}.</p>
  </section>
{secs}
  </main>"""
    written.append(page(path, title, desc, body, [article_ld(url, gtitle, desc), bc, item_list(gtitle, sorted(places, key=P.key), url)]))

# ---------------------------------------------------------------- honors: MICHELIN Guide California 2026 and James Beard
url = f"{DOMAIN}/california-michelin-james-beard.html"
stars = [p for p in HON if p.mi >= 3]
bibs = [p for p in HON if p.mi == 2]
green = [p for p in HON if p.gs]
classics = [p for p in HON if p.h & 1]
jb_rest = [p for p in HON if p.h & 14 and not p.h & 1]
title = fit(["California MICHELIN Stars & James Beard Honorees | CA Eats", "MICHELIN Stars & James Beard Honors in California",
             "MICHELIN & James Beard Restaurants in California | CA Eats"], 50, 60)
desc = fit([f"{len(stars)} MICHELIN-starred restaurants, {len(bibs)} Bib Gourmands and James Beard honorees across California, from the official announcements. Facts, not ratings.",
            f"California's MICHELIN stars, {len(bibs)} Bib Gourmands and James Beard winners, finalists and America's Classics, from the official announcements."], 140, 160)
nav, bc = crumbs([("Home", "/"), ("MICHELIN & James Beard", "/california-michelin-james-beard.html")])


def honor_section(sid, h, sub, ps):
    return f'<section id="{sid}"><h2>{h}</h2><p class="sub">{sub}</p><ol class="places">' + "".join(place_item(p) for p in sorted(ps, key=P.key)) + "</ol></section>" if ps else ""


body = f"""{nav}
  <main id="main">
  <section class="hero">
    <h1><span class="kicker">{BRAND} · honors are facts, not ratings</span>MICHELIN &amp; James Beard in California</h1>
    <p class="lede">The MICHELIN Guide California 2026 selection and James Beard Award honors for California restaurants, as the guide and the Foundation announced them. {len(HON)} honored places are in the app, each with its own address and, where it has one, its official county inspection result.</p>
    {guide_cta()}
  </section>
  <section id="about">
    <h2>Where these come from</h2>
    <p>MICHELIN distinctions are from MICHELIN's own announcement of the 2026 California selection (June 24, 2026). James Beard honors are from the James Beard Foundation's announcements, 2023 through 2026, plus California's America's Classics honorees from the Foundation's past-awards records since the program began. A finalist or semifinalist is always called that, never a winner. Places our research found closed since the announcement are left out. MICHELIN and the MICHELIN Guide are trademarks of Michelin; James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation.</p>
  </section>
{honor_section("stars", "MICHELIN-starred restaurants", f"{len(stars)} restaurants with one, two or three MICHELIN Stars in 2026.", stars)}
{honor_section("bib", "Bib Gourmand", f"{len(bibs)} Bib Gourmand restaurants in 2026.", bibs)}
{honor_section("green", "MICHELIN Green Star", f"{len(green)} restaurants with a MICHELIN Green Star in 2026.", green)}
{honor_section("classics", "James Beard America's Classics", f"{len(classics)} California restaurants the James Beard Foundation named America's Classics.", classics)}
{honor_section("james-beard", "James Beard Award winners, finalists and semifinalists", f"{len(jb_rest)} California restaurants honored from 2023 to 2026.", jb_rest)}
  </main>"""
written.append(page("california-michelin-james-beard.html", title, desc, body, [article_ld(url, "MICHELIN and James Beard in California", desc), bc]))

# ---------------------------------------------------------------- oldest places
if OLD:
    url = f"{DOMAIN}/california-oldest-restaurants.html"
    title = fit(["California's Oldest Restaurants, Checked Open | California Eats", "California's Oldest Restaurants and Bars, Checked Open",
                 "The Oldest Restaurants in California | California Eats"], 50, 60)
    desc = fit([f"{len(OLD)} California restaurants and bars with a sourced opening year, oldest first, each checked open in {CHECKED}: Gold Rush saloons to 1950s burger stands.",
                f"{len(OLD)} of California's oldest restaurants and bars, oldest first, with opening years from their own history or local news, checked open in {CHECKED}."], 140, 160)
    nav, bc = crumbs([("Home", "/"), ("Oldest restaurants", "/california-oldest-restaurants.html")])
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <h1><span class="kicker">{BRAND} · checked {CHECKED}</span>California's oldest restaurants</h1>
    <p class="lede">{len(OLD)} California restaurants and bars, oldest first, each with an opening year taken from its own history or a dated source. The year counts from when it opened at this address; where a business is older than its current home, its note tells the story.</p>
    {guide_cta()}
  </section>
  <section id="list"><h2>Oldest first</h2><ol class="places">{"".join(place_item(p) for p in OLD)}</ol></section>
  </main>"""
    written.append(page("california-oldest-restaurants.html", title, desc, body, [article_ld(url, "California's oldest restaurants", desc), bc]))

# ---------------------------------------------------------------- city pages
city_stats = {}
OWN_HEALTH_DEPT = ("Pasadena", "Long Beach", "Vernon")
COUNT_NOUN = {"Taquerías": ("taquería", "taquerías"), "Dim sum": ("dim sum house", "dim sum houses"), "Burritos": ("burrito shop", "burrito shops"),
              "Fish tacos": ("fish taco spot", "fish taco spots"), "Korean BBQ": ("Korean barbecue restaurant", "Korean barbecue restaurants"),
              "Burger stands": ("burger stand", "burger stands"), "Wine country": ("wine-country restaurant", "wine-country restaurants")}
GUIDE_SETS = [(lbl, t, ps, p_) for b, p_, lbl, t, _, _, ps, _ in GUIDE_PAGES]
for c in CITY_PAGES:
    here = [p for p in REST if p.city == c and p.lat is not None]
    n_town = len(here)
    center = (sorted(p.lat for p in here)[len(here) // 2], sorted(p.lon for p in here)[len(here) // 2])
    # "near" is 5 miles in the dense cores of LA, San Francisco, the East Bay and San Diego (10 miles from Pasadena reached most of
    # San Gabriel's list, so the two pages read alike), 10 miles elsewhere
    radius = 5 if c in ("Los Angeles", "San Francisco", "San Diego", "Pasadena", "Glendale", "San Gabriel", "Santa Monica", "Long Beach",
                        "Oakland", "Berkeley") else 10

    def near(ps):
        out = []
        for p in ps:
            if p.lat is None:
                continue
            d = miles(center, (p.lat, p.lon))
            if p.city == c or d <= radius:
                out.append((0 if p.city == c else 1, d, p))
        out.sort(key=lambda x: (x[0], x[1] if x[0] else 0, x[2].name.lower()))
        return [(d, p) for _, d, p in out]

    def items(lst):
        return "".join(place_item(p, extra=None if p.city == c else f"{d:.0f} mi from {c}") for d, p in lst)

    secs, counts, uniq = [], {}, []
    for lbl, t, ps, p_ in GUIDE_SETS:
        lst = near(ps)
        counts[lbl] = len(lst)
        if lst:
            secs.append(f'<section id="{slug(lbl)}"><h2>{e(t)} in and near {e(c)}</h2><p class="sub">In {e(c)} first, then within {radius} miles. <a href="/{p_}">All {len(ps)} statewide</a>.</p><ol class="places">{items(lst)}</ol></section>')
            uniq += [p for _, p in lst]
    honored = sorted([p for p in here if p.honored], key=lambda p: (-(p.ip or 0), p.name.lower()))
    if honored:
        secs.append(f'<section id="honors"><h2>MICHELIN and James Beard in {e(c)}</h2><p class="sub">From MICHELIN\'s 2026 California selection and the James Beard Foundation\'s announcements. Facts, not ratings.</p><ol class="places">'
                    + "".join(place_item(p) for p in honored) + "</ol></section>")
    old_here = [p for p in OLD if p.city == c]
    if old_here:
        secs.append(f'<section id="oldest"><h2>Open since 1960 or earlier in {e(c)}</h2><p class="sub">From the <a href="/california-oldest-restaurants.html">oldest-restaurants list</a>: '
                    'each opening year is from the place\'s own history or a dated source, and counts from when it opened at this address.</p><ol class="places">'
                    + "".join(place_item(p) for p in old_here) + "</ol></section>")
    insp = [p for p in here if p.insp]
    jur_line = ""
    # Pasadena, Long Beach and Vernon run their own health departments (the FAQ says LA County's grades don't cover them): the few places
    # with those town names and an LA County result sit outside the city or are matches under review, so the page claims none
    if insp and c not in OWN_HEALTH_DEPT:
        j = JURS[insp[0].insp["j"]]
        jur_line = (f" {len(insp):,} {'place' if len(insp) == 1 else 'places'} in {e(c)} also {'shows' if len(insp) == 1 else 'show'} "
                    f"{e(j['name'])}'s official inspection result, as recorded, through {e(nice_date(j['through']))}.")
    cuis = Counter(p.cuisine for p in here if p.cuisine and p.cuisine != "American & Other").most_common(10)
    if cuis:
        rows = "".join(f'<tr><td>{e(k)}</td><td class="n">{n:,}</td></tr>' for k, n in cuis)
        secs.append(f'<section id="cuisines"><h2>What {e(c)} eats</h2><p class="sub">Which kinds of food {e(c)} has the most of, counting its {n_town:,} restaurants in open map data and county records.</p><div class="tablewrap"><table><thead><tr><th scope="col">Kind of place</th><th scope="col" class="n">Places</th></tr></thead><tbody>{rows}</tbody></table></div></section>')
    # a town with almost nothing hand-checked, honored or dated nearby gets a page people can use, but not one search engines index:
    # its words would be the same as every other thin town's
    thin = sum(counts.values()) + len(honored) + len(old_here) < 3
    city_stats[c] = {"restaurants": n_town, **counts, "honored": len(honored), "oldest": len(old_here), "inspected": len(insp), "indexed": not thin}
    path = f"cities/{slug(c)}.html"
    url = DOMAIN + "/" + path
    PHRASE = {"Taquerías": "taquerías", "Dim sum": "dim sum", "Burritos": "burritos", "Fish tacos": "fish tacos", "Korean BBQ": "Korean BBQ",
              "Burger stands": "burger stands", "Wine country": "wine-country dining"}
    TWORD = {"Taquerías": "Taquerías", "Dim sum": "Dim Sum", "Burritos": "Burritos", "Fish tacos": "Fish Tacos", "Korean BBQ": "Korean BBQ",
             "Burger stands": "Burger Stands", "Wine country": "Wine Country Dining"}
    have = [lbl for lbl, *_ in GUIDE_SETS if counts.get(lbl)]
    gl = [PHRASE[lbl] for lbl in have]
    # the title and description promise only what this page lists: no "dim sum" where there's none nearby, no honors where none are
    tw = [TWORD[lbl] for lbl in have]
    titles = []
    if len(tw) >= 2:
        titles += [f"{c} {tw[0]}, {tw[1]} & Restaurants | {BRAND}", f"{c} Restaurants: {tw[0]}, {tw[1]} & More | CA Eats",
                   f"{c} {tw[0]}, {tw[1]} & More | {BRAND}", f"{c}, CA {tw[0]} & {tw[1]} | {BRAND}"]
    if tw:
        titles += [f"{c} {tw[0]} & Restaurant Guide | {BRAND}", f"{c}, CA Restaurants & {tw[0]} | {BRAND}",
                   f"{c} Restaurant Guide: {tw[0]} & More | {BRAND}", f"{c} {tw[0]} & Restaurants | {BRAND} App"]
    titles += [f"{c}, California Restaurant Guide | {BRAND}", f"{c} Restaurants, Cafés & Bars | {BRAND}", f"{c} Restaurants | {BRAND}: Free Guide"]
    title = fit(titles, 50, 60)
    opts = []
    for k in (3, 2, 1):
        if k > len(gl):
            continue
        what = " and ".join([", ".join(gl[:k][:-1]), gl[:k][-1]] if k > 1 else gl[:k])
        cap = what[0].upper() + what[1:]
        if honored:
            opts += [f"Hand-checked {what} near {c}, CA, checked open in {CHECKED}, plus MICHELIN and James Beard honors and {n_town:,} local restaurants in a free app.",
                     f"{c}, CA: hand-checked {what}, local MICHELIN and James Beard honors and {n_town:,} restaurants in the free {BRAND} app.",
                     f"{cap} in and near {c}, checked open in {CHECKED}, with local MICHELIN and James Beard honors. Free California restaurant guide.",
                     f"{cap} near {c}, CA, checked in {CHECKED}, plus local MICHELIN and James Beard honors. A free iPhone, iPad and web guide."]
        else:
            opts += [f"Hand-checked {what} in and near {c}, CA, checked open in {CHECKED}, plus {n_town:,} restaurants in the free {BRAND} app for iPhone and iPad.",
                     f"{cap} in and near {c}, California, checked open in {CHECKED}, with the {n_town:,} restaurants in town. Free iPhone and iPad app, no ads.",
                     f"{c}, California: hand-checked {what}, plus {n_town:,} restaurants, cafés and bars in the free {BRAND} app for iPhone, iPad and the web.",
                     f"The {n_town:,} restaurants in {c}, California, with hand-checked {what} nearby, checked open in {CHECKED}. A free guide for iPhone, iPad and the web."]
    if not gl:
        hon = ", MICHELIN and James Beard honors" if honored else ""
        opts += [f"The {n_town:,} restaurants, cafés and bars in {c}, California{hon}, from open map data and county records, sorted by distance in the free {BRAND} app.",
                 f"{c}, California: {n_town:,} restaurants, cafés and bars{hon} from open map data and county records, in a free iPhone, iPad and web guide.",
                 f"{c}, California: {n_town:,} restaurants, cafés and bars from open map data and county records, sorted by distance in a free iPhone and iPad app."]
    desc = fit(opts, 140, 160)
    nav, bc = crumbs([("Home", "/"), ("Cities", "/#cities"), (c, "/" + path)])
    head = f"""{nav}
  <main id="main">
  <section class="hero">
    <h1><span class="kicker">{BRAND} · {e(c)}, California</span>{e(c)} restaurants</h1>
    <p class="lede">{" · ".join(f"{counts[l]} {COUNT_NOUN[l][counts[l] != 1]}" for l, *_ in GUIDE_SETS if counts.get(l))}{" in and around " + e(c) + ", each checked open in " + CHECKED + "." if any(counts.values()) else ""} In the app, {e(c)} has {n_town:,} restaurants, cafés and bars, nearest first.{jur_line}</p>
    {guide_cta()}
  </section>"""
    body = head + "\n".join(secs) + f'<section id="more"><h2>More California cities</h2>{city_links(skip=c)}</section>\n  </main>'
    lds = [article_ld(url, f"{c} restaurants", desc), bc]
    if uniq:
        seen, u2 = set(), []
        for p in uniq:
            if id(p) not in seen:
                seen.add(id(p)); u2.append(p)
        lds.append(item_list(f"Hand-checked places near {c}", u2, url))
    if thin:
        page(path, title, desc, body, lds, robots="noindex,follow")
        noindexed.append(path)
    else:
        written.append(page(path, title, desc, body, lds))

# ---------------------------------------------------------------- web app (docs/explore/): data files + page
# The web app's first load is small (hub QA HUB6-08: it used to fetch 4.5 MB, core.json + detail.json, before it worked):
#   data/start.json    the lists' metadata (towns, kinds, regions with their map boxes) and the ~860 hand-checked, honored or dated places,
#                      every column. Every guide except All restaurants and Inspections works from it alone.
#   data/places.json   the other ~107,000 places, list/search/map columns only (no ids, phones or websites). Fetched when All restaurants,
#                      Inspections, a saved place or a #p= link outside start.json needs it.
#   data/detail-<k>.json  ids, phones, websites, notes and honors' details for rows k*DETAIL_ROWS .. (k+1)*DETAIL_ROWS-1, fetched when a
#                      place in that block first opens. Rows are sorted by region, town and street, so a block is one area.
#   data/ids-<h>.json  {id: row} for the ids starting with <h> (hex), for #p= links and saved places the first file doesn't hold.
# Every later file is fetched with ?v=<start.json's version>, so a cached old start.json never pairs with new rows.
os.makedirs(f"{DOCS}/data", exist_ok=True)
DETAIL_ROWS = 4096
ROW_KEYS = ["n", "c", "ct", "cu", "t", "s", "a", "z", "la", "lo", "b", "ch", "v", "g", "hc", "ip", "f", "h", "mi", "gs", "di", "liq",
            "rg", "ij", "ir", "is", "id_", "in", "ib"]
DENSE = {"n", "a", "c", "ct", "cu", "t", "s", "rg"}            # every row has one; small ints compress to almost nothing in town order
DELTA = {"la": 1e4, "lo": 1e4, "z": 1}                           # integers, each the change from the previous row (rows are in town order)
all_cities, city_ix, rows = [], {}, []
rix = {r["id"]: n for n, r in enumerate(IDX["regions"])}
for rf in IDX["regions"]:
    R = region_file(rf)
    for r in R["places"]:
        name = R["cities"][r["c"]] if r.get("c") is not None else None
        if name is not None and name not in city_ix:
            city_ix[name] = len(all_cities); all_cities.append(name)
        i = r.get("in") or {}
        row = {k: r.get(k) for k in ROW_KEYS if k in r}
        row.update(c=city_ix.get(name), rg=rix[rf["id"]], la=r.get("la"), lo=r.get("lo"), z=int(r["z"]) if (r.get("z") or "").isdigit() else None,
                   ij=i.get("j"), ir=i.get("r"), id_=i.get("d"), ib=i.get("b"), **{"is": i.get("s"), "in": i.get("n")})
        row["_id"], row["_city"] = r["id"], name or ""
        row["_d"] = {k: r[k] for k in ("ph", "w", "note", "jbf", "bf", "on") if r.get(k)} or None
        rows.append(row)


def featured(r):
    return r.get("hc") == 1 or bool(r.get("mi") or r.get("h") or r.get("gs") or r.get("f"))


def street_key(r):
    m = re.match(r"\s*(\d+)\s*(.*)", r.get("a") or "")
    return (m.group(2).lower(), int(m.group(1))) if m else ((r.get("a") or "").lower(), 0)


order_key = lambda r: (r["rg"], r["_city"], street_key(r), r["n"].lower(), r["_id"])
FEAT = sorted([r for r in rows if featured(r)], key=order_key)
REST_ROWS = sorted([r for r in rows if not featured(r)], key=order_key)
ROWS = FEAT + REST_ROWS
assert len({r["_id"] for r in ROWS}) == len(ROWS), "duplicate place ids"
assert all(re.fullmatch(r"[0-9a-f][0-9a-z]*", r["_id"]) for r in ROWS), "an id the ids-<h>.json files can't shard"


def columns(rs):
    out = {}
    for k in ROW_KEYS:
        v = [r.get(k) for r in rs]
        if k in ("la", "lo"):
            v = [None if x is None else round(x * DELTA[k]) for x in v]
        if k in DELTA:     # [change from the previous non-null value], null stays null
            prev, dv = 0, []
            for x in v:
                dv.append(None if x is None else x - prev)
                prev = prev if x is None else x
            v = dv
        if k in DENSE or k in DELTA:
            out[k] = v
        elif any(x is not None for x in v):   # mostly empty: [rows since the last value, value] pairs
            pairs, last = [], -1
            for i, x in enumerate(v):
                if x is not None:
                    pairs.append([i - last, x]); last = i
            out[k] = {"gap": pairs}
    return out


def dump(name, obj):
    json.dump(obj, open(f"{DOCS}/data/{name}", "w"), separators=(",", ":"), ensure_ascii=False)
    return name


VERSION = hashlib.sha256(json.dumps([[r.get(k) for k in ROW_KEYS] + [r["_id"], r["_d"]] for r in ROWS], ensure_ascii=False).encode()).hexdigest()[:12]
nonvenue = [r for r in ROWS if not r.get("v")]
towns = Counter(all_cities[r["c"]] for r in nonvenue if r.get("c") is not None)
kinds = Counter(CUISINES[r["cu"]] for r in nonvenue if r.get("cu") is not None)
boxes = {}
for r in ROWS:
    b = boxes.setdefault(r["rg"], [r["lo"], r["lo"], r["la"], r["la"]])
    b[:] = [min(b[0], r["lo"]), max(b[1], r["lo"]), min(b[2], r["la"]), max(b[3], r["la"])]
data_files = {dump("start.json", {
    "v": VERSION, "generated": TODAY, "total": len(ROWS), "first": len(FEAT), "block": DETAIL_ROWS,
    "jurs": JURS, "cities": all_cities, "cuisines": CUISINES, "counties": COUNTIES, "brands": BRANDS, "sources": IDX["sources"],
    "regions": [{"id": r["id"], "name": r["name"], "box": [round(x, 3) for x in boxes.get(n, [])]} for n, r in enumerate(IDX["regions"])],
    "liqt": IDX["liqt"], "guides": GB, "calibration": IDX.get("calibration", {}),
    "towns": sorted(towns.items(), key=lambda x: (-x[1], x[0])), "kinds": sorted(kinds.items(), key=lambda x: (-x[1], x[0])),
    "rows": {**columns(FEAT), "id": [r["_id"] for r in FEAT]}})}
data_files.add(dump("places.json", {"v": VERSION, "from": len(FEAT), "rows": columns(REST_ROWS)}))
for k in range(0, len(ROWS), DETAIL_ROWS):
    blk = ROWS[k:k + DETAIL_ROWS]
    data_files.add(dump(f"detail-{k // DETAIL_ROWS}.json", {"v": VERSION, "from": k, "ids": [r["_id"] for r in blk], "d": [r["_d"] for r in blk]}))
by_hex = defaultdict(dict)
for n, r in enumerate(ROWS):
    by_hex[r["_id"][0]][r["_id"]] = n
for h, m in sorted(by_hex.items()):
    data_files.add(dump(f"ids-{h}.json", {"v": VERSION, "rows": m}))
json.dump(json.load(open(f"{ROOT}/data/ca/ca_shapes.json")), open(f"{DOCS}/data/ca_shapes.json", "w"), separators=(",", ":"))
data_files.add("ca_shapes.json")
for f in os.listdir(f"{DOCS}/data"):    # an older build's files (core.json, detail.json, blocks past the end) aren't published
    if f not in data_files:
        os.remove(f"{DOCS}/data/{f}")

EXPLORE_CSS = open(f"{ROOT}/scripts/explore.css").read() if os.path.exists(f"{ROOT}/scripts/explore.css") else ""
url = f"{DOMAIN}/explore/"
title = fit(["Search California Restaurants, Taquerías & Dim Sum", "California Restaurant Search & Map | California Eats",
             "Search California Restaurants | California Eats Web App"], 50, 60)
desc = fit([f"Find a California taquería, dim sum house or any of {N_REST:,} restaurants by name, town, street, zip or dish, on a list or a map. Free, in your browser.",
            f"Search {N_REST:,} California restaurants by name, town, street or dish, and map {len(TAQ)} hand-checked taquerías and {len(DIM)} dim sum houses. Free.",
            f"Search {N_REST:,} California restaurants by name, town, street or dish, and map hand-checked taquerías, dim sum, burritos and more. Free, no account."], 140, 160)
nav, bc = crumbs([("Home", "/"), ("Search", "/explore/")])
guide_buttons = "".join(f'<button type="button" data-g="{k}" aria-pressed="false">{e(t)}</button>' for k, t in
                        [(b, lbl) for b, _, lbl, *_ in GUIDE_PAGES] + [("honors", "MICHELIN & James Beard"), ("oldest", "Oldest"),
                                                                     ("inspections", "Inspections"), ("all", "All restaurants"), ("saved", "Saved")])
body = f"""{nav}
  <main id="main">
  <section class="ex-hero">
    <h1><span class="kicker">{BRAND} · on the web</span>Search California restaurants</h1>
    <p class="sub">Look up any of {N_REST:,} California restaurants, cafés and bars, or start from {len(TAQ)} hand-checked taquerías, {len(DIM)} dim sum houses or the MICHELIN and James Beard list. It's the iPhone app's data in your browser, and what you save stays in this browser.</p>
  </section>
  <p id="ex-loading">Loading the restaurant list…</p>
  <noscript><p>The search needs JavaScript. The guides work without it: {", ".join(f'<a href="/{p}">{e(t.lower())}</a>' for _, p, _, t, *_ in GUIDE_PAGES)}.</p></noscript>
  <div id="ex-app" hidden>
    <div class="ex-controls">
      <div class="ex-guides" role="group" aria-label="Guides">{guide_buttons}</div>
      <div class="ex-row1">
        <label class="skip" for="ex-q">Search</label>
        <input id="ex-q" type="search" placeholder="Name, town, street or dish" autocomplete="off" enterkeyhint="search">
        <button type="button" id="ex-locate" class="ex-small">Near me</button>
      </div>
      <div class="ex-row2">
        <label>Sort <select id="ex-sort" aria-label="Sort"></select></label>
        <select id="ex-region" aria-label="Region"></select>
        <select id="ex-town" aria-label="Town"></select>
        <select id="ex-cuisine" aria-label="Kind of place"></select>
        <select id="ex-jur" aria-label="County" hidden></select>
        <label><input type="checkbox" id="ex-chains"> Hide chains</label>
        <button type="button" id="ex-clear" class="ex-small" hidden>Clear filters</button>
        <div class="ex-view" role="group" aria-label="View"><button type="button" data-v="list" aria-pressed="true">List</button><button type="button" data-v="map" aria-pressed="false">Map</button></div>
      </div>
      <p id="ex-sub"></p>
      <p id="ex-count" aria-live="polite"></p>
      <p id="ex-locmsg" aria-live="polite"></p>
    </div>
    <div id="ex-listwrap"><ol id="ex-list" class="ex-list"></ol><button type="button" id="ex-more" class="ex-small" hidden></button></div>
    <div id="ex-mapwrap" hidden>
      <canvas id="ex-map" role="img" aria-label="Map of California with a dot for each place in the list. The list view has the same places."></canvas>
      <div class="ex-zoom"><button type="button" id="ex-zin" aria-label="Zoom in">+</button><button type="button" id="ex-zout" aria-label="Zoom out">−</button></div>
      <p id="ex-maphint"></p>
    </div>
  </div>
  </main>
<script>
{open(f"{ROOT}/scripts/explore.js").read()}
</script>"""
webapp_ld = {"@context": "https://schema.org", "@type": "WebApplication", "name": f"{BRAND} web app", "url": url,
             "applicationCategory": "TravelApplication", "operatingSystem": "Any", "browserRequirements": "Requires JavaScript",
             "description": desc, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
             "publisher": {"@type": "Organization", "@id": f"{DOMAIN}/#org", "name": BRAND, "url": f"{DOMAIN}/"}}
# the place panel is a modal dialog: it and its scrim sit outside the page wrapper, so the web app can make everything else inert
# while a place is open (Tab and screen readers stay in the dialog)
explore_after = """<div id="ex-scrim" class="ex-scrim" hidden></div>
<aside id="ex-panel" class="ex-panel" role="dialog" aria-modal="true" aria-labelledby="ex-pname" hidden></aside>
"""
written.append(page("explore/index.html", title, desc, body, [webapp_ld, bc], extra_css=EXPLORE_CSS, after=explore_after))

# ---------------------------------------------------------------- landing page
shots = [("home", "California Eats home screen: guides for taquerías, dim sum, burritos, fish tacos, Korean barbecue, burger stands, wine country, MICHELIN and James Beard honors, the oldest places and official inspection results, with a search box for every restaurant in the state.", "Every guide, one screen."),
         ("taquerias", "Taquerías list in California Eats, sorted by distance from downtown Los Angeles, with what each one serves.", "Taquerías, closest first."),
         ("detail", "A taquería's page in California Eats: address, a button for ratings, hours and photos in Apple Maps, what it serves and LA County's official inspection grade.", "A place's page, with its county result and Apple Maps."),
         ("map", "California Eats map with pins for hand-checked taquerías.", "Hand-checked places on the map."),
         ("honors", "MICHELIN & James Beard list in California Eats, with each restaurant's distinction.", "Honors, listed as facts.")]
shot_html = []
for i, (name, alt, cap) in enumerate(shots):
    png = f"{DOCS}/img/screen-{name}.png"
    if not os.path.exists(png):
        continue
    w, h = png_size(png)
    lazy = ' loading="lazy"' if i > 1 else ""
    webp = f'<source srcset="/img/screen-{name}.webp" type="image/webp">' if os.path.exists(f"{DOCS}/img/screen-{name}.webp") else ""
    shot_html.append(f'<li><picture>{webp}<img src="/img/screen-{name}.png" alt="{e(alt)}" width="{w}" height="{h}"{lazy} decoding="async"></picture><p>{e(cap)}</p></li>')
shots_section = f"""
  <section id="screens">
    <h2>Inside the app</h2>
    <ul class="shots" tabindex="0" aria-label="California Eats app screenshots">
      {"".join(shot_html)}
    </ul>
  </section>
""" if shot_html else ""
jnames = " and ".join(j["name"] for j in JURS) if len(JURS) <= 2 else ", ".join(j["name"] for j in JURS[:-1]) + " and " + JURS[-1]["name"]
LAC = next((j for j in JURS if j["id"] == "lac"), None)
faq = [
    ("Does California Eats cost anything?", "No. Downloading and using it is free: there are no ads, nothing to buy inside the app and no sign-up."),
    ("How did the taquerías and dim sum houses make the list?", f"By hand, in {CHECKED}. Every taquería, dim sum house, burrito shop, fish taco spot, Korean barbecue restaurant, burger stand and wine-country restaurant on a list has a 2025 or 2026 source of its own: a menu page, an ordering page it runs, or a dated local news story. The rest of the app's {N_REST:,} restaurants, cafés and bars come from Overture Maps' open place data, county food-facility records and California ABC license data."),
    ("What do LA County's A, B and C restaurant grades mean?", "They're Los Angeles County's own letter grades from a restaurant's latest inspection: A for a score of 90 to 100, B for 80 to 89, C for 70 to 79. Seven cities that never adopted grade cards show the score alone, and Pasadena, Long Beach and Vernon run their own health departments, so LA County's grades don't cover them. The app shows each grade exactly as the county recorded it."),
    ("Why is there no health grade for San Diego restaurants?", f"San Diego County publishes its grades only through a search page, not as a data file, so the app doesn't show them; it uses the county's permit list to measure how often map listings match a permitted restaurant. Inspection results in the app come from {jnames}, each on its own scale and never compared with another county's."),
    ("Where do the ratings come from?", "Not from us: California Eats gives no ratings of its own, and no list in it is ordered by ratings. Opening a place shows Apple Maps' own card inside the app, with Apple's ratings, hours, photos and directions. MICHELIN stars and James Beard awards appear as facts, the way MICHELIN's 2026 California selection and the James Beard Foundation announced them, and a finalist is never called a winner."),
    ("Do I have to share my location?", "No. It's only used to put the nearest places first, it stays on your iPhone or iPad, and it never reaches us. Guides, search and the map all work with it off."),
    ("A taquería closed, or a place is missing. How do I report it?", f"Write to {EMAIL} with the place's name and town, and the fix goes into the next update."),
    ("Will there be an Android app?", f"Not for now: California Eats is built for iPhone and iPad. On an Android phone, the web search on this site works in the browser, and if you'd use an Android app, say so at {EMAIL}."),
]
assert LAC is None or LAC["scale"] == ["A", "B", "C"], "the LA County answer describes an A/B/C scale"
faq_html = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in faq)
faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "@id": f"{DOMAIN}/#faq",
          "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
app_ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "MobileApplication", "@id": f"{DOMAIN}/#app", "name": "California Eats: Restaurants",
     "alternateName": ["California Eats", "CA Eats", "California Eats: Taquería & Dim Sum Guide"],
     "description": f"A free guide to {N_REST:,} California restaurants, with hand-checked taquerías, dim sum, burritos, fish tacos, Korean barbecue, burger stands and wine-country dining, MICHELIN and James Beard honors, and official county inspection results.",
     "url": f"{DOMAIN}/", "image": f"{DOMAIN}/og.png", "operatingSystem": "iOS, iPadOS", "applicationCategory": "TravelApplication",
     "applicationSubCategory": "Food & Drink", "inLanguage": "en", "publisher": {"@id": f"{DOMAIN}/#org"},
     "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD", "category": "free"}},
    {"@type": "Organization", "@id": f"{DOMAIN}/#org", "name": BRAND, "url": f"{DOMAIN}/",
     "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/icon-512.png", "width": 512, "height": 512}, "email": EMAIL,
     "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "email": EMAIL, "availableLanguage": "en"},
     # the Eats Ranked hub lists this site as a subOrganization; say so from this side too (Wisconsin's wording, wi-eats a6d63a5)
     "parentOrganization": {"@type": "Organization", "@id": "https://eatsranked.com/#organization", "name": "Eats Ranked", "url": "https://eatsranked.com/"}},
    {"@type": "WebSite", "@id": f"{DOMAIN}/#website", "name": BRAND, "alternateName": ["CA Eats", "California Eats app"], "url": f"{DOMAIN}/",
     "inLanguage": "en", "publisher": {"@id": f"{DOMAIN}/#org"}}]}
if shot_html:
    app_ld["@graph"][0]["screenshot"] = f"{DOMAIN}/img/screen-home.png"
title = "California Eats: Taquería, Dim Sum & Restaurant App for CA"
desc = fit([f"Taquerías, dim sum and burritos checked by hand, plus {N_REST:,} California restaurants, county inspection results and MICHELIN stars. Free for iPhone and iPad.",
            f"Hand-checked taquerías and dim sum, {N_REST:,} California restaurants, LA County grades and MICHELIN stars, in a free iPhone and iPad app with no ads.",
            f"Free iPhone and iPad guide to {N_REST:,} California restaurants, with {len(TAQ)} hand-checked taquerías, {len(DIM)} dim sum houses and MICHELIN honors.",
            f"Free iPhone and iPad guide to {N_REST:,} California restaurants, with hand-checked taquerías, dim sum, burritos and MICHELIN and James Beard honors.",
            f"Free iPhone and iPad guide to {N_REST:,} California restaurants, with hand-checked taquerías and dim sum, MICHELIN stars and inspection results."], 140, 160)
guide_cards = "".join(f'<a class="card{" lead" if i == 0 else ""}" href="/{p_}"><h3>{e(t)}</h3><p>{len(ps)} {e(nouns if len(ps) != 1 else noun)}, checked open.</p></a>'
                      for i, (_, p_, _, t, noun, nouns, ps, _) in enumerate(GUIDE_PAGES))
guide_cards += f'<a class="card" href="/california-michelin-james-beard.html"><h3>MICHELIN &amp; James Beard</h3><p>{len(stars)} starred restaurants, {len(bibs)} Bib Gourmands and James Beard honorees.</p></a>'
if OLD:
    guide_cards += f'<a class="card" href="/california-oldest-restaurants.html"><h3>Oldest restaurants</h3><p>{len(OLD)} places with a sourced opening year.</p></a>'
city_cards = "".join(f'<li><a href="{city_url(c)}">{e(c)}</a></li>' for c in CITY_PAGES)
body = f"""  <main id="main">
  <section class="hero">
    <h1><span class="kicker">{BRAND}: the {e(TAGLINE.lower())} for iPhone and iPad</span>California's restaurants, starting with the taquería</h1>
    <p class="lede">Al pastor, har gow, a carne asada burrito after the beach: {BRAND} starts from what you're hungry for. It puts {len(TAQ)} taquerías and {len(DIM)} dim sum houses we checked by hand next to {N_REST:,} restaurants, cafés and bars in {N_TOWNS:,} California towns, with MICHELIN and James Beard honors and the inspection results {jnames} publish.</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="/explore/">Search on the web</a><span class="pill store-note">Free on iPhone and iPad soon, with no ads and no sign-up.</span></div>
    <ul class="stats" role="list" aria-label="What's in the app">
      <li><b>{len(TAQ)}</b><span>taquerías</span></li>
      <li><b>{len(DIM)}</b><span>dim sum houses</span></li>
      <li><b>{len(stars)}</b><span>MICHELIN-starred</span></li>
      <li><b>{N_REST:,}</b><span>restaurants</span></li>
    </ul>
  </section>

  <section id="what">
    <h2>Built around how California eats</h2>
    <p class="sub">{BRAND} begins with the food people here plan a day around: al pastor and carnitas, Sunday dim sum, a foil-wrapped burrito, Baja fish tacos, galbi on a tabletop grill, a walk-up burger stand, and dining rooms that have been open for generations. Those lists were checked by hand in {CHECKED}, and nothing in them is sorted by stars. Where {jnames} publish inspection results, a place shows its county's latest one, and every place opens its own Apple Maps card for ratings, hours and photos.</p>
  </section>

  <section id="how">
    <h2>Using {BRAND}</h2>
    <ol class="steps">
      <li class="step"><div class="n" aria-hidden="true">1</div><div><h3>Choose what you're after.</h3><p>Start from Taquerías, Dim Sum, Burritos, Fish Tacos, Korean BBQ, Burger Stands, Wine Country, MICHELIN &amp; James Beard, Oldest Places or Inspections, or type a name, town, street or dish to search {N_REST:,} places.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">2</div><div><h3>Narrow it down.</h3><p>Put the closest first, keep to one of {len(REGIONS)} regions, one town or one kind of food, or switch to the map. Hand-checked places show what their own menus list.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">3</div><div><h3>Head out.</h3><p>Open the place's Apple Maps card for hours and photos, call ahead, get directions, or save it for the weekend.</p></div></li>
    </ol>
  </section>
{shots_section}
  <section id="guides">
    <h2>The hand-checked lists</h2>
    <p class="sub">Each one is on the web too. The app adds distance, the map and saved places.</p>
    <div class="grid2">{guide_cards}</div>
  </section>

  <section id="cities">
    <h2>California restaurants by city</h2>
    <p class="sub">From San Diego to Sacramento: the hand-checked places nearby, local MICHELIN and James Beard honors, and the kinds of food each big town has most of.</p>
    <ul class="cities">{city_cards}</ul>
  </section>

  <section id="pricing">
    <h2>What it costs: nothing</h2>
    <p class="sub">There's no subscription, no ad, nothing to unlock and no login. Every list ships inside the app, so it opens quickly and keeps working when the signal drops on Highway 1 or up in the Sierra.</p>
  </section>

  <section id="privacy">
    <h2>What the app knows about you: nothing</h2>
    <p class="sub">{BRAND} has no analytics and no account, and it sends us nothing. Turn on location and it's used on your phone to sort by distance; saved places stay there too. This site uses no cookies or trackers. <a href="/privacy.html">The privacy policy</a> has the details.</p>
  </section>

  <section id="faq">
    <h2>Questions about {BRAND}</h2>
    {faq_html}
  </section>

  <section id="download" class="final">
    <h2>Find your taquería</h2>
    <p class="sub">{BRAND} for iPhone and iPad will be free when it reaches the App Store. Until then, ask us for early access, or use the search right here.</p>
    <div class="cta-row">{store_button()}<a class="btn btn-ghost" href="/explore/">Search on the web</a></div>
  </section>
  </main>"""
written.append(page("index.html", title, desc, body, [app_ld, faq_ld]))

# ---------------------------------------------------------------- privacy and terms
nav, bc = crumbs([("Home", "/"), ("Privacy policy", "/privacy.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Privacy policy</h1>
    <p class="lede">Short version: the {BRAND} app collects nothing about you, and this website doesn't track you. Last updated {nice_date(SITE_UPDATED)}.</p>
  </section>
  <section>
    <h2>The app</h2>
    <ul>
      <li><b>No account, no analytics, no ads.</b> The app has no sign-in, no advertising and no analytics or crash-reporting code. We receive no data from it.</li>
      <li><b>Location.</b> If you allow it, your location is used on your device to sort places by distance and show where you are on the map. It is never sent to us. You can turn it off in Settings at any time.</li>
      <li><b>Saved places and filters</b> are stored only on your device and are deleted when you delete the app.</li>
      <li><b>Apple Maps.</b> The maps in the app are Apple's, loaded from Apple as you look around them. When you open a place's ratings, hours and photos, or ask for directions, the app asks Apple Maps for that place. Apple handles those requests under <a href="https://www.apple.com/legal/privacy/" rel="noopener">Apple's privacy policy</a>, as it does for any app that shows a map.</li>
      <li><b>Spotlight.</b> The app adds its hand-checked and honored places to your device's search index so you can find them from Spotlight. That index stays on your device.</li>
      <li><b>Calls, websites and email</b> you start from a place open in the Phone app, your browser or Mail, and are handled by them.</li>
    </ul>
    <p>On the App Store, the app's privacy label will be "Data Not Collected" (the app isn't on the store yet).</p>
    <h2>This website</h2>
    <p>The site is static pages hosted on GitHub Pages. It sets no cookies and loads no analytics, fonts or scripts from anyone else. The web app keeps three things in your browser's local storage, on your device only: the places you save (<code>cae-saved</code>), the last guide you opened (<code>cae-guide</code>) and the county you last picked under Inspections (<code>cae-jur</code>). Clearing this site's data in your browser deletes them. Its "Near me" button asks your browser for your location only when you press it; the location is used in the page to sort by distance and is never sent anywhere. GitHub may keep standard server logs, such as IP addresses, for security; see <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">GitHub's privacy statement</a>.</p>
    <h2>Email</h2>
    <p>If you email us, we use your message and address only to reply and to fix the listing you told us about. We don't add you to a mailing list or share your address.</p>
    <h2>Children</h2>
    <p>The app collects no personal information from anyone, including children.</p>
    <h2>California residents</h2>
    <p>Because we collect no personal information through the app or this site, there is nothing for us to sell, share or delete. If you emailed us and want that message deleted, ask at <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
    <h2>Changes and contact</h2>
    <p>If this policy changes, the new version will be posted here with a new date. Questions: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
  </section>
  </main>"""
written.append(page("privacy.html", "Privacy Policy: California Eats Taquería & Restaurant App",
                    fit(["The California Eats privacy policy: the app collects no data, keeps your location and saved places on your device, and this site sets no cookies."], 140, 160),
                    body, [bc]))

nav, bc = crumbs([("Home", "/"), ("Terms of use", "/terms.html")])
jur_items = "".join(f"<li>{e(j['agency'])}: official inspection results through {e(nice_date(j['through']))}.</li>" for j in JURS)
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Terms of use</h1>
    <p class="lede">The plain-language terms for the {BRAND} app and this website. Last updated {nice_date(SITE_UPDATED)}.</p>
  </section>
  <section>
    <h2>What the app is</h2>
    <p>{BRAND} is a free guide to restaurants in California. It is provided as is, for personal use, without charge and without warranties of any kind.</p>
    <h2>Check before you go</h2>
    <p>Restaurants open, close, change their hours and change their menus. What a place serves and when it opened are what the place or a named source said when we checked in {CHECKED}. We work to keep the lists right, but we can't promise that any listing is current or complete. Call the restaurant before you make the trip.</p>
    <h2>Inspection results</h2>
    <p>Inspection results are each county's own, shown as the county recorded them at the latest inspection. We don't compute or change them, and we don't compare counties. One inspection is a snapshot of one day; conditions may have changed since. For the official record, check with the county's environmental health department. No county endorses this app.</p>
    <h2>Other people's content</h2>
    <p>Ratings, reviews, hours and photos in each place card come from Apple Maps and are Apple's and its providers', under Apple's terms. Restaurant names and trademarks belong to their owners. MICHELIN and the MICHELIN Guide are trademarks of Michelin; James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. {BRAND} is not affiliated with any restaurant, chain, award body or government agency.</p>
    <h2>Data sources and licenses</h2>
    <ul>
      <li>Overture Maps Foundation places data, under the Community Data License Agreement, Permissive 2.0 (and Apache 2.0 for Foursquare data); boundaries from Overture Maps.</li>
      <li>County of Los Angeles Environmental Health inventory and inspections, under the County's eGIS Terms of Use ("for informational purposes"; provided as is).</li>
      {jur_items}
      <li>San Diego County Department of Environmental Health and Quality food facility permits, public domain.</li>
      <li>California Department of Alcoholic Beverage Control license data, public domain.</li>
      <li>MICHELIN Guide California 2026 distinctions and James Beard Foundation honors, reported as facts from their announcements.</li>
      <li>Hand-checked guides and opening years: our own research, with a source recorded for every place.</li>
    </ul>
    <h2>Corrections</h2>
    <p>If a listing is wrong, or you own a restaurant and want something fixed, email <a href="mailto:{EMAIL}">{EMAIL}</a>. We fix mistakes in the next update.</p>
    <h2>Liability</h2>
    <p>To the extent the law allows, we are not liable for any loss arising from use of the app or site, including a wasted drive to a closed restaurant. California law governs these terms.</p>
    <h2>Changes</h2>
    <p>We may update these terms; the current version and its date are always on this page. See also the <a href="/privacy.html">privacy policy</a>.</p>
  </section>
  </main>"""
written.append(page("terms.html", "Terms of Use: California Eats Taquería & Restaurant App",
                    fit(["The California Eats terms of use: a free California restaurant guide, provided as is. Check before you go, and see where each listing comes from."], 140, 160),
                    body, [bc]))

body = f"""  <main id="main">
  <section class="hero">
    <h1>Page not found</h1>
    <p class="lede">Nothing lives at this address. Head back to the <a href="/">{BRAND} home page</a>, browse the <a href="/{GUIDE_PAGES[0][1] if GUIDE_PAGES else ''}">taquería guide</a>, or find a restaurant by name in the <a href="/explore/">California restaurant search</a>.</p>
  </section>
  </main>"""
page("404.html", f"Page not found | {BRAND}", "This page doesn't exist.", body, robots="noindex,follow")

# ---------------------------------------------------------------- plumbing
urls = ["" if w == "index.html" else w.replace("index.html", "") for w in written]
urls.sort(key=lambda u: (u != "", u.startswith("cities/"), u))
open(f"{DOCS}/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                       + "".join(f"  <url><loc>{DOMAIN}/{u}</loc><lastmod>{LASTMOD}</lastmod></url>\n" for u in urls) + "</urlset>\n")
open(f"{DOCS}/robots.txt", "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
json.dump({"name": BRAND, "short_name": "CA Eats", "description": f"{TAGLINE}, plus {N_REST:,} California restaurants.", "start_url": f"{BASE}/", "display": "browser",
           "background_color": "#f8fafc", "theme_color": "#003262",
           "icons": [{"src": f"{BASE}/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": f"{BASE}/icon-512.png", "sizes": "512x512", "type": "image/png"}]},
          open(f"{DOCS}/site.webmanifest", "w"), indent=2)
if CUSTOM_DOMAIN:
    open(f"{DOCS}/CNAME", "w").write(CUSTOM_DOMAIN + "\n")
elif os.path.exists(f"{DOCS}/CNAME"):
    os.remove(f"{DOCS}/CNAME")   # no custom domain yet: GitHub serves the project address
open(f"{DOCS}/.nojekyll", "w").write("")
os.makedirs(f"{ROOT}/playbook", exist_ok=True)
json.dump({"generated": TODAY, "restaurants": N_REST, "towns": N_TOWNS, "guides": {lbl: len(ps) for _, _, lbl, _, _, _, ps, _ in GUIDE_PAGES},
           "oldest": len(OLD), "honored": len(HON), "michelin_starred": len(stars), "bib": len(bibs), "inspected": len(INSPECTED),
           "jurisdictions": {j["id"]: {"name": j["name"], "through": j["through"]} for j in JURS}, "cities": city_stats},
          open(f"{ROOT}/playbook/site-numbers.json", "w"), indent=1)
print("wrote", len(written) + len(noindexed) + 1, "pages:", ", ".join(written), "| noindex (thin):", ", ".join(noindexed) or "none")
print(f"restaurants {N_REST:,} in {N_TOWNS} towns | " + " | ".join(f"{lbl} {len(ps)}" for _, _, lbl, _, _, _, ps, _ in GUIDE_PAGES)
      + f" | honored {len(HON)} | oldest {len(OLD)} | inspected {len(INSPECTED):,}")
