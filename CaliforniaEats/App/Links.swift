import Foundation

/// The app's web pages and support address, in one place.
/// The site is GitHub Pages; it moves to california.eatsranked.com once Nick's Cloudflare CNAME resolves (GitHub forwards the old
/// github.io addresses), and these switch with the next build.
enum Links {
    static let site = URL(string: "https://nickstrom5.github.io/california-eats/")!
    /// The app's data updates: scripts/publish_app_data.py writes docs/data/app/ (OTA-DATA.md).
    static let appData = URL(string: site.absoluteString + "data/app/")!
    static let privacy = URL(string: "https://nickstrom5.github.io/california-eats/privacy.html")!
    static let terms = URL(string: "https://nickstrom5.github.io/california-eats/terms.html")!
    static let supportEmail = "nick@eatsranked.com"   // Nick, 2026-10-12: replaced the Gmail address everywhere

    static var correctionEmail: URL {
        URL(string: "mailto:\(supportEmail)?subject=California%20Eats%20correction")!
    }

    // MARK: Share

    /// The web app. It opens a place's panel from the hash, explore/#p=<id> (readHash in scripts/explore.js), using the app's ids.
    static let explore = URL(string: site.absoluteString + "explore/")!

    /// What Share sends: the place's own page in the web app, never an Apple Maps or Google link (Apple Maps has its own button).
    /// The id is escaped the way the page's encodeURIComponent would escape it. The web app lists every place
    /// the app does (a unit test checks the ids against docs/data).
    static func share(_ place: Place) -> URL {
        guard let id = place.id.addingPercentEncoding(withAllowedCharacters: uriComponent),
              let url = URL(string: explore.absoluteString + "#p=" + id) else { return explore }
        return url
    }

    /// The text that goes with the link: the place, its town and the app. No street address, which Messages turns into a Maps link.
    static func shareMessage(_ place: Place) -> String {
        [place.name, place.city ?? ""].filter { !$0.isEmpty }.joined(separator: ", ") + ", on California Eats"
    }

    /// What encodeURIComponent leaves as is.
    private static let uriComponent = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.!~*'()")
}
