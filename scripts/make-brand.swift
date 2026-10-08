// Brand images for California Eats: the app icon (the flat avocado half on Pacific blue that Nick picked on 2026-10-07, concept B
// of scripts/icon-concepts.swift), playbook/brand/, and the site's og.png, favicons and manifest icons.
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

/// The ground: Pacific blue, the sea along the bottom with one lighter wave line.
func ground(_ c: CGContext, _ s: CGFloat) {
    c.setFillColor(blue); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    c.setFillColor(blue2); c.fill(CGRect(x: 0, y: 0, width: s, height: s * 0.17))
    let wave = CGMutablePath()
    wave.move(to: P(s, 0, 0.12))
    for i in 0..<4 {
        let x0 = CGFloat(i) * 0.25
        wave.addCurve(to: P(s, x0 + 0.25, 0.12), control1: P(s, x0 + 0.08, 0.155), control2: P(s, x0 + 0.17, 0.085))
    }
    c.setStrokeColor(rgb(0x5582B4)); c.setLineWidth(s * 0.02); c.setLineCap(.round); c.addPath(wave); c.strokePath()
}

/// B: an avocado half: dark skin rim, pale flesh shading to green, round brown pit
func avocado(_ c: CGContext, _ s: CGFloat) {
    func pear(_ inset: CGFloat) -> CGPath {
        let p = CGMutablePath()   // a pear outline, wide at the bottom, tilted slightly
        let cx: CGFloat = 0.5, top: CGFloat = 0.90 - inset, bot: CGFloat = 0.21 + inset, w: CGFloat = 0.29 - inset
        p.move(to: P(s, cx, top))
        p.addCurve(to: P(s, cx + w, bot + 0.22), control1: P(s, cx + w * 0.55, top), control2: P(s, cx + w * 0.62, bot + 0.40))
        p.addCurve(to: P(s, cx, bot), control1: P(s, cx + w * 1.18, bot + 0.08), control2: P(s, cx + w * 0.55, bot))
        p.addCurve(to: P(s, cx - w, bot + 0.22), control1: P(s, cx - w * 0.55, bot), control2: P(s, cx - w * 1.18, bot + 0.08))
        p.addCurve(to: P(s, cx, top), control1: P(s, cx - w * 0.62, bot + 0.40), control2: P(s, cx - w * 0.55, top))
        p.closeSubpath()
        var t = CGAffineTransform(translationX: s * 0.5, y: s * 0.5).rotated(by: -0.28).translatedBy(x: -s * 0.5, y: -s * 0.5)
        return p.copy(using: &t)!
    }
    c.setFillColor(rgb(0x2F4F1C)); c.addPath(pear(0)); c.fillPath()
    c.setFillColor(rgb(0x9CC94F)); c.addPath(pear(0.03)); c.fillPath()
    c.setFillColor(rgb(0xE4EC9A)); c.addPath(pear(0.075)); c.fillPath()
    // pit in the wide lower half (after the tilt)
    disc(c, s, 0.545, 0.42, 0.11, rgb(0x7A4A26))
    disc(c, s, 0.515, 0.45, 0.034, rgb(0x9C6537))
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
