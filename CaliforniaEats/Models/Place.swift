import Foundation
import CoreLocation

// MARK: - The bundled data (Resources/Data/index.json + places-<region>.json), written by pipeline/california.py with CA_APP=1

/// index.json: shared lookup tables, the region files, data dates and the calibration numbers.
struct DataIndex: Decodable {
    let generated: String
    let regions: [RegionFile]
    let cuisines: [String]
    let brands: [String]
    let sources: [String]
    let counties: [String]
    let liqt: [String]
    let jurs: [InspectionJurisdiction]
    let count_restaurants: Int
    let count_hc: Int
    let calibration: [String: CalibrationArea]
    let overture_release: String

    struct RegionFile: Decodable, Hashable {
        let id: String
        let name: String
        let file: String
        let counties: [String]
        let count: Int
        let count_restaurants: Int
    }
}

struct CalibrationArea: Decodable, Hashable {
    let groups: [String: CalibrationGroup]
    let coverage: Double?
}

struct CalibrationGroup: Decodable, Hashable {
    let n: Int
    let official: Double
}

/// A health department that publishes inspection results in bulk, and its official result scale (best first).
struct InspectionJurisdiction: Decodable, Hashable, Identifiable {
    let id: String          // lac, sf, sac
    let name: String        // "Los Angeles County"
    let agency: String
    let scale: [String]     // ["A", "B", "C"], ["Pass", "Conditional Pass", "Closure"], ["PASS", "CONDITIONAL PASS", "CLOSED"]
    let through: String     // inspections counted through this date
    let newest: String?
}

/// places-<region>.json
struct RegionData: Decodable {
    let region: String
    let cities: [String]
    let places: [PlaceRecord]
}

/// The official result at a place's latest inspection, as the county recorded it. Never a grade of ours.
struct InspectionRecord: Decodable, Hashable {
    let j: Int          // index into DataIndex.jurs
    let r: Int?         // index into that jurisdiction's scale; nil = score only (LA County cities without grade cards)
    let s: Int?         // the county's score, where it has one (LA County)
    let d: String       // date of the latest inspection
    let n: Int?         // inspections on record in the window
    let b: Int?         // of those, how many weren't a pass (LA: B or C; placards: yellow or red)
}

struct PlaceRecord: Decodable {
    let id: String
    let n: String
    let c: Int?
    let cu: Int
    let t: Int
    let s: Int
    let a: String?
    let z: String?
    let la: Double
    let lo: Double
    let ct: Int?
    let b: Int?
    let ch: Int?
    let v: Int?
    let bar: Int?
    let g: Int?
    let hc: Int?
    let liq: Int?
    let h: Int?
    let mi: Int?
    let gs: Int?
    let ip: Double?
    let jbf: String?
    let f: Int?
    let on: String?
    let bf: String?
    let note: String?
    let di: String?
    let w: String?
    let ph: String?
    let inspection: InspectionRecord?

    enum CodingKeys: String, CodingKey {
        case id, n, c, cu, t, s, a, z, la, lo, ct, b, ch, v, bar, g, hc, liq, h, mi, gs, ip, jbf, f, on, bf, note, di, w, ph
        case inspection = "in"
    }
}

// MARK: - The model the views use

/// The hand-checked guides a place is in (each bit means: confirmed open with a 2025–26 source and serving that).
struct GuideTags: OptionSet, Hashable {
    let rawValue: Int
    static let taqueria = GuideTags(rawValue: 1)
    static let burrito = GuideTags(rawValue: 2)
    static let fishTaco = GuideTags(rawValue: 4)
    static let dimSum = GuideTags(rawValue: 8)
    static let koreanBBQ = GuideTags(rawValue: 16)
    static let burgerStand = GuideTags(rawValue: 32)
    static let wineCountry = GuideTags(rawValue: 64)
    static let oldest = GuideTags(rawValue: 128)
}

/// How a place got on the list. The share that matched a permitted business comes from calibration.
enum Tier: Int, Comparable {
    case listing = 0        // one map listing
    case confirmed = 1      // a high-confidence Meta listing, or a hand-checked place
    case official = 2       // on a county food-facility list or an ABC liquor license

    static func < (a: Tier, b: Tier) -> Bool { a.rawValue < b.rawValue }

    var label: String {
        switch self {
        case .official: "On an official list"
        case .confirmed: "Confirmed listing"
        case .listing: "Listing only"
        }
    }
}

