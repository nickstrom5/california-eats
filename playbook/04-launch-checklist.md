# Launch checklist (California Eats)

Everything below is outward-facing: each step needs Nick's explicit yes at the time.

Status 2026-10-08: website steps 1, 2 and 5 are done (Nick's yes, 2026-10-08): the public repo https://github.com/nickstrom5/california-eats,
Pages live at https://nickstrom5.github.io/california-eats/ (all 37 sitemap URLs return 200), and California on the eatsranked.com hub
(commit e9a7c33; the hub's page-size check went from 150 KB to 200 KB with Nick's OK). Build 1.0.0 (1) is archived with the public Xcode
(`build/CaliforniaEats.xcarchive`, DTXcodeBuild 27A266a), but the upload stopped at "App record with bundle identifier
com.californiaeats.ios not found on App Store Connect": nothing was uploaded. After Nick creates the record, upload it with
`DEVELOPER_DIR="/Applications/Xcode 1.app/Contents/Developer" xcodebuild -exportArchive -archivePath build/CaliforniaEats.xcarchive
-exportOptionsPlist build/ExportOptions-upload.plist -exportPath build/export -allowProvisioningUpdates` (the plist is
`scripts/ExportOptions-AppStore.plist` with destination `upload`).
That archive predates the 2026-10-09 icon redraw and still has the old icon: re-archive (App Store step 4) before uploading.

## Website
1. **Done 2026-10-08.** **Create the public repo** `nickstrom5/california-eats` (empty, no README). Then, with Nick's yes, push `main` with only site and app
   files (`.gitignore` keeps `site/*.json`, `data/raw`, `data/ca`, Google data and build products out; `data/app` is git-ignored too, the
   app's copy lives in `CaliforniaEats/Resources/Data/`). Author email: `329204362+nickstrom5@users.noreply.github.com`.
2. **Done 2026-10-08.** **Enable GitHub Pages** from `main` / `docs`. Check every sitemap URL returns 200 at https://nickstrom5.github.io/california-eats/
   (privacy and support URLs must load before App Review).
3. **Cloudflare DNS (Nick):** `california` CNAME → `nickstrom5.github.io`, **DNS only** (grey cloud).
4. When `dig california.eatsranked.com` shows the CNAME: set `CUSTOM_DOMAIN = "california.eatsranked.com"` in `scripts/make-site.py`,
   re-run it (writes `docs/CNAME`), push, wait for the Pages certificate, then
   `gh api -X PUT repos/nickstrom5/california-eats/pages -F https_enforced=true`, set the repo's Website field, and switch
   `CaliforniaEats/App/Links.swift` and the App Store Connect URLs to the new domain in the next build.
5. **Done 2026-10-08.** **Hub:** add `playbook/hub-entry.json` to `eatsranked/tools/site-data.json` and a 256 px copy of `docs/icon-512.png` as
   `eatsranked/docs/icons/california.png`, rebuild the hub, push (with Nick's OK; the hub is shared and public).

## App Store
1. **Nick:** register the bundle ID `com.californiaeats.ios` and create the App Store Connect record "California Eats: Restaurants"
   (SKU e.g. `california-eats`). The API can't create app records.
2. Trademark check: USPTO search for "California Eats" (classes 9, 43).
3. Re-run `pipeline/check_websites.py` and rebuild, run the unit and UI tests on both simulators, recapture screenshots if any UI changed.
4. Archive with the **public Xcode** (`DEVELOPER_DIR="/Applications/Xcode 1.app/Contents/Developer"`), check `DTXcodeBuild`, upload to
   TestFlight (with Nick's yes). Version 1.0.0 (1); App Store Connect's version must be `1.0.0`.
5. Fill in the listing from `06-app-store-listing.md`; screenshots one file at a time (6.9" and 13"); App Review notes from
   `13-app-review-reply.md`; untick "Sign-in required"; reviewer phone; age rating 13+ (alcohol "Infrequent"); price $0; availability
   United States; content rights: yes, third-party (open data, public records, Apple's place card).
6. Record the screen recording from `13-app-review-reply.md` on Nick's iPhone from TestFlight.
7. Show Nick the final summary; **only he submits for review.**

## Data refresh (before each submission)
- LA County's CSVs are a rolling three-year window refreshed quarterly: archive each pull under `data/raw/official/lacounty/` with its
  date before replacing it.
- San Francisco, Sacramento and ABC are weekly or daily feeds; re-fetch with `data/raw/official/_scripts/fetch_*.sh`.
- Hand-checked guides: re-check any place whose source is older than 12 months.
