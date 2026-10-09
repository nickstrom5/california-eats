# Naming, icon and palette (Nick's calls, 2026-10-07)

**App Store name:** `California Eats: Restaurants` (28 of 30)
**Subtitle:** `Taquería & Dim Sum Guide` (24 of 30)
**Home Screen name** (`CFBundleDisplayName`): `CA Eats`
**Website:** https://california.eatsranked.com/ (hub eatsranked.com; until the Cloudflare `california` CNAME resolves, https://nickstrom5.github.io/california-eats/)
**Bundle ID:** `com.californiaeats.ios` · **Repo folder:** `ca-eats/` · planned GitHub repo `nickstrom5/california-eats` (not created; needs Nick's yes)

## Why this name
- It follows the series ("Wisconsin Eats: Restaurants", "Washington Eats: Restaurants") and the eatsranked.com hub, and covers every
  restaurant; the niche sits in the subtitle.
- Taquerías and dim sum are the two guides no California app owns as a hand-checked list; both are things people search by name.
- "CA Eats" fits under the icon; "California Eats" does not.

## Checks run on 2026-10-07 (iTunes Search API, US store)
| Query | Nearest results | Takeaway |
|---|---|---|
| California Eats | California Pizza Kitchen, California Fish Grill ordering, SF Chronicle, ChowNow | no app with the name |
| Golden State Eats | Golden Corral, EatOkra, delivery apps | no exact name |
| Cali Eats | Tijuana Flats, CPK, Washoe Eats (Washoe County, NV) | no exact name; "Cali" reads informal |
| California Restaurants | CPK, California Restaurant Show, CA Restaurant Association | trade-show apps only |

Trademark: not checked. Search USPTO (tmsearch.uspto.gov) for "California Eats" in classes 9 and 43 before submitting.

## Icon
Concept B: a flat avocado half on Pacific blue (`scripts/icon-concepts.swift` draws A taco, B avocado, C fish taco;
`scripts/make-brand.swift` writes the app icon, `docs/og.png` and the favicons).
Redrawn 2026-10-09 in the shared Eats Ranked icon style Nick approved (`../state-prompts/ICON-STYLE.md`): same avocado and colours, now
upright and centred on flat blue, with no sea, wave line or pit highlight. The site's header logo and SVG favicon (`LOGO` in
`scripts/make-site.py`) match it.

## Palette
| Token | Hex | Use |
|---|---|---|
| Pacific blue | `#003262` | headers, buttons, text accents |
| California gold | `#FDB515` | fills only (never text on white: 1.9:1) |
| Poppy | `#E35B1E` | small accents (leaderboard only) |

## Santa Clara County
Its inspection data (green/yellow/red placards + score) states no license and its terms page blocks automated access. Nick: **private
leaderboard only**; the app and website show LA County, San Francisco and Sacramento County results.
