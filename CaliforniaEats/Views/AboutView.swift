import SwiftUI

struct AboutView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Text("CALIFORNIA EATS").displayFont(30).foregroundStyle(Theme.blue)
                    Text("A free guide to \(model.restaurantCount.formatted()) California restaurants, with hand-checked taquerías, dim sum, burritos, fish tacos, Korean barbecue, burger stands and wine-country dining, MICHELIN and James Beard honors, and official county inspection results. No account, no ads, no tracking.")
                        .font(.subheadline).foregroundStyle(Theme.ink2)
                    Text("California Eats (\u{201C}CA Eats\u{201D}) is an independent app by Nicholas Soderstrom. It is not affiliated with, endorsed by or operated by the County of Los Angeles, the City and County of San Francisco, Sacramento County, San Diego County, the California Department of Alcoholic Beverage Control, the State of California, Michelin, the James Beard Foundation, Apple, or any restaurant or chain.")
                        .font(.footnote).foregroundStyle(Theme.muted)
                }
                .padding(.vertical, 4)
            }
            Section("How the lists are built") {
                Text("Taquerías, burritos, fish tacos, dim sum, Korean barbecue, burger stands, wine-country dining and the oldest places are hand-checked: each was checked in October 2026 against a 2025 or 2026 source (the place's own website or menu, or dated local news), with the address checked.")
                Text("The rest come from Overture Maps' open place data, county food-facility records (Los Angeles, San Diego, San Francisco and Sacramento counties) and California ABC liquor licenses. Map listings are kept only when they proved reliable: checked against LA County's and San Diego County's food-facility lists, high-confidence listings matched a permitted food business \(rate("meta_high (>=0.95)")) of the time. Website links are checked, and any that no longer belong to the place are left out.")
                Text("Inspection results are each county's own: LA County's score and letter grade, and San Francisco's and Sacramento County's placards, as recorded at the latest inspection. We never compute a grade of our own or compare counties. Other California counties don't publish inspection results in bulk.")
                Text("Ratings, reviews, hours and photos are Apple Maps' own, shown live in Apple's place card. This app doesn't store or rank by them.")
            }
            .font(.subheadline).foregroundStyle(Theme.ink2)
            Section("Sources") {
                source("Overture Maps Foundation", "Restaurant listings and websites come from Overture Maps Foundation places data (overturemaps.org), release \(model.overtureRelease), filtered and reformatted for this app.\n• Data from Meta, Microsoft, DAC and BrightQuery. Available under CDLA Permissive 2.0.\n• Data from Foursquare. Copyright 2024 Foursquare Labs, Inc. All rights reserved. Available under Apache 2.0. Foursquare data was transformed to the Overture schema; this app further filtered and reformatted it. See the NOTICE below.\n• Data from AllThePlaces. Available under CC0 1.0.", "https://overturemaps.org")
                source("County of Los Angeles", "Environmental Health restaurant and market inventory and inspections (data.lacounty.gov), used under the County's eGIS Terms of Use and modified for this app. \u{201C}The data herein is for informational purposes, and may not have been prepared for or be suitable for legal, engineering, or surveying intents.\u{201D} The data is provided as is, and the County does not endorse this app.", "https://data.lacounty.gov")
                source("City and County of San Francisco", "Department of Public Health health inspection results (data.sf.gov), Open Data Commons Public Domain Dedication and License, modified for this app.", "https://data.sf.gov")
                source("Sacramento County", "Environmental Management Department food facility inspections, Creative Commons Public Domain Dedication, modified for this app.", nil)
                source("San Diego County", "Department of Environmental Health and Quality food facility permits (data.sandiegocounty.gov), public domain, modified for this app. San Diego's inspection grades are published only in the county's own search app, so they aren't shown here.", "https://data.sandiegocounty.gov")
                source("California ABC", "Department of Alcoholic Beverage Control license data (abc.ca.gov), public domain, used to show whether a place holds an on-sale license. The Department makes no claims about the absolute accuracy, completeness or adequacy of its data.", "https://www.abc.ca.gov")
                source("Honors", "MICHELIN Guide California 2026 distinctions from MICHELIN's own announcement, and James Beard Foundation awards, finalists, semifinalists and America's Classics from the Foundation's announcements, reported as facts. MICHELIN and the MICHELIN Guide are trademarks of Michelin. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. Other names belong to their owners.", "https://www.jamesbeard.org/awards/search-past-awards")
                source("Maps", "Maps, place cards and directions by Apple Maps.", nil)
            }
            Section("Licenses") {
                NavigationLink("Community Data License Agreement – Permissive 2.0") { LicenseText(file: "CDLA-Permissive-2.0", title: "CDLA Permissive 2.0") }
                NavigationLink("Apache License 2.0") { LicenseText(file: "Apache-2.0", title: "Apache License 2.0") }
                NavigationLink("Foursquare OS Places NOTICE") { LicenseText(file: "Foursquare-NOTICE", title: "Foursquare NOTICE") }
            }
            Section("Privacy") {
                Text("The app collects nothing. Your location, if you allow it, only sorts lists by distance and shows where you are on the map, on this device. Saved places stay on this device.")
                    .font(.subheadline).foregroundStyle(Theme.ink2)
                Link("Privacy policy", destination: Links.privacy)
                Link("Terms of use", destination: Links.terms)
            }
            Section("Help") {
                Link("Report a missing or closed place", destination: Links.correctionEmail)
                Link("Email \(Links.supportEmail)", destination: URL(string: "mailto:\(Links.supportEmail)")!)
                Link("Website: \(Links.site.host ?? "")", destination: Links.site)
                Text("Data as of \(model.generated). Places open and close; check before you go. Version \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0")")
                    .font(.footnote).foregroundStyle(Theme.muted)
            }
        }
        .navigationTitle("About")
        .tint(Theme.blue)
    }

    private func rate(_ group: String) -> String {
        let v = ["lac", "sd"].compactMap { model.calibration[$0]?.groups[group]?.official }
        guard let lo = v.min(), let hi = v.max() else { return "most" }
        let a = Int((lo * 100).rounded()), b = Int((hi * 100).rounded())
        return a == b ? "\(a)%" : "\(a)–\(b)%"
    }

    @ViewBuilder
    private func source(_ name: String, _ detail: String, _ url: String?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            if let url, let u = URL(string: url) { Link(name, destination: u).font(.subheadline.weight(.semibold)) }
            else { Text(name).font(.subheadline.weight(.semibold)) }
            Text(detail).font(.caption).foregroundStyle(Theme.muted)
        }
    }
}

/// A bundled license text (Resources/Licenses), reflowed rather than shown as raw 80-column lines.
struct LicenseText: View {
    let file: String
    let title: String

    var body: some View {
        ScrollView {
            Text(text).font(.footnote).foregroundStyle(Theme.ink).textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading).padding()
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
    }

    private var text: String {
        guard let url = Bundle.main.url(forResource: file, withExtension: "txt"),
              let raw = try? String(contentsOf: url, encoding: .utf8) else { return "License text missing." }
        // join hard-wrapped lines into paragraphs; keep blank lines and list items as breaks
        var out: [String] = []
        for para in raw.components(separatedBy: "\n\n") {
            let lines = para.components(separatedBy: "\n").map { $0.trimmingCharacters(in: .whitespaces) }
            var joined = ""
            for l in lines where !l.isEmpty {
                let startsItem = l.hasPrefix("–") || l.hasPrefix("-") || l.range(of: #"^\(?[a-z0-9]{1,3}[.)]\s"#, options: .regularExpression) != nil
                joined += joined.isEmpty ? l : (startsItem ? "\n" + l : " " + l)
            }
            if !joined.isEmpty { out.append(joined) }
        }
        return out.joined(separator: "\n\n")
    }
}
