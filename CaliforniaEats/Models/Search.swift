import Foundation

/// Search that matches the start of words, the way the web leaderboard does:
/// "guel" finds Guelaguetza, "north ave" finds N Ave, "mt shasta" = "mount shasta", a town in the query narrows to that town
/// ("san gabriel dim sum"), and "dim sum", "fish tacos" or "korean bbq" mean those hand-checked guides (or a place named that way).
struct Search {
    static let typeSynonyms = ["avenue": "ave", "av": "ave", "street": "st", "boulevard": "blvd", "road": "rd", "drive": "dr", "place": "pl",
                               "court": "ct", "parkway": "pkwy", "highway": "hwy", "lane": "ln", "trail": "trl", "circle": "cir", "terrace": "ter"]
    static let synonyms: [String: String] = typeSynonyms.merging(["north": "n", "south": "s", "east": "e", "west": "w", "saint": "st", "mount": "mt", "fort": "ft"]) { a, _ in a }
    static let abbreviations = Set(synonyms.values)
    static let typeAbbreviations = Set(typeSynonyms.values)
    static let tagPhrases: [(String, GuideTags)] = [("fish tacos", .fishTaco), ("fish taco", .fishTaco), ("dim sum", .dimSum), ("dimsum", .dimSum),
                                                   ("yum cha", .dimSum), ("korean bbq", .koreanBBQ), ("korean barbecue", .koreanBBQ), ("kbbq", .koreanBBQ),
                                                   ("taquerias", .taqueria), ("taqueria", .taqueria), ("burritos", .burrito), ("burrito", .burrito),
                                                   ("burger stands", .burgerStand), ("burger stand", .burgerStand), ("drive ins", .burgerStand),
                                                   ("drive in", .burgerStand), ("wine country", .wineCountry)]

    /// Lowercase, no accents or apostrophes, "&" as "and" ("B&B" stays "bb"), everything else a single space.
    /// Runs for every place at launch (about 200,000 strings), so it's one pass over the characters rather than four regexes;
    /// only the rare "&" still goes through a regex.
    private static let enUS = Locale(identifier: "en_US")
    private static let initialsAnd = try! NSRegularExpression(pattern: #"\b([a-z0-9])\s*&\s*([a-z0-9])\b"#)

    static func normalize(_ s: String) -> String {
        // plain ASCII (most names) needs no accent folding, and folding with a fresh Locale each time was most of the launch
        let ascii = s.utf8.allSatisfy { $0 < 0x80 }
        var t = ascii ? s.lowercased() : s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: enUS).lowercased()
        if t.contains("&") {
            t = initialsAnd.stringByReplacingMatches(in: t, range: NSRange(t.startIndex..., in: t), withTemplate: "$1$2")
            t = t.replacingOccurrences(of: "&", with: " and ")
        }
        if ascii {   // the same rules byte by byte: in ASCII, the letters and numbers are exactly a-z and 0-9 once lowercased
            var bytes = [UInt8]()
            bytes.reserveCapacity(t.utf8.count)
            var gap = false
            for b in t.utf8 {
                if b == 0x27 || b == 0x60 { continue }   // ' and `
                if (b >= 0x61 && b <= 0x7A) || (b >= 0x30 && b <= 0x39) {
                    if gap && !bytes.isEmpty { bytes.append(0x20) }
                    gap = false
                    bytes.append(b)
                } else {
                    gap = true
                }
            }
            return String(decoding: bytes, as: UTF8.self)
        }
        var out = String.UnicodeScalarView()
        var gap = false
        for c in t.unicodeScalars {
            if c == "'" || c == "\u{2019}" || c == "`" { continue }
            switch c.properties.generalCategory {
            case .uppercaseLetter, .lowercaseLetter, .titlecaseLetter, .modifierLetter, .otherLetter,
                 .decimalNumber, .letterNumber, .otherNumber:
                if gap && !out.isEmpty { out.append(" ") }
                gap = false
                out.append(c)
            default:
                gap = true
            }
        }
        return String(out)
    }

    /// Addresses (only) get their street words abbreviated so "north avenue" finds "N Ave".
    static func normalizeAddress(_ s: String) -> String {
        normalize(s).split(separator: " ").map { synonyms[String($0)] ?? String($0) }.joined(separator: " ")
    }

