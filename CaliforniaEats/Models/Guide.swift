import Foundation
import CoreLocation

/// The lists the app is built around. Each is a filter plus an order; none uses ratings (the app only publishes data it may).
enum Guide: String, CaseIterable, Identifiable, Hashable {
    case taquerias, burritos, fishTacos, dimSum, koreanBBQ, burgerStands, wineCountry, honors, oldest, inspections, nearMe, all

    var id: String { rawValue }

    var title: String {
        switch self {
        case .taquerias: "Taquerías"
        case .burritos: "Burritos"
        case .fishTacos: "Fish Tacos"
        case .dimSum: "Dim Sum"
        case .koreanBBQ: "Korean BBQ"
        case .burgerStands: "Burger Stands"
        case .wineCountry: "Wine Country"
        case .honors: "MICHELIN & James Beard"
        case .oldest: "Oldest Places"
        case .inspections: "Inspections"
        case .nearMe: "Near Me"
        case .all: "All Restaurants"
        }
    }

    var subtitle: String {
        switch self {
        case .taquerias: "Hand-checked taquerías and taco shops, with what's on the menu"
        case .burritos: "Mission-style burritos in the Bay Area, California burritos in San Diego"
        case .fishTacos: "Baja-style fish tacos, mostly San Diego"
        case .dimSum: "Dim sum houses and bakeries, from the San Gabriel Valley to the Bay"
        case .koreanBBQ: "Tabletop-grill Korean barbecue, Koreatown and beyond"
        case .burgerStands: "Walk-up burger stands and drive-ins"
        case .wineCountry: "Restaurants in Napa, Sonoma, Paso Robles and other wine towns"
        case .honors: "MICHELIN Guide California 2026 and James Beard honors"
        case .oldest: "Open at the same address for decades, oldest first"
        case .inspections: "Official county results: LA County grades, San Francisco and Sacramento placards"
        case .nearMe: "Everything around you, closest first"
        case .all: "Restaurants, cafés, bars and bakeries statewide"
        }
    }

    var systemImage: String {
        switch self {
        case .taquerias: "flame"
        case .burritos: "takeoutbag.and.cup.and.straw"
        case .fishTacos: "fish"
        case .dimSum: "cup.and.saucer"
        case .koreanBBQ: "frying.pan"
        case .burgerStands: "car"
        case .wineCountry: "wineglass"
        case .honors: "rosette"
        case .oldest: "clock.arrow.circlepath"
        case .inspections: "checkmark.seal"
        case .nearMe: "location"
        case .all: "fork.knife"
        }
    }

    /// The hand-checked guides: each promises "checked open", so a place merely *named* "… Taquería" isn't enough.
    var tag: GuideTags? {
        switch self {
        case .taquerias: .taqueria
        case .burritos: .burrito
        case .fishTacos: .fishTaco
        case .dimSum: .dimSum
        case .koreanBBQ: .koreanBBQ
        case .burgerStands: .burgerStand
        case .wineCountry: .wineCountry
        case .oldest: .oldest
        default: nil
        }
    }
    var isHandChecked: Bool { tag != nil }

    /// Guides whose order is a ranking worth numbering.
    var isRanked: Bool { [.honors, .oldest, .inspections].contains(self) }

    var sortOptions: [SortOrder] {
        switch self {
        case .taquerias, .burritos, .fishTacos, .dimSum, .koreanBBQ, .burgerStands, .wineCountry: [.nearest, .name, .oldest]
        case .honors: [.honored, .nearest, .name]
        case .oldest: [.oldest, .nearest]
        case .inspections: [.bestResult, .worstResult, .nearest]
        case .nearMe: [.nearest]
        case .all: [.name, .nearest]
        }
    }

    var defaultSort: SortOrder { sortOptions[0] }

    /// `jurisdiction`: the Inspections guide shows one county at a time (they score differently, so they're never mixed).
    func includes(_ p: Place, jurisdiction: Int? = nil) -> Bool {
        if let tag { return p.handChecked && p.guides.contains(tag) }
        switch self {
        case .honors: return p.isHonored
        case .inspections: return p.inspection != nil && (jurisdiction == nil || p.inspection?.j == jurisdiction)
        default: return true
        }
    }
}

enum SortOrder: String, CaseIterable, Identifiable {
    case nearest, name, oldest, honored, bestResult, worstResult
    var id: String { rawValue }
    var label: String {
        switch self {
        case .nearest: "Nearest"
        case .name: "A to Z"
        case .oldest: "Oldest first"
        case .honored: "Most honored"
        case .bestResult: "Best latest result"
        case .worstResult: "Lowest latest result"
        }
    }
}

/// Filters shared by every list. Search text lives with each list.
struct Filters: Equatable, Codable {
    var town: String?
    var cuisine: String?
    var region: String?
    var hideChains = false
    var confirmedOnly = false
    var includeNonRestaurants = false

    var activeCount: Int {
        [town != nil, cuisine != nil, region != nil, hideChains, confirmedOnly, includeNonRestaurants].filter { $0 }.count
    }

    func allows(_ p: Place) -> Bool {
        if !includeNonRestaurants && p.isVenue { return false }
        if let region, p.region != region { return false }
        if let town, p.city != town { return false }
        if let cuisine, p.cuisine != cuisine { return false }
        if hideChains && p.isChain { return false }
        if confirmedOnly && p.tier == .listing { return false }
        return true
    }
}

enum Ranking {
    static func sort(_ places: [Place], by order: SortOrder, from here: CLLocation?) -> [Place] {
        // Keys come from precomputed fields: a localized compare, or a new CLLocation per comparison, made a 16,000-place
        // sort take most of a second on a phone (Wisconsin). nameText is the normalized name, so case, accents and
        // apostrophes don't change the order.
        func name(_ a: Place, _ b: Place) -> Bool { a.nameText != b.nameText ? a.nameText < b.nameText : a.id < b.id }
        switch order {
        case .nearest where here != nil:
            let from = here!
            return places.map { p in (p, p.location.map { $0.distance(from: from) } ?? .greatestFiniteMagnitude) }
                .sorted { $0.1 != $1.1 ? $0.1 < $1.1 : name($0.0, $1.0) }
                .map(\.0)
        case .nearest, .name:
            return places.sorted(by: name)
        case .oldest:
            return places.sorted { ($0.founded ?? 9999, $0.nameText) < ($1.founded ?? 9999, $1.nameText) }
        case .honored:
            return places.sorted { ($0.honorPoints ?? -1) != ($1.honorPoints ?? -1) ? ($0.honorPoints ?? -1) > ($1.honorPoints ?? -1) : name($0, $1) }
        case .bestResult, .worstResult:
            // within one county: LA County's own score where there is one (its letter grade comes from the score, and the seven
            // cities without grade cards still have one), otherwise the placard (a pass before a conditional pass before a
            // closure); then fewer non-pass results on record
            func key(_ p: Place) -> (Int, Int) {
                guard let i = p.inspection else { return (99_999, 99) }
                return (i.s.map { -$0 } ?? (i.r ?? 9) * 1000, i.b ?? 0)
            }
            return places.sorted {
                let a = key($0), b = key($1)
                if a != b { return order == .bestResult ? a < b : a > b }
                return name($0, $1)
            }
        }
    }
}
