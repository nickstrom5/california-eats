import SwiftUI
import CoreLocation

struct GuideListView: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    let guide: Guide
    /// iPad passes a selection; iPhone pushes the place onto the stack
    var selection: Binding<Place?>? = nil

    @State private var sort: SortOrder?
    @State private var search = ""
    @State private var showFilters = false
    @State private var shown = 100

    /// Hand-checked guides sort nearest first when we know where you are in California, A to Z otherwise.
    private var order: SortOrder {
        sort ?? (guide.isHandChecked ? (here != nil && !outOfState ? .nearest : .name) : guide.defaultSort)
    }
    private var outOfState: Bool { model.screenshotLocation == nil && location.isOutsideCalifornia }
    private var here: CLLocation? { model.screenshotLocation ?? location.location }

    var body: some View {
        let places = model.list(guide, sort: order, search: search, here: here)
        List {
            Section {
                Text(guide.subtitle + ".").font(.subheadline).foregroundStyle(Theme.muted).listRowSeparator(.hidden)
                if guide == .inspections { jurisdictionPicker }
                if guide.isHandChecked {
                    Text("Every place here was checked open in Oct 2026 against a 2025 or 2026 source: its own site or menu, or dated local news. Menus and hours change, so check before you go.")
                        .font(.caption).foregroundStyle(Theme.ink2).listRowSeparator(.hidden)
                }
                if (order == .nearest || guide == .nearMe) && here == nil { locationPrompt }
                if order == .nearest && outOfState {
                    Text("You're outside California. Every place here is in California, so distances are from where you are now.")
                        .font(.subheadline).foregroundStyle(Theme.ink2).listRowSeparator(.hidden)
                }
                if model.filters.activeCount > 0 { activeFilters }
            }
            Section {
                if places.isEmpty && !(guide == .nearMe && here == nil) {
                    ContentUnavailableView {
                        Label(search.isEmpty ? "Nothing here" : "No matches", systemImage: "magnifyingglass")
                    } description: {
                        Text(search.isEmpty ? "No places match your filters." : "No places match “\(search)” with your filters.")
                    } actions: {
                        if model.filters.activeCount > 0 { Button("Clear filters") { model.filters = Filters() } }
                        if !search.isEmpty { Button("Clear search") { search = "" } }
                    }
                }
                ForEach(Array(places.prefix(shown).enumerated()), id: \.element.id) { i, p in
                    row(p, rank: guide.isRanked ? i + 1 : nil)
                }
                if places.count > shown {
                    Button("Show more (\((places.count - shown).formatted()) left)") { shown += 200 }
                        .frame(maxWidth: .infinity).foregroundStyle(Theme.blue)
                }
            } header: {
                Text("\(places.count.formatted()) \(places.count == 1 ? "place" : "places") · \(order.label)").textCase(nil).foregroundStyle(Theme.ink2)
            }
        }
        .listStyle(.plain)
        .navigationTitle(guide.title)
        .navigationBarTitleDisplayMode(.large)
        .searchable(text: $search, placement: .navigationBarDrawer(displayMode: guide == .all ? .always : .automatic), prompt: "Name, town, street or zip")
        .onChange(of: search) { shown = 100 }
        .onChange(of: sort) { shown = 100 }
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                if guide.sortOptions.count > 1 {
                    Menu {
                        Picker("Sort", selection: Binding(get: { order }, set: { sort = $0; if $0 == .nearest { location.request() } })) {
                            ForEach(guide.sortOptions) { Text($0.label).tag($0) }
                        }
                    } label: { Label("Sort", systemImage: "arrow.up.arrow.down") }
                }
                Button { showFilters = true } label: {
                    Label("Filters", systemImage: model.filters.activeCount > 0 ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
                }
            }
        }
        .sheet(isPresented: $showFilters) { FiltersSheet() }
        .task { if !ScreenshotMode.isActive && (guide == .nearMe || order == .nearest) { location.request() } }
    }

    @ViewBuilder
    private func row(_ p: Place, rank: Int?) -> some View {
        let metric = metricText(p)
        if let selection {
            Button { selection.wrappedValue = p } label: { PlaceRow(place: p, rank: rank, metric: metric, detail: detailLine(p), highlightTop: order != .worstResult) }
                .listRowBackground(selection.wrappedValue?.id == p.id ? Theme.surface2 : Theme.surface)
        } else {
            NavigationLink(value: AppModel.Route.place(p)) { PlaceRow(place: p, rank: rank, metric: metric, detail: detailLine(p), highlightTop: order != .worstResult) }
        }
    }

    /// Inspection rows name the exact place and the date of its latest inspection, so a result is never read without context.
    private func detailLine(_ p: Place) -> String? {
        guard guide == .inspections, let i = p.inspection else { return nil }
        return [p.address, "inspected \(i.d)", i.s.map { "score \($0)" }].compactMap { $0 }.joined(separator: " · ")
    }

    private func metricText(_ p: Place) -> PlaceRow.Metric? {
        if guide == .inspections, let i = p.inspection { return .result(i, model.jurisdiction(of: p)) }
        switch order {
        case .nearest: if let here, let l = p.location { return .text(here.milesText(to: l), "away") }
        case .oldest: if let f = p.founded { return .text("\(f)", "since") }
        case .honored: if let pts = p.honorPoints { return .text("\(Int(pts.rounded()))", "honor pts") }
        default: break
        }
        if let f = p.founded, guide != .all { return .text("\(f)", "since") }
        return nil
    }

    /// Counties score differently (LA's letter grades, San Francisco's and Sacramento's placards), so one at a time.
    private var jurisdictionPicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            Picker("County", selection: Binding(get: { model.inspectionJurisdiction }, set: { model.setInspectionJurisdiction($0); shown = 100 })) {
                ForEach(Array(model.jurisdictions.enumerated()), id: \.offset) { n, j in Text(j.name.replacingOccurrences(of: " County", with: "")).tag(n) }
            }
            .pickerStyle(.segmented)
            if model.inspectionJurisdiction < model.jurisdictions.count {
                let j = model.jurisdictions[model.inspectionJurisdiction]
                Text(inspectionNote(j)).font(.caption).foregroundStyle(Theme.ink2)
            }
        }
        .listRowSeparator(.hidden)
    }

    private func inspectionNote(_ j: InspectionJurisdiction) -> String {
        let how: String = switch j.id {
        case "lac": "LA County's official score and letter grade at the latest inspection (A 90–100, B 80–89, C 70–79). Seven cities that never adopted grade cards show the score only. Pasadena, Long Beach and Vernon inspect on their own and aren't included."
        case "sf": "San Francisco's official placard at the latest inspection: Pass, Conditional Pass or Closure."
        case "sac": "Sacramento County's official placard at the latest inspection: Pass, Conditional Pass or Closed."
        default: "The county's official result at the latest inspection."
        }
        return how + " As recorded by \(j.agency), through \(j.through). We never compute a grade of our own. One inspection is a snapshot of one day."
    }

    private var locationPrompt: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(location.isDenied ? "Location is off for this app. Turn it on in Settings to sort by distance."
                 : location.failed ? "Couldn't find your location. Check that Location Services is on, then try again."
                 : "Sort by distance from where you are. Your location stays on this device.")
                .font(.subheadline).foregroundStyle(Theme.ink2)
            if location.isDenied {
                Button("Open Settings") { LocationService.openSettings() }.buttonStyle(.bordered).tint(Theme.blue)
            } else {
                Button(location.failed ? "Try again" : "Use my location") { location.request() }.buttonStyle(.borderedProminent).tint(Theme.blue)
            }
        }
        .padding(.vertical, 4)
        .listRowSeparator(.hidden)
    }

    private var activeFilters: some View {
        HStack {
            Text("\(model.filters.activeCount) filter\(model.filters.activeCount == 1 ? "" : "s") on").font(.subheadline).foregroundStyle(Theme.ink2)
            Spacer()
            Button("Clear") { model.filters = Filters() }.font(.subheadline.weight(.semibold))
        }
        .listRowSeparator(.hidden)
    }
}

