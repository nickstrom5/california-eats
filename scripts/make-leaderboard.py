"""Builds site/index.html (the private web leaderboard) from wi-eats/site/index.html, with California's regions, boards, sources,
official inspection results and palette. Every replacement is asserted, so a change in the Wisconsin page fails loudly instead of
leaving Wisconsin text behind. Modeled on co-eats/scripts/make-leaderboard.py.

California is ~6x Wisconsin, so the data is split by region (site/ca_<region>.json, written by pipeline/california.py) and the page
loads one region at a time (or all of them), with a region picker in the header. Percentiles are statewide, computed in the
pipeline and shipped as columns, so a place scores the same whichever region is loaded.
Usage: .venv/bin/python scripts/make-leaderboard.py
"""
import os, re, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
src = open(os.path.join(ROOT, "..", "wi-eats", "site", "index.html"), encoding="utf-8").read()
s = src


def R(a, b, n=1):
    global s
    c = s.count(a)
    if c != n:
        sys.exit(f"expected {n} of {a[:90]!r}, found {c}")
    s = s.replace(a, b)


def CUT(start, end, new):
    """Replace from `start` (inclusive) up to `end` (exclusive)."""
    global s
    a = s.index(start); b = s.index(end, a)
    s = s[:a] + new + s[b:]


# ---------------- head, palette, type
R('<title>Wisconsin Restaurant Leaderboard</title>', '<meta charset="utf-8">\n<title>California Restaurant Leaderboard</title>')
R('<meta name="description" content="Every restaurant in Wisconsin, ranked on ratings, popularity, fish fry, supper clubs, custard, value and estimated sales.">',
  '<meta name="description" content="Every restaurant in California, ranked on ratings, popularity, value, estimated sales and official county inspection results, region by region.">')
R('family=Saira+Extra+Condensed:wght@600;700;800;900&family=Source+Sans+3:ital,wght@0,400;0,500;0,600;0,700;1,400',
  'family=Oswald:wght@500;600;700&family=Source+Sans+3:ital,wght@0,400;0,500;0,600;0,700;1,400')
R('''  /* Packers: green #203731, gold #FFB612, white. Light-only by design; gold is a fill with green text on it, never text on white. */
  color-scheme:light;
  --bg:#FFFFFF; --surface:#FFFFFF; --surface-2:#F1F5F2; --surface-3:#E1EAE4;
  --ink:#14241D; --ink-2:#2E4238; --muted:#53665B; --rule:#DAE3DD; --rule-2:#B6C6BC;
  --green:#203731; --green-2:#2D5242; --gold:#FFB612; --gold-soft:#FFE7A8; --on-gold:#203731;
  --map-fill:#EEF3EF; --map-line:#C2D1C7; --dot-edge:rgba(20,36,29,.35);
  --seq1:#CFE2D5; --seq2:#9CC4A9; --seq3:#5F9A74; --seq4:#326B4B; --seq5:#203731;
  --scrim:rgba(20,36,29,.38);
  --shadow:0 1px 2px rgba(20,36,29,.06),0 8px 28px rgba(20,36,29,.10);
  --display:"Saira Extra Condensed","Arial Narrow","Roboto Condensed",sans-serif;
  --body:"Source Sans 3",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;''',
'''  /* Layout: sticky leaderboard tabs over a filter rail + ranked list; one California element, a Pacific-and-sun band under the header.
     California gold #FDB515 (1.8:1 on white, so it is only ever a fill under Pacific-blue text) and Pacific blue #003262 (12.9:1),
     with poppy #E35B1E as a fill accent. Light-only by design, like the other state leaderboards: every color is set explicitly below. */
  color-scheme:light;
  --bg:#FFFFFF; --surface:#FFFFFF; --surface-2:#F2F5F9; --surface-3:#E1E8F1;
  --ink:#0E1B2C; --ink-2:#283A52; --muted:#53627A; --rule:#DCE3EC; --rule-2:#B6C3D4;
  --green:#003262; --green-2:#1A4B80; --gold:#FDB515; --gold-soft:#FEE7B0; --on-gold:#003262; --red:#E35B1E;
  --map-fill:#F1F4F8; --map-line:#C6D1E0; --dot-edge:rgba(14,27,44,.35);
  --seq1:#CFDCEC; --seq2:#94B1D3; --seq3:#5582B4; --seq4:#24578F; --seq5:#003262;
  --scrim:rgba(14,27,44,.38);
  --shadow:0 1px 2px rgba(14,27,44,.06),0 8px 28px rgba(14,27,44,.10);
  --display:"Oswald","Arial Narrow","Roboto Condensed",sans-serif;
  --body:"Source Sans 3",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;''')
R('body{margin:0;background:var(--bg);', 'html,body{background:var(--bg)}\nbody{margin:0;background:var(--bg);')
R('.hmid{padding:22px 16px 18px;border-bottom:4px solid var(--gold)}', '''.hmid{padding:22px 16px 12px}
.band{display:block;width:100%;height:24px;margin-top:-1px}
.band .sun{fill:var(--gold)} .band .sea{fill:var(--green)} .band .sea2{fill:#5582B4} .band .pop{fill:var(--red)}
.regions{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 0}
.regions button{font:600 13.5px/1.2 var(--body);padding:7px 11px;border-radius:999px;border:1px solid var(--rule-2);background:var(--surface);color:var(--ink);cursor:pointer;min-height:36px}
.regions button[aria-pressed="true"]{background:var(--green);border-color:var(--green);color:#fff}
.regions button:disabled{opacity:.6;cursor:progress}
.regions .rn{font-weight:500;opacity:.8;margin-left:4px}
.ijs{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 0}
.ijs button{font:600 12.5px/1.2 var(--body);padding:5px 10px;border-radius:999px;border:1px solid var(--rule-2);background:var(--surface);color:var(--ink);cursor:pointer;min-height:32px}
.ijs button[aria-pressed="true"]{background:var(--gold);border-color:#C98A00;color:var(--on-gold)}''')
R('.tab.wi{border-color:#D9A21A;background:#FFF9EA}', '.tab.wi{border-color:#C98A00;background:#FFF6E0}')
R('.chips.wi .chip[aria-pressed="false"]{background:#FFF9EA;border-color:#D9A21A}', '.chips.wi .chip[aria-pressed="false"]{background:#FFF6E0;border-color:#C98A00}')
R('.badge.sc{background:var(--gold-soft);color:var(--on-gold)}', '''.badge.sc{background:var(--gold-soft);color:var(--on-gold)}
.badge.mi{background:#B3261E;color:#fff}
.res{display:inline-block;font:700 11.5px/1.5 var(--body);letter-spacing:.04em;text-transform:uppercase;padding:1px 7px;border-radius:5px;white-space:nowrap}
.res-0{background:#DDEFE3;color:#0E5A2B} .res-1{background:#FFE9C2;color:#6B3A00} .res-2{background:#F9D5DB;color:#7A0019} .res-n{background:var(--surface-3);color:var(--ink-2)}''')
R('.fhint{font-size:12.5px;color:#8A4B00;margin:0}', '.fhint{font-size:12.5px;color:#8A2A00;margin:0}')
R('#map{display:block;width:100%;max-width:min(760px,max(240px,calc((100dvh - var(--stickyH) - 120px) * 0.95)));margin:0 auto;aspect-ratio:0.95;touch-action:manipulation}',
  '#map{display:block;width:100%;max-width:min(760px,max(240px,calc((100dvh - var(--stickyH) - 120px) * 0.86)));margin:0 auto;aspect-ratio:0.86;touch-action:manipulation}')
