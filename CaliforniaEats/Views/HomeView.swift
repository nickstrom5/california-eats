import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var model
    /// iPad's split view: keep the navigation bar, because in portrait it holds the only sidebar button.
    /// (The size class can't tell: a split-view column reports compact.)
    var inSplitView = false
    @State private var lastRandom: String?
    private let columns = [GridItem(.adaptive(minimum: 158), spacing: 12)]
    static let cards: [Guide] = [.taquerias, .dimSum, .burritos, .fishTacos, .koreanBBQ, .burgerStands, .wineCountry, .honors, .oldest, .inspections, .nearMe, .all]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                Button { model.openGuide(.all) } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "magnifyingglass").foregroundStyle(Theme.blue)
                        Text("Search by name, town or street").foregroundStyle(Theme.muted)
                        Spacer()
                    }
                    .font(.subheadline)
                    .padding(14)
                    .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.blue, lineWidth: 2))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Search every restaurant")
                if model.filters.activeCount > 0 { filtersOn }
                LazyVGrid(columns: columns, spacing: 12) {
                    ForEach(Self.cards) { g in
                        Button { model.openGuide(g) } label: { GuideCard(guide: g, count: model.count(g)) }
                            .buttonStyle(.plain)
                    }
                }
                surpriseButton
                Text("Ratings, hours and photos come live from Apple Maps on each place. Lists are built from open map data, county food-facility records, California ABC licenses, official county inspections and hand-checked research. See About for sources.")
                    .font(.footnote).foregroundStyle(Theme.muted)
            }
            .padding(16)
        }
        .background(Theme.surface)
        .navigationTitle("")
        // iPhone: the big header is the title, so no bar
        .toolbar(inSplitView ? .automatic : .hidden, for: .navigationBar)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Rectangle().fill(Theme.gold).frame(width: 44, height: 5).clipShape(Capsule())
            Text("CALIFORNIA\nEATS")
                .displayFont(52)
                .foregroundStyle(Theme.blue)
                .lineSpacing(-6)
                .accessibilityAddTraits(.isHeader)
            Text("Taquería & dim sum guide")
                .font(.headline).foregroundStyle(Theme.ink)
            Text("Hand-checked taquerías, dim sum, burritos and more, MICHELIN and James Beard honors, official inspection results, and \(model.restaurantCount.formatted()) restaurants in \(model.towns.count.formatted()) towns.")
                .font(.subheadline).foregroundStyle(Theme.ink2)
            WaveBand().frame(height: 12).padding(.top, 4).accessibilityHidden(true)
        }
        .padding(.top, 8)
    }

    /// Filters stick between launches, so say so here: a forgotten town filter made the counts look nearly empty (Wisconsin QA).
    private var filtersOn: some View {
        HStack(spacing: 10) {
            Image(systemName: "line.3.horizontal.decrease.circle.fill").foregroundStyle(Theme.blue).accessibilityHidden(true)
            Text(model.filters.activeCount == 1 ? "A filter is on, so the counts below are filtered." : "\(model.filters.activeCount) filters are on, so the counts below are filtered.")
                .font(.footnote).foregroundStyle(Theme.ink2)
            Spacer(minLength: 4)
            Button("Clear") { model.filters = Filters() }.font(.footnote.weight(.semibold))
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 12).fill(Theme.surface2))
    }

    private var surpriseButton: some View {
        Button {
            if let p = model.randomPick(from: .taquerias, excluding: lastRandom) ?? model.randomPick(from: .all, excluding: lastRandom) {
                lastRandom = p.id
                model.guidesPath.append(.place(p))
                model.selectedPlace = p
            }
        } label: {
            Label("Surprise me with a taquería", systemImage: "dice")
                .font(.subheadline.weight(.semibold))
                .frame(maxWidth: .infinity).padding(12)
                .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.rule2))
        }
        .buttonStyle(.plain)
        .foregroundStyle(Theme.ink)
    }
}

/// The one California element: a low sun over two Pacific swells.
struct WaveBand: View {
    var body: some View {
        Canvas { ctx, size in
            let w = size.width, h = size.height
            var sun = Path(); sun.addEllipse(in: CGRect(x: w * 0.06, y: h * 0.05, width: h * 1.6, height: h * 1.6))
            ctx.fill(sun, with: .color(Theme.gold))
            for (y, color) in [(h * 0.45, Theme.blueLight), (h * 0.75, Theme.blue)] {
                var p = Path(); p.move(to: CGPoint(x: 0, y: y))
                var x: CGFloat = 0
                while x < w { p.addQuadCurve(to: CGPoint(x: x + 24, y: y), control: CGPoint(x: x + 12, y: y - h * 0.35)); x += 24 }
                p.addLine(to: CGPoint(x: w, y: h)); p.addLine(to: CGPoint(x: 0, y: h)); p.closeSubpath()
                ctx.fill(p, with: .color(color))
            }
        }
    }
}

struct GuideCard: View {
    let guide: Guide
    let count: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: guide.systemImage).font(.title3).foregroundStyle(Theme.blue)
                    .frame(width: 36, height: 36).background(Circle().fill(guide.isHandChecked ? Theme.goldSoft : Theme.surface2))
                    .accessibilityHidden(true)
                Spacer()
                if guide != .nearMe && guide != .all {   // "All" would just repeat the total in the header
                    // text styles, not displayFont: cards must scale all the way with Dynamic Type
                    Text(count.formatted()).font(.title3.weight(.black).width(.compressed)).foregroundStyle(Theme.blue).monospacedDigit()
                }
            }
            Text(guide.title).font(.title3.weight(.heavy).width(.compressed)).foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)   // wraps at large text sizes instead of shrinking
            Text(guide.subtitle).font(.caption).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 150, alignment: .topLeading)
        .background(RoundedRectangle(cornerRadius: 14).fill(Theme.surface))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(guide.isHandChecked ? Theme.goldEdge : Theme.rule))
        .accessibilityElement(children: .combine)
        .accessibilityHint(guide == .nearMe ? "" : "\(count) places")
    }
}
