// Brand images for California Eats: the app icon (the flat avocado half on Pacific blue that Nick picked on 2026-10-07, concept B
// of scripts/icon-concepts.swift; redrawn 2026-10-09 in the shared Eats Ranked style Nick approved: upright, flat, no sea or wave line,
// see ../state-prompts/ICON-STYLE.md), playbook/brand/, and the site's og.png, favicons and manifest icons.
// Usage: swift scripts/make-brand.swift ["105,000+"]   (run from ca-eats/; the optional argument is the restaurant count on og.png)
import AppKit
import CoreGraphics

let root = FileManager.default.currentDirectoryPath
func rgb(_ hex: UInt32, _ a: CGFloat = 1) -> CGColor {
    CGColor(srgbRed: CGFloat((hex >> 16) & 255) / 255, green: CGFloat((hex >> 8) & 255) / 255, blue: CGFloat(hex & 255) / 255, alpha: a)
}
let blue = rgb(0x003262), blue2 = rgb(0x1A4B80), gold = rgb(0xFDB515), white = rgb(0xFFFFFF), ink = rgb(0x0E1B2C)

func canvas(_ w: Int, _ h: Int, _ draw: (CGContext) -> Void) -> CGImage {
    let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                        space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    ctx.setShouldAntialias(true); ctx.interpolationQuality = .high
    draw(ctx)
    return ctx.makeImage()!
}
func save(_ img: CGImage, _ path: String) {
    let url = URL(fileURLWithPath: root + "/" + path)
    try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
    try! NSBitmapImageRep(cgImage: img).representation(using: .png, properties: [:])!.write(to: url)
    print("wrote", path)
}
func P(_ s: CGFloat, _ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x * s, y: y * s) }
func disc(_ c: CGContext, _ s: CGFloat, _ x: CGFloat, _ y: CGFloat, _ r: CGFloat, _ col: CGColor) {
    c.setFillColor(col); c.fillEllipse(in: CGRect(x: s * (x - r), y: s * (y - r), width: s * r * 2, height: s * r * 2))
}

/// The ground: flat Pacific blue, edge to edge (no sea, no wave line: the shared Eats Ranked icon style).
func ground(_ c: CGContext, _ s: CGFloat) {
    c.setFillColor(blue); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
}

/// B: an avocado half seen straight on, narrow end up, symmetric about the vertical centre line (Eats Ranked style, 2026-10-09).
/// Three tones of one fruit: a thin dark skin rim (a 16 px band outside the flesh, drawn as a 32 px round-join stroke under the
/// fill, the way Chicago rings its hot dog), a 40 px bright-green flesh ring kept inside the outline by a clip, and pale flesh.
/// One flat brown pit low in the wide end. Paints no background. Painted box 0.58 x 0.72 at 1024 (rows 143 to 880 from the top).
func avocado(_ c: CGContext, _ s: CGFloat) {
    let skin = rgb(0x2F4F1C), ring = rgb(0x9CC94F), flesh = rgb(0xE4EC9A), pit = rgb(0x7A4A26)
    let rim: CGFloat = 16 / 1024, band: CGFloat = 40 / 1024
    // The flesh outline (CG y-up, fractions of s). With the rim the fruit spans y 0.14...0.86 and x 0.21...0.79.
    let cx: CGFloat = 0.5, top: CGFloat = 0.86 - rim, bot: CGFloat = 0.14 + rim, w: CGFloat = 0.29 - rim
    let wide: CGFloat = 0.355                        // height of the widest point (just above the pit's centre)
    let cap: CGFloat = 0.50, base: CGFloat = 0.56    // control reach at the round top and round bottom
    // The neck: a gentle waist on each side, where the narrow top meets the wide base. Tangent kept, so no kink.
    let nx = w * 0.76, ny = bot + (top - bot) * 0.60
    let slope: CGFloat = 1.5, len = (1 + slope * slope).squareRoot()
    let tx = 1 / len, ty = -slope / len              // unit tangent at the neck, pointing down and out
    let hIn: CGFloat = 0.11, hOut: CGFloat = 0.13, rise: CGFloat = 0.35
    let fruit = CGMutablePath()                      // 6 cubic segments, mirror-symmetric
    fruit.move(to: P(s, cx, top))
    fruit.addCurve(to: P(s, cx + nx, ny), control1: P(s, cx + w * cap, top), control2: P(s, cx + nx - tx * hIn, ny - ty * hIn))
    fruit.addCurve(to: P(s, cx + w, wide), control1: P(s, cx + nx + tx * hOut, ny + ty * hOut), control2: P(s, cx + w, wide + (ny - wide) * rise))
    fruit.addCurve(to: P(s, cx, bot), control1: P(s, cx + w, wide - (wide - bot) * base), control2: P(s, cx + w * base, bot))
    fruit.addCurve(to: P(s, cx - w, wide), control1: P(s, cx - w * base, bot), control2: P(s, cx - w, wide - (wide - bot) * base))
    fruit.addCurve(to: P(s, cx - nx, ny), control1: P(s, cx - w, wide + (ny - wide) * rise), control2: P(s, cx - nx - tx * hOut, ny + ty * hOut))
    fruit.addCurve(to: P(s, cx, top), control1: P(s, cx - nx + tx * hIn, ny - ty * hIn), control2: P(s, cx - w * cap, top))
    fruit.closeSubpath()

    c.setLineJoin(.round); c.setLineCap(.round)
    // skin: a band outside the flesh outline only
    c.setStrokeColor(skin); c.setLineWidth(s * rim * 2); c.addPath(fruit); c.strokePath()
    // pale flesh, then the bright-green ring just inside its edge
    c.setFillColor(flesh); c.addPath(fruit); c.fillPath()
    c.saveGState()
    c.addPath(fruit); c.clip()
    c.setStrokeColor(ring); c.setLineWidth(s * band * 2); c.addPath(fruit); c.strokePath()
    c.restoreGState()
    // the pit: one flat disc, 0.22 across, centred at 0.62 from the top
    disc(c, s, cx, 0.38, 0.11, pit)
}


