"""QA for the website in docs/. Exits 1 on any problem. Adapted from wi-eats/scripts/qa-site.py and wa-eats/scripts/qa-site.py.

Static checks, every HTML file (no browser):
  title 50-60 and description 140-160 characters (404 exempt), unique titles and descriptions, one <h1>; a Content-Security-Policy
  <meta> before any inline block whose hashes match exactly this page's inline <script>/<style> blocks; the referrer <meta>; no
  inline style or event attributes, no HTML comments; JSON-LD that parses, has no raw "<", and no ratings or reviews; only http(s),
  mailto, tel, data: icons or same-site links, and every same-site link and #anchor resolves; no "all/every" overclaims; MICHELIN and
  James Beard pages carry the trademark line and never call a finalist a winner; no Google; the expected pages exist; sitemap and
  files agree.

Browser checks (headless Chrome via Python Playwright, 375 and 1280 px wide), every sitemap page:
  no sideways scroll, one <h1>, no console errors, no Content-Security-Policy violations, no broken images; at 375 px, every visible
  link, button, input and select is at least 44x44 px (a link inside a sentence is exempt, as in WCAG 2.5.8).

The web app (explore/): loads; searches; opens a place with Directions and focus on Close, and closes on Escape with focus back on the
  row; an emoji search lists nothing; Near me sorts by distance; the map draws; a saved place survives a reload; hostile hashes and a
  junk stored guide don't break it; the Inspections guide shows each county's own results; a failed start.json shows an error.
  Also: 16 px fields and the page's font on phones, the place panel as a modal dialog, Back/Forward with a place open, junk in any
  cae- key, no 'Nearest' without a location, a fresh fix on every Near me press, and a #p= link that is loading or fails.
  A search inside a guide that finds no (or one or two) places offers 'Search all restaurants (N matches)', also before the statewide
  list has loaded (it says it's counting), and one click finds the place; the first load still doesn't fetch places.json; the search
  box's placeholder fits at 375 px. No blocklisted website (pipeline/website_blocklist.json, which mustn't be empty) anywhere in docs/.

Until the custom domain is live, the site is built for https://nickstrom5.github.io/california-eats/, so it's served here under the same
/california-eats/ prefix (a temporary folder with a link to docs/).

Usage: .venv/bin/python scripts/qa-site.py [--docs DIR] [--workers N]
"""
import argparse
import base64
import functools
import gzip
import hashlib
import html
import http.server
import json
import os
import re
import sys
import tempfile
import threading
import urllib.parse
import xml.etree.ElementTree as ET

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ap = argparse.ArgumentParser()
ap.add_argument("--docs", default=os.path.join(ROOT, "docs"))
ap.add_argument("--workers", type=int, default=2)
ap.add_argument("--static", action="store_true", help="static checks only (no browser)")
ap.add_argument("--port", type=int, default=int(os.environ.get("QA_PORT", "0")), help="local port for the test server (0 = any free port)")
ARGS = ap.parse_args()
DOCS = os.path.abspath(ARGS.docs)
HAS_CNAME = os.path.exists(os.path.join(DOCS, "CNAME"))
DOMAIN = open(os.path.join(DOCS, "CNAME")).read().strip() if HAS_CNAME else "nickstrom5.github.io"
PREFIX = "" if HAS_CNAME else "/california-eats"
problems = []


def bad(msg):
    problems.append(msg)


GZIP_TYPES = (".html", ".json", ".js", ".css", ".svg", ".xml", ".txt", ".webmanifest")
_gz = {}


class Quiet(http.server.SimpleHTTPRequestHandler):
    """Serves docs/ like GitHub Pages does where it matters here: text files gzipped when the browser accepts it, so the transfer
    sizes the budget checks measure are the ones a visitor downloads."""

    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path) and self.path.split("?")[0].endswith("/"):
            path = os.path.join(path, "index.html")
        if "gzip" in self.headers.get("Accept-Encoding", "") and os.path.isfile(path) and path.endswith(GZIP_TYPES):
            if path not in _gz:
                _gz[path] = gzip.compress(open(path, "rb").read(), 6)
            body = _gz[path]
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def serve():
    root = DOCS
    if PREFIX:
        root = tempfile.mkdtemp(prefix="ca-site-")
        os.symlink(DOCS, os.path.join(root, PREFIX.strip("/")))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", ARGS.port), functools.partial(Quiet, directory=root))
    srv.handle_error = lambda *a: None     # a browser dropping a connection mid-file isn't a site problem
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


def file_for(path):
    path = urllib.parse.unquote(path.split("#")[0].split("?")[0])
    if PREFIX:
        if not path.startswith(PREFIX + "/") and path != PREFIX:
            return None
        path = path[len(PREFIX):]
    f = os.path.join(DOCS, path.lstrip("/"))
    if os.path.isdir(f):
        f = os.path.join(f, "index.html")
    return f if os.path.isfile(f) else None


def html_files():
    out = []
    for d, _, fs in os.walk(DOCS):
        out += [os.path.relpath(os.path.join(d, f), DOCS) for f in fs if f.endswith(".html")]
    return sorted(out)


# ---------------------------------------------------------------- static checks
SHA = lambda s: "sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()
BANNED_LD = {"aggregateRating", "review", "reviews", "reviewRating", "ratingValue", "reviewCount", "bestRating"}
OVERCLAIMS = [r"every california restaurant", r"every restaurant", r"\ball the restaurants?\b", r"\bsearch all\b", r"\bhas all\b",
              r"\ball \d[\d,]* (california )?(restaurants|taquer[ií]as|places)", r"\bbest\b", r"\btop[- ]rated\b",
              r"\b(confirmed|verified) (open|listing)\b", r"\bverified opening\b",
              # "363 taquerías in each of California's 9 regions" reads as 363 per region; the honors list IS ordered by stars
              r"\bin each of california's \d+ regions\b", r"\bsorts nothing by stars\b"]
# text that contradicts the data rules or reads wrong: "1 places"; LA County results claimed for a city with its own health department
WRONG_TEXT = [r"\b1 places\b", r"places in (pasadena|long beach|vernon) also shows? los angeles county"]
_ids = {}


def ids_in(f):
    if f not in _ids:
        _ids[f] = set(re.findall(r'\sid="([^"]+)"', open(f).read()))
    return _ids[f]


