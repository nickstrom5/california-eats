# California sources (verified 2026-10-07)

Details, endpoints, field lists and fetch scripts: `data/raw/official/SOURCES_socal.md`, `SOURCES_norcal.md`, `SOURCES_sd_abc.md`
(git-ignored with the raw data) and `data/raw/official/_scripts/`. Honors: `data/research/michelin_ca.json`, `data/research/jbf_ca.json`.

## Official inspection results in bulk (shown as recorded, never re-graded, never blended across counties)

| Jurisdiction | Dataset | Official result | License | Window | Cadence |
|---|---|---|---|---|---|
| Los Angeles County (DEH; not Pasadena, Long Beach, Vernon) | data.lacounty.gov (ArcGIS Hub) CSV items: inspections `19b6607ac82c4512b10811870975dbdc`, violations `5eaea9f89b7549ee841da7617d3a9cba`, inventory `4f31c9a99e444a40a3806e3bbe7b5fdd` | Score (0–100) + letter grade A/B/C | LA County eGIS terms: copy, redistribute, commercial use OK; no implied endorsement | Rolling 3 years (Oct 2023–Sep 2026 today) | Quarterly; **archive every pull** (old quarters drop off) |
| San Francisco (DPH) | data.sf.gov `tvy3-wexg` (2024–present) | Placard: Pass / Conditional Pass / Closure (score retired 2021) | PDDL (public domain) | 2024-01 → | Daily; since Jul 2025 `inspection_type` is blank and volume fell |
| Santa Clara County (DEH) | data.sccgov.org `vuw7-jmjk`, `2u2d-8jej`, `wkaa-4ccv` | Placard G/Y/R + score | **None stated** → private leaderboard only (Nick, 2026-10-07) | Rolling ~2 years | Daily |
| Sacramento County (EMD) | ArcGIS item `aa16a71990f44ff6aa74aff30fbf2cbd` | PASS / CONDITIONAL PASS / CLOSED (only those three values are placards) | CC public domain | Rolling ~3 years | Daily |

LA County quirks: CSVs are Windows-1252; 1,176 inventory rows have 0/0 coordinates; seven cities never adopted grade cards
(Avalon, Bradbury, Hidden Hills, La Habra Heights, San Marino, Sierra Madre, Signal Hill), so we show their score only.

## Lists without inspection results
- **San Diego County DEHQ** food facility permits, `c5ez-ufrd` (public domain, monthly; no coordinates). Its official A/B/C grades
  exist only in the SD Food Info search app, which we don't scrape, so no San Diego grades are shown.
- **California ABC** daily data export (public domain; abc.ca.gov/licensing/licensing-reports/): every active license statewide.
  On-sale types 40/41/42/47/48/49/59/60/61/75/87/90 tell us a place serves beer, beer & wine, or has a full bar. No coordinates.
- **Berkeley** business licenses (NAICS 722) only; inspections are search-only.

## Search-only, blocked or unavailable (not collected)
Orange County (portal 403), Riverside (Cloudflare challenge), San Bernardino (search only), Ventura (Accela search), Alameda (offline
during a software change), Contra Costa (Akamai 403), San Mateo (frozen at 2022; host robots disallows all), Fresno (document search),
Pasadena (search portal), Long Beach (closures page only), Vernon (Akamai 403). data.ca.gov has no statewide food inspections, and
its robots.txt disallows `/api/`: don't use that path.

## Map listings
Overture Maps places, release 2026-09-23.1 (CDLA-Permissive-2.0 / Apache-2.0 / Foursquare NOTICE), 179,975 California eating and
drinking listings before cleanup. County outlines from Overture divisions.

## Honors
- **MICHELIN Guide California 2026** (ceremony 2026-06-24, San Diego): 10 three-star, 13 two-star, 60 one-star, 117 Bib Gourmand,
  18 Green Stars, 321 Recommended (count only). Source: MICHELIN's own release (michelin.com PDF, michelinmedia.com).
  guide.michelin.com's robots.txt disallows ClaudeBot: not used. The michelin.com PDF's starred-table address column is scrambled;
  addresses come from the michelinmedia.com tables.
- **James Beard Awards** 2023–2026 (winners, finalists, semifinalists named as such) and all 16 California America's Classics, from
  jamesbeard.org.
- Hosts that block ClaudeBot and are never used: guide.michelin.com, Eater, LA Times, SF Chronicle, SFGate, SF Standard, Berkeleyside,
  OC Register, San Diego Union-Tribune, NBC LA, Bakersfield.com, The Infatuation, Press Democrat.

## Research incidents to disclose
- 2026-10-07: a source-check agent sent 7 catalog requests to data.ca.gov `/api/` in the same batch as its robots.txt check, before
  reading that robots.txt disallows `/api/`. Nothing from it is used.
- 2026-10-07: the MICHELIN brief told the agent to try one WebFetch of guide.michelin.com; it returned content, but that host's
  robots.txt disallows ClaudeBot, so nothing from it is used. Future briefs: check robots.txt before the first fetch.
- 2026-10-07: the North & Central research agent followed about 8 redirects to hosts whose robots.txt it hadn't checked first, and
  deleted a scratch file `/tmp/x.html` that belonged to another session (Suffolk County, NY data). Nothing from those redirects is used.
- 2026-10-07: the James Beard agent read JBF's past-awards and Good Food Finder records through the site's own search backend (Algolia,
  with the public search key the jamesbeard.org pages ship). No robots.txt there (404); read-only, facts only, cited per entry.
- 2026-10-07: research agents fetched with their own descriptive user agents; the SoCal agent cited ocdrop.com for Orange County dates.
- 2026-10-07: stopping the link checker mid-save truncated `data/ca/website_check.json`; about 24,000 links were fetched a second time
  (one request per domain at a time, as before). Saves are atomic now.