R('@media (max-height:500px){#map{max-width:max(160px,calc((100dvh - var(--stickyH) - 70px) * 0.95))}}', '@media (max-height:500px){#map{max-width:max(160px,calc((100dvh - var(--stickyH) - 70px) * 0.86))}}')

# ---------------- header and filters
BAND = ('<svg class="band" viewBox="0 0 1200 24" preserveAspectRatio="none" aria-hidden="true">'
        '<path class="sun" d="M0 24V14C120 14 160 2 240 2S360 14 480 14H1200V24Z"/>'
        '<path class="sea2" d="M0 24V17C60 14 120 20 180 17S300 14 360 17S480 20 540 17S660 14 720 17S840 20 900 17S1020 14 1080 17S1170 19 1200 17V24Z"/>'
        '<path class="sea" d="M0 24V20C60 17 120 23 180 20S300 17 360 20S480 23 540 20S660 17 720 20S840 23 900 20S1020 17 1080 20S1170 22 1200 20V24Z"/>'
        '</svg>')
R('''    <p class="kicker" id="kicker">Wisconsin · map listings as of Sep 2026</p>
    <h1 id="h1">Every Wisconsin restaurant, <span class="count">ranked</span></h1>
    <p class="lede" id="lede">Supper clubs, taverns, custard stands, Friday fish fries and the places in between, from Superior to Kenosha. Each one is ranked on ratings, popularity, value and estimated sales, with Wisconsin's own boards for fish fry, supper clubs, custard and cheese curds. Flip any leaderboard to see the bottom.</p>
  </div></div>''',
'''    <p class="kicker" id="kicker">California · map listings as of Sep 2026</p>
    <h1 id="h1">Every California restaurant, <span class="count">ranked</span></h1>
    <p class="lede" id="lede">Taquerías, dim sum halls, Korean barbecue, wine-country dining rooms and the places in between, from San Ysidro to Crescent City. Each one is ranked on ratings, popularity, value and estimated sales, with official county inspection results where counties publish them. Pick a region, or load all of California. Flip any leaderboard to see the bottom.</p>
    <div class="regions" id="regions" role="group" aria-label="Region"></div>
  </div></div>''' + BAND)
R('<select id="city"><option value="">All of Wisconsin</option></select>', '<select id="city"><option value="">All of California</option></select>')
R('<span class="flabel" id="l-tags">Wisconsin classics</span>', '<span class="flabel" id="l-tags">California boards</span>')
R('<label class="toggle"><input type="checkbox" id="confirmed"> Only confirmed places (on a Milwaukee or Dane County license list, or in two sources)</label>',
  '<label class="toggle"><input type="checkbox" id="confirmed"> Only confirmed places (on a county food-facility list or an ABC liquor license, or in two sources)</label>')
R('<p class="wnote">Each ingredient is a 0–100 percentile across Wisconsin.', '<p class="wnote">Each ingredient is a 0–100 percentile across all of California, whichever region is loaded.')
R('WI Score recipe: <span id="wname">', 'CA Score recipe: <span id="wname">')
R('placeholder="Search name, town, street, zip, “fish fry”…"', 'placeholder="Search name, town, street, zip, “dim sum”…"')

# ---------------- constants
R('const TAGS = [["supper","Supper clubs",1],["fishfry","Fish fry",2],["custard","Frozen custard",8],["curds","Cheese curds",4]];',
  'const TAGS = [["taqueria","Taquerías",1],["burrito","Burritos",2],["dimsum","Dim sum",4],["kbbq","Korean BBQ",8],["seafood","Seafood",16],["winecountry","Wine country",32]];')
R('const DEFAULT = {board:"overall",dir:"top",view:"list",city:"",',
  'const DEFAULT = {region:"la",ij:"lac",board:"overall",dir:"top",view:"list",city:"",')
R('const JUR = ["", "City of Milwaukee", "Public Health Madison & Dane County"];',
  'const JUR = ["", "Los Angeles County food facility list", "San Diego County food facility permit list", "San Francisco health permit", "Santa Clara County food facility list", "Sacramento County food facility list"];')
R('research:"our verified list, placed with its Google listing"', 'research:"our hand-checked list, placed on its street address"')
R('try { S = sanitize(JSON.parse(localStorage.getItem("wi-eats") || "null")); }', 'try { S = sanitize(JSON.parse(localStorage.getItem("ca-eats") || "null")); }')
R('localStorage.setItem("wi-eats", JSON.stringify(rest));', 'localStorage.setItem("ca-eats", JSON.stringify(rest));')
R('''  if (B.some(b => b.id === s.board)) o.board = s.board;''', '''  if (B.some(b => b.id === s.board)) o.board = s.board;
  if (typeof s.region === "string" && /^[a-z]{2,6}$/.test(s.region)) o.region = s.region;
  if (["lac","sf","scc","sac"].includes(s.ij)) o.ij = s.ij;''')
R('let D = [], META = {}, SHAPES = null, WI_BOUNDS = null,', 'let D = [], META = {}, RMETA = null, FILES = {}, REGION_BOUNDS = null, SHAPES = null, WI_BOUNDS = null,')

