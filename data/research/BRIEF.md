# Research brief: California Eats hand-checked guides (2026-10-07)

You are verifying places for a free restaurant app and website covering California ("California Eats: Restaurants", subtitle
"Taquería & Dim Sum Guide"). A themed guide lists only **hand-checked** places. A listing merely *named* "… Taquería" stays in the
app's directory but is not in a guide unless you check it. **Accuracy beats coverage: a wrong or closed place in a guide is worse
than a missing one.** Work only inside `ca-eats/data/research/`.

## What counts as hand-checked
Each place needs at least one source from **2025 or 2026** that shows it is **open** and **serves the thing the guide is about**:
- the place's own website or menu page (record what you saw and that it was live on the date you checked; prefer pages with a
  2025/2026 date, current hours, or a live online-ordering menu),
- an online-ordering page the restaurant runs (Toast, Square, Clover, ChowNow, its own order site) that is live today,
- a dated 2025–26 local news story from a host whose robots.txt allows ClaudeBot (allowed so far: SFist, Hoodline, LAist, Time Out,
  LA Magazine, WhatNow — check each host's robots.txt first anyway),
- an official 2025–26 health inspection shows the business operates (LA County, SF, Sacramento data), but **not** what it serves:
  you still need a menu or news source for the dishes.
Not acceptable: Yelp, Google (Maps, Search, business.site), TripAdvisor, DoorDash/Uber Eats/Grubhub listings, directory or menu
aggregator sites (menupix, allmenus, restaurantji, etc.), AI summaries, social posts you can't open without logging in.

## Facts only
Record facts, in our own words: what it serves (from its menu), a founding/opening year **only when a source states it** ("opened"
means at this address; a brand's founding year goes in `brand_founded`), and a one-line note. No review text, no star ratings or
scores from anyone, no "best"/"favorite"/"award-winning"/"iconic" claims, no readers' polls. Don't copy menu prices. Never say a
place invented something unless a source says it's *credited with* or *traced to* it, and say who credits it.

## Be polite; never bypass protection
**Check robots.txt before your first fetch of any host.** If it disallows ClaudeBot, anthropic-ai or `*` for the path, don't fetch
and don't use it (blocked already: guide.michelin.com, Eater, LA Times, SF Chronicle, SFGate, SF Standard, Berkeleyside, OC Register,
San Diego Union-Tribune, NBC LA, The Infatuation, Press Democrat). One request at a time per site. A 403/429, a bot check, CAPTCHA,
login wall or "enable JavaScript" means **skip it**: no workarounds, no other user agents. A search-engine summary of a page you
couldn't open is not a source. Don't touch county inspection search portals. Old restaurant domains are often hijacked (gambling,
dating, spam): if a site looks unrelated, record `"website": null` and say so in the note.

## Budget
WebSearch calls are shared across agents (about 140 are left for the whole session). **Use no more than your stated cap.**
WebFetch on a candidate's own website does not count against it, so check candidates' own sites first and search only when needed.
Report how many searches you used.

## Output (write exactly these files; don't touch other files)
1. `data/research/app/<your file>.json`: a JSON list. One object per **checked-open** place:
```json
{"name": "La Taqueria", "address": "2889 Mission St", "city": "San Francisco", "zip": "94110", "county": "San Francisco",
 "kinds": ["taqueria", "burrito"], "open": true, "dishes": ["carnitas taco", "super burrito (no rice)"],
 "opened": 1973, "brand_founded": null, "chain": false,
 "note": "Mission District taquería; burritos come without rice.",
 "website": "https://… (only the place's own live site or ordering page)",
 "sources": [{"url": "https://…", "what": "own menu page, live", "date": "2026-10-07"}],
 "checked": "2026-10-07"}
```
   `kinds` uses only: `taqueria`, `burrito`, `fishtaco`, `dimsum`, `kbbq`, `burgerstand`, `winecountry`, `oldest`.
2. `data/research/closed_<your region>.json`: places you found **closed** (list of {name, address, city, source_url, source_date, why}).
3. `data/research/leads/<your region>.md`: places you couldn't verify, one line each with what's missing.
Use plain ASCII quotes in JSON. Validate your JSON (`python3 -m json.tool file`) before you finish.

Your final message: counts (checked open / closed / leads), searches used, and anything surprising.

## Guide notes
- **Taquerías** (`taqueria`): a place whose menu centers on tacos (taquería, taco shop, taco stand with a fixed address, mariscos
  spots with taco menus). Record the taco styles/fillings on the menu (al pastor, carne asada, carnitas, birria, lengua, tripas,
  cabeza, fish, shrimp) and other headline dishes (burritos, tortas, quesadillas). Chains (Taco Bell, Del Taco, Chipotle) never.
  Regional chains with 3+ locations (e.g. Tacos El Gordo, Leo's) are fine with `"chain": true`, each location checked.
- **Burritos** (`burrito`): Mission-style burrito shops in San Francisco and the Bay Area, and California burritos (carne asada +
  fries) in San Diego. Say which style the menu shows. A taquería can carry both kinds.
- **Fish tacos** (`fishtaco`): Baja-style fried or grilled fish tacos, mostly San Diego County. Menu must show fish tacos.
- **Dim sum** (`dimsum`): a restaurant serving dim sum (daily or weekend brunch), carts or menu order, or a dim sum bakery/takeout
  counter (say which). Record headline items (har gow, siu mai, cha siu bao, cheung fun, egg tarts).
- **Korean BBQ** (`kbbq`): tabletop-grill Korean barbecue restaurants (galbi, samgyeopsal, bulgogi grilled at the table). A Korean
  restaurant without tabletop grills doesn't count.
- **Burger stands** (`burgerstand`): California burger stands and drive-ins (walk-up window or classic drive-in counter). Chains:
  brand facts only from the brand's own site (founding year and city of the first location go in `brand_founded`; `"chain": true`),
  each location confirmed open on the brand's own location page. No logos, nothing about secret menus unless the brand's site shows it.
- **Wine country** (`winecountry`): restaurants (not tasting rooms without a kitchen) in Napa Valley, Sonoma County, Paso Robles,
  the Santa Ynez Valley, Temecula, Lodi, Livermore and Amador. Record the town and a short note on the cooking.
- **Oldest places** (`oldest`): restaurants and bars open at the same address since 1960 or earlier (Gold Rush–era survivors first).
  The opening year must come from a source that states it, and "at this address" must be true (no relocations); put the evidence in
  `opened_note`. Records like "California's oldest restaurant" are claims: write "says it is" or "is credited as", with the source.