struct PlaceRow: View {
    enum Metric { case text(String, String), result(InspectionRecord, InspectionJurisdiction?) }
    let place: Place
    var rank: Int?
    var metric: Metric?
    /// a second line under the town (inspections: street address and last visit date)
    var detail: String? = nil
    /// gold for the top three of a ranking; never on the lowest-scores sort
    var highlightTop = true

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            if let rank {
                Text("\(rank)")
                    .displayFont(rank < 100 ? 26 : 20).monospacedDigit()
                    .foregroundStyle(Theme.blue)
                    .frame(minWidth: 38, minHeight: 38)
                    .background(RoundedRectangle(cornerRadius: 8).fill(rank <= 3 && highlightTop ? Theme.gold : .clear))
                    .accessibilityLabel("Rank \(rank)")
            }
            VStack(alignment: .leading, spacing: 4) {
                Text(place.name).font(.body.weight(.semibold)).foregroundStyle(Theme.ink).multilineTextAlignment(.leading)
                Text(place.townLine).font(.subheadline).foregroundStyle(Theme.muted)
                if let detail { Text(detail).font(.caption).foregroundStyle(Theme.ink2) }
                PlaceChips(place: place, compact: true)
            }
            Spacer(minLength: 8)
            switch metric {
            case .text(let big, let small):
                VStack(alignment: .trailing, spacing: 0) {
                    Text(big).displayFont(22).foregroundStyle(Theme.blue).monospacedDigit()
                    Text(small).font(.caption2).foregroundStyle(Theme.muted)
                }
            case .result(let i, let j):
                ResultBadge(inspection: i, jurisdiction: j)
            case nil: EmptyView()
            }
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
    }
}