# ---------------- boards
BOARDS = r'''const ratedShow = r => [stars(r.rating), revs(r)+(r.reviews === 1 ? " review" : " reviews")+" ('21)"];
const IJ = ["lac", "sf", "scc", "sac"];
const jurOf = r => r.in_j == null ? null : (META.jurs || [])[r.in_j];
const resTxt = r => { const j = jurOf(r); if (!j) return "";
  if (r.in_r == null) return j.id === "lac" ? "Score " + r.in_s : "—";
  return ({G: "Green", Y: "Yellow", R: "Red"})[j.scale[r.in_r]] || j.scale[r.in_r]; };
const resPill = r => { const j = jurOf(r); if (!j) return "";
  if (r.in_r == null) return `<span class="res res-n">${esc(resTxt(r))}</span>`;
  const lbl = j.id === "lac" ? "Grade " + j.scale[r.in_r] : j.id === "scc" ? resTxt(r) + " placard" : j.scale[r.in_r].toLowerCase().replace(/^./, c => c.toUpperCase());
  return `<span class="res res-${Math.min(r.in_r, 2)}">${esc(lbl)}</span>`; };
const inspVal = r => { const j = jurOf(r); if (!j) return null;
  if (r.in_s != null && (j.id === "lac" || j.id === "scc")) return r.in_s;
  return r.in_r == null ? null : 100 - 30 * r.in_r; };
const ijName = () => ((META.jurs || []).find(j => j.id === S.ij) || {}).name || "";
const honTxt = r => r.mi >= 3 ? ["", "", "", "1 MICHELIN Star", "2 MICHELIN Stars", "3 MICHELIN Stars"][r.mi] : r.mi === 2 ? "Bib Gourmand"
  : (r.hon & 1) ? "America's Classic" : (r.hon & 2) ? "James Beard winner" : (r.hon & 4) ? "James Beard finalist" : (r.hon & 8) ? "James Beard semifinalist" : r.gs ? "Green Star" : "honor pts";
const tagShow = r => r.rating != null ? ratedShow(r) : ["—", "not rated in '21"];
const tagBoard = (id, bit, tab, what) => ({id, wi:true, tab, top:`${tab}, highest rated`, bottom:`${tab}, lowest rated`, metric:"rating", val:r=>r.bayes,
  need:(r,d)=>(r.tags & bit) && r.reviews >= (d==="top"?10:30),
  sub:`${what} Ranked by Google rating (Sep 2021), adjusted for review count. Tagged from the business name and its map or Google category, not hand-checked yet.`,
  show:ratedShow, dup:"rating"});
const B = [
  {id:"overall", tab:"CA Score", top:"Top CA Score", bottom:"Lowest CA Score", metric:"CA Score", val:r=>r.score,
   sub:()=>"A blend of rating, popularity, value and estimated profit, weighted by the CA Score recipe in the filters. Each ingredient is a percentile across all of California. Places missing some data are pulled toward 40, a little below the middle.",
   show:r=>[Math.round(r.score), "CA Score"]},
  {id:"rating", tab:"Rating", top:"Highest rated", bottom:"Lowest rated", metric:"rating", val:r=>r.bayes, need:(r,d)=>r.reviews >= (d==="top"?15:40),
   sub:"Google star rating as of the Sep 2021 snapshot, adjusted for review count so a 5.0 from three friends doesn't beat a 4.8 from 3,000 strangers.",
   show:ratedShow, dup:"rating"},
  {id:"popular", tab:"Popularity", top:"Most popular", bottom:"Least popular", metric:"reviews", val:r=>r.reviews, need:r=>r.reviews!=null,
   sub:"Total Google reviews as of Sep 2021: the best public stand-in for how many people walk through the door. Places opened since aren't in the snapshot, and the snapshot caps counts at 9,998 (shown as 9,998+).",
   show:r=>[revs(r), (r.reviews === 1 ? "review" : "reviews")+" ('21) · "+stars(r.rating)], dup:"rating"},
  {id:"gems", tab:"Hidden gems", top:"Hidden gems", bottom:"Popular but panned", metric:"rating", val:r=>r.gem, need:(r,d)=> d==="top" ? (r.reviews>=20 && r.reviews<=250 && r.chain_n<5) : r.reviews>=600,
   sub:"Top: independents with 20–250 reviews and great ratings. Bottom: places with 600+ reviews and the lowest ratings. Both from the Sep 2021 snapshot.",
   show:ratedShow, dup:"rating"},
  tagBoard("taqueria", 1, "Taquerías", "Places named or listed as a taquería or taco shop (Taco Bell, Del Taco and Chipotle left out)."),
  tagBoard("burrito", 2, "Burritos", "Independent places named or listed as a burrito shop, Mission-style and otherwise."),
  tagBoard("dimsum", 4, "Dim sum", "Places named or listed as a dim sum restaurant."),
  tagBoard("kbbq", 8, "Korean BBQ", "Places named or listed as a Korean barbecue restaurant."),
  {id:"iconic", tab:"Honors", top:"Most honored", bottom:"Least honored", metric:"honor points", val:r=>r.s_icon, need:r=>r.s_icon!=null,
   sub:"Only places with an honor: the MICHELIN Guide California 2026 (stars, Bib Gourmand, Green Star, and Recommended where we have it) and the James Beard Awards 2023–26 (winners, finalists and semifinalists, each named as such) plus America's Classics. Points for the honor and for how many people know the place (2021 reviews). Honors are facts, not ratings. MICHELIN is a trademark of Michelin.",
   show:r=>[Math.round(r.s_icon), honTxt(r)]},
  tagBoard("winecountry", 32, "Wine country", "Independent places in wine-country towns: Napa Valley, Sonoma County, Paso Robles, the Santa Ynez Valley, Temecula, Lodi, Livermore, Amador and other wine towns."),
  {id:"value", tab:"Value", top:"Best bang for buck", bottom:"Worst value", metric:"value score", val:r=>r.value_raw, need:r=>r.rating!=null,
   sub:"Rating (2021) relative to price level: a 4.7 at $ beats a 4.7 at $$$.",
   show:r=>[stars(r.rating)+" "+dollars(r.price)+(r.price_est?ESTTAG:""), "value "+Math.round(r.i_value)+" · rating '21"], dup:"rating"},
  {id:"price", tab:"Price", top:"Priciest", bottom:"Cheapest", metric:"price", val:r=>r.spend,
   sub:"Google price level (filled in from the chain or cuisine when missing, and marked est.) with typical spend per person. Within a price level, ties are ordered by CA Score.",
   show:r=>[dollars(r.price)+(r.price_est?ESTTAG:""), "~$"+r.spend+"/person "+ESTTAG]},
  {id:"sales", tab:"Sales", top:"Highest sales", bottom:"Lowest sales", metric:"sales", val:r=>r.rev, need:(r,d)=>r.rev!=null && (d==="top" || r.rev_src!=="model-low"), est:true,
   sub:d=>`Estimated yearly sales. Locations of chains with a published average (${META.model?.n_chains ?? "60+"} brands) use that average scaled by how busy the location is; independents use a model.` + (d==="bottom" ? " This end leaves out places with no review data (their figures are rough placeholders). The model never goes below $100K a year, so the very bottom is a tie, ordered by CA Score." : ""),
   show:r=>[money(r.rev), "sales/yr · " + src(r)], dup:"sales"},
  {id:"profit", tab:"Profit", top:"Most profitable", bottom:"Least profitable", metric:"profit", val:r=>r.profit, need:(r,d)=>r.profit!=null && (d==="top" || r.rev_src!=="model-low"), est:true,
   sub:d=>"Estimated yearly pre-tax profit: estimated sales × a typical margin for the segment, nudged by how well-loved the place is." + (d==="bottom" ? " This end leaves out places with no review data (their figures are rough placeholders). The sales model never goes below $100K a year, so the very bottom is mostly places at that floor, ordered by margin and then CA Score." : ""),
   show:r=>[money(r.profit), "profit/yr "+ESTTAG]},
  {id:"food", tab:"Food cost", top:"Biggest food bill", bottom:"Smallest food bill", metric:"food bill", val:r=>r.rev*r.food_cost/100, need:(r,d)=>r.rev!=null && (d==="top" || r.rev_src!=="model-low"), est:true,
   sub:d=>"Estimated yearly food purchases: estimated sales × the typical food-cost share for the cuisine (steak ~38%, seafood ~36%, pizza ~26%)." + (d==="bottom" ? " This end leaves out places with no review data. The sales model never goes below $100K a year, so the very bottom is mostly places at that floor." : ""),
   show:r=>[money(r.rev*r.food_cost/100), r.food_cost+"% food cost "+ESTTAG]},
  {id:"clean", tab:"Inspections", top:"Best latest inspection", bottom:"Lowest latest inspection", metric:"official result", val:r=>inspVal(r),
   need:r=>r.in_j != null && (META.jurs || [])[r.in_j]?.id === S.ij,
   tie:(a,b,d)=> d==="top" ? (a.in_b-b.in_b) || (b.in_n-a.in_n) : (b.in_b-a.in_b) || (a.in_d < b.in_d ? 1 : -1),
   sub:d=>{ const j = (META.jurs || []).find(x => x.id === S.ij) || {}, thru = (META.inspections_through || {})[S.ij] || "";
     const how = {lac: "LA County's official score (out of 100) and letter grade at the latest inspection. A is 90–100, B 80–89, C 70–79. Seven cities that never adopted grade cards (Avalon, Bradbury, Hidden Hills, La Habra Heights, San Marino, Sierra Madre, Signal Hill) show the score only.",
       sf: "San Francisco's official placard at the latest inspection: Pass (green), Conditional Pass (yellow) or Closure (red). San Francisco retired its 0–100 score in 2021. Ties go to the place with fewer yellow or red placards since 2024.",
       scc: "Santa Clara County's official placard and score at the latest inspection: green (pass), yellow (conditional pass) or red (closed).",
       sac: "Sacramento County's official placard at the latest inspection: PASS (green), CONDITIONAL PASS (yellow) or CLOSED (red). Ties go to the place with fewer yellow or red placards."}[S.ij] || "";
     return `${j.name || ""}: ${how} Ranked only within this county, as recorded by ${j.agency || "the county"}; we never compute a grade of our own or blend counties. Inspections through ${thru}.` + (d==="bottom" ? " One inspection is a snapshot of one day, and most places here passed." : ""); },
   show:r=>[`${resPill(r)}`, `${r.in_s != null ? "score " + r.in_s + " · " : ""}${esc(r.in_d)}`], dup:"grade"},
];'''
CUT('const sigShow = ', 'const board = () =>', BOARDS + "\n")

