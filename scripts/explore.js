// California Eats web app: the iPhone app's guides, search, filters, map and place details, in the browser.
// Same data as the app (split into core + detail by scripts/make-site.py). No cookies, no trackers; saved places and the last guide
// live in this browser's localStorage only. Adapted from wa-eats/scripts/explore.js (itself from wi-eats).
(() => {
  "use strict";
  const BASE = document.documentElement.dataset.base || "";
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get(k, d) { try { const v = localStorage.getItem("cae-" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem("cae-" + k, JSON.stringify(v)); } catch { /* private mode */ } },
  };

  // ---------------------------------------------------------------- search (a port of CaliforniaEats/Models/Search.swift)
  const typeSyn = { avenue: "ave", av: "ave", street: "st", boulevard: "blvd", road: "rd", drive: "dr", place: "pl", court: "ct",
    parkway: "pkwy", highway: "hwy", lane: "ln", trail: "trl", circle: "cir", terrace: "ter" };
  const syn = { ...typeSyn, north: "n", south: "s", east: "e", west: "w", saint: "st", mount: "mt", fort: "ft" };
  // looked up with words people type: no prototype, so "constructor" or "__proto__" is just a word
  Object.setPrototypeOf(typeSyn, null); Object.setPrototypeOf(syn, null);
  const abbrs = new Set(Object.values(syn)), typeAbbrs = new Set(Object.values(typeSyn));
  let G = {};   // guide bits, from the data
  const tagPhraseList = [["fish tacos", "fishtaco"], ["fish taco", "fishtaco"], ["dim sum", "dimsum"], ["dimsum", "dimsum"], ["yum cha", "dimsum"],
    ["korean bbq", "kbbq"], ["korean barbecue", "kbbq"], ["kbbq", "kbbq"], ["taquerias", "taqueria"], ["taqueria", "taqueria"], ["burritos", "burrito"],
    ["burrito", "burrito"], ["burger stands", "burgerstand"], ["burger stand", "burgerstand"], ["drive ins", "burgerstand"], ["drive in", "burgerstand"],
    ["wine country", "winecountry"]];
  function normalize(s) {
    let t = String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    t = t.replace(/\b([a-z0-9])\s*&\s*([a-z0-9])\b/g, "$1$2").replace(/&/g, " and ").replace(/['’`]/g, "");
    return t.replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  }
  const normAddr = (s) => normalize(s).split(" ").map((w) => syn[w] || w).join(" ");

  function parse(text) {
    const q = { tokens: [], town: null, townPhrase: null, tag: 0, tagPhrase: null };
    let raw = normalize(text).split(" ").filter(Boolean);
    if (!raw.length) return q;
    let mapped = raw.map((w) => syn[w] || w);
    const find = (phrase) => {
      const p = phrase.split(" ");
      for (let i = 0; i + p.length <= mapped.length; i++) if (p.every((w, k) => mapped[i + k] === w)) return [i, i + p.length];
      return null;
    };
    const cut = ([a, b]) => { const words = raw.slice(a, b).join(" "); raw.splice(a, b - a); mapped.splice(a, b - a); return words; };
    for (const [phrase, key] of tagPhraseList) { const r = find(normalize(phrase)); if (r) { q.tag = G[key]; q.tagPhrase = cut(r); break; } }
    for (const key of TOWN_KEYS_BY_LENGTH) {
      const r = find(key);
      if (r && !(r[1] < mapped.length && typeAbbrs.has(mapped[r[1]]))) { q.town = TOWN_KEYS[key]; q.townPhrase = cut(r); break; }
    }
    const stop = new Set(["the", "and", "of", "a", "in", "near", "me"]);
    let idx = raw.map((_, i) => i);
    if (q.tag || q.town || idx.some((i) => !stop.has(mapped[i]))) idx = idx.filter((i) => !stop.has(mapped[i]));
    idx.forEach((i, n) => {
      const token = raw[i], isLast = n === idx.length - 1;
      if (syn[token]) { q.tokens.push([` ${syn[token]} `, ` ${token}`]); return; }
      const whole = (abbrs.has(token) && (!isLast || token.length > 1)) || (token.length <= 2 && !isLast);
      const needles = [" " + token + (whole ? " " : "")];
      if (isLast && token.length >= 3) for (const [word, abbr] of Object.entries(typeSyn)) if (word !== token && word.startsWith(token)) needles.push(` ${abbr} `);
      q.tokens.push(needles);
    });
    if (q.tokens.length >= 2 && idx.length && typeAbbrs.has(mapped[idx[idx.length - 1]])) {
      const last = idx[idx.length - 1], prev = idx[idx.length - 2];
      q.tokens.splice(-2, 2, [` ${mapped[prev]} ${mapped[last]} `, ` ${raw[prev]} ${raw[last]}`]);
    }
    return q;
  }
  const qEmpty = (q) => !q.tokens.length && !q.town && !q.tag;
  function matches(p, q) {
    if (q.tag && !(p.hc && (p.g & q.tag))) {
      const stem = normalize(q.tagPhrase || "").replace(/s$/, "");
      if (!stem || !p.nameText.includes(" " + stem)) return false;
    }
    if (q.town && p.c !== q.town && !p.nameText.includes(" " + normalize(q.townPhrase || ""))) return false;
    return q.tokens.every((needles) => needles.some((n) => p.search.includes(n)));
  }
  const nameMatches = (p, q) => q.tokens.length && q.tokens.every((needles) => needles.some((n) => p.nameText.includes(n)));

  // ---------------------------------------------------------------- guides (CaliforniaEats/Models/Guide.swift)
  const MI = { 5: "3 MICHELIN Stars", 4: "2 MICHELIN Stars", 3: "1 MICHELIN Star", 2: "Bib Gourmand", 1: "MICHELIN Recommended" };
  const checked = (key) => (p) => p.hc && (p.g & G[key]);
  const GUIDES = {
    taqueria: { title: "Taquerías", sub: "Hand-checked taquerías and taco shops, with what's on the menu", inc: checked("taqueria"), sorts: ["nearest", "name", "oldest"] },
    dimsum: { title: "Dim Sum", sub: "Hand-checked dim sum houses and bakeries", inc: checked("dimsum"), sorts: ["nearest", "name", "oldest"] },
    burrito: { title: "Burritos", sub: "Mission-style burritos in the Bay Area, California burritos in San Diego, hand-checked", inc: checked("burrito"), sorts: ["nearest", "name", "oldest"] },
    fishtaco: { title: "Fish Tacos", sub: "Hand-checked Baja-style fish tacos, mostly San Diego", inc: checked("fishtaco"), sorts: ["nearest", "name", "oldest"] },
    kbbq: { title: "Korean BBQ", sub: "Hand-checked tabletop-grill Korean barbecue", inc: checked("kbbq"), sorts: ["nearest", "name", "oldest"] },
    burgerstand: { title: "Burger Stands", sub: "Hand-checked walk-up burger stands and drive-ins", inc: checked("burgerstand"), sorts: ["nearest", "name", "oldest"] },
    winecountry: { title: "Wine Country", sub: "Hand-checked restaurants in California's wine towns", inc: checked("winecountry"), sorts: ["nearest", "name", "oldest"] },
    honors: { title: "MICHELIN & James Beard", sub: "MICHELIN Guide California 2026 and James Beard honors, from the official announcements. Facts, not ratings.", inc: (p) => p.mi || p.h || p.gs,
      sorts: ["honored", "nearest", "name"], ranked: true },
    oldest: { title: "Oldest Places", sub: "Opening years we could verify at the current address, oldest first", inc: (p) => p.f != null, sorts: ["oldest", "nearest"], ranked: true },
    inspections: { title: "Inspections", sub: "", inc: (p) => p.ij != null && p.ij === st.jur, sorts: ["best", "lowest", "nearest"] },
    all: { title: "All Restaurants", sub: "Restaurants, cafés and bars statewide", inc: () => true, sorts: ["name", "nearest"] },
    saved: { title: "Saved", sub: "Places you saved in this browser", inc: (p) => saved.has(p.id), sorts: ["name", "nearest"] },
  };
  const SORT_LABEL = { nearest: "Nearest", oldest: "Oldest first", name: "A to Z", honored: "Most honored", best: "Best latest result", lowest: "Lowest latest result" };

  // ---------------------------------------------------------------- state
  let P = [], D = null, CAL = {}, JURS = [], TOWNS = new Set(), KINDS = new Set(), TOWN_KEYS = {}, TOWN_KEYS_BY_LENGTH = [], GENERATED = "", REGIONS = [];
  let here = null, shown = 100, current = [], view = "list";
  const saved = new Set(store.get("saved", []));
  const st = { g: "taqueria", q: "", sort: "", region: "", town: "", cuisine: "", chains: false, p: "", jur: 0 };

  const miles = (a, b) => {
    const r = Math.PI / 180, dLa = (b.la - a.la) * r, dLo = (b.lo - a.lo) * r;
    const h = Math.sin(dLa / 2) ** 2 + Math.cos(a.la * r) * Math.cos(b.la * r) * Math.sin(dLo / 2) ** 2;
    return 3958.8 * 2 * Math.asin(Math.sqrt(h));
  };
  const milesText = (m) => (m < 10 ? m.toFixed(1) : Math.round(m)) + " mi";
  // a simplified California outline: Nevada sits inside the state's bounding box, so a box test would call Reno "California"
  const OUTLINE = [[42.05, -124.6], [42.05, -119.95], [39.0, -119.95], [35.0, -114.55], [34.25, -114.05], [32.718, -114.72], [32.534, -117.124],
    [32.534, -117.5], [33.8, -119.9], [34.6, -121.0], [36.3, -122.2], [37.8, -123.2], [40.2, -124.6]];
  function inCalifornia(la, lo) {
    let inside = false;
    for (let i = 0, j = OUTLINE.length - 1; i < OUTLINE.length; j = i++) {
      const [yi, xi] = OUTLINE[i], [yj, xj] = OUTLINE[j];
      if ((yi > la) !== (yj > la) && lo < (xj - xi) * (la - yi) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }

  function order() {
    const g = GUIDES[st.g];
    if (st.sort && g.sorts.includes(st.sort)) return st.sort;
    if (here && g.sorts.includes("nearest") && ["taqueria", "dimsum", "burrito", "fishtaco", "kbbq", "burgerstand", "winecountry"].includes(st.g)) return "nearest";
    return g.sorts[0] === "nearest" && !here ? g.sorts[1] : g.sorts[0];
  }

  function allows(p) {
    const handPicked = ["taqueria", "dimsum", "burrito", "fishtaco", "kbbq", "burgerstand", "winecountry", "honors", "saved"].includes(st.g);
    if (p.v && !handPicked) return false;            // gas-station counters, stadium stands and the like
    if (st.region && p.rg !== st.region) return false;
    if (st.town && p.c !== st.town) return false;
    if (st.cuisine && p.cu !== st.cuisine) return false;
    if (st.chains && p.ch >= 5) return false;
    return true;
  }

  // within one county: LA County's own score where there is one, otherwise the placard; then fewer non-pass results on record
  const inspKey = (p) => [p.is != null ? -p.is : (p.ir ?? 9) * 1000, p.ib ?? 0];
  function list() {
    const g = GUIDES[st.g], q = parse(st.q), o = order();
    if (qEmpty(q) && st.q.trim()) return [];   // typed something, but nothing searchable ("🌮", "!!!")
    if (!qEmpty(q)) indexAll();
    let out = P.filter((p) => g.inc(p) && allows(p) && (qEmpty(q) || matches(p, q)));
    const byName = (a, b) => a.n.localeCompare(b.n, "en", { sensitivity: "base" });
    const dist = (p) => (here && p.la != null ? miles(here, p) : Infinity);
    if (o === "nearest" && here) out.sort((a, b) => dist(a) - dist(b) || byName(a, b));
    else if (o === "oldest") out.sort((a, b) => (a.f ?? 9999) - (b.f ?? 9999) || byName(a, b));
    else if (o === "honored") out.sort((a, b) => (b.ip ?? -1) - (a.ip ?? -1) || byName(a, b));
    else if (o === "best" || o === "lowest") {
      const s = o === "best" ? 1 : -1;
      out.sort((a, b) => { const x = inspKey(a), y = inspKey(b); return s * (x[0] - y[0]) || s * (x[1] - y[1]) || byName(a, b); });
    } else out.sort(byName);
    if (q.tokens.length && !g.ranked && o !== "best" && o !== "lowest") {       // name matches first when searching
      const named = out.filter((p) => nameMatches(p, q));
      if (named.length && named.length < out.length) { const ids = new Set(named); out = named.concat(out.filter((p) => !ids.has(p))); }
    }
    return out;
  }

  // ---------------------------------------------------------------- rendering
  function chips(p, max) {
    const c = [];
    if (p.mi) c.push(`<span class="tag tag-jb">${MI[p.mi]}</span>`);
    if (p.gs) c.push('<span class="tag tag-jb">MICHELIN Green Star</span>');
    const jb = p.h & 1 ? "America's Classic" : p.h & 2 ? "James Beard winner" : p.h & 4 ? "James Beard finalist" : p.h & 8 ? "James Beard semifinalist" : null;
    if (jb) c.push(`<span class="tag tag-jb">${jb}</span>`);
    if (p.hc) for (const [k, l] of [["taqueria", "Taquería"], ["burrito", "Burritos"], ["fishtaco", "Fish tacos"], ["dimsum", "Dim sum"], ["kbbq", "Korean BBQ"],
      ["burgerstand", "Burger stand"], ["winecountry", "Wine country"]]) if (p.g & G[k]) c.push(`<span class="tag">${l}</span>`);
    if (p.ch >= 5) c.push(`<span class="tag tag-plain">Chain · ${p.ch}</span>`);
    if (p.t === 0 && !p.h && !p.mi && !p.hc) c.push('<span class="tag tag-dash">Listing only</span>');
    return (max ? c.slice(0, max) : c).join("");
  }

  function resultBadge(p) {
    const j = JURS[p.ij];
    if (!j) return "";
    if (p.ir == null) return `<span class="ex-res ex-res-n">${p.is != null ? "Score " + p.is : "—"}</span>`;
    const v = j.scale[p.ir], lbl = j.id === "lac" ? "Grade " + v : v.charAt(0) + v.slice(1).toLowerCase();
    return `<span class="ex-res ex-res-${Math.min(p.ir, 2)}">${esc(lbl)}</span>`;
  }

  function metric(p, o) {
    if (o === "nearest" && here && p.la != null) return [milesText(miles(here, p)), "away"];
    if (o === "honored" && p.ip != null) return [String(Math.round(p.ip)), "honor pts"];
    if (p.f && st.g !== "all") return [String(p.f), "opened"];
    return null;
  }

  function jurNote() {
    const j = JURS[st.jur];
    if (!j) return "";
    const how = { lac: "LA County's official score and letter grade at the latest inspection (A 90–100, B 80–89, C 70–79). Seven cities that never adopted grade cards show the score only. Pasadena, Long Beach and Vernon inspect on their own and aren't included.",
      sf: "San Francisco's official placard at the latest inspection: Pass, Conditional Pass or Closure.",
      sac: "Sacramento County's official placard at the latest inspection: Pass, Conditional Pass or Closed." }[j.id] || "";
    return `${how} As recorded by ${j.agency}, through ${j.through}. We never compute a grade of our own or compare counties. One inspection is a snapshot of one day.`;
  }

  function render() {
    const g = GUIDES[st.g], o = order();
    current = list();
    document.querySelectorAll(".ex-guides button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.g === st.g)));
    $("#ex-sub").textContent = st.g === "inspections" ? jurNote() : g.sub;
    $("#ex-jur").hidden = st.g !== "inspections";
    const sortSel = $("#ex-sort");
    sortSel.innerHTML = g.sorts.map((s) => `<option value="${s}"${s === o ? " selected" : ""}>${SORT_LABEL[s]}</option>`).join("");
    sortSel.disabled = g.sorts.length < 2;
    const regionName = st.region && (REGIONS.find((r) => r.id === st.region) || {}).name;
    const filters = [regionName && `in ${regionName}`, st.town && `in ${st.town}`, st.cuisine && st.cuisine, st.chains && "no chains"].filter(Boolean);
    $("#ex-count").textContent = `${current.length.toLocaleString()} ${current.length === 1 ? "place" : "places"} · ${SORT_LABEL[o]}` + (filters.length ? ` · ${filters.join(", ")}` : "");
    $("#ex-clear").hidden = !filters.length;
    $("#ex-locate").hidden = Boolean(here);
    if (view === "list") renderList(o); else drawMap();
    saveHash();
  }

  function renderList(o) {
    const ol = $("#ex-list");
    const g = GUIDES[st.g];
    if (!current.length) {
      ol.innerHTML = `<li class="ex-empty">${st.g === "saved" ? "Nothing saved yet. Open a place and tap Save to keep it here, in this browser." : "No places match. Try fewer words or clear the filters."}</li>`;
      $("#ex-more").hidden = true;
      return;
    }
    ol.innerHTML = current.slice(0, shown).map((p, i) => {
      const m = metric(p, o);
      const rank = g.ranked ? `<span class="ex-rank${i < 3 ? " top" : ""}" aria-label="Rank ${i + 1}">${i + 1}</span>` : "";
      const insp = st.g === "inspections";
      const second = insp ? [p.a, p.id_ && "inspected " + p.id_, p.is != null && p.ir != null && "score " + p.is].filter(Boolean).join(" · ") : (p.hc ? p.di : "");
      const metricHtml = insp ? `<span class="ex-metric">${resultBadge(p)}<small>official</small></span>` : m ? `<span class="ex-metric"><b>${esc(m[0])}</b><small>${m[1]}</small></span>` : "";
      return `<li><button class="ex-row" data-i="${p.i}">${rank}<span class="ex-main"><b>${esc(p.n)}</b><span class="ex-town">${esc([p.c, p.cu].filter(Boolean).join(" · "))}</span>${second ? `<span class="ex-town">${esc(second)}</span>` : ""}<span class="ex-chips">${chips(p, 4)}</span></span>${metricHtml}</button></li>`;
    }).join("");
    const left = current.length - shown;
    $("#ex-more").hidden = left <= 0;
    $("#ex-more").textContent = `Show more (${left.toLocaleString()} left)`;
  }

  // ---------------------------------------------------------------- place panel
  const TIER = { 2: "On an official list", 1: "Confirmed listing", 0: "Listing only" };

  function rate(p) {
    if (p.t === 2) return null;
    const src = SOURCES[p.s] || "meta";
    const group = src === "meta" ? (p.t === 1 ? "meta_high (>=0.95)" : "meta_mid (0.90-0.95)") : (src === "AllThePlaces" || src === "DAC") ? "brand_feed" : null;
    const v = ["lac", "sd"].map((k) => group && CAL[k]?.groups?.[group]?.official).filter((x) => x != null);
    if (!v.length) return null;
    const lo = Math.round(Math.min(...v) * 100), hi = Math.round(Math.max(...v) * 100);
    return lo === hi ? `${lo}%` : `${lo}–${hi}%`;
  }

  function howWeKnow(p) {
    const src = SOURCES[p.s] || "meta";
    if (src === "research") return "On our hand-checked or honors list. The open map data didn't list it as a place to eat (it may sit inside a hotel or inn), so it's placed from its own map listing or street address.";
    if (p.t === 2) return src === "official"
      ? "From a county food-facility list. The open map data didn't have it, so its location comes from the county's record."
      : "Matched to a county food-facility record or an active California ABC liquor license.";
    const r = rate(p);
    return (p.t === 1 ? "A high-confidence listing in Overture's open map data." : "A single listing in Overture's open map data, so it may be closed or misfiled.")
      + (r ? ` Checked against LA County's and San Diego County's food-facility lists, listings like this matched a permitted business ${r} of the time.` : "")
      + (p.hc ? " It's also on our hand-checked list, checked in Oct 2026 against a 2025 or 2026 source." : "");
  }

  const kv = (k, v) => (v == null || v === "" ? "" : `<div class="ex-kv"><span>${esc(k)}</span><b>${esc(v)}</b></div>`);
  const section = (t, body) => `<section class="ex-sec"><h3>${esc(t)}</h3>${body}</section>`;

  function openPlace(p, push = true) {
    st.p = p.id;
    const d = (D && D[p.i]) || {};
    const addr = [p.a, [p.c, p.z].filter(Boolean).join(" ")].filter(Boolean).join(", ");
    const apple = p.la != null
      ? `https://maps.apple.com/?q=${encodeURIComponent(p.n)}&ll=${p.la},${p.lo}`
      : `https://maps.apple.com/?q=${encodeURIComponent(p.n + ", " + addr)}`;
    const dirs = p.la != null ? `https://maps.apple.com/?daddr=${p.la},${p.lo}&dirflg=d` : apple;
    const site = d.w && /^https?:\/\//i.test(d.w) ? d.w : null;
    let html = `<button class="ex-close" id="ex-close" aria-label="Close">×</button>
      <p class="ex-kicker">${esc([(p.c || "California"), p.co].filter(Boolean).join(" · ").toUpperCase())}</p>
      <h2 id="ex-pname">${esc(p.n)}</h2>
      <p class="ex-addr">${esc([addr, p.cu].filter(Boolean).join(" · "))}</p>
      ${here && p.la != null ? `<p class="ex-dist">${milesText(miles(here, p))} away</p>` : ""}
      <p class="ex-chips">${chips(p)}</p>
      <div class="ex-actions">
        <a class="btn ex-apple" href="${esc(apple)}" rel="noopener" target="_blank">Ratings, hours &amp; photos · Apple Maps</a>
        <div class="ex-act-row">
          <a href="${esc(dirs)}" rel="noopener" target="_blank">Directions</a>
          ${d.ph ? `<a href="tel:${esc(d.ph.replace(/[^\d+]/g, ""))}">Call</a>` : ""}
          ${site ? `<a href="${esc(site)}" rel="noopener nofollow" target="_blank">Website</a>` : ""}
          <button id="ex-save" aria-pressed="${saved.has(p.id)}">${saved.has(p.id) ? "Saved" : "Save"}</button>
        </div>
      </div>`;
    if (p.hc || d.note || p.di) {
      html += section(p.hc ? "Hand-checked" : "Notes", (d.note ? `<p>${esc(d.note)}</p>` : "") + (p.di ? `<p><b>On the menu</b><br>${esc(p.di)}</p>` : "")
        + (p.hc ? `<p class="ex-fine">Checked open in Oct 2026 against a 2025 or 2026 source: the place's own site, menu or ordering page, or dated local news. Menus and hours change, so check before you go.</p>` : ""));
    }
    if (p.mi || p.h || p.gs || p.f || d.bf) {
      const lines = [p.mi && `${MI[p.mi]} · MICHELIN Guide California 2026`, p.gs && "MICHELIN Green Star (2026)",
        ...(d.jbf ? d.jbf.split("; ").map((x) => "James Beard: " + x) : [])].filter(Boolean);
      html += section("Honors & history", (lines.length ? `<ul>${lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>` : "")
        + (p.f ? kv("Opened here", String(p.f) + (d.on ? ` · ${d.on}` : "")) : "") + (d.bf ? kv("Founded", d.bf) : "")
        + (p.mi || p.h || p.gs ? `<p class="ex-fine">Honors are facts from MICHELIN's and the James Beard Foundation's own announcements, not ratings. MICHELIN is a trademark of Michelin; James Beard Award is a trademark of the James Beard Foundation.</p>` : ""));
    }
    if (p.ij != null && JURS[p.ij]) {
      const j = JURS[p.ij];
      html += section(`Health inspections · ${j.name}`,
        `<p class="ex-grade">${resultBadge(p)} Latest inspection ${esc(p.id_ || "")}${p.is != null ? " · score " + p.is : ""}</p>`
        + kv("Inspections on record", p.in) + kv(j.id === "lac" ? "Graded B or C" : "Yellow or red placards", p.ib)
        + (j.id === "lac" && p.ir == null ? `<p class="ex-fine">This city never adopted LA County's letter-grade cards, so only the official score is shown.</p>` : "")
        + `<p class="ex-fine">Official result, as recorded by ${esc(j.agency)}, through ${esc(j.through)}. One inspection is a snapshot of one day; conditions may have changed since.</p>`);
    }
    html += section("How we know it's here", kv("Listed as", TIER[p.t]) + kv("County", p.co)
      + kv("Serves alcohol", p.liq ? `${LIQT[p.liq]} (ABC on-sale license)` : "— (no on-sale license matched)")
      + (p.ch >= 2 ? kv("Locations in California", p.ch.toLocaleString()) : "") + `<p class="ex-fine">${esc(howWeKnow(p))}</p>`);
    html += `<p class="ex-app">Save it on your phone: <a class="store-btn" href="${BASE}/#download"><span class="store-label">Get the free iPhone app</span></a></p>`;
    const panel = $("#ex-panel");
    panel.innerHTML = html;
    panel.hidden = false;
    document.body.classList.add("ex-open");
    $("#ex-close").onclick = closePlace;
    $("#ex-save").onclick = (e) => {
      if (saved.has(p.id)) saved.delete(p.id); else saved.add(p.id);
      store.set("saved", [...saved]);
      e.target.textContent = saved.has(p.id) ? "Saved" : "Save";
      e.target.setAttribute("aria-pressed", String(saved.has(p.id)));
      if (st.g === "saved") render();
    };
    panel.scrollTop = 0;
    $("#ex-close").focus();
    if (push) saveHash();
    if (!D) loadDetail().then(() => { if (st.p === p.id) openPlace(p, false); });
  }

  function closePlace() {
    const was = st.p;
    st.p = "";
    $("#ex-panel").hidden = true;
    document.body.classList.remove("ex-open");
    saveHash();
    const row = was && document.querySelector(`.ex-row[data-i="${P.findIndex((p) => p.id === was)}"]`);
    if (row) row.focus();
  }

  // ---------------------------------------------------------------- map (canvas: county outlines + a dot per place)
  let SHAPES = null, cam = null;
  const LAT0 = 37.2, KX = Math.cos(LAT0 * Math.PI / 180);
  const proj = (lo, la) => [(lo + 119.4) * KX, -(la - LAT0)];

  function fitCam(w, h, box) {
    const [x0, y0] = proj(box[0], box[3]), [x1, y1] = proj(box[1], box[2]);
    const k = Math.min(w / (x1 - x0), h / (y1 - y0)) * 0.95;
    return { k, x: (w - (x1 - x0) * k) / 2 - x0 * k, y: (h - (y1 - y0) * k) / 2 - y0 * k };
  }
  const STATE_BOX = [-124.5, -114.1, 32.5, 42.05];

  async function drawMap() {
    const cv = $("#ex-map"), wrap = $("#ex-mapwrap");
    const w = wrap.clientWidth, h = wrap.clientHeight, dpr = window.devicePixelRatio || 1;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    if (!cam) cam = fitCam(w, h, STATE_BOX);
    if (!SHAPES) SHAPES = await fetchJSON(`${BASE}/data/ca_shapes.json`).catch(() => ({ state: [], counties: [] }));
    const c = cv.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const X = (lo, la) => { const [x, y] = proj(lo, la); return [x * cam.k + cam.x, y * cam.k + cam.y]; };
    const ring = (r) => { r.forEach(([lo, la], i) => { const [x, y] = X(lo, la); i ? c.lineTo(x, y) : c.moveTo(x, y); }); c.closePath(); };
    c.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--surface").trim() || "#fff";
    c.beginPath(); (SHAPES.state || []).forEach((poly) => poly.forEach(ring)); c.fill("evenodd");
    c.strokeStyle = "rgba(74,90,114,.35)"; c.lineWidth = 0.8;
    for (const co of SHAPES.counties || []) { c.beginPath(); co.c.forEach(ring); c.stroke(); }
    const pts = current.filter((p) => p.la != null);
    const r = Math.max(1.6, Math.min(5, 1.2 + cam.k / 160));
    for (const featured of [false, true]) {
      c.fillStyle = featured ? "#fdb515" : "#003262";
      c.strokeStyle = "#003262"; c.lineWidth = 1;
      for (const p of pts) {
        if (Boolean(p.hc || p.mi) !== featured) continue;
        const [x, y] = X(p.lo, p.la);
        if (x < -5 || y < -5 || x > w + 5 || y > h + 5) continue;
        c.beginPath(); c.arc(x, y, featured ? r + 1 : r, 0, 6.2832); c.fill(); if (featured) c.stroke();
      }
    }
    $("#ex-maphint").textContent = pts.length ? `${pts.length.toLocaleString()} places · tap a dot` : "No places to show";
  }

  function nearestDot(px, py) {
    let best = null, bd = 14 * 14;
    for (const p of current) {
      if (p.la == null) continue;
      const [x0, y0] = proj(p.lo, p.la), x = x0 * cam.k + cam.x, y = y0 * cam.k + cam.y;
      const d = (x - px) ** 2 + (y - py) ** 2;
      if (d < bd) { bd = d; best = p; }
    }
    return best;
  }

  function zoomAt(f, px, py) {
    const k = Math.min(Math.max(cam.k * f, 30), 80000);
    const s = k / cam.k;
    cam = { k, x: px - (px - cam.x) * s, y: py - (py - cam.y) * s };
    drawMap();
  }

  function mapEvents() {
    const cv = $("#ex-map");
    const ptrs = new Map();
    let moved = false, pinch0 = null;
    cv.addEventListener("wheel", (e) => { e.preventDefault(); const b = cv.getBoundingClientRect(); zoomAt(e.deltaY < 0 ? 1.25 : 0.8, e.clientX - b.left, e.clientY - b.top); }, { passive: false });
    cv.addEventListener("pointerdown", (e) => { cv.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, [e.clientX, e.clientY]); moved = false; pinch0 = null; });
    cv.addEventListener("pointermove", (e) => {
      if (!ptrs.has(e.pointerId)) return;
      const prev = ptrs.get(e.pointerId);
      ptrs.set(e.pointerId, [e.clientX, e.clientY]);
      if (ptrs.size === 2) {
        const [a, b] = [...ptrs.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        const r = cv.getBoundingClientRect();
        if (pinch0) zoomAt(d / pinch0, (a[0] + b[0]) / 2 - r.left, (a[1] + b[1]) / 2 - r.top);
        pinch0 = d; moved = true; return;
      }
      const dx = e.clientX - prev[0], dy = e.clientY - prev[1];
      if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
      cam.x += dx; cam.y += dy; drawMap();
    });
    const up = (e) => {
      ptrs.delete(e.pointerId);
      if (!moved && ptrs.size === 0) {
        const b = cv.getBoundingClientRect(), p = nearestDot(e.clientX - b.left, e.clientY - b.top);
        if (p) openPlace(p);
      }
      if (ptrs.size < 2) pinch0 = null;
    };
    cv.addEventListener("pointerup", up);
    cv.addEventListener("pointercancel", (e) => ptrs.delete(e.pointerId));
    $("#ex-zin").onclick = () => zoomAt(1.6, cv.clientWidth / 2, cv.clientHeight / 2);
    $("#ex-zout").onclick = () => zoomAt(0.625, cv.clientWidth / 2, cv.clientHeight / 2);
    window.addEventListener("resize", () => { if (view === "map") drawMap(); });
  }

  function centerOn(pt) {
    const cv = $("#ex-map"), w = cv.clientWidth, h = cv.clientHeight;
    const k = 4000, [x, y] = proj(pt.lo, pt.la);
    cam = { k, x: w / 2 - x * k, y: h / 2 - y * k };
  }

  // ---------------------------------------------------------------- data, URL state, controls
  let SOURCES = [], LIQT = [];
  // Search text for every place. Building it for 120,000 places blocks the page for seconds on a phone, and the first screen
  // (a guide) doesn't need it: it's built in small slices after the first paint, and finished at once if a search comes first.
  let indexed = 0;
  function indexPlace(p) {
    p.search = " " + normalize([p.n, p.c, p.co, p.z, p.cu, p.b, p.di].filter(Boolean).join(" ")) + " " + normAddr(p.a || "") + " ";
    p.nameText = " " + normalize([p.n, p.b].filter(Boolean).join(" ")) + " ";
  }
  function indexAll() { while (indexed < P.length) indexPlace(P[indexed++]); }
  const idle = (f) => ("requestIdleCallback" in window ? requestIdleCallback(f, { timeout: 2000 }) : setTimeout(f, 50));
  function indexSome(deadline) {
    const until = performance.now() + Math.min(deadline && !deadline.didTimeout ? deadline.timeRemaining() : 12, 12);
    while (indexed < P.length && performance.now() < until) indexPlace(P[indexed++]);
    if (indexed < P.length) idle(indexSome);
  }
  async function fetchJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(r.status + " " + url); return r.json(); }
  let detailPromise = null;
  function loadDetail() {
    detailPromise ||= fetchJSON(`${BASE}/data/detail.json`).then((d) => { D = d; }).catch(() => { D = {}; });
    return detailPromise;
  }

  async function load() {
    const d = await fetchJSON(`${BASE}/data/core.json`);
    GENERATED = d.generated; CAL = d.calibration || {}; SOURCES = d.sources || []; JURS = d.jurs || []; G = d.guides || {}; LIQT = d.liqt || [];
    REGIONS = d.regions || [];
    const C = d.cols, n = C.id.length, towns = new Map();
    for (const k in C) if (C[k] && !Array.isArray(C[k])) {   // sparse columns: [rows since the last value, value] pairs
      const full = new Array(n).fill(null);
      let i = -1;
      for (const [gap, v] of C[k].gap) { i += gap; full[i] = v; }
      C[k] = full;
    }
    P = new Array(n);
    for (let i = 0; i < n; i++) {
      const city = C.c[i] == null ? null : d.cities[C.c[i]], cu = d.cuisines[C.cu[i]], brand = C.b[i] == null ? null : d.brands[C.b[i]];
      const co = C.ct[i] == null ? null : d.counties[C.ct[i]];
      const p = { i, id: C.id[i], n: C.n[i], c: city, co, cu, t: C.t[i], s: C.s[i], a: C.a[i], z: C.z[i], la: C.la[i], lo: C.lo[i],
        ch: C.ch[i] || 1, v: C.v[i] === 1, g: C.g[i] || 0, hc: C.hc[i] === 1, ip: C.ip[i], f: C.f[i], h: C.h[i] || 0, mi: C.mi[i] || 0, gs: C.gs[i] === 1,
        di: C.di[i], liq: C.liq[i] || 0, rg: (REGIONS[C.rg[i]] || {}).id, ij: C.ij[i], ir: C.ir[i], is: C.is[i], id_: C.id_[i], in: C.in[i], ib: C.ib[i], b: brand };
      P[i] = p;
      if (city && !p.v) towns.set(city, (towns.get(city) || 0) + 1);
    }
    const byCount = [...towns.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    for (const [name] of byCount) { const k = normAddr(name); if (!(k in TOWN_KEYS)) TOWN_KEYS[k] = name; }
    TOWN_KEYS_BY_LENGTH = Object.keys(TOWN_KEYS).sort((a, b) => b.length - a.length);
    TOWNS = new Set(towns.keys());
    $("#ex-region").innerHTML = '<option value="">All of California</option>' + REGIONS.map((r) => `<option value="${esc(r.id)}">${esc(r.name)}</option>`).join("");
    $("#ex-town").innerHTML = '<option value="">All towns</option>' + [...towns.keys()].sort((a, b) => a.localeCompare(b)).map((t) => `<option>${esc(t)}</option>`).join("");
    const cuis = new Map();
    for (const p of P) if (!p.v) cuis.set(p.cu, (cuis.get(p.cu) || 0) + 1);
    KINDS = new Set(cuis.keys());
    $("#ex-cuisine").innerHTML = '<option value="">All kinds</option>' + [...cuis.entries()].sort((a, b) => b[1] - a[1]).map(([c, k]) => `<option value="${esc(c)}">${esc(c)} (${k.toLocaleString()})</option>`).join("");
    $("#ex-jur").innerHTML = JURS.map((j, i) => `<option value="${i}">${esc(j.name)}</option>`).join("");
  }

  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    st.g = Object.hasOwn(GUIDES, h.get("g") || "") ? h.get("g") : store.get("guide", "taqueria");
    if (!Object.hasOwn(GUIDES, String(st.g))) st.g = "taqueria";
    st.q = h.get("q") || ""; st.region = h.get("region") || ""; st.town = h.get("town") || ""; st.cuisine = h.get("kind") || ""; st.chains = h.get("chains") === "1";
    st.sort = h.get("sort") || ""; st.p = h.get("p") || ""; st.jur = Number(h.get("county") || store.get("jur", 0)) || 0;
  }
  function saveHash() {
    const h = new URLSearchParams();
    h.set("g", st.g);
    if (st.q) h.set("q", st.q); if (st.region) h.set("region", st.region); if (st.town) h.set("town", st.town); if (st.cuisine) h.set("kind", st.cuisine);
    if (st.chains) h.set("chains", "1"); if (st.sort) h.set("sort", st.sort); if (st.p) h.set("p", st.p); if (st.g === "inspections") h.set("county", String(st.jur));
    history.replaceState(null, "", "#" + h.toString());
    store.set("guide", st.g); store.set("jur", st.jur);
  }

  function locate() {
    if (!navigator.geolocation) { $("#ex-locmsg").textContent = "This browser can't share its location."; return; }
    $("#ex-locmsg").textContent = "Finding you…";
    navigator.geolocation.getCurrentPosition((pos) => {
      here = { la: pos.coords.latitude, lo: pos.coords.longitude };
      const outside = !inCalifornia(here.la, here.lo);
      $("#ex-locmsg").textContent = outside ? "You're outside California, so distances are from where you are now. Your location stays in this browser."
        : "Sorted by distance from you. Your location stays in this browser.";
      st.sort = GUIDES[st.g].sorts.includes("nearest") ? "nearest" : st.sort;
      if (view === "map" && !outside) centerOn(here);
      shown = 100; render();
    }, () => { $("#ex-locmsg").textContent = "Location is off for this site. Allow it in your browser settings to sort by distance."; },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
  }

  function setView(v) {
    view = v;
    document.querySelectorAll(".ex-view button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
    $("#ex-listwrap").hidden = v !== "list";
    $("#ex-mapwrap").hidden = v !== "map";
    render();
  }

  function controls() {
    document.querySelectorAll(".ex-guides button").forEach((b) => b.onclick = () => { st.g = b.dataset.g; st.sort = ""; shown = 100; render(); });
    let t = null;
    $("#ex-q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { st.q = e.target.value; shown = 100; render(); }, 150); });
    $("#ex-sort").onchange = (e) => { st.sort = e.target.value; if (st.sort === "nearest" && !here) locate(); shown = 100; render(); };
    $("#ex-region").onchange = (e) => {
      st.region = e.target.value; st.town = ""; $("#ex-town").value = ""; shown = 100;
      if (view === "map") {   // the map zooms to the region
        const ps = P.filter((p) => p.rg === st.region && p.la != null);
        cam = ps.length ? fitCam($("#ex-map").clientWidth, $("#ex-map").clientHeight, [Math.min(...ps.map((p) => p.lo)), Math.max(...ps.map((p) => p.lo)),
          Math.min(...ps.map((p) => p.la)), Math.max(...ps.map((p) => p.la))]) : null;
      }
      render();
    };
    $("#ex-town").onchange = (e) => { st.town = e.target.value; shown = 100; render(); };
    $("#ex-cuisine").onchange = (e) => { st.cuisine = e.target.value; shown = 100; render(); };
    $("#ex-jur").onchange = (e) => { st.jur = Number(e.target.value) || 0; shown = 100; render(); };
    $("#ex-chains").onchange = (e) => { st.chains = e.target.checked; shown = 100; render(); };
    $("#ex-clear").onclick = () => { st.region = st.town = st.cuisine = ""; st.chains = false; syncInputs(); shown = 100; render(); };
    $("#ex-locate").onclick = locate;
    $("#ex-more").onclick = () => { shown += 200; renderList(order()); };
    document.querySelectorAll(".ex-view button").forEach((b) => b.onclick = () => setView(b.dataset.v));
    $("#ex-list").addEventListener("click", (e) => { const b = e.target.closest(".ex-row"); if (b) openPlace(P[+b.dataset.i]); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && st.p) closePlace(); });
    // a link or an edited address bar changing the hash (our own updates use replaceState, which doesn't fire this)
    window.addEventListener("hashchange", () => {
      readHash(); checkState(); syncInputs(); shown = 100; render();
      const p = st.p && P.find((x) => x.id === st.p);
      if (p) openPlace(p, false); else if (!$("#ex-panel").hidden) closePlace();
    });
    mapEvents();
  }
  function checkState() {
    if (st.region && !REGIONS.some((r) => r.id === st.region)) st.region = "";
    if (st.town && !TOWNS.has(st.town)) st.town = "";
    if (st.cuisine && !KINDS.has(st.cuisine)) st.cuisine = "";
    if (!(st.jur >= 0 && st.jur < JURS.length)) st.jur = 0;
  }
  function syncInputs() {
    $("#ex-q").value = st.q; $("#ex-region").value = st.region; $("#ex-town").value = st.town; $("#ex-cuisine").value = st.cuisine;
    $("#ex-chains").checked = st.chains; $("#ex-jur").value = String(st.jur);
  }

  (async () => {
    readHash();
    // #ex-count is inside the hidden app, so a failed load is reported where "Loading…" was
    try { await load(); } catch (e) { $("#ex-loading").textContent = "The restaurant list couldn't load. Refresh to try again."; return; }
    checkState(); syncInputs(); controls();
    $("#ex-app").hidden = false;
    $("#ex-loading").hidden = true;
    render();
    const open = st.p && P.find((p) => p.id === st.p);
    if (open) { await loadDetail(); openPlace(open, false); }
    idle(() => loadDetail());
    idle(indexSome);
  })();
})();
