import Foundation

/// The app's web pages and support address, in one place.
/// The site is GitHub Pages; it moves to california.eatsranked.com once Nick's Cloudflare CNAME resolves (GitHub forwards the old
/// github.io addresses), and these switch with the next build.
enum Links {
    static let site = URL(string: "https://nickstrom5.github.io/california-eats/")!
    static let privacy = URL(string: "https://nickstrom5.github.io/california-eats/privacy.html")!
    static let terms = URL(string: "https://nickstrom5.github.io/california-eats/terms.html")!
    static let supportEmail = "work-with-nick@gmail.com"

    static var correctionEmail: URL {
        URL(string: "mailto:\(supportEmail)?subject=California%20Eats%20correction")!
    }
}
