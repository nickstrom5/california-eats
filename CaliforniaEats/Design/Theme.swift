import SwiftUI

/// California gold and Pacific blue (Nick's pick, 2026-10-07), light only. Gold is always a fill with blue text on it
/// (gold text on white is 1.8:1); Pacific blue on white is 12.9:1.
enum Theme {
    static let blue = Color(hex: 0x003262)
    static let blue2 = Color(hex: 0x1A4B80)
    static let blueLight = Color(hex: 0x5582B4)
    static let gold = Color(hex: 0xFDB515)
    static let goldSoft = Color(hex: 0xFEE7B0)
    static let goldEdge = Color(hex: 0xC98A00)
    static let ink = Color(hex: 0x0E1B2C)
    static let ink2 = Color(hex: 0x283A52)
    static let muted = Color(hex: 0x4A5A72)
    static let surface = Color.white
    static let surface2 = Color(hex: 0xF2F5F9)
    static let surface3 = Color(hex: 0xE1E8F1)
    static let rule = Color(hex: 0xDCE3EC)
    static let rule2 = Color(hex: 0xB6C3D4)

    /// Official results, by position on the county's own scale: the best (A, Pass), the middle (B, Conditional Pass), the worst
    /// (C, Closure). Text on each passes AA.
    static let resultFill: [Color] = [Color(hex: 0xDDEFE3), Color(hex: 0xFFE9C2), Color(hex: 0xF9D5DB)]
    static let resultText: [Color] = [Color(hex: 0x0E5A2B), Color(hex: 0x6B3A00), Color(hex: 0x7A0019)]
}

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255, blue: Double(hex & 0xFF) / 255)
    }
}

/// A small uppercase label: "TAQUERÍA", "1 MICHELIN STAR".
struct Chip: View {
    enum Style { case gold, blue, plain, dashed }
    let text: String
    var style: Style = .plain

    var body: some View {
        Text(text.uppercased())
            .font(.caption2.weight(.bold))
            .tracking(0.4)
            .padding(.horizontal, 7).padding(.vertical, 3)
            .foregroundStyle(style == .blue ? Color.white : style == .dashed ? Theme.muted : Theme.blue)
            .background {
                RoundedRectangle(cornerRadius: 5).fill(style == .gold ? Theme.goldSoft : style == .blue ? Theme.blue : style == .dashed ? .clear : Theme.surface2)
            }
            .overlay {
                if style == .dashed { RoundedRectangle(cornerRadius: 5).strokeBorder(Theme.rule2, style: StrokeStyle(lineWidth: 1, dash: [3, 2])) }
            }
            .accessibilityLabel(text)
    }
}

/// The county's own result at the latest inspection ("Grade A", "Pass", "CONDITIONAL PASS"), never a grade of ours.
struct ResultBadge: View {
    let inspection: InspectionRecord
    let jurisdiction: InspectionJurisdiction?
    var large = false

    var body: some View {
        let (text, level) = label
        Text(text)
            .font(large ? .headline.weight(.heavy) : .caption.weight(.heavy))
            .padding(.horizontal, large ? 10 : 7).padding(.vertical, large ? 6 : 3)
            .foregroundStyle(level.map { Theme.resultText[$0] } ?? Theme.ink2)
            .background(RoundedRectangle(cornerRadius: 6).fill(level.map { Theme.resultFill[$0] } ?? Theme.surface3))
            .accessibilityLabel("\(jurisdiction?.name ?? "County") inspection: \(text)")
    }

    private var label: (String, Int?) {
        guard let j = jurisdiction else { return ("—", nil) }
        guard let r = inspection.r, r < j.scale.count else { return (inspection.s.map { "Score \($0)" } ?? "—", nil) }
        let v = j.scale[r]
        let text = j.id == "lac" ? "Grade \(v)" : v.capitalized
        return (text, min(r, 2))
    }
}

/// Condensed, heavy display type for titles and big numbers (the system font's compressed width). It scales with the
/// reader's text size, capped at 1.6× so a big number can't swallow its row.
struct DisplayFont: ViewModifier {
    let size: CGFloat
    var weight: Font.Weight = .black
    @ScaledMetric(relativeTo: .body) private var scale: CGFloat = 1

    func body(content: Content) -> some View {
        content.font(.system(size: size * min(scale, 1.6), weight: weight).width(.compressed))
    }
}

extension View {
    func displayFont(_ size: CGFloat, weight: Font.Weight = .black) -> some View {
        modifier(DisplayFont(size: size, weight: weight))
    }
}