def walk_dicts(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from walk_dicts(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk_dicts(v)


def walk_keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk_keys(v)


ITUNES = '<!-- <meta name="apple-itunes-app" content="app-id=APP_ID"> fill in once the App Store record exists -->'
# other Eats Ranked apps, their repos and folders, and their web apps' storage prefixes (bare state names are fine: Washington Blvd,
# chile colorado, a New York steak)
SIBLINGS = re.compile(r"(?i)\b(?:(?:wisconsin|florida|washington|colorado|connecticut|maine|idaho|new york|michigan|texas) eats"
                      r"|chicago restaurants|chi ranked|(?:wi|fl|wa|co|ct|me|id|ny|chi|mi|tx)-eats|(?:wisconsin|florida|washington|colorado|connecticut"
                      r"|maine|idaho|new-york|michigan|texas)-eats|chicago-restaurants-ranked|(?:fleats|coeats|ideats|nye|wae)-)")


def static_checks():
    titles, descs = {}, {}
    files = html_files()
    for rel in files:
        s = open(os.path.join(DOCS, rel)).read()
        where = rel
        t = re.search(r"<title>(.*?)</title>", s, re.S)
        d = re.search(r'<meta name="description" content="([^"]*)"', s)
        title, desc = html.unescape(t.group(1)) if t else "", html.unescape(d.group(1)) if d else ""
        if rel != "404.html":
            if not 50 <= len(title) <= 60:
                bad(f"{where}: title is {len(title)} characters: {title}")
            if not 140 <= len(desc) <= 160:
                bad(f"{where}: description is {len(desc)} characters")
            if title in titles:
                bad(f"{where}: same title as {titles[title]}")
            if desc in descs:
                bad(f"{where}: same description as {descs[desc]}")
            titles[title], descs[desc] = rel, rel
        else:
            if 'rel="canonical"' in s or 'property="og:url"' in s:
                bad("404.html: has a canonical or og:url")
            if f'href="{PREFIX}/explore/"' not in s:
                bad("404.html: no search link")
        n_h1 = len(re.findall(r"<h1[\s>]", s))
        if n_h1 != 1:
            bad(f"{where}: {n_h1} <h1>")
        m = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', s)
        if not m:
            bad(f"{where}: no Content-Security-Policy meta")
        else:
            csp = dict((p.split(" ", 1) + [""])[:2] for p in (x.strip() for x in m.group(1).split(";")) if p)
            first_inline = min([i for i in (s.find("<style>"), s.find("<script>")) if i >= 0] or [len(s)])
            if m.start() > first_inline:
                bad(f"{where}: the CSP meta comes after an inline block, so it doesn't cover it")
            for k, ok in {"default-src": ("'none'", "'self'"), "object-src": ("'none'",), "base-uri": ("'none'",)}.items():
                if csp.get(k) not in ok:
                    bad(f"{where}: CSP {k} is {csp.get(k)!r}, want one of {ok}")
            if "*" in m.group(1) or "unsafe" in m.group(1):
                bad(f"{where}: CSP has a wildcard or unsafe- source")
            for kind, blocks in (("script-src", re.findall(r"<script>(.*?)</script>", s, re.S)), ("style-src", re.findall(r"<style>(.*?)</style>", s, re.S))):
                have = set(re.findall(r"'(sha256-[^']+)'", csp.get(kind, "")))
                need = {SHA(b) for b in blocks}
                if have != need:
                    bad(f"{where}: CSP {kind} hashes don't match the page's inline blocks")
        if '<meta name="referrer"' not in s:
            bad(f"{where}: no referrer meta")
        # part of the Eats Ranked family: every page's footer links the hub (the hub lists this site as a subOrganization)
        if '<a href="https://eatsranked.com/">Eats Ranked</a>' not in s:
            bad(f"{where}: no 'Part of Eats Ranked' link in the footer")
        if re.search(r"<[a-zA-Z][^>]*\sstyle=", s):
            bad(f"{where}: inline style attribute (blocked by the CSP)")
        if re.search(r"<[a-zA-Z][^>]*\son[a-z]+=", s):
            bad(f"{where}: inline event handler (blocked by the CSP)")
        # the one comment allowed: SEO-SPEC's App Store banner placeholder, in every page's head
        if ITUNES not in s:
            bad(f"{where}: no commented apple-itunes-app placeholder in the head")
        if "<!--" in s.replace(ITUNES, ""):
            bad(f"{where}: HTML comment left in the output")
        # this state's own site: no sibling app, repo or storage prefix named anywhere, comments and inline script included
        for m in re.finditer(SIBLINGS, s):
            bad(f"{where}: names another state's app or repo: {m.group(0)!r}")
        ld_nodes = []
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
            if "<" in raw:
                bad(f"{where}: raw '<' inside JSON-LD")
            try:
                obj = json.loads(raw)
            except ValueError as e:
                bad(f"{where}: bad JSON-LD ({e})")
                continue
            hit = BANNED_LD & set(walk_keys(obj))
            if hit:
                bad(f"{where}: ratings or reviews in JSON-LD: {sorted(hit)}")
            ld_nodes.append(obj)
        # JSON-LD: no empty values, and a bare {"@id": ...} reference points at a node defined on this page
        defined = {n.get("@id") for o in ld_nodes for n in walk_dicts(o) if len(n) > 1 and n.get("@id")}
        for o in ld_nodes:
            for n in walk_dicts(o):
                if any(v == "" for v in n.values()):
                    bad(f"{where}: JSON-LD has an empty value in {n.get('@type') or n.get('name')}")
                if set(n) == {"@id"} and n["@id"] not in defined:
                    bad(f"{where}: JSON-LD refers to {n['@id']}, which this page doesn't define")
        ld_nodes.clear()
        text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S)))
        # a list cut at a comma inside parentheses ("california burrito (carne asada, ...") leaves a paragraph with an open "("
        for blk in re.findall(r"<(p|li|h[1-6]|summary|td)\b[^>]*>(.*?)</\1>", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S), re.S):
            t = html.unescape(re.sub(r"<[^>]+>", "", blk[1]))
            if t.count("(") != t.count(")"):
                bad(f"{where}: unbalanced parentheses in {t[:80]!r}")
        low = text.lower()
        for rx in OVERCLAIMS:
            if re.search(rx, low):
                bad(f"{where}: overclaim matching {rx!r}")
        for rx in WRONG_TEXT:
            if re.search(rx, low):
                bad(f"{where}: text matching {rx!r}")
        if "google" in low and rel not in ("privacy.html", "terms.html"):
            bad(f"{where}: mentions Google")
        if "michelin" in low and not re.search(r"trademarks? of michelin", low):
            bad(f"{where}: MICHELIN without its trademark line")
        if "james beard" in low and not re.search(r"trademarks? of the james beard foundation", low):
            bad(f"{where}: James Beard without its trademark line")
        plain = re.sub(r"san ho won|never (?:called )?a winner", " ", low)   # a restaurant's name; the rule stated
        if re.search(r"(finalist|semifinalist)[^.]{0,40}\b(won|winner|wins)\b|\b(won|winner|wins)\b[^.]{0,40}(finalist|semifinalist)", plain):
            bad(f"{where}: a finalist or semifinalist may read as a win")
        markup = re.sub(r"<script>.*?</script>", "", s, flags=re.S)     # links built inside the web app's script are checked in the browser
        for tag, ref in re.findall(r'<(a|img|link|source|script)\b[^>]*?\s(?:href|src|srcset)="([^"]*)"', markup):
            ref = html.unescape(ref)
            scheme = urllib.parse.urlsplit(ref).scheme.lower()
            if scheme in ("http", "https"):
                continue
            if scheme == "mailto":
                continue
            if scheme == "tel":
                if not re.fullmatch(r"tel:\+?\d{10,15}", ref):
                    bad(f"{where}: bad tel: link {ref}")
                continue
            if scheme == "data" and tag == "link":
                continue
            if scheme:
                bad(f"{where}: link with scheme {scheme}: {ref[:60]}")
                continue
            target = urllib.parse.urljoin(PREFIX + "/" + rel, ref)
            path, _, frag = target.partition("#")
            f = file_for(path) if path else os.path.join(DOCS, rel)
            if not f:
                bad(f"{where}: broken link {ref}")
            elif frag and f.endswith(".html") and "/explore" not in path and frag not in ids_in(f):
                bad(f"{where}: link to a missing anchor {ref}")
    return files


