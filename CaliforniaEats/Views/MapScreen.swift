import SwiftUI
import MapKit

struct MapScreen: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    var selection: Binding<Place?>? = nil

    @State private var layer: Layer = .taquerias
    @State private var pushed: Place?
    @State private var region: MKCoordinateRegion?
    /// "My location": where to move the map (a new object each tap, so a second tap re-centers after panning away)
    @State private var centerOn: CLLocation?
    @State private var centerWhenFound = false
    @State private var notice: String?
    @State private var askSettings = false
    /// places at the same spot (a food hall, a shared building) that clustering can never pull apart
    @State private var stacked: [Place] = []

    /// All 16,000 Wisconsin restaurants at once kept the map busy for a minute and more in QA (California has 100,000+), so the
    /// Everything layer fills in only once you zoom to about town size, only for what's in view, and only up to `maxPins`:
    /// downtown Los Angeles has thousands of places in one town-sized view.
    /// measured as the side of a square with the view's area (degrees of latitude), so a tall, narrow map (the iPad's middle
    /// column) and a wide one fill in at the same zoom
    private static let everythingSpan = 0.25
    private static let maxPins = 1200

    enum Layer: String, CaseIterable, Identifiable {
        case taquerias = "Taquerías", dimSum = "Dim sum", burritos = "Burritos", koreanBBQ = "Korean BBQ", honors = "Honors", all = "Everything"
        var id: String { rawValue }
        var guide: Guide {
            switch self {
            case .taquerias: .taquerias
            case .dimSum: .dimSum
            case .burritos: .burritos
            case .koreanBBQ: .koreanBBQ
            case .honors: .honors
            case .all: .all
            }
        }
    }

    var body: some View {
        // as in the guide lists: a hand-checked or honored place counts even where it's a market stall or a hotel dining room
        // (worked out in a closure: a bare assignment in a view body is read as a view and stalls the type checker)
        let layerFilters = { var f = model.filters; f.includeNonRestaurants = true; return f }()
        let layerPlaces = layer == .all ? [] : model.places.filter { layer.guide.includes($0) && layerFilters.allows($0) && $0.coordinate != nil }
        let side = region.map { ($0.span.latitudeDelta * $0.span.longitudeDelta * cos($0.center.latitude * .pi / 180)).squareRoot() }
        let zoomedOut = layer == .all && (side ?? .infinity) > Self.everythingSpan
        let inViewAll = layer == .all && !zoomedOut ? model.places.filter { inView($0) && model.filters.allows($0) } : []
        let tooMany = inViewAll.count > Self.maxPins
        let places = layer != .all ? layerPlaces : (zoomedOut || tooMany) ? [] : inViewAll
        ZStack(alignment: .top) {
            ClusteredMap(places: places, showsUser: location.location != nil, center: centerOn, onRegion: { region = $0 },
                         onStack: { stacked = $0 }) { p in open(p) }
            .ignoresSafeArea(edges: .bottom)
            VStack(spacing: 6) {
                // rows that wrap, not a sideways scroll: six chips don't fit an iPhone or the iPad's middle column,
                // and a chip scrolled out of sight ("Everything") is one people never find
                ChipFlow(spacing: 8) {
                    ForEach(Layer.allCases) { l in
                        LayerChip(title: l.rawValue, selected: layer == l) { layer = l }
                    }
                }
                .padding(.horizontal, 12)
                .accessibilityElement(children: .contain)
                .accessibilityIdentifier("layers")
                Text(notice ?? (zoomedOut ? "Zoom in to a town to see every place"
                               : tooMany ? "\(inViewAll.count.formatted()) places here. Zoom in closer to see them"
                               : "\(places.count.formatted()) \(layer == .all ? "places here" : "places") · tap a pin, then its name"))
                    .font(.caption).foregroundStyle(Theme.ink2)
                    .padding(.horizontal, 10).padding(.vertical, 4).background(Capsule().fill(.thinMaterial))
            }
            .padding(.top, 8)
        }
        .navigationTitle("Map")
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(item: $pushed) { PlaceDetailView(place: $0) }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    if location.isDenied {
                        askSettings = true
                    } else {
                        // a fix from launch may be miles out of date, so always ask for a fresh one; a very recent fix moves the map now
                        if let here = location.location, here.timestamp.timeIntervalSinceNow > -60 { center(on: here) }
                        centerWhenFound = true
                        location.request()
                    }
                } label: { Label("My location", systemImage: "location") }
            }
        }
        .onChange(of: location.location) { _, here in
            guard centerWhenFound, let here else { return }
            centerWhenFound = false
            center(on: here)
        }
        .onChange(of: location.failed) { _, failed in
            guard failed && centerWhenFound else { return }
            centerWhenFound = false
            // the map already moved to a fix from the last minute or so; only say so when there was nothing to go on
            if (location.location?.timestamp.timeIntervalSinceNow ?? -.infinity) < -90 {
                flash("Couldn't find your location. Check that Location Services is on.")
            }
        }
        .onChange(of: location.status) { _, _ in
            if location.isDenied { centerWhenFound = false }   // they said no; don't jump the map if they allow it later
        }
        .confirmationDialog("Places here", isPresented: Binding(get: { !stacked.isEmpty }, set: { if !$0 { stacked = [] } })) {
            ForEach(stacked) { p in Button(p.name) { open(p) } }
        } message: {
            Text("These places share one spot on the map.")
        }
        .alert("Location is off", isPresented: $askSettings) {
            Button("Open Settings") { LocationService.openSettings() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Turn on location for California Eats in Settings to center the map on you. It stays on your device.")
        }
    }
}