# ---------------- rows, badges, stats
R('''  if (r.hon & 1) h += `<span class="badge jbf">America's Classic</span>`;''',
  '''  if (r.mi) h += `<span class="badge mi">${esc(["", "MICHELIN Recommended", "Bib Gourmand", "1 MICHELIN Star", "2 MICHELIN Stars", "3 MICHELIN Stars"][r.mi])}</span>`;
  if (r.hon & 1) h += `<span class="badge jbf">America's Classic</span>`;''')
R('''  if ((r.hon & 16) && !(r.hon & 7)) h += `<span class="badge icon">Icon</span>`;
  if ((r.tags & 1) && !/supper ?club/i.test(r.name)) h += `<span class="badge sc">Supper club</span>`;''',
  '''  if (r.gs) h += `<span class="badge sc">MICHELIN Green Star</span>`;
  if ((r.hon & 16) && r.founded) h += `<span class="badge icon">Since ${esc(r.founded)}</span>`;''')
R('''  if (r.ff_n >= 3 && b.id !== "fishfry") bits.push(`<span>${r.ff_n} <i>fish fry mentions</i></span>`);
  if (r.grade) bits.push(`<span class="${dup("grade")}" title="Our grade from Dane County inspection results, not an official grade"><span class="grade sm g-${r.grade}">${r.grade}</span> <i>our inspection grade</i></span>`);''',
  '''  if (r.in_j != null) bits.push(`<span class="${dup("grade")}" title="Official result at the latest inspection, as recorded by the county">${resPill(r)} <i>${esc(r.addr || "")} · ${esc(jurOf(r).name)} · inspected ${esc(r.in_d)}${r.in_s != null && r.in_r != null && b.id !== "clean" ? " · score " + r.in_s : ""}</i></span>`);''')
R('''  if (S.board !== "overall" && r.score != null) bits.push(`<span>${Math.round(r.score)} <i>WI Score</i></span>`);''',
  '''  if (S.board !== "overall" && r.score != null) bits.push(`<span>${Math.round(r.score)} <i>CA Score</i></span>`);''')
R('''const TAG_PH = [["friday fish fry","fishfry"],["fish fries","fishfry"],["fish fry","fishfry"],["fishfry","fishfry"],["supper clubs","supper"],["supper club","supper"],
  ["supperclub","supper"],["frozen custard","custard"],["custard","custard"],["cheese curds","curds"],["cheese curd","curds"],["curds","curds"]].map(([p, t]) => [norm(p), t]);''',
  '''const TAG_PH = [["taquerias","taqueria"],["taqueria","taqueria"],["taquería","taqueria"],["burritos","burrito"],["burrito","burrito"],["dim sum","dimsum"],["dimsum","dimsum"],
  ["yum cha","dimsum"],["korean bbq","kbbq"],["korean barbecue","kbbq"],["kbbq","kbbq"],["k bbq","kbbq"],["wine country","winecountry"]].map(([p, t]) => [norm(p), t]);''')
R('''  // "fish fry", "supper club", "custard", "cheese curds" mean the Wisconsin tags, not words in a name''', '''  // "dim sum", "korean bbq", "wine country" mean the California boards, not words in a name''')
R('''  // "fond du lac fish fry" means the town; "green bay rd" or "madison st" is a street, not the town''', '''  // "san gabriel dim sum" means the town; "san pablo ave" or "los angeles st" is a street, not the town''')
R('''  // a town named in the search ("fond du lac fish fry") narrows to it; a place NAMED that way still counts''', '''  // a town named in the search ("san gabriel dim sum") narrows to it; a place NAMED that way still counts''')
R('''    return `No places match “${esc(S.q.trim())}” in Wisconsin.''', '''    return `No places match “${esc(S.q.trim())}” in ${esc(regionLabel())}.''')
R('''  if (S.board === "overall" && !weightTotal) return `The WI Score recipe is empty.''', '''  if (S.board === "overall" && !weightTotal) return `The CA Score recipe is empty.''')
R('''  if (pool.length && board().id === "clean") return `${plural(pool.length, "place matches", "places match")} ${what}, but inspection results are only published for Dane County (Madison and its suburbs). ${f.length ? undo + " to see them." : ""}`;''',
  '''  if (pool.length && board().id === "clean") return `${plural(pool.length, "place matches", "places match")} ${what}, but none has a ${esc(ijName())} inspection result here. Counties that publish results in bulk: Los Angeles (not Pasadena, Long Beach or Vernon), San Francisco, Santa Clara and Sacramento. Pick one above${S.region === "all" ? "" : ", or load the region it's in"}. ${f.length ? undo + " to see more." : ""}`;''')
R('''"All of Wisconsin"}</option>`''', '''"All of " + esc(regionLabel())}</option>`''')
R('''$("#cityhint").textContent = `No Wisconsin town matches''', '''$("#cityhint").textContent = `No ${regionLabel()} town matches''')
R('''    else if (cityFromBox && S.city) { S.city = ""; cityFromBox = false; rerender(); }   // "Wausauk" is no longer Wausau''', '''    else if (cityFromBox && S.city) { S.city = ""; cityFromBox = false; rerender(); }   // "Fresnoo" is no longer Fresno''')
R('''    const hit = CITY_N.get(v) || (CITIES.find(([c]) => (" " + norm(c)).includes(" " + v)) || [])[0];   // CITIES is biggest first: "bay" -> Green Bay''',
  '''    const hit = CITY_N.get(v) || (CITIES.find(([c]) => (" " + norm(c)).includes(" " + v)) || [])[0];   // CITIES is biggest first: "jose" -> San Jose''')
R('''const cols = [["name","City or town"],["n","Places","r"],["score","Avg WI Score","r"]''', '''const cols = [["name","City or town"],["n","Places","r"],["score","Avg CA Score","r"]''')
R('''  const setPh = () => { $("#q").placeholder = innerWidth < 400 ? "Search name, town, street…" : "Search name, town, street, zip, “fish fry”…"; };''',
  '''  const setPh = () => { $("#q").placeholder = innerWidth < 400 ? "Search name, town, street…" : "Search name, town, street, zip, “dim sum”…"; };''')
# the board subtitle carries the inspection jurisdiction switch on the Inspections board
R('''  $("#bsub").textContent = typeof b.sub === "function" ? b.sub(S.dir) : b.sub;''',
  '''  if (b.id === "clean") {   // only the counties present in what's loaded; switch to the first one if the chosen one isn't
    const have = IJ.filter(j => D.some(r => r.in_j != null && (META.jurs || [])[r.in_j]?.id === j));
    if (have.length && !have.includes(S.ij)) S.ij = have[0];
    $("#bsub").innerHTML = esc(b.sub(S.dir)) + (have.length ? `<span class="ijs" role="group" aria-label="County">${have.map(j => `<button type="button" data-ij="${j}" aria-pressed="${j === S.ij}">${esc(((META.jurs || []).find(x => x.id === j) || {}).name || j)}</button>`).join("")}</span>` : "");
  } else $("#bsub").textContent = typeof b.sub === "function" ? b.sub(S.dir) : b.sub;''')

