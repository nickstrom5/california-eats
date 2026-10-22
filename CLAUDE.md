# California Eats (ca-eats) — notes for Claude Code sessions

Two products share this folder and one data pipeline:
- **The iOS/iPadOS app** "California Eats: Restaurants" (subtitle "Taquería & Dim Sum Guide", Home Screen "CA Eats", bundle
  `com.californiaeats.ios`; SwiftUI, iOS 18+), plus its generated website in `docs/` (planned home https://california.eatsranked.com/; until
  Nick's Cloudflare `california` CNAME resolves it's built for https://nickstrom5.github.io/california-eats/).
- **The web leaderboard** (`site/`), a private claude.ai Artifact (https://claude.ai/artifact/Nj2pmtTTJjsYL2nSovjx9C). It uses Google 2021
  ratings; the app never does.

Read `../STATE_EATS_PLAYBOOK.md`, then `playbook/12-sources.md`. Never modify `../chi-eats/`, `../wi-eats/` or another state's folder.

## Nick's calls (2026-10-07)
- Name, subtitle and Home Screen name above; icon = the flat avocado half on Pacific blue (`scripts/icon-concepts.swift` concept B),
  redrawn 2026-10-09 in the shared Eats Ranked style Nick approved (upright, flat, no sea or wave line; same food and colours; guide
  `../state-prompts/ICON-STYLE.md`). `swift scripts/make-brand.swift` writes the app icon, og.png and favicons; the site's header logo and
  SVG favicon are `LOGO` in `scripts/make-site.py`. Palette California gold #FDB515 (a fill only, never text on white) and Pacific blue #003262.
- **Santa Clara County's inspection data states no license: private leaderboard only.** The app export (`CA_APP=1`) ships LA County,
  San Francisco and Sacramento results only.

## Data rules (the app's promise)
- The App Store build ships **no Google-derived data**: no ratings, reviews, price levels or Google matching. `CA_APP=1` switches
  `pipeline/california.py` into that mode and writes `data/app/index.json` + `data/app/places-<region>.json`. Copy them to
  `CaliforniaEats/Resources/Data/` after every rebuild. Ratings, hours and photos come live from Apple Maps' own place card.
- **Official inspection results are each county's own, as recorded, never re-graded or blended**: LA County's score and A/B/C grade
  (seven cities without grade cards show the score only: Avalon, Bradbury, Hidden Hills, La Habra Heights, San Marino, Sierra Madre,
  Signal Hill), San Francisco's Pass / Conditional Pass / Closure placard, Sacramento's PASS / CONDITIONAL PASS / CLOSED (only those three
  values are placards). Pasadena, Long Beach and Vernon run their own health departments: not LA County's data. San Diego's grades are
  search-only: not shown. "Through" dates are 7+ days before the fetch (`THROUGH` in california.py), never hard-coded in the app.
- LA County's CSVs keep a rolling 3-year window and are refreshed quarterly: **archive every pull** (old quarters drop off for good).
- The hand-checked guides (taquerías, burritos, fish tacos, dim sum, Korean BBQ, burger stands, wine country, oldest) list only
  `hc` places whose `g` bit is set (1 taqueria, 2 burrito, 4 fishtaco, 8 dimsum, 16 kbbq, 32 burgerstand, 64 winecountry, 128 oldest).
  Each matches an open entry in `data/research/app/*.json` with a 2025–26 source. A listing merely *named* "Taquería" stays in the
  directory but not in the guide. Research brief: `data/research/BRIEF.md`; candidates come from map data only (`pipeline/candidates.py`).
- Honors are facts: MICHELIN Guide California 2026 (`data/research/michelin_ca.json`, from MICHELIN's own release on michelin.com /
  michelinmedia.com) and James Beard 2023–26 + America's Classics (`data/research/jbf_ca.json`). Finalists and semifinalists are never
  called winners. Trademark lines for MICHELIN and James Beard wherever they appear.
- **Respect robots.txt**: a host that disallows ClaudeBot or anthropic-ai is never a source (guide.michelin.com, Eater, LA Times,
  SF Chronicle, SFGate, SF Standard, Berkeleyside, OC Register, San Diego Union-Tribune, NBC LA, The Infatuation, Press Democrat).
  data.ca.gov's robots.txt disallows `/api/`. Never bypass bot protection; don't scrape search-only inspection portals.
- Hijacked pages (QA 2026-10-19, P1 #4; ported 2026-10-21): `check_websites.py` runs `pipeline/injection.py`, Wisconsin's detector, on every
  page (planted casino, betting, adult, pharma and link-farm links, visible, hidden or off-screen; other-language gambling text; parked
  and default pages). Keep it identical to `../wi-eats/pipeline/injection.py`; `test_injection.py` must pass. `--recheck-ok` fetches every
  passing page again before each submission (resumable: pages re-checked in the last 2 days are skipped), `--retry-transient` re-fetches
  429s and connection errors afterwards, and `CHECK_WORKERS=4` slows a run (Squarespace rate-limits across all our concurrent checkers).
- Tracking tags: the app export strips `ref=google`, `referrer=google_food_ordering`, `cn_channel`, `utm_*`, `fbclid`, Yext `cid=RF:YXT…`
  and similar from every outbound link (`pipeline/tracking_params.py`, the same in every state; store ids and locations stay). The site
  reads the app export, and a unit test fails if a tracked link is bundled (QA 2026-10-19, P1 #13).
- Not open to the public (QA 2026-10-19, P1 #7): `pipeline/private_dining.py` (identical in wa-eats and ca-eats) hides employer
  cafeterias ("Google Cafe Nuage", "Amazon Block 21", "Ba @ Google …"), contract caterers' units (Bon Appétit, Guckenheimer, Sodexo,
  Compass One) and school dining ("Basis Independent", "… @ Seattle U") with the non-restaurants. Legal-entity names show the trade
  name (after "dba", without an "Lp"/"LLC" tail); a bare holder name ("Joban & Supreet Enterprises") is removed, and so is a
  repaired one that duplicates a same-address listing starting with the same word. Hand-checked and honored places are exempt; ids
  keep the old name. Read the export's dump of what each rule hid or removed after every change; a unit test guards the bundle.
- Website links: `pipeline/check_websites.py` fetches every link politely; the export ships only links it passed (fail closed). Order:
  export (`CA_APP=1`), check, export again. Re-run before each submission.
- Accents: `norm_name` folds them ("Taco María" = "Taco Maria"); stage-1 keys are recomputed at the start of california.py.
- Official-record matching is cached in `data/ca/official_match.pkl` until stage1, the records or the matching code change.

## Rebuild
```bash
.venv/bin/python pipeline/fetch_overture.py                  # Overture 2026-09-23.1 places, sources, state + county outlines -> data/ca
bash data/raw/official/_scripts/fetch_*.sh                   # county + ABC records (see SOURCES_*.md; archive LA County pulls)
cd pipeline && ../.venv/bin/python listings.py && ../.venv/bin/python calibrate.py
../.venv/bin/python california.py                            # leaderboard -> site/ca_meta.json, ca_<region>.json (+ _detail), ca_shapes.json
CA_APP=1 ../.venv/bin/python california.py                   # app data -> data/app/, and data/ca/website_candidates.json
../.venv/bin/python check_websites.py && CA_APP=1 ../.venv/bin/python california.py
#   faster on a busy Mac: four processes, each owning a quarter of the domains (still one request per domain at a time), then merge:
#   for i in 0 1 2 3; do ../.venv/bin/python check_websites.py --shard $i/4 & done; wait; ../.venv/bin/python check_websites.py --merge
cd .. && .venv/bin/python scripts/make-leaderboard.py         # site/index.html from wi-eats/site/index.html (asserted patches)
cp data/app/*.json CaliforniaEats/Resources/Data/ && .venv/bin/python scripts/make-site.py && .venv/bin/python scripts/qa-site.py
```
Republish the artifact with the same file path (`site/index.html` + its JSON files) to keep the URL.

## Website (`docs/`, generated; QA pass 2026-10-12)
- Generate and check: `.venv/bin/python scripts/make-site.py && .venv/bin/python scripts/qa-site.py` (`--static` skips the browser,
  `--docs DIR` checks another copy, `--port N` pins the test server). Never hand-edit `docs/`.
- Contact on the site is `nick@eatsranked.com` (Nick, 2026-10-12); `qa-site.py` fails on the old Gmail address anywhere in `docs/`. The
  app's `Links.swift` and the playbook's listing/reply files still have the old one until the next build.
- Every page's footer says "Part of Eats Ranked" and the home `#org` node has `parentOrganization` (the hub's `#organization`).
- Copy decisions (Nick, 2026-10-13, family-wide): the web app's middle tier is "High-confidence listing", never "Confirmed listing";
  only Nick's internal TestFlight group exists, so the site never promises a TestFlight invite or link (early-access copy ends at an
  ask; the button's mailto body may ask). `qa-site.py` fails on either (`label_and_promise_checks`).
- Web app data (`docs/data/`): `start.json` (metadata + the ~860 hand-checked, honored and dated places; the first load is ~80 KB
  gzipped with the page), `places.json` (the rest, fetched for All restaurants, Inspections, saved places and `#p=` links), `detail-<k>.json`
  (ids, phones, websites and notes per block of 4,096 rows, fetched when a place opens) and `ids-<h>.json` (rows by id). `qa-site.py`
  measures the transfer with Chrome's DevTools protocol: first load under 1.5 MB, All restaurants under 2.2 MB (hub QA HUB6-08 found 4.5 MB).
- `pipeline/website_blocklist.json` lists website links the site must never publish (hacked or taken-over domains, listing farms such as
  mybistro.online and cafecityguide.website, another business's page): `make-site.py` drops those links (never the place) from every page
  and web-app data file, and `qa-site.py` fails if one appears anywhere in `docs/`. Add entries there; the app's bundle still has them
  until the next export (`check_websites.py` doesn't read the list yet).
- City pages with fewer than three hand-checked, honored or dated places nearby are `noindex` and left out of the sitemap; titles and
  descriptions only name what a page lists. Bump `SITE_UPDATED` in `make-site.py` when the copy, privacy policy or terms change.

## Build the app (shared Mac: see the playbook's "Machine rules")
- The Xcode project is **generated**: `xcodegen generate`. Never commit `CaliforniaEats.xcodeproj`.
- Simulators: this project's own "CA Eats 6.9" (iPhone 17 Pro Max) and "CA Eats iPad 13" (iPad Pro 13-inch), iOS 27.0. Before booting,
  check `ps -u $(id -u) | wc -l` (wait if over ~2,300) and `xcrun simctl list devices | grep Booted` (wait if two or more other "… Eats"
  sims are booted). One booted at a time; shut down after use; never touch other sessions' simulators. One xcodebuild at a time.
- Build: `xcodebuild build -project CaliforniaEats.xcodeproj -scheme CaliforniaEats -destination 'platform=iOS Simulator,name=CA Eats 6.9' -derivedDataPath ./DerivedData CODE_SIGNING_ALLOWED=NO`
- Unit tests: same with `test -only-testing:CaliforniaEatsTests`. UI tests (`-only-testing:CaliforniaEatsUITests`) **without**
  `CODE_SIGNING_ALLOWED=NO`.
- Light mode only. `PrivacyInfo.xcprivacy`: UserDefaults CA92.1, no tracking, no collected data.
- Screens: `-screenshot <home|taquerias|dimsum|detail|map|inspections|honors|saved|about>` (DEBUG only; downtown LA).
- Launch speed: about 107,000 places in nine files decode in parallel (~1.3 s on the Mac simulator). `-timing` (DEBUG) prints app init,
  load start/end and Home shown as Unix times. Most of the cost was `Search.normalize` per place; keep its ASCII fast path. The loading
  screen is static text: a spinner kept XCUITest waiting for the app to go idle.
- **App Store builds use the public Xcode**: `DEVELOPER_DIR="/Applications/Xcode 1.app/Contents/Developer"`. Check `DTXcodeBuild`.

## Outward actions
Everything outward-facing needs Nick's explicit yes each time: pushing (repo https://github.com/nickstrom5/california-eats, Pages live since 2026-10-08),
App Store Connect, uploads, emails, records requests. Never submit for review or accept agreements. Public commits use
`329204362+nickstrom5@users.noreply.github.com`. Never publish Google or raw data (`site/*.json`, `data/ca`, `data/raw`) in a public repo.