extension MapScreen {
    private func open(_ p: Place) {
        if let selection { selection.wrappedValue = p } else { pushed = p }
    }

    /// Town-level zoom on the reader, unless they're outside California: then the map stays on the state and says why.
    private func center(on here: CLLocation) {
        if location.isOutsideCalifornia {
            flash("You're outside California, so the map stays on the state.")
        } else {
            centerOn = CLLocation(latitude: here.coordinate.latitude, longitude: here.coordinate.longitude)
        }
    }

    private func flash(_ text: String) {
        notice = text
        Task { try? await Task.sleep(for: .seconds(5)); if notice == text { notice = nil } }
    }

    /// On screen, with half a screen of margin so panning doesn't show empty edges.
    private func inView(_ p: Place) -> Bool {
        guard let r = region, let c = p.coordinate else { return false }
        return abs(c.latitude - r.center.latitude) <= r.span.latitudeDelta && abs(c.longitude - r.center.longitude) <= r.span.longitudeDelta
    }
}

/// MKMapView with clustering: SwiftUI's Map can't cluster thousands of pins.
struct ClusteredMap: UIViewRepresentable {
    let places: [Place]
    let showsUser: Bool
    /// move the map here (town-level zoom) whenever a new location object arrives
    var center: CLLocation? = nil
    var onRegion: (MKCoordinateRegion) -> Void = { _ in }
    var onStack: ([Place]) -> Void = { _ in }
    let onSelect: (Place) -> Void

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.delegate = context.coordinator
        map.pointOfInterestFilter = .excludingAll
        map.register(PlaceMarker.self, forAnnotationViewWithReuseIdentifier: PlaceMarker.id)
        map.register(ClusterMarker.self, forAnnotationViewWithReuseIdentifier: MKMapViewDefaultClusterAnnotationViewReuseIdentifier)
        map.setRegion(MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 37.25, longitude: -119.3),
                                         span: MKCoordinateSpan(latitudeDelta: 10.2, longitudeDelta: 10.6)), animated: false)
        let start = map.region
        DispatchQueue.main.async { onRegion(start) }
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        context.coordinator.onSelect = onSelect
        context.coordinator.onRegion = onRegion
        context.coordinator.onStack = onStack
        map.showsUserLocation = showsUser
        if let c = center, c !== context.coordinator.centered {
            context.coordinator.centered = c
            map.setRegion(MKCoordinateRegion(center: c.coordinate, span: MKCoordinateSpan(latitudeDelta: 0.15, longitudeDelta: 0.15)),
                          animated: !UIAccessibility.isReduceMotionEnabled)
        }
        let want = Set(places.map(\.id))
        let have = map.annotations.compactMap { $0 as? PlaceAnnotation }
        let haveIds = Set(have.map(\.place.id))
        guard want != haveIds else { return }
        map.removeAnnotations(have.filter { !want.contains($0.place.id) })
        map.addAnnotations(places.filter { !haveIds.contains($0.id) }.map(PlaceAnnotation.init))
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, MKMapViewDelegate {
        var onSelect: ((Place) -> Void)?
        var onRegion: ((MKCoordinateRegion) -> Void)?
        var onStack: (([Place]) -> Void)?
        var centered: CLLocation?

        func mapView(_ map: MKMapView, regionDidChangeAnimated animated: Bool) {
            let r = map.region
            DispatchQueue.main.async { self.onRegion?(r) }   // not during a SwiftUI view update
        }

        func mapView(_ map: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            if annotation is MKUserLocation { return nil }
            if annotation is MKClusterAnnotation { return nil }   // the registered ClusterMarker
            return map.dequeueReusableAnnotationView(withIdentifier: PlaceMarker.id, for: annotation)
        }

        func mapView(_ map: MKMapView, annotationView view: MKAnnotationView, calloutAccessoryControlTapped control: UIControl) {
            if let a = view.annotation as? PlaceAnnotation { onSelect?(a.place) }
        }

        func mapView(_ map: MKMapView, didSelect annotation: MKAnnotation) {
            if let cluster = annotation as? MKClusterAnnotation {
                map.deselectAnnotation(cluster, animated: false)
                let members = cluster.memberAnnotations.compactMap { $0 as? PlaceAnnotation }
                let lats = members.map(\.coordinate.latitude), lons = members.map(\.coordinate.longitude)
                // within ~20 m of each other: zooming in can never split them, so offer a list
                if let a = lats.min(), let b = lats.max(), let c = lons.min(), let d = lons.max(), b - a < 0.0002, d - c < 0.0003 {
                    onStack?(members.map(\.place).sorted { $0.name < $1.name })
                } else {
                    map.showAnnotations(cluster.memberAnnotations, animated: !UIAccessibility.isReduceMotionEnabled)
                }
            }
        }
    }
}