    struct Query {
        var tokens: [[String]] = []     // each token: needles, any of which may match
        var town: String?
        var townPhrase: String?
        var tag: GuideTags?
        var tagPhrase: String?
        /// worked out once per query, not once per place: " taqueria" for "taquerias", " san gabriel" for the town
        var tagStem: String?
        var townNeedle: String?
        var isEmpty: Bool { tokens.isEmpty && town == nil && tag == nil }
    }

    /// `towns` maps a normalized town name ("st helena", "san luis obispo") to its display name.
    static func parse(_ text: String, towns: [String: String]) -> Query {
        var q = Query()
        var raw = normalize(text).split(separator: " ").map(String.init)
        guard !raw.isEmpty else { return q }
        var mapped = raw.map { synonyms[$0] ?? $0 }
        func find(_ phrase: String) -> Range<Int>? {
            let p = phrase.split(separator: " ").map(String.init)
            guard p.count <= mapped.count else { return nil }
            for i in 0...(mapped.count - p.count) where Array(mapped[i..<i + p.count]) == p { return i..<i + p.count }
            return nil
        }
        func cut(_ r: Range<Int>) -> String {
            let words = raw[r].joined(separator: " ")
            raw.removeSubrange(r); mapped.removeSubrange(r)
            return words
        }
        for (phrase, tag) in tagPhrases {
            if let r = find(normalize(phrase)) { q.tag = tag; q.tagPhrase = cut(r); break }
        }
        if let phrase = q.tagPhrase {
            let stem = normalize(phrase).replacingOccurrences(of: #"s$"#, with: "", options: .regularExpression)
            q.tagStem = stem.isEmpty ? nil : " " + stem
        }
        // the longest town named in the query wins, unless a street type follows it ("san pablo ave" is a street)
        for key in towns.keys.sorted(by: { $0.count > $1.count }) {
            if let r = find(key), !(r.upperBound < mapped.count && typeAbbreviations.contains(mapped[r.upperBound])) {
                q.town = towns[key]; q.townPhrase = cut(r); q.townNeedle = " " + normalize(q.townPhrase ?? ""); break
            }
        }
        let stop: Set<String> = ["the", "and", "of", "a", "in", "near", "me"]   // "tacos near me" isn't a place called Me
        var idx = Array(raw.indices)
        // stop words drop out when something real is left, or when the query already named a guide or town ("dim sum near me")
        if q.tag != nil || q.town != nil || idx.contains(where: { !stop.contains(mapped[$0]) }) { idx = idx.filter { !stop.contains(mapped[$0]) } }
        for (n, i) in idx.enumerated() {
            let token = raw[i], isLast = n == idx.count - 1
            if let abbr = synonyms[token] { q.tokens.append([" \(abbr) ", " \(token)"]); continue }
            let whole = (abbreviations.contains(token) && (!isLast || token.count > 1)) || (token.count <= 2 && !isLast)
            var needles = [" " + token + (whole ? " " : "")]
            if isLast && token.count >= 3 {
                for (word, abbr) in typeSynonyms where word != token && word.hasPrefix(token) { needles.append(" \(abbr) ") }
            }
            q.tokens.append(needles)
        }
        // "mission st": a finished street type sticks to the word before it
        if q.tokens.count >= 2, let last = idx.last, typeAbbreviations.contains(mapped[last]) {
            let prev = idx[idx.count - 2]
            q.tokens.removeLast(2)
            q.tokens.append([" \(mapped[prev]) \(mapped[last]) ", " \(raw[prev]) \(raw[last])"])
        }
        return q
    }

    static func matches(_ p: Place, _ q: Query) -> Bool {
        if let tag = q.tag, !(p.handChecked && p.guides.contains(tag)) {
            guard let stem = q.tagStem, p.nameText.contains(stem) else { return false }
        }
        if let town = q.town, p.city != town {
            guard let needle = q.townNeedle, p.nameText.contains(needle) else { return false }
        }
        for needles in q.tokens where !needles.contains(where: { p.searchText.contains($0) }) { return false }
        return true
    }

    /// Name matches first ("mission" puts Mission Chinese Food ahead of places on Mission St).
    static func nameMatches(_ p: Place, _ q: Query) -> Bool {
        !q.tokens.isEmpty && q.tokens.allSatisfy { needles in needles.contains { p.nameText.contains($0) } }
    }
}