# ---------------- map
R('shapesPending = fetchJSON("wi_shapes.json").then(j => {', 'shapesPending = fetchJSON("ca_shapes.json").then(j => {')
R("WI_BOUNDS = a[0] < a[1] ? a : [-92.9, -86.8, 42.49, 47.08];", "WI_BOUNDS = a[0] < a[1] ? a : [-124.42, -114.13, 32.53, 42.01];")
R("const w = c.clientWidth || 600, h = Math.round(w / 0.95);", "const w = c.clientWidth || 600, h = Math.round(w / 0.86);")
R("  const full = WI_BOUNDS;", "  const full = (S.region !== \"all\" && REGION_BOUNDS) || WI_BOUNDS;")
R("  ctx.save(); land(); ctx.clip(\"evenodd\");   // county lines stop at the shore", "  ctx.save(); land(); ctx.clip(\"evenodd\");   // county lines stop at the coast")
R('''  $("#live").textContent = pool.length === 1 ? `Only one place matches your filters: ${r.name}.` : `Random pick: ${r.name}, ${r.city || "Wisconsin"}.`;''',
  '''  $("#live").textContent = pool.length === 1 ? `Only one place matches your filters: ${r.name}.` : `Random pick: ${r.name}, ${r.city || "California"}.`;''')

# ---------------- drawer
CUT('function calibNote(r) {', 'function sigCard(n, rt, what)', r'''function calibNote(r) {
  const c = META.calibration || {}, g = k => [c.lac?.groups?.[k], c.sd?.groups?.[k]].filter(Boolean);
  const range = k => { const v = g(k).map(x => x.official); if (!v.length) return null; const lo = Math.min(...v), hi = Math.max(...v); return lo === hi ? pctTxt(lo) : `${pctTxt(lo)}–${pctTxt(hi)}`; };
  const feed = r.src === "AllThePlaces" || r.src === "DAC";
  if (r.src === "research") return "This place isn't in the map listings as a place to eat. It's on our hand-checked list, confirmed open with a 2025–26 source, and placed on its street address.";
  if (r.tier === 2) return r.src === "official" ? `This place comes straight from the ${esc(JUR[r.jur])}. The map listings we use didn't have it, so its location comes from the county's record.`
    : r.jur ? `Matched to the ${esc(JUR[r.jur])}, so it's confirmed as a permitted food business.` : "Matched to an active California ABC on-premises liquor license, so it's confirmed as a licensed business.";
  const via = feed ? (r.tier === 1 ? "brand feed + Google 2021" : "brand feed only") : r.src === "meta" ? (r.tier === 1 ? "Meta + open in Google 2021" : "Meta only") : null;
  const rate = via ? range(via) : null, kind = feed ? "chain store-list listings" : "listings";
  if (!via) return "Kept because an official record or our research confirms it, even though its only map listing comes from a source that's usually unreliable.";
  if (r.tier === 1) return `Found in two independent sources: a map listing and Google's 2021 data. Checked against LA County's and San Diego County's food-facility lists, ${kind} like this matched a permitted business ${rate || "most"} of the time.`;
  return `Found in one map source only. Checked against LA County's and San Diego County's food-facility lists, single-source ${kind} like this matched a permitted business ${rate || "about half"} of the time, so this one may be closed or misfiled.`;
}
''')
R('''  const gq = encodeURIComponent(`${r.name} ${r.addr || ""} ${r.city || ""} WI`);''', '''  const gq = encodeURIComponent(`${r.name} ${r.addr || ""} ${r.city || ""} CA`);''')
R('''  const x = Object.assign({}, r, DETAIL ? DETAIL[r.id] || {} : {});
  const wait = DETAIL ? null : (detailFailed ? "not loaded" : "…");   // values that only the details file has''',
  '''  const hasD = DREG.has(r.rg), x = Object.assign({}, r, DETAIL[r.id] || {});
  const wait = hasD ? null : (detailFailed ? "not loaded" : "…");   // values that only the details file has''')
R('''  const heroLbl = r.score == null ? (weightTotal ? "No WI Score: not enough data" : "WI Score recipe is empty")
    : ri >= 0 ? `WI Score · #${fmtN(ri+1)} of ${fmtN(L.length)} with your filters (ignoring search)` : "WI Score · outside your current filters";''',
  '''  const heroLbl = r.score == null ? (weightTotal ? "No CA Score: not enough data" : "CA Score recipe is empty")
    : ri >= 0 ? `CA Score · #${fmtN(ri+1)} of ${fmtN(L.length)} in ${esc(regionLabel())} with your filters (ignoring search)` : "CA Score · outside your current filters";''')
R('''  const cats = `<div class="dsec"><h3>Category scores (percentile vs. all Wisconsin places)</h3>''', '''  const cats = `<div class="dsec"><h3>Category scores (percentile vs. all California places)</h3>''')
CUT('  const sig = [sigCard(', '  const moneyNote = {', '')
R('''This location isn't in the 2021 review snapshot, so this uses 85% of the chain's published U.S. average sales per location." : "Based on the chain's published U.S. average sales per location, scaled up or down by how busy this location was (2021 reviews) compared with the chain's other Wisconsin locations.",''',
  '''This location isn't in the 2021 review snapshot, so this uses 85% of the chain's published U.S. average sales per location." : "Based on the chain's published U.S. average sales per location, scaled up or down by how busy this location was (2021 reviews) compared with the chain's other California locations.",''')
R('''scaled by 2021 review volume relative to similar Wisconsin places''', '''scaled by 2021 review volume relative to similar California places''')
CUT('  const honorsList = [', '  $("#drawer").innerHTML = `${dhead(', r'''  const honorsList = x.honors || [];
  const tagsTxt = TAGS.filter(([, , bit]) => r.tags & bit).map(([, l]) => l);
  const j = jurOf(r);
  const insp = j ? `<div class="dsec"><h3>Health inspections · ${esc(j.name)}</h3>
      <div class="hero" style="margin:0 0 10px">${resPill(r)}<span class="lbl">Official result at the latest inspection, ${esc(r.in_d)}${r.in_s != null ? " · score " + r.in_s + " of 100" : ""}</span></div>
      ${kv([["Inspections on record", fmtN(r.in_n) + (x.insp && x.insp.first ? ` since ${esc(x.insp.first)}` : "")],
        [j.id === "lac" ? "Inspections graded B or C" : "Yellow or red placards", fmtN(r.in_b)],
        x.insp && x.insp.mean != null ? ["Average score", Math.round(x.insp.mean) + " of 100"] : null,
        x.insp && x.insp.lic ? ["County record", esc(x.insp.lic)] : null])}
      <p class="note">${j.id === "lac" && r.in_r == null ? "This city never adopted LA County's letter-grade cards, so only the official score is shown. " : ""}As recorded by ${esc(j.agency)}; we never compute a grade of our own or compare counties. Inspections through ${esc((META.inspections_through || {})[j.id] || "")}. Conditions may have changed since the inspection.</p></div>` : "";
  const abc = x.abc ? ["ABC license", `Type ${esc(x.abc[1])} · ${esc(x.abc[0])}`] : null;
''')
R('''  $("#drawer").innerHTML = `${dhead(esc(r.city || "Wisconsin"), random)}''', '''  $("#drawer").innerHTML = `${dhead(esc(r.city || "California") + (r.county ? " · " + esc(r.county) : ""), random)}''')
R('''    <div class="addr">${r.addr ? esc(r.addr) + ", " : ""}${esc(r.city || "Wisconsin")}''', '''    <div class="addr">${r.addr ? esc(r.addr) + ", " : ""}${esc(r.city || "California")}''')
R('''    ${sig ? `<div class="dsec"><h3>Wisconsin classics · from Google reviews through Sep 2021</h3><div class="wisig">${sig}</div><p class="note">Average star rating of just the reviews that mention it. Reviews rate the whole visit, so read these as a lean, not a verdict.</p></div>` : ""}
    ${(honorsList.length || x.icon || x.founded) ? `<div class="dsec"><h3>Honors &amp; history</h3>${x.icon?`<p style="margin:0 0 8px;color:var(--ink-2);font-size:14px">${esc(x.icon)}</p>`:""}${honorsList.length?`<ul class="lines">${honorsList.map(v=>`<li>${esc(v)}</li>`).join("")}</ul>`:""}${x.founded ? `<p class="note">Open since ${esc(x.founded)} (verified).</p>` : ""}</div>`
      : (r.hon && !DETAIL ? `<div class="dsec"><h3>Honors &amp; history</h3><p class="note">${detailFailed ? "Couldn't load the honors. Check your connection and reopen this place." : "Loading…"}</p></div>` : "")}
    ${insp}''',
  '''    ${honorsList.length ? `<div class="dsec"><h3>Honors</h3><ul class="lines">${honorsList.map(v=>`<li>${esc(v)}</li>`).join("")}</ul><p class="note">From the MICHELIN Guide California 2026 (announced June 24, 2026) and the James Beard Foundation's own announcements. MICHELIN and the MICHELIN Guide are trademarks of Michelin; James Beard Awards are the Foundation's. Honors are facts, not ratings.</p></div>`
      : ((r.mi || r.hon) && !hasD ? `<div class="dsec"><h3>Honors</h3><p class="note">${detailFailed ? "Couldn't load the honors. Check your connection and reopen this place." : "Loading…"}</p></div>` : "")}
    ${insp}''')