/// The small labels on a place: honors, hand-checked guides, chain size, how sure we are it's real.
struct PlaceChips: View {
    let place: Place
    var compact = false

    var body: some View {
        let chips = items
        if !chips.isEmpty {
            FlowLayout(spacing: 5) {
                ForEach(chips, id: \.0) { Chip(text: $0.0, style: $0.1) }
            }
        }
    }

    private var items: [(String, Chip.Style)] {
        var out: [(String, Chip.Style)] = []
        if let mi = place.michelinLabel { out.append((mi, .blue)) }
        if place.greenStar { out.append(("MICHELIN Green Star", .blue)) }
        if let jb = place.jamesBeardLabel { out.append((jb, .blue)) }
        if place.handChecked {
            for (tag, label) in [(GuideTags.taqueria, "Taquería"), (.burrito, "Burritos"), (.fishTaco, "Fish tacos"), (.dimSum, "Dim sum"),
                                 (.koreanBBQ, "Korean BBQ"), (.burgerStand, "Burger stand"), (.wineCountry, "Wine country")] where place.guides.contains(tag) {
                out.append((label, .gold))
            }
        }
        if place.isChain { out.append(("Chain · \(place.chainCount)", .plain)) }
        if place.tier == .listing && !place.isHonored && !place.handChecked { out.append(("Listing only", .dashed)) }
        return compact ? Array(out.prefix(4)) : out
    }
}

/// Wraps chips onto new lines.
struct FlowLayout: Layout {
    var spacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxW = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowH: CGFloat = 0, widest: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > 0 && x + s.width > maxW { y += rowH + spacing; x = 0; rowH = 0 }
            x += s.width + spacing; rowH = max(rowH, s.height); widest = max(widest, x - spacing)
        }
        return CGSize(width: min(widest, maxW), height: y + rowH)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowH: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > bounds.minX && x + s.width > bounds.maxX { y += rowH + spacing; x = bounds.minX; rowH = 0 }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
            x += s.width + spacing; rowH = max(rowH, s.height)
        }
    }
}