OLD_EMAIL = "work-with-nick@gmail.com"     # Nick, 2026-10-12: the site's address is nick@eatsranked.com
SITE_EMAIL = "nick@eatsranked.com"


def family_and_contact_checks():
    """The contact address is nick@eatsranked.com everywhere in docs/ (every file, not just pages), and the home page's Organization
    names Eats Ranked as its parent."""
    for d, _, fs in os.walk(DOCS):
        for f in fs:
            if f.endswith((".html", ".json", ".xml", ".txt", ".webmanifest", ".js", ".css", ".md", ".svg")):
                if OLD_EMAIL in open(os.path.join(d, f), encoding="utf-8", errors="replace").read():
                    bad(f"{os.path.relpath(os.path.join(d, f), DOCS)}: still shows {OLD_EMAIL}")
    home = open(os.path.join(DOCS, "index.html")).read()
    if f'href="mailto:{SITE_EMAIL}' not in home:
        bad(f"index.html: no mailto:{SITE_EMAIL}")
    org = None
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', home, re.S):
        for n in json.loads(raw).get("@graph", []):
            if n.get("@type") == "Organization" and n.get("@id", "").endswith("/#org"):
                org = n
    if not org:
        bad("index.html: no Organization #org node")
    else:
        if (org.get("parentOrganization") or {}).get("@id") != "https://eatsranked.com/#organization":
            bad("index.html: the #org node has no parentOrganization https://eatsranked.com/#organization")
        if org.get("email") != SITE_EMAIL or (org.get("contactPoint") or {}).get("email") != SITE_EMAIL:
            bad(f"index.html: the #org email isn't {SITE_EMAIL}")


CITY_PROMISES = {"taquer": "taquerias", "dim sum": "dim-sum", "burrito": "burritos", "fish taco": "fish-tacos", "korean b": "korean-bbq",
                  "burger stand": "burger-stands", "wine country": "wine-country", "wine-country": "wine-country", "michelin": "honors", "james beard": "honors"}


def city_page_checks(files):
    """A city page's title and description promise only sections the page has (no "Dim Sum" in a town with none nearby, no honors
    where there are none, no "checked open" without a hand-checked list), and a town page listing fewer than three places stays out
    of search (noindex), since its text would match every other thin town's."""
    for f in files:
        if not f.startswith("cities/"):
            continue
        s = open(os.path.join(DOCS, f)).read()
        head = html.unescape(re.search(r"<title>(.*?)</title>", s, re.S).group(1) + " " + re.search(r'<meta name="description" content="([^"]*)"', s).group(1)).lower()
        head = head.replace("í", "i")
        for word, sec in CITY_PROMISES.items():
            if word in head and f'<section id="{sec}"' not in s:
                bad(f"{f}: title or description mentions {word!r}, but the page has no {sec} section")
        guide_secs = [v for k, v in CITY_PROMISES.items() if v != "honors" and f'<section id="{v}"' in s]
        if "checked open" in head and not guide_secs:
            bad(f"{f}: says checked open, but lists no hand-checked guide")
        lede = html.unescape(re.sub(r"<[^>]+>", "", re.search(r'<p class="lede">(.*?)</p>', s, re.S).group(1)))
        if re.search(r"\b1 (taquerías|dim sum\b(?! house)|burrito shops|fish taco spots|burger stands|wine country|fish tacos)|korean bbq|\b\d+ wine country\b", lede):
            bad(f"{f}: lede counts don't read right: {lede[:90]!r}")
        n_places = len(re.findall(r'<ol class="places">.*?</ol>', s, re.S)) and sum(x.count("<li>") for x in re.findall(r'<ol class="places">(.*?)</ol>', s, re.S))
        if n_places < 3 and 'content="noindex' not in s:
            bad(f"{f}: lists {n_places} places but is indexable (thin)")


def city_overlap_checks(files):
    """No two city pages read alike: the share of 5-word runs two town pages' main text has in common stays under half (a 10-mile
    radius once made Pasadena's page mostly San Gabriel's list)."""
    sh = {}
    for f in files:
        if f.startswith("cities/"):
            s = open(os.path.join(DOCS, f)).read()
            main = re.search(r"<main.*?</main>", s, re.S).group(0)
            words = re.findall(r"[a-z0-9']+", html.unescape(re.sub(r"<[^>]+>", " ", main)).lower())
            sh[f] = {tuple(words[i:i + 5]) for i in range(len(words) - 4)}
    names = sorted(sh)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            j = len(sh[a] & sh[b]) / max(1, len(sh[a] | sh[b]))
            if j > 0.5:
                bad(f"{a} and {b} share {j:.0%} of their text")


def privacy_storage_checks():
    """The privacy page names every localStorage key the web app writes, and doesn't call the App Store label live before the app is."""
    ex = open(os.path.join(DOCS, "explore/index.html")).read()
    prefix = re.search(r'localStorage\.setItem\("([a-z]+-)"', ex)
    keys = set(re.findall(r'store\.set\("([a-z]+)"', ex))
    priv = open(os.path.join(DOCS, "privacy.html")).read()
    if not prefix or not keys:
        bad("explore: can't find the web app's localStorage keys")
        return
    if prefix.group(1) != "cae-":
        bad(f"explore: localStorage prefix {prefix.group(1)!r} isn't California's cae-")
    for k in sorted(keys):
        if prefix.group(1) + k not in priv:
            bad(f"privacy.html: doesn't name the web app's {prefix.group(1) + k} key")
    for name in ("privacy.html", "terms.html"):
        page_s = open(os.path.join(DOCS, name)).read()
        if not re.search(r"Last updated (January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}\.", page_s):
            bad(f"{name}: no readable 'Last updated <Month D, YYYY>' date")
    if re.search(r"privacy label is", priv):
        bad("privacy.html: says the App Store privacy label is live (the app isn't on the store yet)")


def page_type_checks(files):
    need = ["index.html", "california-taquerias.html", "california-michelin-james-beard.html", "privacy.html", "terms.html",
            "explore/index.html", "404.html"]
    for n in need:
        if n not in files:
            bad(f"missing page {n}")
    cities = [f for f in files if f.startswith("cities/")]
    if len(cities) < 10:
        bad(f"only {len(cities)} city pages")
    home = open(os.path.join(DOCS, "index.html")).read()
    for c in cities:
        if f'href="{PREFIX}/{c}"' not in home:
            bad(f"home doesn't link {c}")


def sitemap_checks(files):
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.parse(os.path.join(DOCS, "sitemap.xml")).getroot()
    locs, paths = [], set()
    for u in root.findall("s:url", ns):
        loc, lastmod = u.find("s:loc", ns).text, u.find("s:lastmod", ns)
        if lastmod is None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lastmod.text or ""):
            bad(f"sitemap: {loc} has no valid lastmod")
        p = urllib.parse.urlparse(loc)
        if p.netloc != DOMAIN:
            bad(f"sitemap: {loc} isn't on {DOMAIN}")
        f = file_for(p.path)
        if not f:
            bad(f"sitemap: {loc} has no file")
        else:
            paths.add(os.path.relpath(f, DOCS))
        locs.append(loc)
    if len(locs) != len(set(locs)):
        bad("sitemap: duplicate URLs")
    for f in files:
        noindex = 'content="noindex' in open(os.path.join(DOCS, f)).read()
        if f != "404.html" and f not in paths and not noindex:
            bad(f"sitemap: {f} exists but isn't in the sitemap")
        if noindex and f in paths:
            bad(f"sitemap: {f} is noindex but listed")
    robots = open(os.path.join(DOCS, "robots.txt")).read()
    if "Sitemap:" not in robots:
        bad("robots.txt doesn't point at the sitemap")
    return locs


