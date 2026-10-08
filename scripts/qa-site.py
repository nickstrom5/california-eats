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
  junk stored guide don't break it; the Inspections guide shows each county's own results; a failed core.json shows an error.

Until the custom domain is live, the site is built for https://nickstrom5.github.io/california-eats/, so it's served here under the same
/california-eats/ prefix (a temporary folder with a link to docs/).

Usage: .venv/bin/python scripts/qa-site.py [--docs DIR] [--workers N]
"""
import argparse
import base64
import functools
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
ARGS = ap.parse_args()
DOCS = os.path.abspath(ARGS.docs)
HAS_CNAME = os.path.exists(os.path.join(DOCS, "CNAME"))
DOMAIN = open(os.path.join(DOCS, "CNAME")).read().strip() if HAS_CNAME else "nickstrom5.github.io"
PREFIX = "" if HAS_CNAME else "/california-eats"
problems = []


def bad(msg):
    problems.append(msg)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    root = DOCS
    if PREFIX:
        root = tempfile.mkdtemp(prefix="ca-site-")
        os.symlink(DOCS, os.path.join(root, PREFIX.strip("/")))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
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
              r"\ball \d[\d,]* (california )?(restaurants|taquer[ií]as|places)", r"\bbest\b", r"\btop[- ]rated\b"]
_ids = {}


def ids_in(f):
    if f not in _ids:
        _ids[f] = set(re.findall(r'\sid="([^"]+)"', open(f).read()))
    return _ids[f]


def walk_keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk_keys(v)


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
        if re.search(r"<[a-zA-Z][^>]*\sstyle=", s):
            bad(f"{where}: inline style attribute (blocked by the CSP)")
        if re.search(r"<[a-zA-Z][^>]*\son[a-z]+=", s):
            bad(f"{where}: inline event handler (blocked by the CSP)")
        if "<!--" in s:
            bad(f"{where}: HTML comment left in the output")
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
        text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S)))
        low = text.lower()
        for rx in OVERCLAIMS:
            if re.search(rx, low):
                bad(f"{where}: overclaim matching {rx!r}")
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
        if f != "404.html" and f not in paths:
            bad(f"sitemap: {f} exists but isn't in the sitemap")
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
    page.route("**/data/core.json", lambda r: r.abort())
    goto(page, ex, "networkidle")
    page.wait_for_timeout(500)
    if "couldn" not in (page.locator("#ex-loading").text_content() or ""):
        bad("explore: a failed core.json didn't show an error")
    ctx.close()


def main():
    base = serve()
    files = static_checks()
    page_type_checks(files)
    locs = sitemap_checks(files)
    n_static = len(problems)
    jobs = [(urllib.parse.urlparse(loc).path, width) for loc in locs for width in (375, 1280)]
    chunks = [jobs[i::ARGS.workers] for i in range(ARGS.workers)]
    threads = [threading.Thread(target=page_worker, args=(base, c)) for c in chunks]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        webapp_checks(browser, base)
        browser.close()
    print(f"static: {len(files)} HTML files, {n_static} problems | browser: {len(jobs)} page loads at 375 and 1280 px, plus the web app")
    for p in problems:
        print("  ✗", p)
    print("OK" if not problems else f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
