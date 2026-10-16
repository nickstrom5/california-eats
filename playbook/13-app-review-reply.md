# App Review: prepared before submitting (Guideline 2.1 "Information Needed")

Wisconsin's new-developer review (2026-09-28) asked for a screen recording from a physical device, starting at launch, plus answers to six
questions. California Eats should expect the same. Put the reply below in **App Review Information → Notes** from the start, and record the
video before submitting so it's ready to attach. Numbers must match `site-numbers.json`.

## Screen recording (Nick, on his iPhone, latest iOS)

Install from TestFlight first (internal group with Nick; the tester email must be the Apple ID under Settings › your name › Media & Purchases
on the phone, or TestFlight says "not available"). Record with Control Center → Screen Recording, 60–120 seconds, no sound needed:

1. Start on the Home Screen and tap **CA Eats**. The recording must begin with the launch.
2. Home: scroll the cards a little.
3. Tap **Taquerías**, then tap any taquería.
4. On the place: tap **Ratings, hours & photos**. Apple's place card opens. Close it.
5. Tap the **heart** (Save), then go back.
6. Back on Home, tap the search box and type `dim sum monterey park`. Open one result.
7. Tap **MICHELIN & James Beard** on Home and open one place; scroll to "Honors".
8. Tap **Inspections** on Home (LA County is selected; switch to San Francisco), then open one place and scroll to "Health inspections".
9. Tap the **Map** tab, then **Taquerías**, then a pin and its name.
10. Tap the **Saved** tab, where the saved place shows. Then tap **About** and scroll to the sources.

## Reply text (under 4,000 characters)

```
Thank you. Here is the information requested. A screen recording from an iPhone running the latest iOS is attached. It starts at launch and shows the full flow.

1. Screen recording: attached. There is no account, login, user-generated content or paid content.

2. Purpose and audience: California Eats is a free guide to restaurants in California. Its focus is the state's food traditions: 363 taquerías, 86 burrito shops, 87 fish taco spots, 53 dim sum houses, 74 Korean barbecue restaurants, 19 burger stands and 31 wine-country restaurants, each checked by hand in October 2026 against a 2025 or 2026 source: the restaurant's own website, menu or ordering page, or dated local news. It also lists 103,585 restaurants, cafés and bars statewide, MICHELIN and James Beard honors as announced, and official health inspection results from three counties. It is for California residents and visitors deciding where to eat. No ads, account or tracking.

3. How to use it (no login, no setup, no sample files needed):
- Home → Taquerías (or Burritos, Fish Tacos, Dim Sum, Korean BBQ, Burger Stands, Wine Country, MICHELIN & James Beard, Oldest Places, Inspections, Near Me, All Restaurants) → tap any place.
- On a place, tap "Ratings, hours & photos" to open Apple Maps' own place card through MapKit. Directions, Call and Website are below it.
- Search from the Home search box by name, town, street or dish ("al pastor oakland", "dim sum monterey park").
- The Map tab shows each guide as pins. "My location" and the Nearest sort use location only if allowed, on the device.
- The heart saves a place on the device (Saved tab). About lists the sources, licenses and independence statement.
- On iPad, a sidebar replaces the tabs; a place opens in the right-hand column.
- Outside California, the map says so and stays on California; distance sorting still works.
- "CA Eats" is the short Home Screen name of "California Eats: Restaurants".

4. External services and data:
- Apple MapKit: maps, local search to find a place's Apple Maps listing, and Apple's place card for live hours, photos and ratings.
- Core Location: optional, on-device only, for distance sorting.
- Core Spotlight: on-device indexing so places appear in iPhone search.
- No backend, accounts, analytics, advertising, payments or AI services. The restaurant data is bundled in the app.
- Bundled data: Overture Maps Foundation open place data (CDLA Permissive 2.0; Foursquare records Apache 2.0, AllThePlaces CC0; license texts in the app); public food-facility and inspection records of Los Angeles County, San Francisco, Sacramento County and San Diego County; California ABC license data; MICHELIN's and the James Beard Foundation's announcements (facts only); and our own research of restaurants' websites, menus and local news.
- The website with the privacy policy and support page is static and hosted on GitHub Pages: https://nickstrom5.github.io/california-eats/

5. Regional differences: none. The content covers California; the app is offered in the United States and works the same everywhere.

6. Regulated or protected material: the app is not in a regulated industry and includes no protected third-party material. The data is open-licensed or public record, with attribution and licenses on the About tab. Ratings, hours and photos appear only inside Apple's own place card through MapKit; the app stores no ratings or reviews. Inspection results are each county's own (LA County's score and letter grade, San Francisco's and Sacramento County's placard results), labeled official and dated; the app never computes its own grades. MICHELIN and James Beard honors are stated as announced, with trademark notices. Restaurant names are factual references. Every website link was checked before release, and adult venues are excluded. The app is independent and not affiliated with any restaurant, agency, Michelin or the James Beard Foundation.

Support: nick@eatsranked.com
```

(If the custom domain is live by submission, replace the website line with https://california.eatsranked.com and update Links.swift.)