# ---------------------------------------------------------------- browser checks
INIT = """
window.__csp = [];
document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(e.violatedDirective + ' ' + (e.blockedURI || 'inline')));
"""
TAP = """(scope) => {
  const out = [];
  const root = scope ? document.querySelector(scope) : document;
  const blockOf = (el) => { let n = el.parentElement; while (n && getComputedStyle(n).display.startsWith('inline')) n = n.parentElement; return n; };
  for (const el of root.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, summary')) {
    let t = el;
    if (el.matches('input[type=checkbox], input[type=radio]') && el.closest('label')) t = el.closest('label');
    if (t.closest('[hidden], [inert]') && !scope) continue;
    const cs = getComputedStyle(t);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const r = t.getBoundingClientRect();
    if (r.width === 0 || r.height === 0 || r.right + scrollX <= 0 || r.bottom + scrollY <= 0) continue;
    if (t.tagName === 'A' && cs.display === 'inline') {
      const b = blockOf(t), own = t.textContent.replace(/\\s+/g, ' ').trim(), all = (b ? b.textContent : '').replace(/\\s+/g, ' ').trim();
      if (all.length > own.length + 2) continue;
    }
    if (r.width < 43.5 || r.height < 43.5) out.push(`${t.tagName.toLowerCase()}${t.id ? '#' + t.id : ''}${t.className && typeof t.className === 'string' ? '.' + t.className.split(' ')[0] : ''} "${(t.textContent || t.getAttribute('aria-label') || '').trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
  }
  return out;
}"""


def goto(page, url, until="load"):
    """Navigate, once more with a longer wait if the machine is busy; None if the page never loaded."""
    err = None
    for timeout in (30000, 90000):
        try:
            return page.goto(url, wait_until=until, timeout=timeout)
        except Exception as e:
            err = e
    bad(f"{urllib.parse.urlparse(url).path}: didn't load ({str(err).splitlines()[0][:80]})")
    return None


def fresh(page, url):
    page.goto("about:blank")
    return goto(page, url, "networkidle")


def rows_ready(page):
    page.wait_for_function("() => document.querySelectorAll('.ex-row').length > 0", timeout=90000)


def page_worker(base, jobs):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        pages, errors = {}, []
        for width in (375, 1280):
            ctx = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 900})
            ctx.add_init_script(INIT)
            pg = ctx.new_page()
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pages[width] = pg
        for path, width in jobs:
            page = pages[width]
            errors.clear()
            if not goto(page, base + path, "networkidle" if "/explore" in path else "load"):
                continue
            if "/explore" in path:
                rows_ready(page)
            where = f"{path} @{width}"
            over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if over > 1:
                bad(f"{where}: scrolls sideways by {over}px")
            if page.locator("h1").count() != 1:
                bad(f"{where}: {page.locator('h1').count()} <h1>")
            for v in page.evaluate("window.__csp"):
                bad(f"{where}: CSP violation: {v}")
            if width == 375:
                for t in page.evaluate(TAP, None):
                    bad(f"{where}: tap target under 44px: {t}")
            else:
                imgs = page.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.currentSrc || i.src)")
                imgs = [u for u in imgs if not page.request.get(u).ok]
                problems.extend(f"{where}: image didn't load {u}" for u in imgs)
            problems.extend(f"{where}: console error: {e}" for e in errors)
        browser.close()


def webapp_checks(browser, base):
    ex = base + PREFIX + "/explore/"
    for width in (375, 1280):
        ctx = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 760},
                                  geolocation={"latitude": 34.0522, "longitude": -118.2437}, permissions=["geolocation"])
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        w = f"explore @{width}"
        goto(page, ex + "#g=all", "networkidle")
        rows_ready(page)
        search = page.locator("#ex-q")
        search.fill("providence melrose")
        page.wait_for_timeout(700)
        if not page.locator(".ex-row").count():
            bad(f"{w}: search 'providence melrose' found nothing")
        else:
            page.locator(".ex-row").first.click()
            page.wait_for_function("() => document.querySelector('#ex-panel .ex-act-row a')", timeout=30000)
            page.wait_for_timeout(400)
            panel = page.locator("#ex-panel")
            if not panel.is_visible() or not panel.locator("a", has_text="Directions").count():
                bad(f"{w}: opening a place showed no details")
            if page.evaluate("document.activeElement?.id") != "ex-close":
                bad(f"{w}: focus isn't on Close when a place opens")
            if "MICHELIN" not in (panel.text_content() or ""):
                bad(f"{w}: Providence's panel shows no MICHELIN honor")
            if width == 375:
                for t in page.evaluate(TAP, "#ex-panel"):
                    bad(f"{w} (panel open): tap target under 44px: {t}")
            page.keyboard.press("Escape")
            page.wait_for_timeout(250)
            st = page.evaluate("({ hidden: document.querySelector('#ex-panel').hidden, row: document.activeElement?.classList.contains('ex-row') })")
            if not st["hidden"] or not st["row"]:
                bad(f"{w}: Escape didn't close the panel and return focus to the row: {st}")
        for q in ("taco maria costa mesa", "dim sum monterey park", "al pastor oakland"):
            search.fill(q)
            page.wait_for_timeout(700)
            if not page.locator(".ex-row").count():
                bad(f"{w}: search {q!r} found nothing")
        # a name that is the whole query comes first; a street named like a town is still a street
        for q, want, first in (("taco maria", "Taco Mar", True), ("1001 n alameda", "Philippe", False)):
            search.fill(q)
            page.wait_for_timeout(900)
            names = page.locator(".ex-row b").all_text_contents()
            if (first and not (names and names[0].startswith(want))) or (not first and not any(n.startswith(want) for n in names[:20])):
                bad(f"{w}: search {q!r} should {'start with' if first else 'list'} {want}…, got {names[:3]}")
        search.fill("🌮")
        page.wait_for_timeout(500)
        if page.locator(".ex-row").count():
            bad(f"{w}: an emoji search listed places")
        search.fill("")
        page.wait_for_timeout(400)
        page.locator("#ex-locate").click()
        page.wait_for_timeout(1200)
        if "away" not in (page.locator(".ex-row").first.text_content() or "") and "mi" not in (page.locator(".ex-row").first.text_content() or ""):
            bad(f"{w}: Near me didn't sort by distance")
        page.locator('.ex-view button[data-v="map"]').click()
        page.wait_for_timeout(1500)
        painted = page.evaluate("""() => { const c = document.querySelector('#ex-map'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let n = 0; for (let i = 3; i < d.length; i += 4 * 7) if (d[i]) n++; return n; }""")
        if painted < 500:
            bad(f"{w}: the map didn't draw")
        page.locator('.ex-view button[data-v="list"]').click()
        page.wait_for_timeout(300)
        page.locator(".ex-row").first.click()
        page.wait_for_selector("#ex-save")
        name = page.locator("#ex-pname").text_content()
        page.locator("#ex-save").click()
        page.keyboard.press("Escape")
        fresh(page, ex + "#g=saved")
        page.wait_for_function("() => document.querySelector('.ex-row, .ex-empty')", timeout=90000)
        if name not in (page.locator("#ex-list").text_content() or ""):
            bad(f"{w}: a saved place ({name}) wasn't in Saved after a reload")
        # each county's own results, never blended
        for i, label in ((0, ("A", "B", "C")), (1, ("Pass", "Conditional Pass", "Closure")), (2, ("PASS", "CONDITIONAL PASS", "CLOSED"))):
            fresh(page, ex + f"#g=inspections&county={i}")
            rows_ready(page)
            badges = {t.strip().lower() for t in page.locator("#ex-list .ex-res").all_text_contents()}
            if not badges & {x.lower() for x in label} and not badges & {"grade " + x.lower() for x in label}:
                bad(f"{w}: Inspections county {i} shows none of {label}")
        for h in ("#g=constructor", "#g=__proto__", "#g=toString&sort=__proto__&town=constructor&county=99"):
            errors.clear()
            fresh(page, ex + h)
            page.wait_for_timeout(400)
            if errors or not page.locator(".ex-row").count():
                bad(f"{w}: {h} broke the web app: {errors[:2]}")
        page.evaluate("localStorage.setItem('cae-guide', JSON.stringify('__proto__'))")
        errors.clear()
        fresh(page, ex)
        page.wait_for_timeout(400)
        if errors or not page.locator(".ex-row").count():
            bad(f"{w}: a junk stored guide broke the web app: {errors[:2]}")
        for v in page.evaluate("window.__csp"):
            bad(f"{w}: CSP violation: {v}")
        problems.extend(f"{w}: console error: {e}" for e in errors)
        ctx.close()
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    page.route("**/data/start.json", lambda r: r.abort())
    goto(page, ex, "networkidle")
    page.wait_for_timeout(500)
    if "couldn" not in (page.locator("#ex-loading").text_content() or ""):
        bad("explore: a failed start.json didn't show an error")
    ctx.close()
    # the statewide list fails to load: All restaurants says so and offers Try again, which works once the network is back
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    blocked = [True]
    page.route("**/data/places.json*", lambda r: r.abort() if blocked[0] else r.continue_())
    goto(page, ex + "#g=all", "networkidle")
    try:
        page.wait_for_selector("#ex-retry", timeout=30000)
        blocked[0] = False
        page.locator("#ex-retry").click()
        rows_ready(page)
    except Exception as e:
        bad(f"explore: a failed places.json didn't offer a working Try again ({str(e).splitlines()[0][:80]})")
    ctx.close()