R('''      x.lic ? ["License number", esc(x.lic.replace(/^(MKE|PHMDC)-/, ""))] : null,
      tagsTxt.length ? ["Wisconsin tags", esc(tagsTxt.join(", "))] : null,
      ["Listed as a bar or tavern", r.bar ? "Yes" : "No"], ["Locations in Wisconsin", r.chain_n >= 2 ? fmtN(r.chain_n) : "This one only"],''',
  '''      x.rec ? ["County record", esc(x.rec[1])] : null,
      r.liq ? ["Serves alcohol", "Yes · " + esc((META.liqt || [])[r.liq] || "") + " (ABC on-sale license)"] : ["Serves alcohol", "— (no on-sale ABC license matched)"], abc,
      tagsTxt.length ? ["California boards", esc(tagsTxt.join(", "))] : null,
      r.county ? ["County", esc(r.county)] : null,
      ["Listed as a bar or tavern", r.bar ? "Yes" : "No"], ["Locations in California", r.chain_n >= 2 ? fmtN(r.chain_n) : "This one only"],''')
R('''      ["Confirmed by", r.tier === 2 ? esc(JUR[r.jur]) + " license list" : r.tier === 1 ? "Map listing (2026) and Google (2021)" : "One map listing (2026) only"],''',
  '''      ["Confirmed by", r.tier === 2 ? (r.jur ? esc(JUR[r.jur]) : "California ABC liquor license") : r.tier === 1 ? "Map listing (2026) and Google (2021)" : "One map listing (2026) only"],''')
R('''  if (!DETAIL && !detailPending) loadDetail();
}''', '''  if (!DREG.has(r.rg)) loadDetail(r.rg);
}''')
CUT('function loadDetail() {', 'function refreshDrawer() {', r'''let DETAIL = {}, DREG = new Set(), DPEND = {};
function loadDetail(rg) {   // one detail file per region, loaded the first time a drawer opens there
  if (!rg || DREG.has(rg)) return Promise.resolve();
  if (DPEND[rg]) return DPEND[rg];
  detailFailed = false;
  const off = (REGION_OFFSETS[rg] ?? null);
  DPEND[rg] = fetchJSON(`ca_${rg}_detail.json`).then(j => {
    if (off == null) return;
    const ex = (j && j.extra) || {};
    for (const k in ex) DETAIL[off + +k] = ex[k];
    DREG.add(rg); delete DPEND[rg];
    refreshDrawer();
  }).catch(() => { delete DPEND[rg]; detailFailed = true; refreshDrawer(); });
  return DPEND[rg];
}
''')
R('let D = [], META = {}, RMETA = null, FILES = {}, REGION_BOUNDS = null, SHAPES = null, WI_BOUNDS = null, CITIES = [], CITY_N = new Map(), shown = 50, current = [], pool = [], loaded = false, DETAIL = null, detailPending = null;',
  'let D = [], META = {}, RMETA = null, FILES = {}, REGION_BOUNDS = null, REGION_OFFSETS = {}, SHAPES = null, WI_BOUNDS = null, CITIES = [], CITY_N = new Map(), shown = 50, current = [], pool = [], loaded = false;')