func icon(_ size: Int) -> CGImage {
    canvas(size, size) { c in let s = CGFloat(size); ground(c, s); avocado(c, s) }
}

func text(_ c: CGContext, _ str: String, font: NSFont, color: CGColor, at p: CGPoint) {
    let attr = NSAttributedString(string: str, attributes: [.font: font, .foregroundColor: NSColor(cgColor: color)!])
    c.textPosition = p
    CTLineDraw(CTLineCreateWithAttributedString(attr), c)
}
func heavy(_ size: CGFloat) -> NSFont {
    NSFont(name: "HelveticaNeue-CondensedBlack", size: size) ?? NSFont.systemFont(ofSize: size, weight: .black)
}

let appIcon = icon(1024)
let fm = FileManager.default
if fm.fileExists(atPath: root + "/CaliforniaEats/Resources/Assets.xcassets/AppIcon.appiconset") {
    save(appIcon, "CaliforniaEats/Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png")
}
save(appIcon, "playbook/brand/icon-1024.png")
save(icon(512), "docs/icon-512.png")
save(icon(192), "docs/icon-192.png")
save(icon(180), "docs/apple-touch-icon.png")
save(icon(32), "docs/favicon-32.png")

let count = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "100,000+"
let og = canvas(1200, 630) { c in
    c.setFillColor(blue); c.fill(CGRect(x: 0, y: 0, width: 1200, height: 630))
    c.setFillColor(gold); c.fill(CGRect(x: 72, y: 470, width: 90, height: 12))
    text(c, "CALIFORNIA", font: heavy(120), color: white, at: CGPoint(x: 66, y: 326))
    text(c, "EATS", font: heavy(120), color: gold, at: CGPoint(x: 66, y: 210))
    text(c, "Taquería & dim sum guide · \(count) California restaurants", font: NSFont.systemFont(ofSize: 30, weight: .semibold), color: white, at: CGPoint(x: 70, y: 150))
    text(c, "Free for iPhone and iPad", font: NSFont.systemFont(ofSize: 30, weight: .regular), color: gold, at: CGPoint(x: 70, y: 96))
    c.saveGState(); c.translateBy(x: 760, y: 120); avocado(c, 420); c.restoreGState()
    c.setFillColor(blue2); c.fill(CGRect(x: 0, y: 0, width: 1200, height: 12))
}
save(og, "docs/og.png")