final class PlaceAnnotation: NSObject, MKAnnotation {
    let place: Place
    let coordinate: CLLocationCoordinate2D
    var title: String? { place.name }
    var subtitle: String? { place.townLine }
    init(_ p: Place) { place = p; coordinate = p.coordinate! }
}

final class PlaceMarker: MKMarkerAnnotationView {
    static let id = "place"
    override var annotation: MKAnnotation? { didSet { configure() } }

    private func configure() {
        clusteringIdentifier = "places"
        canShowCallout = true
        let info = UIButton(type: .detailDisclosure)
        info.accessibilityLabel = "Details"
        rightCalloutAccessoryView = info
        guard let p = (annotation as? PlaceAnnotation)?.place else { return }
        let featured = p.handChecked && !p.guides.isEmpty
        markerTintColor = UIColor(featured ? Theme.gold : Theme.blue)
        glyphTintColor = UIColor(featured ? Theme.blue : .white)
        glyphImage = UIImage(systemName: p.michelin >= 3 ? "star.fill" : p.guides.contains(.dimSum) ? "cup.and.saucer.fill"
                             : p.guides.contains(.fishTaco) ? "fish.fill" : p.guides.contains(.taqueria) ? "flame.fill" : "fork.knife")
        displayPriority = p.isHonored || featured ? .defaultHigh : .defaultLow
    }
}

final class ClusterMarker: MKMarkerAnnotationView {
    override var annotation: MKAnnotation? {
        didSet {
            markerTintColor = UIColor(Theme.blue)
            glyphText = (annotation as? MKClusterAnnotation).map { "\($0.memberAnnotations.count)" }
            displayPriority = .defaultHigh
        }
    }
}

/// Lays its children out left to right and starts a new row when the next one wouldn't fit, each row centered.
struct ChipFlow: Layout {
    var spacing: CGFloat = 8

    private func rows(_ sizes: [CGSize], width: CGFloat) -> [[Int]] {
        var rows: [[Int]] = [[]], x: CGFloat = 0
        for (i, s) in sizes.enumerated() {
            if !rows[rows.count - 1].isEmpty && x + spacing + s.width > width { rows.append([]); x = 0 }
            x += (rows[rows.count - 1].isEmpty ? 0 : spacing) + s.width
            rows[rows.count - 1].append(i)
        }
        return rows
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let sizes = subviews.map { $0.sizeThatFits(.unspecified) }
        let width = proposal.width ?? sizes.reduce(0) { $0 + $1.width + spacing }
        let rs = rows(sizes, width: width)
        let height = rs.reduce(0) { $0 + ($1.map { sizes[$0].height }.max() ?? 0) } + spacing * CGFloat(max(rs.count - 1, 0))
        let used = rs.map { r in r.reduce(0) { $0 + sizes[$1].width } + spacing * CGFloat(max(r.count - 1, 0)) }.max() ?? 0
        return CGSize(width: proposal.width ?? used, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let sizes = subviews.map { $0.sizeThatFits(.unspecified) }
        var y = bounds.minY
        for r in rows(sizes, width: bounds.width) {
            let rowWidth = r.reduce(0) { $0 + sizes[$1].width } + spacing * CGFloat(max(r.count - 1, 0))
            let rowHeight = r.map { sizes[$0].height }.max() ?? 0
            var x = bounds.minX + max(0, (bounds.width - rowWidth) / 2)
            for i in r {
                subviews[i].place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(sizes[i]))
                x += sizes[i].width + spacing
            }
            y += rowHeight + spacing
        }
    }
}

/// One map layer button: filled when it's the layer shown.
struct LayerChip: View {
    let title: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        let fill: Color = selected ? Theme.blue : Theme.surface
        let ink: Color = selected ? .white : Theme.blue
        Button(action: action) {
            Text(title).font(.subheadline.weight(.semibold))
                .padding(.horizontal, 12).padding(.vertical, 8)
                .foregroundStyle(ink)
                .background(Capsule().fill(fill))
                .overlay(Capsule().strokeBorder(Theme.rule2, lineWidth: selected ? 0 : 1))
        }
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}