struct Place: Identifiable, Hashable {
    let id: String
    let name: String
    let address: String?
    let city: String?
    let zip: String?
    let coordinate: CLLocationCoordinate2D?
    let county: String?
    let region: String
    let cuisine: String
    let brand: String?
    let chainCount: Int
    let tier: Tier
    let source: String
    let isVenue: Bool
    let isBar: Bool
    let guides: GuideTags
    /// On our hand-checked list (data/research/app): confirmed open with a 2025–26 source.
    let handChecked: Bool
    /// 0 none, 1 beer, 2 beer & wine, 3 full bar (an on-sale ABC license matched)
    let liquor: Int
    /// James Beard bits: 1 America's Classic, 2 winner, 4 finalist, 8 semifinalist
    let honorFlags: Int
    /// MICHELIN Guide California 2026: 0 none, 1 Recommended, 2 Bib Gourmand, 3/4/5 one/two/three Stars
    let michelin: Int
    let greenStar: Bool
    let honorPoints: Double?
    let jamesBeard: String?
    let founded: Int?
    let openedNote: String?
    let brandFounded: String?
    let note: String?
    let dishes: String?
    let website: URL?
    let phone: String?
    let inspection: InspectionRecord?
    /// normalized text for search: name, town, zip, cuisine, brand, dishes, then the address with street words abbreviated
    let searchText: String
    let nameText: String

    static func == (a: Place, b: Place) -> Bool { a.id == b.id }
    func hash(into h: inout Hasher) { h.combine(id) }

    var isHonored: Bool { honorFlags != 0 || michelin != 0 || greenStar }
    var isChain: Bool { chainCount >= 5 }
    var michelinLabel: String? {
        switch michelin {
        case 5: "3 MICHELIN Stars"
        case 4: "2 MICHELIN Stars"
        case 3: "1 MICHELIN Star"
        case 2: "Bib Gourmand"
        case 1: "MICHELIN Recommended"
        default: nil
        }
    }
    var jamesBeardLabel: String? {
        if honorFlags & 1 != 0 { return "America's Classic" }
        if honorFlags & 2 != 0 { return "James Beard winner" }
        if honorFlags & 4 != 0 { return "James Beard finalist" }
        if honorFlags & 8 != 0 { return "James Beard semifinalist" }
        return nil
    }
    var liquorLabel: String? { ["", "Beer", "Beer & wine", "Full bar"][min(max(liquor, 0), 3)].nonEmpty }
    var townLine: String { [city, cuisine].compactMap { $0 }.joined(separator: " · ") }
    var fullAddress: String {
        [address, [city, zip].compactMap { $0 }.joined(separator: " ")].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: ", ")
    }
    var location: CLLocation? { coordinate.map { CLLocation(latitude: $0.latitude, longitude: $0.longitude) } }

    init(_ r: PlaceRecord, region: RegionData, index: DataIndex) {
        let city = r.c.flatMap { $0 < region.cities.count ? region.cities[$0] : nil }
        let cuisine = r.cu < index.cuisines.count ? index.cuisines[r.cu] : "American & Other"
        let brand = r.b.flatMap { $0 < index.brands.count ? index.brands[$0] : nil }
        id = r.id
        name = r.n
        address = r.a
        self.city = city
        zip = r.z
        coordinate = CLLocationCoordinate2D(latitude: r.la, longitude: r.lo)
        county = r.ct.flatMap { $0 < index.counties.count ? index.counties[$0] : nil }
        self.region = region.region
        self.cuisine = cuisine
        self.brand = brand
        chainCount = r.ch ?? 1
        tier = Tier(rawValue: r.t) ?? .listing
        source = r.s < index.sources.count ? index.sources[r.s] : "meta"
        isVenue = r.v == 1
        isBar = r.bar == 1
        guides = GuideTags(rawValue: r.g ?? 0)
        handChecked = r.hc == 1
        liquor = r.liq ?? 0
        honorFlags = r.h ?? 0
        michelin = r.mi ?? 0
        greenStar = r.gs == 1
        honorPoints = r.ip
        jamesBeard = r.jbf
        founded = r.f
        openedNote = r.on
        brandFounded = r.bf
        note = r.note
        dishes = r.di
        // web links only: a bare host gets https://, and any other scheme (javascript:, tel:, a custom app URL) is dropped
        website = r.w.flatMap { URL(string: $0.contains("://") ? $0 : "https://" + $0) }
            .flatMap { ["http", "https"].contains($0.scheme?.lowercased() ?? "") && $0.host != nil ? $0 : nil }
        phone = r.ph
        inspection = r.inspection
        // the dishes a hand-checked place serves are searchable too: "al pastor east la"
        searchText = " " + Search.normalize([r.n, city, r.z, cuisine, brand, r.di].compactMap { $0 }.joined(separator: " ")) + " " + Search.normalizeAddress(r.a ?? "") + " "
        nameText = " " + Search.normalize([r.n, brand].compactMap { $0 }.joined(separator: " ")) + " "
    }
}

extension String {
    var nonEmpty: String? { isEmpty ? nil : self }
}
