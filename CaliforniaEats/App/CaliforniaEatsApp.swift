import SwiftUI
import CoreSpotlight

@main
struct CaliforniaEatsApp: App {
    @State private var model = AppModel()
    @State private var location = LocationService()

    init() {
        LaunchTiming.mark("app init")
        // Large titles in the same compressed black type as the home header.
        let blue = UIColor(Theme.blue)
        UINavigationBar.appearance().largeTitleTextAttributes = [
            .font: UIFont.systemFont(ofSize: 36, weight: .black, width: .compressed), .foregroundColor: blue,
        ]
        UINavigationBar.appearance().titleTextAttributes = [
            .font: UIFont.systemFont(ofSize: 19, weight: .heavy, width: .compressed), .foregroundColor: blue,
        ]
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .environment(location)
                .tint(Theme.blue)
                .task {
                    LaunchTiming.mark("load start")
                    await model.load()
                    LaunchTiming.mark("load end")
                    ScreenshotMode.apply(to: model)
                    if model.isLoaded && !ScreenshotMode.isActive {
                        SpotlightIndexer.indexIfNeeded(model.places, generated: model.generated)
                    }
                }
                .onContinueUserActivity(CSSearchableItemActionType) { activity in
                    guard let id = activity.userInfo?[CSSearchableItemActivityIdentifier] as? String else { return }
                    Task {
                        await model.load()
                        if let p = model.place(id: id) { model.tab = .guides; model.selectedPlace = p; model.guidesPath = [.place(p)] }
                    }
                }
        }
    }
}

/// `-timing` (DEBUG builds only) prints when launch milestones happen, as Unix times to compare with the moment of launch.
enum LaunchTiming {
    static func mark(_ what: String) {
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("-timing") { print(String(format: "timing %@ %.3f", what, Date().timeIntervalSince1970)) }
        #endif
    }
}
