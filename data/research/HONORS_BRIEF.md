# Brief: California honors research (2026-10-07)

We're building a free California restaurant app + website and a private web leaderboard. Honors are **facts, not ratings**:
"1 MICHELIN Star", "Bib Gourmand", "James Beard Award winner: Best Chef: California 2024". Work only inside
`ca-eats/data/research/`.

## Rules
- **Facts only, with a source URL for each entry.** No review text, no star ratings or scores from anyone, no readers' polls,
  no "best of" lists.
- **Never call a finalist or semifinalist a winner.** Record the exact level: winner, finalist, semifinalist, America's Classic.
- **Respect robots.txt.** Before using a host as a source, fetch `https://<host>/robots.txt`; if it disallows ClaudeBot or
  anthropic-ai (or `*`) for the path, don't use that host. Record every host you checked in your output's `robots` list.
- **Never bypass bot protection.** A 403/429, CAPTCHA, "verify you are human", an HTTP 202 with an empty body (guide.michelin.com
  answers automated requests like that today), a login wall or "enable JavaScript" means: stop, don't retry with tricks, use
  another honest source. A search-engine snippet of a page you couldn't open is not a source.
- One request at a time per host; be polite.
- **Closures matter.** If a source from 2025–26 says the place closed (or moved), record it in `closed` with the source.
  "Opened" years are only recorded when a source states them, and mean at this address.
- Addresses: street address + city (the place's own site, the guide's page, or the press list). Use plain ASCII quotes in JSON
  and validate it (`python3 -m json.tool <file>`) before you finish.

## Budget
WebSearch calls are shared across agents (about 200 for the whole session; about 180 are left). **Use at most your stated cap.**
WebFetch of a page doesn't count against it. Report how many searches you used.

## Output
Your final message: counts, searches used, hosts you couldn't use and why, anything surprising.
