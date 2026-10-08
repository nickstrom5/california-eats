import XCTest
import CoreLocation

/// Taps through every screen and control a reviewer is likely to touch, on iPhone (tabs) and iPad (split view).
/// Pass = nothing crashes and each screen shows what it should. Slow (network place cards, map tiles), so CI runs
/// only the unit tests; run this before every App Store submission:
/// xcodebuild test -scheme CaliforniaEats -only-testing:CaliforniaEatsUITests -destination 'id=<sim>'
final class SmokeUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = false
        // a test that failed in landscape mustn't leave the next one there (the iPad tour starts in portrait)
        XCUIDevice.shared.orientation = .portrait
        app = XCUIApplication()
        // the location prompt can appear on Near Me or the Nearest sort; answer it like a first-time user would
        addUIInterruptionMonitor(withDescription: "Location") { alert in
            for b in ["Allow While Using App", "Allow Once", "Don’t Allow", "Don't Allow"] where alert.buttons[b].exists {
                alert.buttons[b].tap(); return true
            }
            return false
        }
        app.launch()
    }

    private func button(containing text: String) -> XCUIElement {
        app.buttons.matching(NSPredicate(format: "label CONTAINS[c] %@", text)).firstMatch
    }

    private func text(containing text: String) -> XCUIElement {
        app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", text)).firstMatch
    }

    private func waitFor(_ e: XCUIElement, _ seconds: TimeInterval = 10, _ what: String) {
        XCTAssertTrue(e.waitForExistence(timeout: seconds), "missing: \(what)")
    }

    private func scrollTo(_ e: XCUIElement, max: Int = 8) {
        var n = 0
        while !e.isHittable && n < max { app.swipeUp(); n += 1 }
    }

    private var isPad: Bool { UIDevice.current.userInterfaceIdiom == .pad }

    /// Place detail: Apple Maps card (or the "not on Apple Maps" fallback), save, share.
    private func exerciseDetail(named name: String) {
        waitFor(text(containing: name), 10, "detail for \(name)")
        let card = button(containing: "Ratings, hours")
        waitFor(card, 5, "Apple Maps button")
        card.tap()
        // either Apple's place card sheet or our fallback alert
        let fallback = app.alerts["Not on Apple Maps"]
        let deadline = Date().addingTimeInterval(15)
        var opened = false
        while Date() < deadline && !opened {
            if fallback.exists { fallback.buttons["OK"].tap(); opened = true; break }
            let close = app.buttons.matching(NSPredicate(format: "label ==[c] 'Close' OR identifier ==[c] 'Close'")).firstMatch
            if close.exists && close.isHittable { close.tap(); opened = true; break }
            Thread.sleep(forTimeInterval: 0.5)
        }
        if !opened { app.swipeDown(velocity: .fast) }   // dismiss the sheet if its close button isn't labelled
        XCTAssertEqual(app.state, .runningForeground)
        let save = app.buttons["Save"]
        if save.waitForExistence(timeout: 3) {
            save.tap()
            // on iPad Apple's card is a centered sheet that a tap outside dismisses; that first tap may only close it
            if !app.buttons["Saved"].waitForExistence(timeout: 2) && app.buttons["Save"].exists { app.buttons["Save"].tap() }
            waitFor(app.buttons["Saved"], 3, "heart turns to Saved")
        }
        let share = app.buttons["Share"]
        if share.exists {
            share.tap()
            Thread.sleep(forTimeInterval: 1.5)
            let close = app.buttons.matching(NSPredicate(format: "label ==[c] 'Close' OR label ==[c] 'Cancel'")).firstMatch
            if close.exists { close.tap() } else { app.swipeDown(velocity: .fast) }
        }
        XCTAssertEqual(app.state, .runningForeground)
    }

    /// A clean start for each section, so one screen's navigation state can't strand the next (also proves saved places persist).
    private func fresh() {
        app.terminate()
        app.launch()
        waitFor(text(containing: "Taquería & dim sum guide"), 15, "home header")
    }

    func testTourEveryScreen() throws {
        if isPad { try padTour(); return }
        waitFor(text(containing: "Taquería & dim sum guide"), 15, "home header")

        // Taquerías: sort, filters, search
        button(containing: "Taquerías").tap()
        waitFor(app.navigationBars["Taquerías"], 5, "taquería list")
        waitFor(text(containing: "places ·"), 5, "list count header")
        app.buttons["Sort"].tap()
        waitFor(app.buttons["Oldest first"], 3, "sort menu"); app.buttons["Oldest first"].tap()
        waitFor(text(containing: "Oldest first"), 3, "sorted header")
        app.buttons["Filters"].tap()
        waitFor(app.navigationBars["Filters"], 3, "filters sheet")
        // tap the switch itself (its right edge); a tap on the middle of a Toggle row lands on the label
        let hide = app.switches.matching(NSPredicate(format: "label CONTAINS 'Hide chains'")).firstMatch
        waitFor(hide, 3, "hide-chains toggle")
        hide.coordinate(withNormalizedOffset: CGVector(dx: 0.93, dy: 0.5)).tap()
        XCTAssertEqual(hide.value as? String, "1", "toggle switched on")
        app.buttons["Done"].tap()
        waitFor(text(containing: "1 filter on"), 3, "active-filter row")
        button(containing: "Clear").tap()
        XCTAssertFalse(text(containing: "filter on").waitForExistence(timeout: 1), "filters cleared")
        let search = app.searchFields.firstMatch
        if !search.exists { app.swipeDown() }
        waitFor(search, 3, "search field"); search.tap(); search.typeText("al pastor")
        waitFor(text(containing: "places ·"), 3, "search results header")

        // the full directory → a known place → Apple Maps card, save, share
        fresh()
        button(containing: "Search every restaurant").tap()
        let search2 = app.searchFields.firstMatch
        waitFor(search2, 5, "directory search"); search2.tap(); search2.typeText("providence melrose")
        let providence = button(containing: "Providence")
        waitFor(providence, 5, "Providence in results"); providence.tap()
        exerciseDetail(named: "PROVIDENCE")

        // every other guide opens with a list
        for g in ["Dim Sum", "Burritos", "Fish Tacos", "Korean BBQ", "Burger Stands", "Wine Country", "MICHELIN & James Beard", "Oldest Places",
                  "Inspections", "Near Me", "All Restaurants"] {
            fresh()
            let card = button(containing: g)
            scrollTo(card)
            card.tap()
            if g == "Near Me" { app.swipeDown() }   // any interaction lets the monitor answer the location prompt (a tap could open a row)
            waitFor(app.navigationBars[g], 5, "\(g) list")
            if g != "Near Me" { waitFor(text(containing: "places ·"), 5, "\(g) count header") }
        }

        // surprise me
        fresh()
        let surprise = button(containing: "Surprise me")
        scrollTo(surprise); surprise.tap()
        waitFor(button(containing: "Ratings, hours"), 5, "a random taquería")

        // Map: every layer
        fresh()
        app.tabBars.buttons["Map"].tap()
        for l in ["Dim sum", "Burritos", "Korean BBQ", "Honors", "Everything", "Taquerías"] {
            tapLayer(l)
            // statewide, Everything asks you to zoom in instead of drawing 100,000 pins
            waitFor(text(containing: l == "Everything" ? "Zoom in to a town" : "tap a pin"), 5, "map hint for \(l)")
        }

        // Saved: Providence, saved earlier, survived relaunches; remove it
        app.tabBars.buttons["Saved"].tap()
        let saved = button(containing: "Providence")
        waitFor(saved, 5, "saved place")
        saved.swipeLeft()
        if app.buttons["Remove"].waitForExistence(timeout: 2) { app.buttons["Remove"].tap() }

        // About
        app.tabBars.buttons["About"].tap()
        waitFor(text(containing: "CALIFORNIA EATS"), 5, "about header")
        let privacy = app.buttons["Privacy policy"].exists ? app.buttons["Privacy policy"] : app.links["Privacy policy"]
        scrollTo(privacy)
        XCTAssertTrue(privacy.exists, "privacy link")
        XCTAssertEqual(app.state, .runningForeground)
    }

    /// iPad sidebar row. The rows themselves carry no label; the name is a text inside the "Sidebar" list.
    private func sidebarItem(_ name: String) -> XCUIElement {
        app.collectionViews["Sidebar"].staticTexts[name]
    }

    /// Launched in portrait and turned to landscape, the iPad keeps the sidebar folded away until "Show Sidebar" is tapped.
    private func showSidebar() {
        guard !app.collectionViews["Sidebar"].exists else { return }
        let toggle = app.buttons.matching(NSPredicate(format: "identifier == 'ToggleSidebar' OR label == 'Show Sidebar'")).firstMatch
        if toggle.waitForExistence(timeout: 5) { toggle.tap() }
        _ = app.collectionViews["Sidebar"].waitForExistence(timeout: 5)
    }

    private func padTour() throws {
        // iPad opens on Home in portrait, and a Home card opens its guide
        waitFor(text(containing: "Taquería & dim sum guide"), 15, "Home at launch in portrait")
        // in portrait the sidebar button is the only way from Home to Map, Saved and About (build 3 hid it with the nav bar)
        let toggle = app.buttons.matching(NSPredicate(format: "identifier == 'ToggleSidebar' OR label CONTAINS[c] 'sidebar'")).firstMatch
        waitFor(toggle, 5, "a sidebar button on Home in portrait")
        toggle.tap()
        waitFor(sidebarItem("Map"), 5, "the sidebar opens from Home in portrait")
        sidebarItem("Home").tap()
        waitFor(text(containing: "Taquería & dim sum guide"), 5, "back on Home")
        // in portrait the sidebar floats over Home's cards; fold it away so the tap reaches the card
        let hide = app.buttons.matching(NSPredicate(format: "label == 'Hide Sidebar'")).firstMatch
        if app.collectionViews["Sidebar"].exists && hide.exists { hide.tap(); Thread.sleep(forTimeInterval: 0.8) }
        button(containing: "Taquerías").tap()
        // a tap while the floating sidebar is still up only closes the sidebar; the second one reaches the card
        if !app.navigationBars["Taquerías"].waitForExistence(timeout: 3) { button(containing: "Taquerías").tap() }
        waitFor(app.navigationBars["Taquerías"], 15, "a Home card opens its guide on iPad")
        XCUIDevice.shared.orientation = .landscapeLeft     // all three columns
        Thread.sleep(forTimeInterval: 1.5)
        showSidebar()
        // ends on All Restaurants: the search below looks for a restaurant that's in no hand-checked guide
        for g in ["Dim Sum", "Burritos", "MICHELIN & James Beard", "Inspections", "Oldest Places", "Taquerías", "All Restaurants"] {
            let item = sidebarItem(g)
            waitFor(item, 5, "sidebar \(g)"); item.tap()
            waitFor(app.navigationBars[g], 5, "\(g) list")
        }
        let search = app.searchFields.firstMatch
        if !search.exists { app.swipeDown() }
        waitFor(search, 5, "search"); search.tap(); search.typeText("french laundry")
        let row = button(containing: "The French Laundry")
        waitFor(row, 5, "French Laundry in results"); row.tap()
        exerciseDetail(named: "THE FRENCH LAUNDRY")
        for s in ["Map", "Saved", "About"] {
            let item = sidebarItem(s)
            waitFor(item, 5, "sidebar \(s)"); item.tap()
        }
        waitFor(text(containing: "CALIFORNIA EATS"), 5, "about header")
        XCUIDevice.shared.orientation = .portrait
        Thread.sleep(forTimeInterval: 1.5)
        XCTAssertEqual(app.state, .runningForeground)
    }

    func testEverythingLayerFillsInWhenZoomed() {
        if isPad {
            XCUIDevice.shared.orientation = .landscapeLeft
            Thread.sleep(forTimeInterval: 1.5)     // let the columns settle, or a tap lands where a chip used to be
            showSidebar()
            waitFor(sidebarItem("Map"), 15, "sidebar Map"); sidebarItem("Map").tap()
        } else {
            waitFor(text(containing: "Taquería & dim sum guide"), 15, "home header")
            app.tabBars.buttons["Map"].tap()
        }
        tapLayer("Everything")
        waitFor(text(containing: "Zoom in to a town"), 5, "zoom hint statewide")
        let map = app.maps.firstMatch
        // pinch rather than double-tap: a double tap that lands on a cluster opens it instead of zooming
        for _ in 0..<8 where !text(containing: "places here").exists { map.pinch(withScale: 3, velocity: 3); Thread.sleep(forTimeInterval: 1) }
        waitFor(text(containing: "places here"), 10, "restaurants appear once zoomed in")
        XCTAssertEqual(app.state, .runningForeground)
        if isPad { XCUIDevice.shared.orientation = .portrait }
    }

    /// The map's layer chips wrap onto a second row where they don't fit, so every one is on screen to tap.
    @discardableResult
    private func tapLayer(_ label: String) -> XCUIElement {
        let chip = app.buttons[label]
        waitFor(chip, 5, "map layer \(label)")
        XCTAssertTrue(chip.isHittable, "map layer \(label) on screen")
        chip.tap()
        if !chip.isSelected { Thread.sleep(forTimeInterval: 1); chip.tap() }
        if !chip.isSelected {   // keep what the screen looked like, for the result bundle
            let shot = XCTAttachment(screenshot: app.screenshot()); shot.name = "layer \(label) not selected"; shot.lifetime = .keepAlways; add(shot)
        }
        XCTAssertTrue(chip.isSelected, "map layer \(label) selected")
        return chip
    }

    /// "My location" moves the map to you at town level, which also fills in the Everything layer.
    /// The simulator's own location resets to Apple's campus, so each location test sets where "you" are.
    private func openMapEverything(at here: CLLocation) {
        // a clean slate: scripts/capture-screenshots.sh revokes location, and the last test left the simulator somewhere else.
        // Resetting asks again (the interruption monitor allows it), and relaunching makes the app's first fix this one.
        app.resetAuthorizationStatus(for: .location)
        XCUIDevice.shared.location = XCUILocation(location: here)
        app.terminate(); app.launch()
        if isPad {
            XCUIDevice.shared.orientation = .landscapeLeft
            Thread.sleep(forTimeInterval: 1.5)     // let the columns settle, or a tap lands where a chip used to be
            showSidebar()
            waitFor(sidebarItem("Map"), 15, "sidebar Map"); sidebarItem("Map").tap()
        } else {
            waitFor(text(containing: "Taquería & dim sum guide"), 15, "home header")
            app.tabBars.buttons["Map"].tap()
        }
        let chip = tapLayer("Everything")
        waitFor(text(containing: "Zoom in to a town"), 5, "zoom hint statewide")
        app.buttons["My location"].tap()
        chip.tap()    // an interaction, so the monitor can answer the permission prompt if it appears
    }

    func testMyLocationCentersTheMap() {
        openMapEverything(at: CLLocation(latitude: 38.5816, longitude: -121.4944))   // downtown Sacramento
        waitFor(text(containing: "places here"), 15, "map moved to the simulated location and filled in")
        if isPad { XCUIDevice.shared.orientation = .portrait }
    }

    /// A reader outside the state (Las Vegas is inside California's bounding box, not the state): the map says so and stays on
    /// California rather than showing an empty map.
    func testMyLocationOutsideCalifornia() {
        openMapEverything(at: CLLocation(latitude: 36.1699, longitude: -115.1398))
        waitFor(text(containing: "outside California"), 15, "the outside-California note")
        XCTAssertTrue(text(containing: "Zoom in to a town").waitForExistence(timeout: 8), "the map stayed statewide")
        if isPad { XCUIDevice.shared.orientation = .portrait }
    }

    /// Apple's accessibility audit on the main iPhone screens. Prints every issue (prefixed AUDIT) instead of failing,
    /// so a run lists them all; read the log and fix what's ours (system bars and Apple's place card aren't).
    func testAccessibilityAudit() throws {
        if isPad { return }
        waitFor(text(containing: "Taquería & dim sum guide"), 15, "home header")
        func audit(_ screen: String) throws {
            try app.performAccessibilityAudit { issue in
                let el = issue.element.map { "\($0.elementType.rawValue) '\($0.label.prefix(40))'" } ?? "-"
                print("AUDIT [\(screen)] \(issue.auditType.rawValue) | \(issue.compactDescription) | \(el)")
                return true
            }
        }
        try audit("home")
        button(containing: "Taquerías").tap()
        waitFor(text(containing: "places ·"), 5, "taquería list")
        try audit("taquerias")
        app.buttons.matching(NSPredicate(format: "label CONTAINS ' · '")).firstMatch.tap()
        waitFor(button(containing: "Ratings, hours"), 5, "a place")
        try audit("detail")
        app.tabBars.buttons["About"].tap()
        try audit("about")
        // not the Map tab: auditing thousands of MapKit annotations times out, and those views are Apple's
    }

    func testLaunchIsQuick() {
        // nine region files (about 17 MB) decode in parallel off the main thread; the home screen should be up within a few seconds
        // the faster of two launches: the first after an install also pays for cold file reads, and the shared test Mac is often busy
        var best = Double.infinity
        for _ in 0..<2 {
            app.terminate()
            let start = Date()
            app.launch()
            let ready = isPad ? app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'places ·' OR label CONTAINS 'Taquería & dim sum guide'")).firstMatch
                              : text(containing: "Taquería & dim sum guide")
            XCTAssertTrue(ready.waitForExistence(timeout: 15), "home didn't appear")
            best = min(best, Date().timeIntervalSince(start))
        }
        print("launch to home: \(String(format: "%.2f", best)) s")
        XCTAssertLessThan(best, 6)
    }
}