# ---------------------------------------------------------------- web app: what a visitor downloads, and links to one place
FIRST_ROW = """window.__firstRow = 0;
new MutationObserver(() => { if (!window.__firstRow && document.querySelector('.ex-row')) window.__firstRow = performance.now(); })
  .observe(document, { subtree: true, childList: true });"""
BUDGET_FIRST = 1_500_000   # bytes over the wire for /explore/ until it's usable, idle prefetches included (HUB6-08: it was 4.5 MB)
BUDGET_ALL = 2_200_000     # All restaurants: the statewide list (1.9 MB in Oct 2026), fetched only when that guide or Inspections opens


def transfer(browser, url, ready):
    """Fresh, uncached load of url: total encoded (gzip) bytes of every response, measured with the Chrome DevTools protocol, once
    `ready` holds and the network has been quiet (plus 2.5 s for requestIdleCallback prefetches)."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    sizes, names = {}, {}
    cdp.on("Network.responseReceived", lambda e: names.__setitem__(e["requestId"], e["response"]["url"]))
    cdp.on("Network.loadingFinished", lambda e: sizes.__setitem__(e["requestId"], e["encodedDataLength"]))
    goto(page, url, "load")
    try:
        page.wait_for_function(ready, timeout=90000)
    except Exception:
        bad(f"{url.split('/explore/')[-1] or 'explore'}: never became usable")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2500)
    page.wait_for_load_state("networkidle")
    files = {urllib.parse.urlparse(names.get(k, "")).path.rsplit("/", 2)[-2:][-1] or "explore/": v for k, v in sizes.items()}
    ctx.close()
    return sum(sizes.values()), files


def load_source():
    """Every place the app ships, by id (data/app/, the generator's input), to check what the web app shows against."""
    idx = json.load(open(os.path.join(ROOT, "data/app/index.json")))
    out = {}
    for rf in idx["regions"]:
        R = json.load(open(os.path.join(ROOT, "data/app", rf["file"])))
        for r in R["places"]:
            out[r["id"]] = {**r, "city": R["cities"][r["c"]] if r.get("c") is not None else ""}
    return out


def panel_matches(page, rec, where):
    """The open place panel shows this record: name, street address and zip, Directions to its coordinates, its phone and website."""
    try:
        page.wait_for_function("(n) => document.querySelector('#ex-pname')?.textContent === n", arg=rec["n"], timeout=60000)
        page.wait_for_function("() => !document.querySelector('#ex-save')?.disabled", timeout=60000)
        # its block of details (phone, website) can arrive after its id (a #p= link resolves the id from ids-<h>.json first)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(300)
    except Exception:
        bad(f"{where}: the panel never showed {rec['n']!r} (shows {page.locator('#ex-pname').text_content() if page.locator('#ex-pname').count() else None!r})")
        return
    addr = page.locator(".ex-addr").text_content() or ""
    for part in (rec.get("a"), rec.get("z"), rec.get("city")):
        if part and part not in addr:
            bad(f"{where}: panel address {addr!r} lacks {part!r}")
    dirs = page.locator("#ex-panel a", has_text="Directions").get_attribute("href") or ""
    want = f"daddr={round(rec['la'], 4)},{round(rec['lo'], 4)}"
    m = re.search(r"daddr=(-?[\d.]+),(-?[\d.]+)", dirs)
    if not m or abs(float(m.group(1)) - rec["la"]) > 6e-5 or abs(float(m.group(2)) - rec["lo"]) > 6e-5:
        bad(f"{where}: Directions go to {dirs[-40:]}, want about {want}")
    tel = page.locator("#ex-panel a[href^='tel:']")
    if rec.get("ph") and (not tel.count() or tel.first.get_attribute("href") != "tel:" + re.sub(r"[^\d+]", "", rec["ph"])):
        bad(f"{where}: panel phone isn't {rec['ph']}")
    site = page.locator("#ex-panel a", has_text="Website")
    if rec.get("w") and (not site.count() or site.first.get_attribute("href") != rec["w"]):
        bad(f"{where}: panel website isn't {rec['w']}")
    if not rec.get("w") and site.count():
        bad(f"{where}: panel shows a website the data doesn't have")


def explore_load_checks(browser, base):
    ex = base + PREFIX + "/explore/"
    data = os.path.join(DOCS, "data")
    rows = lambda: "() => document.querySelectorAll('.ex-row').length > 0"
    total, files = transfer(browser, ex, rows())
    print(f"  explore first load: {total / 1e6:.2f} MB over the wire ({', '.join(f'{k} {v // 1024} KB' for k, v in sorted(files.items()))})")
    if total > BUDGET_FIRST:
        bad(f"explore: first load transfers {total / 1e6:.2f} MB, over the {BUDGET_FIRST / 1e6:.1f} MB budget: {files}")
    extra = sorted(set(files) - {"explore/", "start.json"})
    if extra:
        bad(f"explore: the first load fetches more than the page and start.json: {extra}")
    total, files = transfer(browser, ex + "#g=all", rows())
    print(f"  explore All restaurants: {total / 1e6:.2f} MB over the wire")
    # once the statewide list has arrived, it's on screen within 2 s (sorting 100,000 names with localeCompare took 3-5 s): the time the
    # first row appeared, minus the end of the last data file that had arrived before it
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    ctx.add_init_script(FIRST_ROW)
    page = ctx.new_page()
    goto(page, ex + "#g=all", "load")
    rows_ready(page)
    lag = page.evaluate("""() => { const f = window.__firstRow, r = performance.getEntriesByType('resource').filter((e) => /data\\/[a-z]+\\.json/.test(e.name) && e.responseEnd <= f);
        return f && r.length ? f - Math.max(...r.map((e) => e.responseEnd)) : null; }""")
    ctx.close()
    if lag is not None and lag > 2000:
        bad(f"explore #g=all: the list took {lag / 1000:.1f} s to show after its data arrived")
    if total > BUDGET_ALL:
        bad(f"explore #g=all: transfers {total / 1e6:.2f} MB, over the {BUDGET_ALL / 1e6:.1f} MB budget: {files}")
    if not os.path.exists(os.path.join(data, "start.json")):
        bad("explore: no data/start.json")
        return
    src = load_source()
    start = json.load(open(os.path.join(data, "start.json")))
    first_ids = start["rows"]["id"]
    # a featured place (the first file) and two from the statewide list, each opened by a #p= link on a fresh load
    feat = next(i for i in first_ids if src.get(i, {}).get("w") and src[i].get("ph"))
    blk = json.load(open(os.path.join(data, "detail-3.json")))
    rest = [i for i in blk["ids"] if src.get(i, {}).get("w")][:1] + [blk["ids"][-1]]
    for pid, h in [(feat, f"#p={feat}"), (rest[0], f"#p={rest[0]}"), (rest[1], f"#g=all&p={rest[1]}")]:
        if pid not in src:
            bad(f"explore: {pid} isn't in data/app")
            continue
        if h.startswith("#p=") and pid == feat:
            total, files = transfer(browser, ex + h, "() => document.querySelector('#ex-pname')")
            if total > BUDGET_FIRST:
                bad(f"explore {h}: a link to a hand-checked place transfers {total / 1e6:.2f} MB: {files}")
        ctx = browser.new_context(viewport={"width": 375, "height": 812})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        goto(page, ex + h, "load")
        panel_matches(page, src[pid], f"explore {h}")
        if f"p={pid}" not in page.evaluate("location.hash"):
            bad(f"explore {h}: the address bar lost the place")
        problems.extend(f"explore {h}: {e}" for e in errors)
        ctx.close()
    # a row from the statewide list opened from the list: its panel matches the data, and the address bar gets its id
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    goto(page, ex + "#g=all", "load")
    rows_ready(page)
    page.locator("#ex-q").fill(src[rest[0]]["n"] + " " + src[rest[0]]["city"])
    page.wait_for_timeout(900)
    hit = page.locator(".ex-row", has_text=src[rest[0]]["n"])
    if not hit.count():
        bad(f"explore: All restaurants search didn't find {src[rest[0]]['n']} in {src[rest[0]]['city']}")
    else:
        hit.first.click()
        panel_matches(page, src[rest[0]], "explore (opened from the All list)")
        page.wait_for_function("(id) => location.hash.includes('p=' + id)", arg=rest[0], timeout=30000)
    keys = page.evaluate("Object.keys(localStorage)")
    if any(not k.startswith("cae-") for k in keys):
        bad(f"explore: localStorage keys without California's cae- prefix: {keys}")
    ctx.close()


def webapp_behavior_checks(browser, base):
    """The web app's phone fonts, the place dialog, Back/Forward, junk in localStorage, the sort label without a location, a fresh
    location fix on every press, and a #p= link whose place is still loading or fails to load (verification pass, 2026-10-12)."""
    ex = base + PREFIX + "/explore/"
    src = open(os.path.join(DOCS, "explore", "index.html"), encoding="utf-8").read()
    # 1. 'font: 14px inherit' is invalid CSS, so the browser drops the whole rule: inputs fell to 13.33 px (iOS zooms on focus)
    for m in re.findall(r"font:\s*([^;}]*)", src):
        if "inherit" in m and m.strip() != "inherit":
            bad(f"explore: invalid font shorthand 'font: {m.strip()}' (the browser ignores it)")
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    goto(page, ex + "#g=taqueria")
    rows_ready(page)
    f = page.evaluate("""() => { const cs = (s) => getComputedStyle(document.querySelector(s)), body = getComputedStyle(document.body).fontFamily;
        return { small: ['#ex-q', '#ex-sort', '#ex-region', '#ex-town', '#ex-cuisine'].filter((s) => parseFloat(cs(s).fontSize) < 16),
                 font: ['.ex-guides button', '#ex-locate', '.ex-view button', '#ex-zin'].filter((s) => cs(s).fontFamily !== body) }; }""")
    for sel in f["small"]:
        bad(f"explore @375: {sel} is under 16 px (iOS Safari zooms the page when it gets focus)")
    for sel in f["font"]:
        bad(f"explore @375: {sel} doesn't use the page's font")
    # 3. the place panel is a modal dialog: named, the page behind inert, Tab stays inside, Escape returns to the row
    page.locator(".ex-row").nth(2).click()
    page.wait_for_timeout(500)
    d = page.evaluate("""() => { const p = document.querySelector('#ex-panel');
        return { role: p.getAttribute('role'), modal: p.getAttribute('aria-modal'), name: !!document.getElementById(p.getAttribute('aria-labelledby') || '-'),
                 inert: !!document.querySelector('#ex-q').closest('[inert]') }; }""")
    if d != {"role": "dialog", "modal": "true", "name": True, "inert": True}:
        bad(f"explore: the place panel isn't a named modal dialog with the page behind it inert: {d}")
    for _ in range(14):
        page.keyboard.press("Tab")
        if page.evaluate("(() => { const a = document.activeElement; return a !== document.body && !document.querySelector('#ex-panel').contains(a); })()"):
            bad("explore: Tab left the open place panel for the page behind it")
            break
    ctx.close()
    # 2. Back with a place open closes it and keeps the search; Forward opens it again
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    goto(page, base + PREFIX + "/")
    goto(page, ex + "#g=taqueria&q=oakland")
    rows_ready(page)
    page.locator(".ex-row").first.click()
    page.wait_for_selector("#ex-pname")
    name = page.locator("#ex-pname").text_content()
    page.go_back()
    page.wait_for_timeout(600)
    st = page.evaluate("({ path: location.pathname, panel: document.querySelector('#ex-panel')?.hidden, q: document.querySelector('#ex-q')?.value })")
    if not st["path"].endswith("/explore/") or st["panel"] is not True or st["q"] != "oakland":
        bad(f"explore: Back with a place open should close it and keep the search, got {st}")
    else:
        page.go_forward()
        page.wait_for_timeout(800)
        if page.evaluate("document.querySelector('#ex-panel').hidden ? null : document.querySelector('#ex-pname').textContent") != name:
            bad("explore: Forward didn't reopen the place")
    # the skip link's #main isn't app state: the search stays
    fresh(page, ex + "#g=taqueria&q=oakland")
    rows_ready(page)
    page.evaluate("location.hash = 'main'")
    page.wait_for_timeout(400)
    if page.evaluate("document.querySelector('#ex-q').value") != "oakland":
        bad("explore: the skip link (#main) cleared the search")
    ctx.close()
    # 4. any page on the shared github.io origin can write cae- keys: junk in them mustn't stop the app
    for key, val in (("cae-saved", '{"x":1}'), ("cae-saved", "not json"), ("cae-saved", "[null, 5, {}]"), ("cae-saved", '"abc"'),
                     ("cae-guide", '{"x":1}'), ("cae-jur", '"__proto__"')):
        ctx = browser.new_context(viewport={"width": 375, "height": 812})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        goto(page, base + PREFIX + "/404.html")
        page.evaluate("([k, v]) => localStorage.setItem(k, v)", [key, val])
        goto(page, ex)
        try:
            rows_ready(page)
            page.locator('.ex-guides button[data-g="saved"]').click()
            page.wait_for_function("() => /^\\d+ place/.test(document.querySelector('#ex-count').textContent)", timeout=30000)
        except Exception:
            bad(f"explore: {key}={val} in localStorage stopped the web app: {errors[:1]}")
        ctx.close()
    # 5. no "Nearest" before there's a location (the list is A to Z until then)
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    goto(page, ex + "#g=taqueria&sort=nearest")
    rows_ready(page)
    if "Nearest" in (page.locator("#ex-count").text_content() or ""):
        bad("explore: the count says 'Nearest' with no location")
    ctx.close()
    # 6. Near me asks for a fresh fix on every press, and says so outside California
    ctx = browser.new_context(viewport={"width": 375, "height": 812}, geolocation={"latitude": 34.0522, "longitude": -118.2437}, permissions=["geolocation"])
    page = ctx.new_page()
    goto(page, ex + "#g=taqueria")
    rows_ready(page)
    page.locator("#ex-locate").click()
    page.wait_for_timeout(1000)
    la = page.locator(".ex-row .ex-town").first.text_content()
    ctx.set_geolocation({"latitude": 38.5816, "longitude": -121.4944})   # Sacramento
    if not page.locator("#ex-locate").is_visible():
        bad("explore: Near me is gone after the first fix, so it can't be refreshed")
    else:
        page.locator("#ex-locate").click()
        page.wait_for_timeout(1000)
        if "Sacramento" not in (page.locator(".ex-row .ex-town").first.text_content() or "") or la == page.locator(".ex-row .ex-town").first.text_content():
            bad("explore: a second Near me press kept the old location")
        ctx.set_geolocation({"latitude": 39.5296, "longitude": -119.8138})   # Reno
        page.locator("#ex-locate").click()
        page.wait_for_timeout(1000)
        if "outside California" not in (page.locator("#ex-locmsg").text_content() or ""):
            bad("explore: Near me in Reno didn't say it's outside California")
    ctx.close()
    # a #p= link to a place in the statewide list: says it's loading, and if the list can't load, says so and offers Try again
    blk = os.path.join(DOCS, "data", "detail-9.json")
    if not os.path.exists(blk):
        bad("explore: no data/detail-9.json to take a statewide-list place from")
        return
    pid = json.load(open(blk))["ids"][7]
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    hold = [True]
    page.route("**/data/places.json*", lambda r: r.abort() if hold[0] else r.continue_())
    goto(page, ex + f"#p={pid}")
    try:
        page.wait_for_selector("#ex-linkretry", timeout=30000)
        if f"p={pid}" not in page.evaluate("location.hash"):
            bad("explore: a #p= link whose place failed to load lost its p= from the address bar")
        hold[0] = False
        page.locator("#ex-linkretry").click()
        page.wait_for_function("() => document.querySelector('#ex-pname')", timeout=60000)
    except Exception as e:
        bad(f"explore: a #p= link whose place failed to load showed no error with a working Try again ({str(e).splitlines()[0][:80]})")
    ctx.close()
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)    # a slow connection (300 kbps): the 2 MB statewide list takes about a minute
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 200, "downloadThroughput": 300 * 128, "uploadThroughput": 300 * 128})
    goto(page, ex + f"#p={pid}", "commit")
    page.wait_for_function("() => document.querySelector('#ex-app') && !document.querySelector('#ex-app').hidden", timeout=60000)
    if "Opening the place" not in (page.locator("#ex-locmsg").text_content() or ""):
        bad("explore: a #p= link to a place still loading shows nothing while it loads")
    ctx.close()


