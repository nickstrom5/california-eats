# App Store listing (ASO)

Numbers here must match `site-numbers.json`, which `scripts/make-site.py` rewrites from the data on every run. Current (2026-10-07 build):
363 taquerías, 86 burrito shops, 87 fish taco spots, 53 dim sum houses, 74 Korean BBQ restaurants, 19 burger stands, 31 wine-country
restaurants (hand-checked; a place can be in two guides), 18 places open at the same address since 1960 or earlier, 285 MICHELIN and James
Beard honorees, 103,585 restaurants in 1,126 towns, official inspection results on 33,669 places (LA County, San Francisco, Sacramento
County). Re-check after every data refresh.

## Name (30 max)
`California Eats: Restaurants` (28)

## Subtitle (30 max)
`Taquería & Dim Sum Guide` (24)

Together they index: california, eats, restaurants, taquería (Apple folds the accent, so "taqueria" matches), dim, sum, guide.

## Keywords (100 max, commas, no spaces after commas, no words already in the name or subtitle)
`la,sf,san diego,taco,burrito,fish taco,korean bbq,oldest,bay area,oakland,san jose,sacramento,food` (98)

- "taco" and "burrito" are the head terms the subtitle doesn't carry; "fish taco" and "korean bbq" are guides.
- City names are the biggest win. Los Angeles is too long; "la" and "sf" carry the short forms people type. Fresno, Long Beach, Pasadena and
  Orange County didn't fit; rotate them in after a month of App Store Connect search-term data.
- No trademarks (no MICHELIN, James Beard, In-N-Out, Yelp), no "best", "top" or "#1".

## Promotional text (170 max, editable any time without review)
`363 taquerías, 53 dim sum houses, burritos, fish tacos and Korean BBQ, each checked by hand. Plus 100,000+ California restaurants near you.` (139)

## Description
The first lines show before "more", so they carry the pitch.

```
California's restaurants, starting with the taquería.

California Eats is a free guide to eating in California: 363 taquerías, 86 burrito shops, 87 fish taco spots, 53 dim sum houses, 74 Korean barbecue restaurants, 19 burger stands and 31 wine-country restaurants we checked by hand, plus 103,585 restaurants, cafés and bars in 1,126 towns, from Los Angeles, San Francisco and San Diego to Fresno, Sacramento and Eureka. No account, no ads.

CALIFORNIA GUIDES
• Taquerías: from East LA and the Mission to San Diego taco shops, with what each one serves.
• Burritos: Mission-style burritos in the Bay Area and California burritos in San Diego.
• Fish Tacos: Baja-style fried and grilled fish tacos, mostly in San Diego County.
• Dim Sum: San Gabriel Valley halls, Chinatowns and the Bay Area.
• Korean BBQ: tabletop grills in Koreatown and across the state.
• Burger Stands and Wine Country: walk-up stands, and restaurants in Napa, Sonoma, Paso Robles and other wine towns.
• MICHELIN & James Beard: restaurants in the MICHELIN Guide California 2026 selection, and James Beard winners, finalists and semifinalists, labeled exactly as announced.
• Oldest Places: restaurants and bars open at the same address since 1960 or earlier, oldest first.
• Inspections: official results from Los Angeles County (score and A/B/C grade), San Francisco and Sacramento County, shown as each county records them.

FIND IT FAST
• Sort by distance, or browse the map by taquerías, dim sum, burritos, Korean BBQ or honors.
• Search by name, town, street or dish: "al pastor oakland", "dim sum monterey park".
• Filter by region, town or cuisine, hide chains.
• Save places, and find hand-checked places from iPhone search (Spotlight).

LIVE DETAILS FROM APPLE MAPS
Tap "Ratings, hours & photos" on any place to open Apple Maps' own place card, with current hours, photos, ratings and directions.

HOW THE LISTS ARE BUILT
Every place in the taquería, burrito, fish taco, dim sum, Korean barbecue, burger stand and wine-country guides was checked by hand in October 2026 against a 2025 or 2026 source: its own website, menu or ordering page, or dated local news. The rest of the restaurants come from Overture Maps open data, county food-facility records and California ABC license data, checked for reliability against those records. Website links are checked too. Nothing is ranked by star ratings.

PRIVATE BY DESIGN
No account, no tracking, no ads. Your location, if you share it, only sorts lists on your device. Saved places stay on your device.

Places open and close, so check before you go. Spot a mistake? Email nick@eatsranked.com.

An independent app, not affiliated with any restaurant, chain or government agency (including the County of Los Angeles, the City and County of San Francisco, Sacramento County and California ABC), or with Michelin or the James Beard Foundation. MICHELIN and the MICHELIN Guide are trademarks of Michelin. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. Place data from Overture Maps Foundation (CDLA Permissive 2.0) and others; sources and licenses are on the About tab.
```

## What's New (1.0)
`First release: taquerías, dim sum, burritos, fish tacos, Korean BBQ and 100,000+ California restaurants.`

## Screenshots
Upload in this order (one file at a time into Media Manager's 6.9" and 13" slots; verify the order after a reload). No negative board and no
B, C, Conditional Pass, Closure or CLOSED place in any image: the Inspections shot uses the best-first sort.

| # | File (iPhone 6.9" / iPad 13") | Caption to overlay (optional) |
|---|---|---|
| 1 | `home.png` / `ipad-home.png` | 100,000+ California restaurants |
| 2 | `taquerias.png` / `ipad-taquerias.png` | Taquerías, nearest first |
| 3 | `detail.png` / `ipad-detail.png` | Live hours & photos from Apple Maps |
| 4 | `map.png` / `ipad-map.png` | Taquerías, dim sum and honors on the map |
| 5 | `dimsum.png` / `ipad-dimsum.png` | Dim sum, checked by hand |
| 6 | `honors.png` / `ipad-honors.png` | MICHELIN & James Beard, as announced |
| 7 | `inspections.png` / `ipad-inspections.png` | Official county inspection results |
| 8 | `saved.png` / `ipad-saved.png` | Save your spots |

## Category
Primary Food & Drink, secondary Travel. Age rating: alcohol references "Infrequent" (bars, wine country, "Serves alcohol") → 13+;
everything else None/No.

## App Review
Reply and recording script: `13-app-review-reply.md`. Put the reply text in App Review Information → Notes from the start.
