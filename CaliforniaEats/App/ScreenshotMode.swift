import Foundation
import CoreLocation
import UIKit

/// `-screenshot <name>` opens one screen with fixed state for App Store screenshots (scripts/capture-screenshots.sh).
/// Names: home, taquerias, dimsum, detail, map, inspections, honors, saved, about.
enum ScreenshotMode {
    /// Debug builds only: an App Store build ignores the launch argument, so no one can reach seeded screens or fake locations.
    static var name: String? {
        #if DEBUG
        let args = ProcessInfo.processInfo.arguments
        guard let i = args.firstIndex(of: "-screenshot"), i + 1 < args.count else { return nil }
        return args[i + 1]
        #else
        return nil
        #endif
    }
    static var isActive: Bool { name != nil }

    @MainActor
    static func apply(to model: AppModel) {
        guard let name, model.isLoaded else { return }
        model.filters = Filters()
        // downtown Los Angeles, so "nearest" lists have distances without a permission prompt
        model.screenshotLocation = CLLocation(latitude: 34.0522, longitude: -118.2437)
        // a place shown in an App Store image has a clean record: no inspection on file, or the best result every time on file
        let clean = { (p: Place) in p.inspection.map { ($0.r ?? 0) == 0 && ($0.b ?? 0) == 0 } ?? true }
        let firstIn = { (g: Guide) in
            model.list(g, sort: g == .honors ? .honored : .nearest, search: "", here: model.screenshotLocation).first(where: clean)
        }
        for g in [Guide.taquerias, .dimSum, .honors] {
            if let p = firstIn(g), !model.isSaved(p) { model.toggleSaved(p) }
        }
        let open = { (g: Guide) in model.tab = .guides; model.selectedGuide = g; model.guidesPath = [.guide(g)] }
        switch name {
        case "taquerias": open(.taquerias)
        case "dimsum": open(.dimSum)
        case "honors": open(.honors)
        case "inspections":
            model.setInspectionJurisdiction(0)   // LA County; App Store shots show the best results, never the lowest
            open(.inspections)
        case "detail":
            open(.taquerias)
            if let p = firstIn(.taquerias) ?? model.places.first { model.selectedPlace = p; model.guidesPath.append(.place(p)) }
        case "map": model.tab = .map
        case "saved": model.tab = .saved
        case "about": model.tab = .about
        default: model.tab = .guides; model.selectedGuide = nil
        }
        // iPad shows the place column next to every list, so give each shot a place instead of "Pick a place".
        guard UIDevice.current.userInterfaceIdiom == .pad, model.selectedPlace == nil else { return }
        let place: Place? = switch name {
        case "dimsum": firstIn(.dimSum)
        case "honors", "saved": firstIn(.honors)
        case "inspections": model.list(.inspections, sort: .bestResult, search: "", here: nil).first(where: clean)
        case "about": nil
        default: firstIn(.taquerias)
        }
        model.selectedPlace = place
    }
}