FAMOUS = ("porto's bakery", "Porto's Bakery")   # a famous California place in no guide (only in the statewide list, places.json)


def guide_search_checks(browser, base):
    """The web app opens on a guide, and typing searches that guide only (ME-V08 / WI-V-03): a search the guide can't answer offers
    'Search all restaurants' with the same words, before the statewide list (places.json) has loaded too (it fetches it, says it's
    counting, then shows the count), and one click finds the place. The first load still doesn't fetch places.json. Also: the search
    box's placeholder isn't cut off at 375 px (it read "...zip or d")."""
    ex = base + PREFIX + "/explore/"
    q, want = FAMOUS
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    held = []   # places.json requests, held until released: the offer must work while they're in flight
    page.route("**/data/places.json*", lambda r: held.append(r))
    goto(page, ex + "#g=taqueria")
    rows_ready(page)
    # the placeholder's text as the value of the same box: same width, font, padding and border, as type=text (a type=search box with a
    # value makes room for its clear button, which the placeholder doesn't have), then scrollWidth against clientWidth
    ph = page.evaluate("""() => { const el = document.querySelector('#ex-q'), t = el.type, v = el.value, cs = getComputedStyle(el);
        const keep = { fontSize: cs.fontSize, fontFamily: cs.fontFamily, fontWeight: cs.fontWeight, fontStyle: cs.fontStyle, letterSpacing: cs.letterSpacing,
          paddingLeft: cs.paddingLeft, paddingRight: cs.paddingRight, borderLeftWidth: cs.borderLeftWidth, borderRightWidth: cs.borderRightWidth,
          borderStyle: 'solid', boxSizing: cs.boxSizing, width: cs.width, flex: 'none' };
        const size = parseFloat(cs.fontSize);
        el.type = 'text'; Object.assign(el.style, keep); el.value = el.placeholder;
        const r = { ph: el.placeholder, scroll: el.scrollWidth, client: el.clientWidth, size };
        el.value = v; el.type = t; el.removeAttribute('style'); return r; }""")
    if ph["scroll"] > ph["client"]:
        bad(f"explore @375: the search placeholder {ph['ph']!r} is cut off (scrollWidth {ph['scroll']} > clientWidth {ph['client']})")
    if ph["size"] < 16:
        bad(f"explore @375: the search box is {ph['size']}px, under 16px")
    page.wait_for_timeout(300)
    if held:
        bad("explore: the first load (a guide, no search) fetched places.json")
    page.locator("#ex-q").fill(q)
    page.wait_for_timeout(700)
    if page.locator(".ex-row").count():
        bad(f"explore: {q!r} now has a result in the Taquerías guide; pick another famous place outside every guide for this check")
    btn = page.locator("#ex-all")
    if not btn.count():
        bad(f"explore: searching {q!r} in Taquerías before the statewide list loaded is a dead end ({(page.locator('#ex-list').text_content() or '').strip()[:90]!r}), with no way to search all restaurants")
        ctx.close()
        return
    if "counting" not in (btn.text_content() or "") or not held:
        bad(f"explore: while the statewide list loads, the offer should fetch it and say it's counting: {btn.text_content()!r}, places.json requested: {bool(held)}")
    for r in held:
        r.continue_()
    page.unroute("**/data/places.json*")
    try:
        page.wait_for_function("() => /\\(\\d[\\d,]* match/.test(document.querySelector('#ex-all')?.textContent || '')", timeout=60000)
    except Exception:
        bad(f"explore: the 'Search all restaurants' offer never showed a count after the statewide list loaded: {page.locator('#ex-list').text_content()!r}")
        ctx.close()
        return
    n = int(re.search(r"\(([\d,]+) match", btn.text_content()).group(1).replace(",", ""))
    page.locator("#ex-all").click()
    page.wait_for_timeout(600)
    first = page.locator(".ex-row").first.text_content() if page.locator(".ex-row").count() else ""
    count = page.locator("#ex-count").text_content() or ""
    pressed = page.evaluate("document.querySelector('.ex-guides button[aria-pressed=\"true\"]')?.dataset.g")
    if want not in first or pressed != "all" or page.locator("#ex-q").input_value() != q:
        bad(f"explore: one click on 'Search all restaurants' should list {want} first in All restaurants with the same words: first row {first[:60]!r}, guide {pressed!r}")
    if not count.startswith(f"{n:,} place"):
        bad(f"explore: the offer said {n:,} matches but All restaurants lists {count!r}")
    if not page.evaluate("document.activeElement?.classList.contains('ex-row')"):
        bad("explore: after 'Search all restaurants', keyboard focus isn't on the first result")
    # one or two results in a guide, more statewide: the offer follows the short list (Tito's Tacos: Culver City is a hand-checked taquería)
    page.locator('.ex-guides button[data-g="taqueria"]').click()
    page.locator("#ex-q").fill("tito's tacos")
    page.wait_for_timeout(700)
    rows, offer = page.locator(".ex-row").count(), page.locator("#ex-all").text_content() if page.locator("#ex-all").count() else ""
    if not (1 <= rows < 3 and re.search(r"\(\d+ matches\)", offer or "")):
        bad(f"explore: 'tito's tacos' in Taquerías ({rows} rows) should offer the statewide matches too: {offer!r}")
    # nothing anywhere: no offer, the plain message
    page.locator("#ex-q").fill("zzqxv")
    page.wait_for_timeout(700)
    if page.locator("#ex-all").count() or "No places match" not in (page.locator("#ex-list").text_content() or ""):
        bad("explore: a search nothing statewide matches still offers 'Search all restaurants'")
    ctx.close()
    # clicking the offer before the statewide list arrives: All restaurants says it's loading, then lists the place
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    held = []
    page.route("**/data/places.json*", lambda r: held.append(r))
    goto(page, ex + "#g=dimsum")
    rows_ready(page)
    page.locator("#ex-q").fill(q)
    page.wait_for_timeout(700)
    if not page.locator("#ex-all").count():
        bad(f"explore: searching {q!r} in Dim Sum before the statewide list loaded offers nothing")
    else:
        page.locator("#ex-all").click()
        page.wait_for_timeout(300)
        if "Loading" not in (page.locator("#ex-count").text_content() or ""):
            bad(f"explore: 'Search all restaurants' clicked while the statewide list loads shows no loading state: {page.locator('#ex-count').text_content()!r}")
        for r in held:
            r.continue_()
        page.unroute("**/data/places.json*")
        try:
            page.wait_for_function("(w) => (document.querySelector('.ex-row')?.textContent || '').includes(w)", arg=want, timeout=60000)
        except Exception:
            bad(f"explore: 'Search all restaurants' clicked while the statewide list loaded never listed {want}")
    ctx.close()


