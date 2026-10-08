import Foundation
import Observation
import CoreLocation

/// The whole app's state: the bundled places, filters, saved places and what's selected.
@MainActor
@Observable
final class AppModel {
    private(set) var places: [Place] = []
    private(set) var isLoaded = false
    private(set) var loadError: String?
    private(set) var generated = ""
    private(set) var restaurantCount = 0
    private(set) var regions: [DataIndex.RegionFile] = []
    private(set) var jurisdictions: [InspectionJurisdiction] = []
    private(set) var calibration: [String: CalibrationArea] = [:]
    private(set) var overtureRelease = ""
    /// towns sorted by how many restaurants they have
    private(set) var towns: [(name: String, count: Int)] = []
    private(set) var cuisines: [(name: String, count: Int)] = []
    /// normalized town name -> display name ("mt shasta" -> "Mount Shasta")
    private(set) var townKeys: [String: String] = [:]

    var filters = Filters() { didSet { saveFilters() } }
    private(set) var saved: Set<String> = []
    /// the county the Inspections guide shows (index into jurisdictions); counties score differently, so one at a time
    var inspectionJurisdiction = 0

    // navigation (iPad sidebar / iPhone tabs)
    var selectedGuide: Guide?
    var selectedPlace: Place?
    var tab: Tab = .guides
    enum Tab: Hashable { case guides, map, saved, about }
    /// the iPhone guides stack: a guide, then a place
    var guidesPath: [Route] = []
    enum Route: Hashable { case guide(Guide), place(Place) }
    /// bumped by openGuide so the iPad sidebar follows even when the same guide is picked again
    private(set) var guideRequest = 0

    /// Open a guide from Home: pushes it on iPhone, selects it in the iPad sidebar.
    func openGuide(_ g: Guide) {
        tab = .guides
        selectedGuide = g
        guidesPath = [.guide(g)]
        guideRequest += 1
    }

