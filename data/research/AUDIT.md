# Research audit log

Edits made to researchers' entries after review, and rules the pipeline applies on top of them.

## 2026-10-07
- **Pipeline rule, all files:** a display note's "known for X" becomes "serving X" (`load_research` in `pipeline/california.py`), so a
  reputation claim reads as a menu fact.
- **Pipeline rule, Oldest guide:** an entry keeps the `oldest` kind only when `opened` (a year at this address) is 1960 or earlier. A year
  without the address history goes in `brand_founded` and shows as "Founded"; the place stays hand-checked but isn't in the guide.
  Tadich Grill (at 240 California St since 1967, founded 1849) is therefore not in the guide.
- `app/bay.json`, El Toro Taqueria: removed "briefly closed by the health department on 2026-01-15 and cleared on reinspection the next
  day" from the note. Inspection results belong to San Francisco's own record, shown as recorded, not to a guide note.
- `app/statewide.json`, Madonna Inn: the opened note quoted the inn's own "a legendary destination"; now "Own site: open since 1958 at
  100 Madonna Road (a single purpose-built property)."
- `closed_bay.json` keeps two announced closings that were still open on 2026-10-07 (Al Pastor Papi, closing 2026-12-31; Mama Ji's,
  closing 2026-10-31): the app is not shipped before then, so they are left out of the guides.
- Brand-only entries (Foster's Freeze, The Habit, Farmer Boys, Fatburger, Baker's Drive-Thru, Nation's) have no address, so they place
  nowhere: their stores weren't checked one by one and aren't in the Burger stands guide.