def blocklist_checks():
    """No blocklisted website (pipeline/website_blocklist.json: hacked sites, listing farms, another business's page) anywhere in docs/:
    pages, JSON-LD and every web-app data file, any case, with or without www. or http(s)://. An empty or missing list fails too (the
    check would pass on anything), and so does an entry this check couldn't match."""
    path = os.path.join(ROOT, "pipeline", "website_blocklist.json")
    if not os.path.exists(path):
        bad("no pipeline/website_blocklist.json")
        return
    entries = json.load(open(path))
    if not isinstance(entries, list) or not entries:
        bad("pipeline/website_blocklist.json is empty: the blocklist check would pass on anything")
        return
    pats = []
    for b in entries:
        if b.get("match", "domain") == "domain":
            dom = (b.get("domain") or "").strip().lower().removeprefix("www.")
            if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", dom):
                bad(f"pipeline/website_blocklist.json: {b.get('domain')!r} isn't a bare domain (no scheme, path or spaces)")
                continue
            pats.append((b["domain"], re.compile(r"(?<![a-z0-9.-])(?:[a-z0-9-]+\.)*" + re.escape(dom) + r"(?![a-z0-9-])", re.I)))
        else:
            raw = b.get("url") or b.get("domain") or ""     # make-site.py reads a "url" entry the same way
            if not raw.strip():
                bad(f"pipeline/website_blocklist.json: a url entry without a url ({b.get('place')!r})")
                continue
            u = re.escape(re.sub(r"^https?://(www\.)?", "", raw.strip().lower()).rstrip("/"))
            pats.append((raw, re.compile(r"(?<![a-z0-9.-])(?:www\.)?" + u + r"/?(?![a-z0-9/_-])", re.I)))
    for d, _, fs in os.walk(DOCS):
        for fn in fs:
            if not fn.endswith(GZIP_TYPES):
                continue
            text = open(os.path.join(d, fn), encoding="utf-8", errors="replace").read()
            for name, rx in pats:
                n = len(rx.findall(text))
                if n:
                    bad(f"{os.path.relpath(os.path.join(d, fn), DOCS)}: blocklisted website {name} appears {n}x")


def main():
    base = serve()
    files = static_checks()
    page_type_checks(files)
    family_and_contact_checks()
    city_page_checks(files)
    city_overlap_checks(files)
    privacy_storage_checks()
    blocklist_checks()
    locs = sitemap_checks(files)
    n_static = len(problems)
    if ARGS.static:
        print(f"static: {len(files)} HTML files, {n_static} problems (browser checks skipped)")
        for p in problems:
            print("  ✗", p)
        sys.exit(1 if problems else 0)
    # every page, noindexed ones and the 404 included (the sitemap leaves those out)
    jobs = [(PREFIX + "/" + f.removesuffix("index.html"), width) for f in files for width in (375, 1280)]
    chunks = [jobs[i::ARGS.workers] for i in range(ARGS.workers)]
    threads = [threading.Thread(target=page_worker, args=(base, c)) for c in chunks]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        explore_load_checks(browser, base)
        webapp_checks(browser, base)
        webapp_behavior_checks(browser, base)
        guide_search_checks(browser, base)
        browser.close()
    print(f"static: {len(files)} HTML files, {n_static} problems | browser: {len(jobs)} page loads at 375 and 1280 px, plus the web app")
    for p in problems:
        print("  ✗", p)
    print("OK" if not problems else f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
