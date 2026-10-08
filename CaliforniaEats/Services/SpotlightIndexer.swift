import CoreSpotlight
import UniformTypeIdentifiers

/// Puts the hand-checked and honored places (taquerías, dim sum, MICHELIN and James Beard honorees...) into iPhone search,
/// so "dim sum millbrae" in Spotlight can open the place in the app.
enum SpotlightIndexer {
    static let domain = "places"
    private static let versionKey = "spotlightIndexedGenerated"

    static func indexIfNeeded(_ places: [Place], generated: String, defaults: UserDefaults = .standard) {
        // the data date alone missed same-day rebuilds; the build number changes with every update
        let version = "\(generated)|\(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "")"
        guard CSSearchableIndex.isIndexingAvailable(), defaults.string(forKey: versionKey) != version else { return }
        let featured = places.filter { !$0.isVenue && ($0.isHonored || $0.handChecked) && !$0.isChain }
        let items = featured.map { p -> CSSearchableItem in
            let attrs = CSSearchableItemAttributeSet(contentType: .content)
            attrs.title = p.name
            var kinds: [String] = []
            if p.handChecked {
                for (tag, label) in [(GuideTags.taqueria, "Taquería"), (.burrito, "Burritos"), (.fishTaco, "Fish tacos"), (.dimSum, "Dim sum"),
                                     (.koreanBBQ, "Korean barbecue"), (.burgerStand, "Burger stand"), (.wineCountry, "Wine country")] where p.guides.contains(tag) {
                    kinds.append(label)
                }
            }
            if let mi = p.michelinLabel { kinds.append(mi) }
            if let jb = p.jamesBeardLabel { kinds.append(jb) }
            attrs.contentDescription = ([kinds.joined(separator: " · ")] + [p.fullAddress]).filter { !$0.isEmpty }.joined(separator: "\n")
            attrs.keywords = kinds + [p.city, p.cuisine, "California"].compactMap { $0 }
            if let c = p.coordinate { attrs.latitude = NSNumber(value: c.latitude); attrs.longitude = NSNumber(value: c.longitude); attrs.supportsNavigation = true }
            let item = CSSearchableItem(uniqueIdentifier: p.id, domainIdentifier: domain, attributeSet: attrs)
            item.expirationDate = .distantFuture   // the default is about a month, after which places vanished from search
            return item
        }
        CSSearchableIndex.default().deleteSearchableItems(withDomainIdentifiers: [domain]) { _ in
            CSSearchableIndex.default().indexSearchableItems(items) { error in
                if error == nil { defaults.set(version, forKey: versionKey) }
            }
        }
    }
}