    /// a fixed "you are here" for screenshots, so lists sort by distance without a permission prompt
    var screenshotLocation: CLLocation?

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        saved = Set(defaults.stringArray(forKey: "saved") ?? [])
        if let data = defaults.data(forKey: "filters"), let f = try? JSONDecoder().decode(Filters.self, from: data) { filters = f }
        inspectionJurisdiction = defaults.integer(forKey: "inspectionJurisdiction")
    }

    /// A cold launch from Spotlight asks for the data twice (the app's .task and the search continuation); both wait on one decode.
    private var loading: Task<Void, Never>?

    nonisolated static var bundledData: URL? { Bundle.main.url(forResource: "Data", withExtension: nil) }

    func load(from folder: URL? = AppModel.bundledData) async {
        guard !isLoaded else { return }
        if let loading { await loading.value; return }
        let task = Task { await decode(from: folder) }
        loading = task
        await task.value
    }

    /// The index first, then every region file at once on background threads (about 100,000 places in nine files).
    private func decode(from folder: URL?) async {
        guard let folder else { loadError = "The restaurant data is missing from the app."; return }
        do {
            let index = try await Task.detached(priority: .userInitiated) {
                try JSONDecoder().decode(DataIndex.self, from: Data(contentsOf: folder.appendingPathComponent("index.json")))
            }.value
            let parts = try await withThrowingTaskGroup(of: (Int, [Place]).self) { group in
                for (n, r) in index.regions.enumerated() {
                    group.addTask(priority: .userInitiated) {
                        let data = try Data(contentsOf: folder.appendingPathComponent(r.file))
                        let region = try JSONDecoder().decode(RegionData.self, from: data)
                        return (n, region.places.map { Place($0, region: region, index: index) })
                    }
                }
                var out: [(Int, [Place])] = []
                for try await part in group { out.append(part) }
                return out.sorted { $0.0 < $1.0 }.flatMap(\.1)
            }
            apply(index: index, places: parts)
        } catch {
            loadError = "The restaurant data couldn't be read (\(error.localizedDescription))."
        }
    }

    func apply(index: DataIndex, places: [Place]) {
        self.places = places
        generated = index.generated
        restaurantCount = index.count_restaurants
        regions = index.regions
        jurisdictions = index.jurs
        calibration = index.calibration
        overtureRelease = index.overture_release
        if inspectionJurisdiction >= jurisdictions.count { inspectionJurisdiction = 0 }
        var tc: [String: Int] = [:], cc: [String: Int] = [:]
        for p in places where !p.isVenue {
            if let c = p.city { tc[c, default: 0] += 1 }
            cc[p.cuisine, default: 0] += 1
        }
        towns = tc.map { ($0.key, $0.value) }.sorted { $0.count != $1.count ? $0.count > $1.count : $0.name < $1.name }
        cuisines = cc.map { ($0.key, $0.value) }.sorted { $0.count != $1.count ? $0.count > $1.count : $0.name < $1.name }
        var keys: [String: String] = [:]
        for (name, _) in towns {   // biggest town wins a shared spelling
            let k = Search.normalizeAddress(name)
            if keys[k] == nil { keys[k] = name }
        }
        townKeys = keys
        if let t = filters.town, tc[t] == nil { filters.town = nil }
        if let c = filters.cuisine, cc[c] == nil { filters.cuisine = nil }
        if let r = filters.region, !regions.contains(where: { $0.id == r }) { filters.region = nil }
        byID = Dictionary(places.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        isLoaded = true
    }

    @ObservationIgnored private var byID: [String: Place] = [:]
    func place(id: String) -> Place? { byID[id] }

    func setInspectionJurisdiction(_ j: Int) {
        inspectionJurisdiction = j
        defaults.set(j, forKey: "inspectionJurisdiction")
    }

    /// The last list asked for. A list view's body runs on every change (an iPad row tap re-renders it), so the same
    /// guide, sort, search, filters and location (to ~100 m) reuse the result instead of filtering 100,000 places again.
    private struct ListKey: Equatable {
        let guide: Guide, sort: SortOrder, search: String, filters: Filters, count: Int, lat: Int?, lon: Int?, jurisdiction: Int
    }
    @ObservationIgnored private var lastList: (key: ListKey, places: [Place])?

    func list(_ guide: Guide, sort: SortOrder, search: String, here: CLLocation?) -> [Place] {
        // reading filters and places here keeps SwiftUI observing them even when the cached list is returned
        let key = ListKey(guide: guide, sort: sort, search: search, filters: filters, count: places.count,
                          lat: here.map { Int(($0.coordinate.latitude * 1000).rounded()) },
                          lon: here.map { Int(($0.coordinate.longitude * 1000).rounded()) },
                          jurisdiction: guide == .inspections ? inspectionJurisdiction : -1)
        if let lastList, lastList.key == key { return lastList.places }
        let out = makeList(guide, sort: sort, search: search, here: here)
        lastList = (key, out)
        return out
    }

    private func makeList(_ guide: Guide, sort: SortOrder, search: String, here: CLLocation?) -> [Place] {
        let q = Search.parse(search, towns: townKeys)
        // typed something, but nothing searchable ("🍕", "!!!"): show nothing rather than everything
        if q.isEmpty && !search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return [] }
        if guide == .nearMe && here == nil { return [] }
        var f = filters
        if guide == .honors || guide.isHandChecked { f.includeNonRestaurants = true }   // a starred hotel dining room is shown
        let j = guide == .inspections ? inspectionJurisdiction : nil
        var out = places.filter { guide.includes($0, jurisdiction: j) && f.allows($0) && (q.isEmpty || Search.matches($0, q)) }
        out = Ranking.sort(out, by: sort, from: here)
        if !q.tokens.isEmpty && !guide.isRanked {   // name matches first when searching
            let named = out.filter { Search.nameMatches($0, q) }
            if !named.isEmpty && named.count < out.count {
                let ids = Set(named.map(\.id))
                out = named + out.filter { !ids.contains($0.id) }
            }
        }
        return out
    }

    func count(_ guide: Guide) -> Int {
        var f = filters
        if guide == .honors || guide.isHandChecked { f.includeNonRestaurants = true }   // as in list()
        return places.lazy.filter { guide.includes($0) && f.allows($0) }.count
    }

    // MARK: saved places

    func isSaved(_ p: Place) -> Bool { saved.contains(p.id) }

    func toggleSaved(_ p: Place) {
        if saved.contains(p.id) { saved.remove(p.id) } else { saved.insert(p.id) }
        defaults.set(Array(saved).sorted(), forKey: "saved")
    }

    var savedPlaces: [Place] { saved.compactMap { byID[$0] }.sorted { $0.nameText < $1.nameText } }

    /// A random place from a guide, never the one just shown.
    func randomPick(from guide: Guide, excluding last: String?) -> Place? {
        let pool = places.filter { guide.includes($0) && filters.allows($0) && $0.id != last }
        return pool.randomElement()
    }

    private func saveFilters() {
        if let data = try? JSONEncoder().encode(filters) { defaults.set(data, forKey: "filters") }
    }

    // MARK: honest labels

    /// "73–86%": how often a listing of this kind matched a permitted food business in LA County and San Diego County.
    func matchRate(for p: Place) -> String? {
        guard p.tier != .official else { return nil }   // on a county list or an ABC license: no listing caveat needed
        let group: String
        switch (p.source, p.tier) {
        case ("meta", .confirmed): group = "meta_high (>=0.95)"
        case ("meta", _): group = "meta_mid (0.90-0.95)"
        case ("AllThePlaces", _), ("DAC", _): group = "brand_feed"
        default: return nil
        }
        let v = ["lac", "sd"].compactMap { calibration[$0]?.groups[group]?.official }
        guard let lo = v.min(), let hi = v.max() else { return nil }
        let a = Int((lo * 100).rounded()), b = Int((hi * 100).rounded())
        return a == b ? "\(a)%" : "\(a)–\(b)%"
    }

    /// Inspection data dates, from the data itself (never hard-coded): "LA County through Sep 30, 2026".
    func jurisdiction(of p: Place) -> InspectionJurisdiction? {
        guard let j = p.inspection?.j, j < jurisdictions.count else { return nil }
        return jurisdictions[j]
    }
}
