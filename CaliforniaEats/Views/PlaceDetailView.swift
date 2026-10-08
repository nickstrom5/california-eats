import SwiftUI
import MapKit

struct PlaceDetailView: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    let place: Place

    @State private var mapItem: MKMapItem?
    @State private var lookingUp = false
    @State private var mapsUnreachable = false
    @State private var notOnAppleMaps = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                header
                actions
                if let c = place.coordinate { mapSnippet(c) }
                if place.handChecked || place.note != nil || place.dishes != nil { checkedFacts }
                if place.isHonored || place.founded != nil || place.brandFounded != nil { honors }
                if let i = place.inspection { inspections(i) }
                listing
            }
            .padding(16)
        }
        .background(Theme.surface)
        .navigationTitle(place.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button { model.toggleSaved(place) } label: {
                    Label(model.isSaved(place) ? "Saved" : "Save", systemImage: model.isSaved(place) ? "heart.fill" : "heart")
                }
                ShareLink(item: shareText) { Label("Share", systemImage: "square.and.arrow.up") }
            }
        }
        .mapItemDetailSheet(item: $mapItem)
        .alert("Not on Apple Maps", isPresented: $notOnAppleMaps) {
            Button("Open Apple Maps anyway") { AppleMaps.openInMaps(place) }
            Button("OK", role: .cancel) {}
        } message: {
            Text("Apple Maps doesn't have a listing for \(place.name) at this spot, so there are no ratings or hours to show here.")
        }
        .alert("Couldn't reach Apple Maps", isPresented: $mapsUnreachable) {
            Button("OK", role: .cancel) {}
        } message: {
            Text("Ratings, hours and photos come live from Apple Maps. Check your connection and try again.")
        }
    }

    // MARK: sections

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text([place.city ?? "California", place.county].compactMap { $0 }.joined(separator: " · ").uppercased())
                .font(.caption.weight(.bold)).tracking(1.2).foregroundStyle(Theme.blue2)
            Text(place.name.uppercased())
                .displayFont(38).foregroundStyle(Theme.blue)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityLabel(place.name)   // VoiceOver spells out some all-caps words
                .accessibilityAddTraits(.isHeader)
            Text([place.fullAddress, place.cuisine].filter { !$0.isEmpty }.joined(separator: " · "))
                .font(.subheadline).foregroundStyle(Theme.ink2)
                .textSelection(.enabled)
            if let here = model.screenshotLocation ?? location.location, let l = place.location {
                Text("\(here.milesText(to: l)) away").font(.subheadline).foregroundStyle(Theme.muted)
            }
            PlaceChips(place: place)
        }
    }

    private var actions: some View {
        VStack(spacing: 10) {
            Button {
                lookingUp = true
                Task {
                    let result = await AppleMaps.findItem(for: place)
                    lookingUp = false
                    switch result {
                    case .found(let item): mapItem = item
                    case .notListed: notOnAppleMaps = true
                    case .unreachable: mapsUnreachable = true
                    }
                }
            } label: {
                HStack {
                    if lookingUp { ProgressView().tint(Theme.blue) } else { Image(systemName: "star.bubble") }
                    Text("Ratings, hours & photos").fontWeight(.semibold)
                    Spacer()
                    Text("Apple Maps").font(.caption).foregroundStyle(Theme.blue2)
                }
                .padding(14)
                .foregroundStyle(Theme.blue)
                .background(RoundedRectangle(cornerRadius: 12).fill(Theme.gold))
            }
            .disabled(place.coordinate == nil || lookingUp)
            .accessibilityHint("Opens the Apple Maps place card with current ratings and hours")

            HStack(spacing: 10) {
                actionButton("Directions", "arrow.triangle.turn.up.right.diamond") { AppleMaps.openInMaps(place, directions: true) }
                if let phone = place.phone, let url = URL(string: "tel:\(phone.filter { $0.isNumber || $0 == "+" })") {
                    actionButton("Call", "phone") { UIApplication.shared.open(url) }
                }
                if let web = place.website {
                    actionButton("Website", "safari") { UIApplication.shared.open(web) }
                }
            }
        }
    }

    private func actionButton(_ title: String, _ icon: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: icon).font(.title3)
                Text(title).font(.caption.weight(.semibold))
            }
            .frame(maxWidth: .infinity, minHeight: 56)
            .foregroundStyle(Theme.blue)
            .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.rule2))
        }
    }

    private func mapSnippet(_ c: CLLocationCoordinate2D) -> some View {
        Map(initialPosition: .region(MKCoordinateRegion(center: c, latitudinalMeters: 900, longitudinalMeters: 900)), interactionModes: []) {
            Marker(place.name, systemImage: "fork.knife", coordinate: c).tint(Theme.blue)
        }
        .frame(height: 170)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .onTapGesture { AppleMaps.openInMaps(place) }
        .accessibilityLabel("Map of \(place.name). Opens Apple Maps.")
        .accessibilityAddTraits(.isButton)
    }

    /// Facts our research recorded from the place's own menu or dated local news (never review text or ratings).
    private var checkedFacts: some View {
        section(place.handChecked ? "Hand-checked" : "Notes") {
            VStack(alignment: .leading, spacing: 8) {
                let kinds = [(GuideTags.taqueria, "Taquería"), (.burrito, "Burritos"), (.fishTaco, "Fish tacos"), (.dimSum, "Dim sum"),
                             (.koreanBBQ, "Korean barbecue"), (.burgerStand, "Burger stand"), (.wineCountry, "Wine country"), (.oldest, "Oldest places")]
                    .filter { place.guides.contains($0.0) }.map(\.1)
                if !kinds.isEmpty { fact("In our guides", kinds.joined(separator: ", ")) }
                if let d = place.dishes { fact("On the menu", d) }
                if let note = place.note { Text(note).font(.subheadline).foregroundStyle(Theme.ink2) }
                if place.handChecked {
                    Text("Checked open in Oct 2026 against a 2025 or 2026 source: the place's own site or menu, or dated local news. Menus and hours change, so check before you go.")
                        .font(.caption).foregroundStyle(Theme.ink2)
                }
            }
        }
    }

    private var honors: some View {
        section("Honors & history") {
            VStack(alignment: .leading, spacing: 8) {
                if let mi = place.michelinLabel { Label(mi + " · MICHELIN Guide California 2026", systemImage: "rosette").font(.subheadline).foregroundStyle(Theme.ink) }
                if place.greenStar { Label("MICHELIN Green Star (2026)", systemImage: "leaf").font(.subheadline).foregroundStyle(Theme.ink) }
                ForEach(lines(place.jamesBeard, prefix: "James Beard: "), id: \.self) { l in
                    Label(l, systemImage: "rosette").font(.subheadline).foregroundStyle(Theme.ink)
                }
                // "opened", at this address, only when a source says so; a brand's founding year is labeled as the brand's
                if let f = place.founded { fact("Opened here", "\(f)" + (place.openedNote.map { " · \($0)" } ?? "")) }
                if let bf = place.brandFounded { fact("Founded", bf) }
                if place.isHonored {
                    Text("Honors are facts from MICHELIN's and the James Beard Foundation's own announcements, not ratings. MICHELIN is a trademark of Michelin; James Beard Award is a trademark of the James Beard Foundation.")
                        .font(.caption).foregroundStyle(Theme.muted)
                }
            }
        }
    }

    /// The county's own result as recorded, with its date and what the scale means. Never a grade of ours.
    private func inspections(_ i: InspectionRecord) -> some View {
        let j = model.jurisdiction(of: place)
        return section("Health inspections · \(j?.name ?? "County")") {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 12) {
                    ResultBadge(inspection: i, jurisdiction: j, large: true)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Latest inspection \(i.d)" + (i.s.map { " · score \($0)" } ?? "")).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
                        Text("Official result, as recorded by \(j?.agency ?? "the county").").font(.caption).foregroundStyle(Theme.muted)
                    }
                }
                kv("Inspections on record", i.n.map(String.init))
                kv(j?.id == "lac" ? "Graded B or C" : "Yellow or red placards", i.b.map(String.init))
                if j?.id == "lac" && i.r == nil {
                    Text("This city never adopted LA County's letter-grade cards, so only the official score is shown.").font(.caption).foregroundStyle(Theme.ink2)
                }
                Text(scaleNote(j) + " Inspections through \(j?.through ?? ""). One inspection is a snapshot of one day; conditions may have changed since.")
                    .font(.caption).foregroundStyle(Theme.muted)
            }
        }
    }

    private func scaleNote(_ j: InspectionJurisdiction?) -> String {
        switch j?.id {
        case "lac": "LA County grades: A is 90–100, B 80–89, C 70–79."
        case "sf": "San Francisco's placards: Pass (green), Conditional Pass (yellow), Closure (red)."
        case "sac": "Sacramento County's placards: Pass (green), Conditional Pass (yellow), Closed (red)."
        default: ""
        }
    }

    private var listing: some View {
        section("How we know it's here") {
            VStack(alignment: .leading, spacing: 8) {
                kv("Listed as", place.tier.label)
                kv("Serves alcohol", place.liquorLabel.map { "\($0) (ABC on-sale license)" } ?? "— (no on-sale license matched)")
                if place.chainCount >= 2 { kv("Locations in California", place.chainCount.formatted()) }
                Text(listingNote).font(.caption).foregroundStyle(Theme.muted)
            }
        }
    }

    private var listingNote: String {
        let checked = place.handChecked
        if place.source == "research" {
            return "On our hand-checked or honors list. The open map data didn't list it as a place to eat (it may sit inside a hotel or inn), so it's placed from its own map listing or street address."
        }
        switch place.tier {
        case .official:
            return place.source == "official"
                ? "From a county food-facility list. The open map data didn't have it, so its location comes from the county's record."
                : "Matched to a county food-facility record or an active California ABC liquor license." + (checked ? " It's also hand-checked." : "")
        case .confirmed, .listing:
            let rate = model.matchRate(for: place)
            let base = place.tier == .confirmed
                ? "A high-confidence listing in Overture's open map data."
                : "A single listing in Overture's open map data, so it may be closed or misfiled."
            let measured = rate.map { " Checked against LA County's and San Diego County's food-facility lists, listings like this matched a permitted business \($0) of the time." } ?? ""
            return base + measured + (checked ? " It's also on our hand-checked list, checked in Oct 2026 against a 2025 or 2026 source." : "")
        }
    }

    // MARK: helpers

    private var shareText: String {
        [place.name, place.fullAddress, "via California Eats", Links.site.absoluteString].filter { !$0.isEmpty }.joined(separator: "\n")
    }

    private func lines(_ s: String?, prefix: String) -> [String] {
        (s ?? "").components(separatedBy: "; ").filter { !$0.isEmpty }.map { prefix + $0 }
    }

    private func section<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title.uppercased()).font(.caption.weight(.bold)).tracking(1).foregroundStyle(Theme.ink2)
            Divider()
            content()
        }
    }

    private func fact(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
            Text(value).font(.subheadline).foregroundStyle(Theme.ink2)
        }
    }

    @ViewBuilder
    private func kv(_ k: String, _ v: String?) -> some View {
        if let v {
            HStack(alignment: .firstTextBaseline) {
                Text(k).font(.subheadline).foregroundStyle(Theme.ink2)
                Spacer(minLength: 12)
                Text(v).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink).multilineTextAlignment(.trailing)
            }
        }
    }
}