# ---------------- method cards
CUT('function methodCards() {', '// ---------------- boot ----------------', r'''function methodCards() {
  const m = META, c = m.calibration || {};
  const dv = ["Foursquare only", "BrightQuery only", "Microsoft only", "Foursquare/BrightQuery/Microsoft + Google 2021"].flatMap(k => [c.lac?.groups?.[k], c.sd?.groups?.[k]]).filter(Boolean).map(g => g.official);
  const dropRange = dv.length ? `${Math.round(Math.min(...dv) * 100)}–${Math.round(Math.max(...dv) * 100)}%` : "a small share";
  const th = m.inspections_through || {};
  const cols = [
    ["m", "Official records", [
      ["County inspections, as recorded", `Four health departments publish inspection results in bulk, and each place shows its own county's official result at its latest inspection, never a grade of ours: Los Angeles County's score and A/B/C grade (Environmental Health, Oct 2023 to ${esc(th.lac || "")}; Pasadena, Long Beach and Vernon run their own departments and aren't included), San Francisco's Pass / Conditional Pass / Closure placard (2024 to ${esc(th.sf || "")}), Santa Clara County's green/yellow/red placard and score (Oct 2024 to ${esc(th.scc || "")}) and Sacramento County's placard (Oct 2023 to ${esc(th.sac || "")}). Counties score differently, so they're ranked separately.`],
      ["County food-facility lists", "LA County's restaurant and market inventory, San Diego County's food facility permits, and the San Francisco, Santa Clara and Sacramento facility lists. A map listing that matches one is marked confirmed. LA County, San Francisco and Sacramento restaurants the map data lacks are added from the record. San Diego posts A/B/C grades only in its search app, so they aren't here."],
      ["ABC liquor licenses", "California's Department of Alcoholic Beverage Control daily license export (public domain): active on-sale licenses statewide. A match confirms the place and says what it can pour: beer, beer and wine, or a full bar. No license matched means unknown, not \"no\"."],
      ["The rest of the state", "Orange, Riverside, San Bernardino, Ventura, Alameda, Contra Costa, San Mateo and Fresno counties, Pasadena, Long Beach and Vernon publish inspections one search at a time or not at all, and some of those sites block automated access, so we don't collect them. There, places come from map listings and the ABC list."]]],
    ["s", "Map listings & 2021 snapshot", [
      ["Places statewide", `Overture Maps' open map listings (${esc(m.overture_release || "Sep 2026")} release, which merges Meta, Foursquare, chain store lists and other sources). We keep listings from Meta and from chains' own store lists, and drop Foursquare, BrightQuery and Microsoft listings: in LA and San Diego counties only ${dropRange} of those matched a permitted food business. Anything Google already showed as closed in 2021 is dropped, unless an official record confirms it.`],
      ["Ratings, reviews & price level", "Google Maps ratings from the UCSD Google Local research dataset, frozen in September 2021. Each Google listing is matched to one place at most, on a shared distinctive name word nearby. Places that opened later aren't in it, and the rating boards leave them out rather than guess."],
      ["California boards", "Taquerías, burritos, dim sum, Korean barbecue and wine country are tagged from the business name and its map or Google category. They aren't hand-checked yet; the app's guides will be."],
      ["Honors", "The MICHELIN Guide California 2026 (10 three-star, 13 two-star and 60 one-star restaurants, 117 Bib Gourmands, 18 Green Stars), from MICHELIN's own release, and James Beard Award winners, finalists and semifinalists 2023–26 plus every California America's Classic, from jamesbeard.org. Honored places our research found closed are removed. MICHELIN is a trademark of Michelin."]]],
    ["e", "Estimated", [
      ["Sales & profit", `Chains use their published U.S. average sales per store (QSR 50, Technomic, company filings and franchise disclosures; ${m.model?.n_chains ?? "60+"} brands found here), scaled by how busy the location is. Independents start from a typical figure for their price level ($600K for $ up to $3.5M for $$$$) and scale with 2021 review volume relative to similar California places, with an exponent of ${m.model?.b ?? 0.76} fit on published Chicago sales. Places without reviews get a rough placeholder. Profit = sales × a typical segment margin.`],
      ["Price, cuisine & food cost", "Missing price levels are filled in from the chain's or cuisine's usual California level and marked est. Cuisine comes from the listing's category, the business name and Google categories, so a few will be off. Food cost is the typical share for that cuisine × estimated sales, a benchmark rather than the restaurant's own invoices."]]],
  ];
  $("#srcgrid").innerHTML = cols.map(([t, h, cards]) => `<div class="srccol"><span class="tag ${t}">${h}</span>${cards.map(([h,p]) => `<div class="src"><h3>${h}</h3><p>${p}</p></div>`).join("")}</div>`).join("");
  const G = [["Meta + open in Google 2021","Meta listing, open in Google's 2021 data","kept · two sources"],["Meta only","Meta listing only","kept · listing only"],
    ["brand feed + Google 2021","Chain store list + Google 2021","kept · two sources"],["brand feed only","Chain store list only","kept · listing only"],
    ["Foursquare/BrightQuery/Microsoft + Google 2021","Foursquare / BrightQuery / Microsoft + Google 2021","dropped"],["Foursquare only","Foursquare only","dropped"],
    ["BrightQuery only","BrightQuery only","dropped"],["Microsoft only","Microsoft only","dropped"],["Google 2021 says closed","Google showed it closed in 2021","dropped"]];
  const cell = (j, k) => { const g = c[j]?.groups?.[k]; return g ? `${Math.round(g.official * 100)}% <span style="color:var(--muted)">of ${fmtN(g.n)}</span>` : "—"; };
  const regs = (RMETA && RMETA.regions) || [];
  $("#calib").innerHTML = (c.lac ? `<div class="src" style="display:grid;gap:10px"><h3>How the map listings were checked</h3>
    <p>In LA County (Environmental Health's food-facility inventory) and San Diego County (its food-facility permits), every map listing was checked against the official list: same business name nearby, or the same street address with a distinctive name word in common (and the same zip, where the record has no location). The share that matched decides what's kept. Statewide, ABC's liquor licenses are a third check, but only places that serve alcohol hold one. Coverage runs the other way too: the map listings held ${Math.round((c.lac.coverage||0)*100)}% of LA County's permitted restaurants and ${Math.round((c.sd?.coverage||0)*100)}% of San Diego County's.</p>
    <div class="calib"><table><thead><tr><th scope="col">Kind of listing</th><th scope="col" class="r">LA County</th><th scope="col" class="r">San Diego County</th><th scope="col" class="r">ABC, statewide</th><th scope="col">Here</th></tr></thead><tbody>
    ${G.map(([k, l, what]) => `<tr><td>${esc(l)}</td><td class="r num">${cell("lac", k)}</td><td class="r num">${cell("sd", k)}</td><td class="r num">${cell("abc", k)}</td><td>${what}</td></tr>`).join("")}</tbody></table></div>
    <p class="note">Matched = on the county's list of permitted food facilities (restaurants and markets), or on an active ABC on-sale license. These are lower bounds: a real place under a different name on its permit counts as a miss. ABC's column is lower still, since coffee shops and most taquerías don't hold a liquor license.</p></div>` : "") +
    (regs.length ? `<div class="src" style="display:grid;gap:10px"><h3>Regions</h3><div class="calib"><table><thead><tr><th scope="col">Region</th><th scope="col">Counties</th><th scope="col" class="r">Restaurants</th><th scope="col" class="r">Towns</th></tr></thead><tbody>
    ${regs.map(g => `<tr><td>${esc(g.name)}</td><td>${esc(g.counties.map(x => x.replace(/ County$/, "")).join(", "))}</td><td class="r num">${fmtN(g.count_restaurants)}</td><td class="r num">${fmtN(g.n_cities)}</td></tr>`).join("")}</tbody></table></div></div>` : "");
}

''')

