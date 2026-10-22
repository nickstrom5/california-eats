import XCTest
import CoreLocation
@testable import CaliforniaEats

@MainActor
final class CaliforniaEatsTests: XCTestCase {

    /// A tiny data folder with the same shape as Resources/Data: index.json plus two region files.
    private func sampleModel() async throws -> AppModel {
        let index = """
        {"v":1,"generated":"2026-10-07","cuisines":["Mexican","Chinese","Burgers","Bar & Pub","American & Other"],"brands":["In-N-Out Burger"],
         "sources":["official","meta","AllThePlaces","DAC","research"],"counties":["Los Angeles County","San Francisco","San Diego County"],
         "guides":{"taqueria":1,"burrito":2,"fishtaco":4,"dimsum":8,"kbbq":16,"burgerstand":32,"winecountry":64,"oldest":128},
         "liqt":["","beer","beer & wine","full bar"],
         "jurs":[{"id":"lac","name":"Los Angeles County","agency":"LA County DPH","scale":["A","B","C"],"through":"2026-09-30","newest":"2026-09-30"},
                 {"id":"sf","name":"San Francisco","agency":"SF DPH","scale":["Pass","Conditional Pass","Closure"],"through":"2026-09-30","newest":"2026-09-29"}],
         "count":9,"count_restaurants":8,"count_hc":3,
         "calibration":{"lac":{"groups":{"meta_high (>=0.95)":{"n":17409,"official":0.86},"meta_mid (0.90-0.95)":{"n":3731,"official":0.482}},"coverage":0.611},
                        "sd":{"groups":{"meta_high (>=0.95)":{"n":6472,"official":0.729},"meta_mid (0.90-0.95)":{"n":1117,"official":0.44}},"coverage":0.583}},
         "michelin":{"edition":"2026"},"overture_release":"2026-09-23.1",
         "regions":[{"id":"la","name":"Los Angeles","file":"places-la.json","counties":["Los Angeles County"],"count":6,"count_restaurants":5},
                    {"id":"bay","name":"Bay Area","file":"places-bay.json","counties":["San Francisco"],"count":3,"count_restaurants":3}]}
        """
        let la = """
        {"region":"la","cities":["Los Angeles","Signal Hill","Glendale","East Los Angeles"],"places":[
          {"id":"a","n":"Guisados","c":0,"cu":0,"t":2,"s":1,"hc":1,"g":1,"a":"2100 E Cesar E Chavez Ave","z":"90033","la":34.0466,"lo":-118.2174,"ct":0,"di":"tinga, chicharrón","in":{"j":0,"r":0,"s":96,"d":"2026-08-01","n":3,"b":0}},
          {"id":"b","n":"Taquería El Sol","c":3,"cu":0,"t":0,"s":1,"a":"4400 Whittier Blvd","la":34.0233,"lo":-118.1720,"ct":0},
          {"id":"c","n":"In-N-Out Burger","c":1,"cu":2,"t":2,"s":2,"b":0,"ch":296,"a":"799 E Spring St","la":33.81,"lo":-118.18,"ct":0,"in":{"j":0,"s":94,"d":"2026-04-08","n":2,"b":0}},
          {"id":"d","n":"Corner Bar","c":2,"cu":3,"t":2,"s":0,"a":"100 N Brand Blvd","la":34.15,"lo":-118.25,"ct":0,"liq":3,"in":{"j":0,"r":1,"s":84,"d":"2026-05-02","n":4,"b":2}},
          {"id":"e","n":"Gas Mart Grill","c":0,"cu":4,"t":1,"s":1,"v":1,"la":34.05,"lo":-118.25,"ct":0},
          {"id":"f","n":"Providence","c":0,"cu":4,"t":2,"s":1,"a":"5955 Melrose Ave","la":34.0836,"lo":-118.3302,"ct":0,"h":2,"mi":5,"gs":1,"ip":95.2,"jbf":"Outstanding Hospitality 2026: winner"}
        ]}
        """
        let bay = """
        {"region":"bay","cities":["San Francisco","Millbrae"],"places":[
          {"id":"g","n":"La Taqueria","c":0,"cu":0,"t":2,"s":1,"hc":1,"g":3,"h":1,"ip":60,"jbf":"America's Classics 2017","a":"2889 Mission St","la":37.7509,"lo":-122.4181,"ct":1,"f":1973,"in":{"j":1,"r":0,"d":"2026-06-01","n":2,"b":0}},
          {"id":"h","n":"Dim Sum House","c":0,"cu":1,"t":1,"s":1,"hc":1,"g":8,"a":"1 San Pablo Ave","la":37.78,"lo":-122.41,"ct":1,"in":{"j":1,"r":2,"d":"2026-09-10","n":3,"b":2}},
          {"id":"i","n":"Golden Dragon","c":1,"cu":1,"t":0,"s":1,"a":"500 Broadway","la":37.6,"lo":-122.39,"ct":1}
        ]}
        """
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("ca-data-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try index.data(using: .utf8)!.write(to: dir.appendingPathComponent("index.json"))
        try la.data(using: .utf8)!.write(to: dir.appendingPathComponent("places-la.json"))
        try bay.data(using: .utf8)!.write(to: dir.appendingPathComponent("places-bay.json"))
        let model = AppModel(defaults: UserDefaults(suiteName: "test-\(UUID().uuidString)")!)
        await model.load(from: dir)
        XCTAssertTrue(model.isLoaded, model.loadError ?? "")
        return model
    }

    func testDecodesEveryRegionAndHidesNonRestaurants() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.places.count, 9)
        XCTAssertEqual(Set(m.places.map(\.region)), ["la", "bay"])
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.name == "Gas Mart Grill" }, "non-restaurants are hidden unless asked for")
        m.filters.includeNonRestaurants = true
        XCTAssertTrue(m.list(.all, sort: .name, search: "", here: nil).contains { $0.name == "Gas Mart Grill" })
    }

    func testGuidesListOnlyHandCheckedPlaces() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(Set(m.list(.taquerias, sort: .name, search: "", here: nil).map(\.id)), ["a", "g"])
        XCTAssertFalse(m.list(.taquerias, sort: .name, search: "", here: nil).contains { $0.id == "b" },
                       "a listing merely named \u{201C}Taquería\u{201D} stays out of the checked guide")
        XCTAssertEqual(m.list(.all, sort: .name, search: "el sol", here: nil).map(\.id), ["b"], "but it's still in the directory")
        XCTAssertEqual(m.list(.burritos, sort: .name, search: "", here: nil).map(\.id), ["g"])
        XCTAssertEqual(m.list(.dimSum, sort: .name, search: "", here: nil).map(\.id), ["h"])
        XCTAssertEqual(Set(m.list(.honors, sort: .honored, search: "", here: nil).map(\.id)), ["f", "g"])
        XCTAssertEqual(m.list(.honors, sort: .honored, search: "", here: nil).first?.id, "f", "three stars and a James Beard win rank first")
        XCTAssertEqual(m.list(.nearMe, sort: .nearest, search: "", here: nil), [], "near me needs a location")
        XCTAssertEqual(m.count(.taquerias), 2)
    }

    /// Counties score differently, so the Inspections guide shows one county at a time, ranked on its own official scale.
    func testInspectionsStayWithinOneCounty() async throws {
        let m = try await sampleModel()
        m.setInspectionJurisdiction(0)
        XCTAssertEqual(m.list(.inspections, sort: .bestResult, search: "", here: nil).map(\.id), ["a", "c", "d"],
                       "A before the score-only no-card city before B; LA County only")
        XCTAssertEqual(m.list(.inspections, sort: .worstResult, search: "", here: nil).first?.id, "d")
        m.setInspectionJurisdiction(1)
        XCTAssertEqual(m.list(.inspections, sort: .bestResult, search: "", here: nil).map(\.id), ["g", "h"], "San Francisco only: Pass, then Closure")
        let signalHill = m.place(id: "c")!
        XCTAssertNil(signalHill.inspection?.r, "Signal Hill never adopted grade cards: the score is shown, not a letter")
        XCTAssertEqual(signalHill.inspection?.s, 94)
    }

    func testNearestSort() async throws {
        let m = try await sampleModel()
        let downtown = CLLocation(latitude: 34.0522, longitude: -118.2437)
        let near = m.list(.nearMe, sort: .nearest, search: "", here: downtown)
        XCTAssertEqual(near.first?.id, "a", "Guisados in Boyle Heights is closest to downtown LA")
        XCTAssertEqual(near.last?.region, "bay")
    }

    func testSearchWordStartsAccentsTownsAndStreets() async throws {
        let m = try await sampleModel()
        func ids(_ q: String) -> [String] { m.list(.all, sort: .name, search: q, here: nil).map(\.id) }
        XCTAssertEqual(ids("guis"), ["a"])
        XCTAssertTrue(ids("isados").isEmpty, "matches the start of words only")
        XCTAssertEqual(ids("taqueria el sol"), ["b"], "no accent needed for Taquería")
        XCTAssertEqual(ids("chicharron"), ["a"], "a hand-checked place's dishes are searchable")
        XCTAssertEqual(ids("east cesar e chavez avenue"), ["a"], "east/avenue match the abbreviated address")
        XCTAssertEqual(ids("millbrae"), ["i"])
        // "san francisco" is a town, but "san pablo ave" is a street
        XCTAssertEqual(Set(ids("san francisco")), ["g", "h"])
        XCTAssertEqual(ids("san pablo ave"), ["h"])
        XCTAssertEqual(ids("san francisco dim sum"), ["h"], "a guide phrase plus a town")
        XCTAssertEqual(ids("🌮"), [], "nothing searchable typed means no results, not everything")
        XCTAssertEqual(ids("!!! ?"), [])
    }

    func testFiltersRegionsAndSavedPlaces() async throws {
        let m = try await sampleModel()
        m.filters.hideChains = true
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.name == "In-N-Out Burger" })
        m.filters = Filters(confirmedOnly: true)
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.id == "b" }, "single listings drop out")
        m.filters = Filters(region: "bay")
        XCTAssertEqual(Set(m.list(.all, sort: .name, search: "", here: nil).map(\.id)), ["g", "h", "i"])
        m.filters = Filters()
        let p = m.place(id: "g")!
        m.toggleSaved(p)
        XCTAssertEqual(m.savedPlaces.map(\.id), ["g"])
        m.toggleSaved(p)
        XCTAssertTrue(m.savedPlaces.isEmpty)
        XCTAssertEqual(m.place(id: "d")?.liquorLabel, "Full bar")
        XCTAssertNil(m.place(id: "a")?.liquorLabel, "no license matched is unknown, not \u{201C}no\u{201D}")
    }

    func testMatchRatesAndTiers() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.matchRate(for: m.place(id: "h")!), "73–86%")
        XCTAssertEqual(m.matchRate(for: m.place(id: "i")!), "44–48%")
        XCTAssertNil(m.matchRate(for: m.place(id: "a")!), "official places don't cite a listing rate")
        XCTAssertEqual(m.place(id: "a")!.tier, .official)
    }

    func testListCacheFollowsFiltersAndSearch() async throws {
        let m = try await sampleModel()
        let all = m.list(.all, sort: .name, search: "", here: nil)
        XCTAssertTrue(all.contains { $0.name == "In-N-Out Burger" })
        m.filters.hideChains = true
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.name == "In-N-Out Burger" }, "a filter change isn't served from the cache")
        m.filters = Filters()
        XCTAssertEqual(m.list(.all, sort: .name, search: "", here: nil).map(\.id), all.map(\.id))
        XCTAssertEqual(m.list(.all, sort: .name, search: "guisados", here: nil).map(\.id), ["a"])
    }

    func testNearMeIsntASearchWord() {
        let q = Search.parse("dim sum near me", towns: ["menlo park": "Menlo Park"])
        XCTAssertEqual(q.tag, .dimSum)
        XCTAssertNil(q.town)
        XCTAssertTrue(q.tokens.isEmpty, "\"me\" mustn't match Menlo Park or Mexican places")
    }

    func testOutsideCalifornia() {
        XCTAssertTrue(LocationService.inCalifornia(CLLocationCoordinate2D(latitude: 34.05, longitude: -118.24)), "Los Angeles")
        XCTAssertTrue(LocationService.inCalifornia(CLLocationCoordinate2D(latitude: 37.77, longitude: -122.42)), "San Francisco")
        XCTAssertTrue(LocationService.inCalifornia(CLLocationCoordinate2D(latitude: 41.75, longitude: -124.2)), "Crescent City")
        XCTAssertTrue(LocationService.inCalifornia(CLLocationCoordinate2D(latitude: 32.72, longitude: -117.16)), "San Diego")
        XCTAssertFalse(LocationService.inCalifornia(CLLocationCoordinate2D(latitude: 39.53, longitude: -119.81)), "Reno is in the state's box but not the state")
        XCTAssertFalse(LocationService.inCalifornia(CLLocationCoordinate2D(latitude: 36.17, longitude: -115.14)), "Las Vegas")
        XCTAssertFalse(LocationService.inCalifornia(CLLocationCoordinate2D(latitude: 32.53, longitude: -117.02)), "Tijuana")
    }

    /// The one-pass normalize must agree with the regex version it replaced, on tricky strings and every bundled name and address.
    func testNormalizeMatchesTheRegexVersion() async throws {
        func reference(_ s: String) -> String {
            var t = s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .init(identifier: "en_US")).lowercased()
            t = t.replacingOccurrences(of: #"\b([a-z0-9])\s*&\s*([a-z0-9])\b"#, with: "$1$2", options: .regularExpression)
            t = t.replacingOccurrences(of: "&", with: " and ")
            t = t.replacingOccurrences(of: #"['’`]"#, with: "", options: .regularExpression)
            t = t.replacingOccurrences(of: #"[^\p{L}\p{N}]+"#, with: " ", options: .regularExpression)
            return t.trimmingCharacters(in: .whitespaces)
        }
        for s in ["Taquería El Sol", "Phở Hòa", "In-N-Out Burger", "Philippe's", "Café Händel", "Joe`s", "A&W", "½ Price",
                  "2100 E Cesar E Chavez Ave", "🌮 Tacos", "Ⅻ Club", "", "---", "Nanbantei of Tokyo 南蛮亭"] {
            XCTAssertEqual(Search.normalize(s), reference(s), s)
        }
    }

    /// The real bundled data decodes, holds what the app promises and ships nothing it may not.
    func testBundledData() async throws {
        let m = AppModel(defaults: UserDefaults(suiteName: "bundle-\(UUID().uuidString)")!)
        let t0 = Date()
        await m.load()
        print("bundled data loaded in \(String(format: "%.2f", Date().timeIntervalSince(t0))) s on \(ProcessInfo.processInfo.activeProcessorCount) cores")
        XCTAssertTrue(m.isLoaded, m.loadError ?? "")
        XCTAssertGreaterThan(m.restaurantCount, 80_000)
        XCTAssertEqual(m.regions.count, 9)
        XCTAssertEqual(Set(m.places.map(\.id)).count, m.places.count, "ids are unique")
        XCTAssertTrue(m.places.allSatisfy { $0.coordinate != nil }, "every place is on the map")
        XCTAssertEqual(Set(m.jurisdictions.map(\.id)), ["lac", "sf", "sac"], "Santa Clara's inspections stay out of the app (no license stated)")
        XCTAssertGreaterThan(m.count(.inspections), 20_000)
        XCTAssertGreaterThan(m.count(.honors), 200)
        XCTAssertTrue(m.places.contains { $0.name == "The French Laundry" && $0.michelin == 5 })
        // a hand check names its guide, or it's an old place whose year isn't tied to this address (shown as "Founded", not in Oldest Places)
        XCTAssertTrue(m.places.filter(\.handChecked).allSatisfy { !$0.guides.isEmpty || $0.isHonored || $0.brandFounded != nil },
                      "a hand check always names its guide")
        XCTAssertTrue(m.list(.oldest, sort: .oldest, search: "", here: nil).allSatisfy { ($0.founded ?? 9999) <= 1960 },
                      "Oldest Places: open at this address since 1960 or earlier")
        XCTAssertFalse(m.places.contains { $0.name.range(of: #"gentlem[ae]n'?s club|strip club|exotic dancer|spearmint rhino"#, options: [.regularExpression, .caseInsensitive]) != nil },
                       "adult clubs aren't restaurants")
        XCTAssertFalse(m.places.contains { ($0.website?.absoluteString ?? "").range(
            of: #"yelp\.com|business\.site|google\.com|groupon\.com|yellowpages\.com"#, options: .regularExpression) != nil },
                       "directory links were checked out")
        // no Google-derived field may ship: the region files carry only these keys
        let allowed: Set<String> = ["id", "n", "c", "cu", "t", "s", "a", "z", "la", "lo", "ct", "b", "ch", "v", "bar", "g", "hc", "liq", "h", "mi", "gs",
                                    "ip", "jbf", "f", "on", "bf", "note", "di", "w", "ph", "in"]
        let folder = try XCTUnwrap(AppModel.bundledData)
        for r in m.regions {
            let obj = try JSONSerialization.jsonObject(with: Data(contentsOf: folder.appendingPathComponent(r.file))) as! [String: Any]
            for p in obj["places"] as! [[String: Any]] {
                let extra = Set(p.keys).subtracting(allowed)
                XCTAssertTrue(extra.isEmpty, "unexpected keys \(extra) in \(r.file)")
                if !extra.isEmpty { break }
            }
        }
    }
}

/// pipeline/website_blocklist.json (hacked, taken-over, expired or another business's sites, confirmed by hand in the link sweeps):
/// no link on it may ship in any field of any JSON file the app bundles. The 2026-10-19 QA found the export had only filtered the
/// website field, or nothing, so hijacked links were still in the bundle. Read from the repo, so a new entry needs no code change.
final class LinkBlocklistTests: XCTestCase {
    func testNoBlocklistedLinkInBundledData() throws {
        let entries = try LinkBlocklist.entries()
        XCTAssertFalse(entries.isEmpty, "the blocklist is missing or empty")
        let files = LinkBlocklist.bundledJSON()
        XCTAssertFalse(files.isEmpty, "no bundled JSON found")
        var hits: [String] = []
        for url in files {
            let text = try String(contentsOf: url, encoding: .utf8)
            hits += LinkBlocklist.hits(in: text, entries).map { "\(url.lastPathComponent): \($0)" }
        }
        XCTAssertEqual(hits, [], "blocklisted links in the app's bundled data")
    }

    /// The guard fires on a copy of the bundled data broken three ways: a blocklisted domain, its subdomain, and a "url" entry.
    func testBlocklistGuardCatchesABrokenCopy() throws {
        let entries = try LinkBlocklist.entries()
        let file = try XCTUnwrap(LinkBlocklist.bundledJSON().max { (try? $0.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0) ?? 0 < (try? $1.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0) ?? 0 })
        let text = try String(contentsOf: file, encoding: .utf8)
        let domain = try XCTUnwrap(entries.first { ($0["match"] as? String ?? "domain") == "domain" }?["domain"] as? String)
        let fake: [[String: Any]] = entries + [["match": "url", "url": "https://example.org/hacked-page"]]
        let before = LinkBlocklist.hits(in: text, fake).count
        let broken = text + "{\"w\":\"https://www.\(domain)/menu\"}{\"src\":\"http://shop.\(domain)/\"}{\"w\":\"https://example.org/hacked-page/\"}"
        XCTAssertEqual(LinkBlocklist.hits(in: broken, fake).count, before + 3, "a domain, a subdomain and a url entry are all caught")
        XCTAssertEqual(LinkBlocklist.hits(in: "{\"w\":\"https://not\(domain)/\"}", entries), [], "a host that only ends with the domain's letters isn't it")
    }
}

enum LinkBlocklist {
    static func entries() throws -> [[String: Any]] {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("pipeline/website_blocklist.json")
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [[String: Any]])
    }

    /// every .json file in the app bundle, subfolders included
    static func bundledJSON() -> [URL] {
        let root = Bundle.main.bundleURL
        let all = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil)?.allObjects as? [URL] ?? []
        return all.filter { $0.pathExtension == "json" && !$0.path.contains("/PlugIns/") }
    }

    private static func host(_ u: URLComponents) -> String {
        var h = (u.host ?? "").lowercased()
        if h.hasSuffix(".") { h.removeLast() }
        return h.hasPrefix("www.") ? String(h.dropFirst(4)) : h
    }

    private static func trimmedPath(_ p: String) -> String { p.hasSuffix("/") ? String(p.dropLast()) : p }

    /// the links in a JSON text that an entry covers: a "domain" entry its domain and subdomains, a "url" entry that page only
    static func hits(in text: String, _ entries: [[String: Any]]) -> [String] {
        let t = text.replacingOccurrences(of: "\\/", with: "/")
        let rx = try! NSRegularExpression(pattern: #"https?://[^"\s\\]+"#, options: [.caseInsensitive])
        return rx.matches(in: t, range: NSRange(t.startIndex..., in: t)).compactMap { m -> String? in
            let s = String(t[Range(m.range, in: t)!])
            guard let u = URLComponents(string: s) else { return nil }
            let h = host(u)
            for e in entries {
                if (e["match"] as? String ?? "domain") == "url" {
                    guard let v = URLComponents(string: e["url"] as? String ?? "") else { continue }
                    if !h.isEmpty && h == host(v) && trimmedPath(u.path) == trimmedPath(v.path) { return s }
                } else {
                    var d = (e["domain"] as? String ?? "").lowercased()
                    if let r = d.range(of: "://") { d = String(d[r.upperBound...]) }
                    d = String(d.split(separator: "/").first ?? "")
                    if d.hasPrefix("www.") { d = String(d.dropFirst(4)) }
                    if !d.isEmpty && (h == d || h.hasSuffix("." + d)) { return s }
                }
            }
            return nil
        }
    }
}

/// QA 2026-10-19, P1 #13: outbound links ship without tracking tags (ref=google, referrer=google_food_ordering, cn_channel, utm_* …).
/// pipeline/tracking_params.py strips them in the export; these are the same rules.
final class TrackingParamTests: XCTestCase {
    func testNoTrackingParametersInBundledLinks() throws {
        let files = TrackingParams.bundledJSON()
        XCTAssertFalse(files.isEmpty, "no bundled JSON found")
        var hits: [String] = []
        for url in files {
            let text = try String(contentsOf: url, encoding: .utf8)
            hits += TrackingParams.tracked(in: text).map { "\(url.lastPathComponent): \($0)" }
        }
        XCTAssertEqual(hits, [], "links with tracking parameters in the app's bundled data")
    }

    /// The guard fires on a broken copy (four kinds of tracking tag, one in escaped JSON) and leaves a store's own parameters alone.
    func testTrackingGuardCatchesABrokenCopy() {
        let broken = #"[{"w":"https:\/\/places.example.com\/menu?ref=google"},{"w":"https://a.example/?utm_source=gmb&store=4"},"#
            + #"{"w":"https://b.example/x?referrer=google_food_ordering"},{"w":"https://c.example/order/1?cn_channel=cn_google"}]"#
        XCTAssertEqual(TrackingParams.tracked(in: broken).count, 4)
        let clean = #"[{"w":"https://order.example.com/menu?restaurantId=51&location=7"},{"w":"https://shop.example.com/?cid=12&ref=gs"}]"#
        XCTAssertEqual(TrackingParams.tracked(in: clean), [])
    }
}

enum TrackingParams {
    /// tracking by name, whatever the value
    static let keys = try! NSRegularExpression(pattern: #"^(?:utm[_-].*|gclid|gbraid|wbraid|dclid|fbclid|msclkid|mc_cid|mc_eid|_ga|_gl|igsh|"#
        + #"igshid|mibextid|srsltid|cn_channel|y_source|rwg_token|olonwp|ost_redirect_attribution|cmpid|yext_?.*)$"#, options: [.caseInsensitive])
    /// tracking only with these values
    static let values: [String: String] = ["ref": #"^(?:google|gmb|gbp|yext|bookmarks)\b"#, "referrer": "^google",
                                           "source": #"^(?:google|gmb|gbp|yext)\b"#, "cid": "^RF:YXT", "cmp": "^OKC-"]

    /// every .json file in the app bundle, subfolders included
    static func bundledJSON() -> [URL] {
        let all = FileManager.default.enumerator(at: Bundle.main.bundleURL, includingPropertiesForKeys: nil)?.allObjects as? [URL] ?? []
        return all.filter { $0.pathExtension == "json" && !$0.path.contains("/PlugIns/") }
    }

    static func isTracking(_ key: String, _ value: String) -> Bool {
        let k = key.trimmingCharacters(in: .whitespaces)
        if keys.firstMatch(in: k, range: NSRange(k.startIndex..., in: k)) != nil { return true }
        guard let pattern = values[k.lowercased()] else { return false }
        return value.trimmingCharacters(in: .whitespaces).range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil
    }

    /// links in a JSON text whose query carries a tracking parameter
    static func tracked(in text: String) -> [String] {
        let t = text.replacingOccurrences(of: "\\/", with: "/")
        let rx = try! NSRegularExpression(pattern: #"https?://[^\s"'<>\\]+"#)
        return rx.matches(in: t, range: NSRange(t.startIndex..., in: t)).compactMap { m -> String? in
            let s = String(t[Range(m.range, in: t)!])
            guard let q = s.split(separator: "?", maxSplits: 1).dropFirst().first else { return nil }
            let query = q.split(separator: "#", maxSplits: 1, omittingEmptySubsequences: false).first ?? ""
            for part in query.split(separator: "&") {
                let kv = part.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false)
                let k = String(kv[0]).replacingOccurrences(of: "+", with: " ").removingPercentEncoding ?? String(kv[0])
                let v = kv.count > 1 ? (String(kv[1]).replacingOccurrences(of: "+", with: " ").removingPercentEncoding ?? String(kv[1])) : ""
                if isTracking(k, v) { return s }
            }
            return nil
        }
    }
}

/// QA 2026-10-19, P1 #7: no employer cafeteria, contract caterer's unit, school dining room or legal-entity name is shown as a restaurant.
/// pipeline/private_dining.py hides the first three with the non-restaurants ("v": 1) and fixes or drops entity names; hand-checked and
/// honored places are exempt. These are the same patterns.
final class PrivateDiningTests: XCTestCase {
    func testNoPrivateDiningOrEntityNameShown() throws {
        var shown: [[String: Any]] = []
        for url in PrivateDining.bundledJSON() {
            shown += PrivateDining.shownPlaces(in: try Data(contentsOf: url))
        }
        XCTAssertGreaterThan(shown.count, 1000, "the bundled places weren't found")
        XCTAssertEqual(PrivateDining.hits(shown), [], "private dining or legal-entity names shown as restaurants")
    }

    /// The guard fires on a broken copy (one of each kind shown) and spares hidden, hand-checked and look-alike places.
    func testPrivateDiningGuardCatchesABrokenCopy() throws {
        let json = #"{"places":[{"n":"Google Cafe Nuage"},{"n":"Bon Appétit at Whitman"},{"n":"Basis Independent Bellevue"},"#
            + #"{"n":"One Market Restaurant Partners Lp"},{"n":"Joban & Supreet Enterprises"},{"n":"Boeing Co","v":1},{"n":"Ba @ Google Hub","hc":1},"#
            + #"{"n":"Big Apple Pizza N Grill"},{"n":"University of Beer"},{"n":"Cisco's"},{"n":"Amazonia Cafe"},{"n":"Partners Deli and Arcade"}]}"#
        let shown = PrivateDining.shownPlaces(in: Data(json.utf8))
        XCTAssertEqual(shown.count, 10)
        XCTAssertEqual(PrivateDining.hits(shown), ["Google Cafe Nuage", "Bon Appétit at Whitman", "Basis Independent Bellevue",
                                                  "One Market Restaurant Partners Lp", "Joban & Supreet Enterprises"])
    }
}

enum PrivateDining {
    static let rules = [#"^(?:GOOGLE|AMAZON|MICROSOFT|BOEING)\b|^(?:GOOGLE|AMAZON|MICROSOFT|BOEING|ALASKA AIRLINES|NINTENDO|T MOBILE|EXPEDIA|F5(?: NETWORKS)?|PACCAR|KENWORTH|ZILLOW|META|FACEBOOK|SALESFORCE|TABLEAU|WEYERHAEUSER|GATES FOUNDATION|REI CORPORATE|SNAP|APPLE|CISCO|ORACLE|NETFLIX|LINKEDIN|INTEL|NVIDIA|ADOBE|GENENTECH|ROCKETDYNE|LOREAL|TESLA|UBER|AIRBNB|VMWARE|INTUIT|PAYPAL|EBAY|YAHOO|DROPBOX|PINTEREST|SERVICENOW|WORKDAY|QUALCOMM|AUTODESK|ELECTRONIC ARTS)$|^(?:GOOGLE|AMAZON|MICROSOFT|BOEING|ALASKA AIRLINES|NINTENDO|T MOBILE|EXPEDIA|F5(?: NETWORKS)?|PACCAR|KENWORTH|ZILLOW|META|FACEBOOK|SALESFORCE|TABLEAU|WEYERHAEUSER|GATES FOUNDATION|REI CORPORATE|SNAP|APPLE|CISCO|ORACLE|NETFLIX|LINKEDIN|INTEL|NVIDIA|ADOBE|GENENTECH|ROCKETDYNE|LOREAL|TESLA|UBER|AIRBNB|VMWARE|INTUIT|PAYPAL|EBAY|YAHOO|DROPBOX|PINTEREST|SERVICENOW|WORKDAY|QUALCOMM|AUTODESK|ELECTRONIC ARTS) (?:CAFES?|CAFETERIA|COFFEE|BARISTA|KITCHEN|MARKET|DINING|BLOCK|BLDG|BUILDING|CAMPUS|HQ|HEADQUARTERS|RETAIL|CO|COMPANY|CORP|CORPORATION|INC|PARK CAFE|DAY 1|BOARD ROOM)\b|^(?:GOOGLE|AMAZON|MICROSOFT|BOEING|ALASKA AIRLINES|NINTENDO|T MOBILE|EXPEDIA|F5(?: NETWORKS)?|PACCAR|KENWORTH|ZILLOW|META|FACEBOOK|SALESFORCE|TABLEAU|WEYERHAEUSER|GATES FOUNDATION|REI CORPORATE|SNAP|APPLE|CISCO|ORACLE|NETFLIX|LINKEDIN|INTEL|NVIDIA|ADOBE|GENENTECH|ROCKETDYNE|LOREAL|TESLA|UBER|AIRBNB|VMWARE|INTUIT|PAYPAL|EBAY|YAHOO|DROPBOX|PINTEREST|SERVICENOW|WORKDAY|QUALCOMM|AUTODESK|ELECTRONIC ARTS) @|@ (?:GOOGLE|AMAZON|MICROSOFT|BOEING|ALASKA AIRLINES|NINTENDO|T MOBILE|EXPEDIA|F5(?: NETWORKS)?|PACCAR|KENWORTH|ZILLOW|META|FACEBOOK|SALESFORCE|TABLEAU|WEYERHAEUSER|GATES FOUNDATION|REI CORPORATE|SNAP|APPLE|CISCO|ORACLE|NETFLIX|LINKEDIN|INTEL|NVIDIA|ADOBE|GENENTECH|ROCKETDYNE|LOREAL|TESLA|UBER|AIRBNB|VMWARE|INTUIT|PAYPAL|EBAY|YAHOO|DROPBOX|PINTEREST|SERVICENOW|WORKDAY|QUALCOMM|AUTODESK|ELECTRONIC ARTS)\b|\bAT (?:GOOGLE|AMAZON|MICROSOFT|BOEING|NINTENDO|SALESFORCE|GENENTECH|NETFLIX|LINKEDIN)\b"#, #"\bBON APPETIT\b|\bGUCKENHEIMER\b|\bSODEXO\w*|\bCULINART\b|\bFLIK\b|\bRESTAURANT ASSOCIATES\b|\bCOMPASS (?:ONE|TWO)\b|\bCANTEEN VENDING\b|\bEUREST\b|\bARAMARK\b|^BA @"#, #"\b(?:MONTESSORI|PRESCHOOL|PRE SCHOOL|BASIS INDEPENDENT|CHILDRENS ACADEMY|ADULT SCHOOL|LAW SCHOOL|HIGH SCHOOL|MIDDLE SCHOOL|ELEMENTARY|CAMPUS DINING|STUDENT CENTER|STUDENT UNION)\b|@ (?:THE )?(?:[A-Z0-9]+ ){0,5}(?:UNIVERSITY|COLLEGE|SCHOOL|ACADEMY|PREPARATORY|CAMPUS|U)\b(?! (?:AVE|AVENUE|AREA|ST|STREET|BLVD|DR|DRIVE|RD|ROAD|WAY|PARK|HEIGHTS|SQUARE|VILLAGE|PLAZA|CENTER|TOWN|DISTRICT|HILL|HOUSE))|\bAT (?:THE )?(?:[A-Z0-9]+ ){0,5}(?:UNIVERSITY|COLLEGE|SCHOOL|ACADEMY|PREPARATORY)\b(?! (?:AVE|AVENUE|AREA|ST|STREET|BLVD|DR|DRIVE|RD|ROAD|WAY|PARK|HEIGHTS|SQUARE|VILLAGE|PLAZA|CENTER|TOWN|DISTRICT|HILL|HOUSE))"#].map { try! NSRegularExpression(pattern: $0) }
    static let entityTail = try! NSRegularExpression(pattern: #"(?:[,\s]+(?:L\.?\s?P\.?|LTD\.?|LLC\.?|L\.L\.C\.?|LLP\.?|L\.L\.P\.?|INC\.?|INCORPOR\w*|CORP\.?|CORPORATION))+\s*$"#, options: [.caseInsensitive])
    static let holder = try! NSRegularExpression(pattern: #"(?:^|\s)(?:PARTNERS|PARTNERSHIP|HOLDINGS?|ENTERPRISES?|VENTURES|OWNER|INVESTMENTS|PROPERTIES)\s*$"#, options: [.caseInsensitive])

    /// private_dining.fold(): upper-case ASCII words, apostrophes dropped, "@" and spaced dashes as " @ "
    static func fold(_ name: String) -> String {
        var s = name.folding(options: [.diacriticInsensitive], locale: Locale(identifier: "en_US")).uppercased()
        s = s.replacingOccurrences(of: "['\u{2019}`]", with: "", options: .regularExpression)
        s = s.replacingOccurrences(of: #"\s+[-\x{2013}\x{2014}]+\s+|\s*--\s*|@"#, with: " @ ", options: .regularExpression)
        s = s.replacingOccurrences(of: "&", with: " AND ")
        s = s.replacingOccurrences(of: "[^A-Z0-9@ ]+", with: " ", options: .regularExpression)
        return s.replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression).trimmingCharacters(in: .whitespaces)
    }

    static func matches(_ rx: NSRegularExpression, _ s: String) -> Bool {
        rx.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil
    }

    static func hits(_ places: [[String: Any]]) -> [String] {
        places.compactMap { p in
            guard let n = p["n"] as? String else { return nil }
            let f = fold(n)
            return rules.contains { matches($0, f) } || matches(entityTail, n) || matches(holder, n) ? n : nil
        }
    }

    /// places a reader sees as restaurants: not hidden with the non-restaurants, not hand-checked or honored (those are exempt)
    static func shownPlaces(in data: Data) -> [[String: Any]] {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let places = obj["places"] as? [[String: Any]] else { return [] }
        return places.filter { p in
            let flag = { (k: String) -> Bool in (p[k] as? NSNumber).map { $0.intValue != 0 } ?? (p[k] != nil) }
            return !flag("v") && !flag("hc") && !flag("h")
        }
    }

    static func bundledJSON() -> [URL] {
        let all = FileManager.default.enumerator(at: Bundle.main.bundleURL, includingPropertiesForKeys: nil)?.allObjects as? [URL] ?? []
        return all.filter { $0.pathExtension == "json" && !$0.path.contains("/PlugIns/") }
    }
}