# ---------------- build and load: one file per region, cached; statewide percentiles come from the data
CUT('function build(j) {', 'function toSearch() {', r'''function regionLabel() {
  if (S.region === "all" || !RMETA) return "California";
  return (RMETA.regions.find(g => g.id === S.region) || {}).name || "California";
}
function build(files) {
  if (!files.length || files.some(j => !j || !j.cols || !Number.isFinite(j.n))) { const e = new Error("the data file is incomplete"); e.http = true; throw e; }
  const mean = META.rating_mean || 4.3, rows = [];
  REGION_OFFSETS = {};
  for (const j of files) {
    const m = j.meta || {}, C = j.cols, sc = j.scale || {}, N = j.n, off = rows.length;
    REGION_OFFSETS[m.region] = off;
    const col = (c, i) => { const v = C[c] ? C[c][i] : null; return v == null ? null : sc[c] ? v / sc[c] : v; };
    for (let i = 0; i < N; i++) {
      const o = {id: off + i, rg: m.region, li: i};
      o.name = C.name[i]; o.addr = C.addr[i]; o.city = C.city[i] == null ? null : m.cities[C.city[i]]; o.zip = C.zip[i] == null ? null : String(C.zip[i]);
      o.lat = col("lat", i); o.lon = col("lon", i); o.cuisine = m.cuisines[C.cuisine[i]] || "American & Other"; o.brand = C.brand[i] == null ? null : m.brands[C.brand[i]];
      o.chain_n = C.chain_n[i] || 1; o.rating = col("rating", i); o.reviews = C.reviews[i]; o.price = C.price[i]; o.price_est = C.price_est[i];
      o.rev = C.rev_k[i] * 1000; o.rev_src = META.src[C.rev_src[i]] || "model"; o.margin = col("margin", i); o.profit = o.rev * o.margin;
      o.value_raw = col("value_raw", i); o.tier = C.tier[i]; o.both = o.tier >= 1 ? 1 : 0; o.jur = C.jur[i]; o.bar = C.bar[i]; o.venue = C.venue[i]; o.tags = C.tags[i] || 0;
      o.src = (META.srcs || [])[C.src[i]] || null; o.liq = C.liq[i] || 0; o.county = C.county[i] == null ? null : META.counties[C.county[i]];
      for (const k of ["i_rating", "i_pop", "i_value", "i_profit"]) o[k] = C[k][i] == null ? null : C[k][i] / 10;   // statewide percentiles
      o.food_cost = (META.food_cost || {})[o.cuisine] ?? 30; o.spend = (META.spend || {})[o.price];
      o.bayes = o.rating == null ? null : (o.reviews*o.rating + 40*mean)/(o.reviews + 40);
      o.gem = o.rating == null ? null : (o.reviews*o.rating + 8*mean)/(o.reviews + 8);
      o._s = " " + normRaw([o.name, o.city, o.zip, o.cuisine, o.brand, o.county].join(" ")) + " " + norm(o.addr) + " ";
      o._n = " " + normRaw([o.name, o.brand].join(" ")) + " ";
      rows.push(o);
    }
    const sp = j.sparse || {};
    for (const [i, s, f, mi, gs] of sp.hon || []) { const o = rows[off + i]; if (o) { o.s_icon = s / 10; o.hon = f; o.mi = mi; o.gs = gs; } }
    for (const [i, jx, res, score, d, n, bad] of sp.insp || []) { const o = rows[off + i]; if (o) Object.assign(o, {in_j: jx, in_r: res, in_s: score, in_d: d, in_n: n, in_b: bad}); }
  }
  const cnt = new Map(); for (const r of rows) if (r.city && !r.venue) cnt.set(r.city, (cnt.get(r.city) || 0) + 1);
  for (const r of rows) if (r.city && !cnt.has(r.city)) cnt.set(r.city, 0);
  CITIES = [...cnt.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  CITY_N = new Map();   // "la canada", "La Cañada" and "La Cañada Flintridge" spellings collapse through norm()
  for (const [c] of CITIES) { const k = norm(c); if (!CITY_N.has(k)) CITY_N.set(k, c); const sq = k.replace(/ /g, ""); if (!CITY_N.has(sq)) CITY_N.set(sq, c); }
  CITY_PH = [...CITY_N.entries()].sort((a, b) => b[0].length - a[0].length);
  D = rows;
  // the map zooms to the loaded region (2nd-98th percentile, so a stray listing doesn't widen it)
  const la = rows.map(r => r.lat).filter(v => v != null).sort((p, q) => p - q), lo = rows.map(r => r.lon).filter(v => v != null).sort((p, q) => p - q);
  const q = (a, f) => a[Math.min(a.length - 1, Math.max(0, Math.floor(a.length * f)))];
  REGION_BOUNDS = la.length ? [q(lo, 0.005) - 0.08, q(lo, 0.995) + 0.08, q(la, 0.005) - 0.06, q(la, 0.995) + 0.06] : null;
  CUISINE_ALL = {}; D.forEach(r => CUISINE_ALL[r.cuisine] = 1);
  CUISINE_WORDS = new Set(Object.keys(CUISINE_ALL).flatMap(c => norm(c).split(" ")).filter(w => !STOPW.has(w) && !["other", "s", "n", "e", "w"].includes(w))
    .concat(["pizzas", "tacos", "taco", "burger", "donuts", "coffee", "cafe", "bakery", "wings", "dogs", "ramen", "noodles", "bagels", "ice", "cream", "brunch",
             "taqueria", "taquerias", "burrito", "burritos", "dim", "sum", "dumplings", "boba", "pho", "poke", "korean", "bbq", "wine", "tavern", "tap", "brewery", "sushi", "seafood", "fish"]));
  PLACE_WORDS = new Set(CITIES.flatMap(([c]) => norm(c).split(" ")).filter(w => w.length > 2));
}
function setHeader() {
  const n = D.filter(r => !r.venue).length, all = S.region === "all";
  $("#h1").innerHTML = all ? `<span class="count num">${fmtN(n)}</span> California restaurants, ranked` : `<span class="count num">${fmtN(n)}</span> restaurants in ${esc(regionLabel())}, ranked`;
  $("#kicker").textContent = `${fmtN(CITIES.filter(([, c]) => c > 0).length)} cities and towns · map listings as of Sep 2026 · ratings as of Sep 2021`;
}
function renderRegions(busy) {
  const regs = (RMETA && RMETA.regions) || [], tot = regs.reduce((a, g) => a + g.count_restaurants, 0);
  $("#regions").innerHTML = [["all", "All California", tot], ...regs.map(g => [g.id, g.name, g.count_restaurants])]
    .map(([id, name, n]) => `<button type="button" data-rg="${id}" aria-pressed="${id === S.region}"${busy ? " disabled" : ""}>${esc(name)}<span class="rn">${fmtN(n)}</span></button>`).join("");
}
let loadSeq = 0;
function load(fromRetry) {
  const seq = ++loadSeq;
  $("#list").innerHTML = `<li class="loading">Loading restaurants…</li>`; $("#btitle").textContent = "Loading…";
  (RMETA ? Promise.resolve(RMETA) : fetchJSON("ca_meta.json")).then(m => {
    RMETA = META = m;
    if (S.region !== "all" && !m.regions.some(g => g.id === S.region)) S.region = DEFAULT.region;
    renderRegions(true);
    const ids = S.region === "all" ? m.regions.map(g => g.id) : [S.region];
    let done = 0;
    const want = ids.map(id => (FILES[id] = FILES[id] || fetchJSON(`ca_${id}.json`).catch(e => { delete FILES[id]; throw e; })).then(j => {
      done++; if (ids.length > 1 && seq === loadSeq) $("#btitle").textContent = `Loading ${done} of ${ids.length} regions…`; return j; }));
    return Promise.all(want);
  }).then(files => {
    if (seq !== loadSeq) return;
    build(files);
    readHash();
    if (S.cuisine && !D.some(r => r.cuisine === S.cuisine)) S.cuisine = "";
    if (S.city && !CITY_N.has(norm(S.city))) S.city = ""; else if (S.city) S.city = CITY_N.get(norm(S.city));
    const typed = $("#q").value; if (typed) { S.q = typed; setQuery(); }
    document.body.classList.remove("failed");
    if (!loaded) buildControls();
    FCACHE.clear(); rankMemo = {key: ""}; DETAIL = {}; DREG = new Set(); DPEND = {};
    methodCards(); setHeader(); renderRegions(false);
    scoreAll(); loaded = true; shown = 50; render({scrollTabs: true});
    if (fromRetry) focusResults();
    const idle = window.requestIdleCallback || (f => setTimeout(f, 2500));
    idle(() => { if (S.view === "map") loadShapes(); });
  }).catch(err => {
    if (seq !== loadSeq) return;
    console.error(err);
    renderRegions(false);
    document.body.classList.add("failed");
    $("#btitle").textContent = "Couldn't load the data";
    $("#bsub").textContent = "";
    const why = err.http ? `The restaurant data didn't load: ${esc(err.message)}.` : err.name === "AbortError" ? "The restaurant data is taking too long to load." : "The restaurant data didn't load. Check your connection.";
    $("#list").innerHTML = `<li class="empty">${why} <button class="more" id="retry" type="button" style="display:inline-block;margin:10px 0 0">Try again</button></li>`;
    $("#live").textContent = "Couldn't load the restaurant data. A Try again button is available.";
    $("#retry").onclick = () => load(true);
    if (fromRetry) $("#retry").focus();
  });
}
$("#regions").onclick = e => { const b = e.target.closest("[data-rg]"); if (!b || b.disabled || b.dataset.rg === S.region) return;
  S.region = b.dataset.rg; S.city = ""; $("#cityq").value = ""; cityFromBox = false; save(); load(); };
$("#bsub").onclick = e => { const b = e.target.closest("[data-ij]"); if (!b) return; S.ij = b.dataset.ij; rerender(); const nb = document.querySelector(`#bsub [data-ij="${S.ij}"]`); if (nb) nb.focus(); };
''')
R('let rankMemo = {key: ""};', 'var rankMemo = {key: ""};')

for word in ("Wisconsin", "Milwaukee", "Dane County", "fish fry", "supper club", "custard", "WI Score", "wi_", "wi-eats", "DETAIL ?", "!DETAIL"):
    hits = [m.start() for m in re.finditer(re.escape(word), s)]
    if hits:
        print(f"note: {len(hits)} '{word}' left, e.g. {s[max(0, hits[0]-80):hits[0]+40]!r}")
os.makedirs(os.path.join(ROOT, "site"), exist_ok=True)
open(os.path.join(ROOT, "site", "index.html"), "w", encoding="utf-8").write(s)
print("wrote site/index.html", len(s) // 1024, "KB")
