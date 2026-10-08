// California icon concepts (2026-10-07), flat (Nick prefers flat to glossy): A taco · B avocado half · C fish taco with a lime wedge.
// Ground: Pacific blue with one wave line along the bottom. No text, no logos, no flag or seal.
// Usage: swift scripts/icon-concepts.swift   (run from ca-eats/) -> playbook/brand/concepts.png and concept-<x>-1024.png
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

/// A shell taco seen from the side: a half-moon tortilla holding meat, lettuce, salsa and white onion.
func tacoShell(_ c: CGContext, _ s: CGFloat, cx: CGFloat, cy: CGFloat, r: CGFloat, fill: (CGContext, CGFloat) -> Void) {
    // filling sits above the opening; drawn first so the tortilla's front edge overlaps it
    fill(c, s)
    let shell = CGMutablePath()
    shell.addArc(center: P(s, cx, cy), radius: s * r, startAngle: .pi, endAngle: 2 * .pi, clockwise: false)
    shell.closeSubpath()
    c.setFillColor(rgb(0xF2C766)); c.addPath(shell); c.fillPath()
    // the inner back edge of the tortilla, a thin darker band, and a few toasted spots
    let rim = CGMutablePath()
    rim.addArc(center: P(s, cx, cy), radius: s * (r - 0.035), startAngle: .pi, endAngle: 2 * .pi, clockwise: false)
    c.setStrokeColor(rgb(0xD9A441)); c.setLineWidth(s * 0.022); c.addPath(rim); c.strokePath()
    for (x, y, rr) in [(cx - 0.17, cy - 0.10, 0.018), (cx + 0.05, cy - 0.20, 0.02), (cx + 0.19, cy - 0.07, 0.016), (cx - 0.04, cy - 0.12, 0.014)] as [(CGFloat, CGFloat, CGFloat)] {
        disc(c, s, x, y, rr, rgb(0xC98F2E))
    }
}

func tacoFill(_ cx: CGFloat, _ cy: CGFloat, _ r: CGFloat) -> (CGContext, CGFloat) -> Void {
    return { c, s in
        // meat
        let meat = CGMutablePath()
        meat.move(to: P(s, cx - r + 0.03, cy))
        meat.addCurve(to: P(s, cx + r - 0.03, cy), control1: P(s, cx - r * 0.5, cy + 0.16), control2: P(s, cx + r * 0.5, cy + 0.16))
        meat.closeSubpath()
        c.setFillColor(rgb(0x8A4B24)); c.addPath(meat); c.fillPath()
        // lettuce: a scalloped green band
        let let_ = CGMutablePath()
        let_.move(to: P(s, cx - r + 0.02, cy + 0.01))
        let n = 7
        for i in 0..<n {
            let x0 = cx - r + 0.02 + CGFloat(i) * (2 * r - 0.04) / CGFloat(n)
            let x1 = x0 + (2 * r - 0.04) / CGFloat(n)
            let h: CGFloat = 0.10 + (i % 2 == 0 ? 0.035 : 0)
            let_.addQuadCurve(to: P(s, x1, cy + 0.02), control: P(s, (x0 + x1) / 2, cy + h + 0.03))
        }
        let_.addLine(to: P(s, cx + r - 0.02, cy)); let_.addLine(to: P(s, cx - r + 0.02, cy)); let_.closeSubpath()
        c.setFillColor(rgb(0x5DA83A)); c.addPath(let_); c.fillPath()
        // salsa and onion
        for (x, y, rr, col) in [(cx - 0.15, cy + 0.10, 0.04, 0xD7372B), (cx + 0.01, cy + 0.125, 0.044, 0xD7372B), (cx + 0.17, cy + 0.095, 0.038, 0xD7372B),
                               (cx - 0.07, cy + 0.10, 0.026, 0xF7F3E8), (cx + 0.09, cy + 0.095, 0.024, 0xF7F3E8)] as [(CGFloat, CGFloat, CGFloat, UInt32)] {
            disc(c, s, x, y, rr, rgb(col))
        }
    }
}

/// A: the taco
func taco(_ c: CGContext, _ s: CGFloat) {
    tacoShell(c, s, cx: 0.5, cy: 0.58, r: 0.37, fill: tacoFill(0.5, 0.58, 0.37))
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

/// C: a fish taco (battered fish, purple cabbage, crema) with a lime wedge leaning on it
func fishTaco(_ c: CGContext, _ s: CGFloat) {
    let cx: CGFloat = 0.46, cy: CGFloat = 0.58, r: CGFloat = 0.33
    tacoShell(c, s, cx: cx, cy: cy, r: r) { c, s in
        // battered fish: a golden rounded slab
        let fish = CGPath(roundedRect: CGRect(x: s * (cx - r + 0.05), y: s * (cy - 0.02), width: s * (2 * r - 0.10), height: s * 0.10),
                          cornerWidth: s * 0.05, cornerHeight: s * 0.05, transform: nil)
        c.setFillColor(rgb(0xE0A23A)); c.addPath(fish); c.fillPath()
        // purple cabbage shreds
        c.setStrokeColor(rgb(0x8E3E9E)); c.setLineWidth(s * 0.026); c.setLineCap(.round)
        for (x0, y0, x1, y1) in [(cx - 0.20, cy + 0.10, cx - 0.10, cy + 0.15), (cx - 0.06, cy + 0.11, cx + 0.04, cy + 0.16), (cx + 0.08, cy + 0.10, cx + 0.19, cy + 0.14)] as [(CGFloat, CGFloat, CGFloat, CGFloat)] {
            c.move(to: P(s, x0, y0)); c.addLine(to: P(s, x1, y1)); c.strokePath()
        }
        // crema drizzle
        let cr = CGMutablePath()
        cr.move(to: P(s, cx - 0.22, cy + 0.085))
        cr.addCurve(to: P(s, cx + 0.22, cy + 0.085), control1: P(s, cx - 0.10, cy + 0.14), control2: P(s, cx + 0.08, cy + 0.03))
        c.setStrokeColor(rgb(0xF7F3E8)); c.setLineWidth(s * 0.024); c.addPath(cr); c.strokePath()
    }
    // lime wedge, lower right: a quarter circle of rind with pale flesh and segment lines
    let lx: CGFloat = 0.78, ly: CGFloat = 0.33, lr: CGFloat = 0.18
    let rind = CGMutablePath()
    rind.move(to: P(s, lx, ly)); rind.addArc(center: P(s, lx, ly), radius: s * lr, startAngle: .pi * 0.5, endAngle: .pi * 1.05, clockwise: false); rind.closeSubpath()
    var t = CGAffineTransform(translationX: s * lx, y: s * ly).rotated(by: -0.5).translatedBy(x: -s * lx, y: -s * ly)
    c.setFillColor(rgb(0x3F8F2A)); c.addPath(rind.copy(using: &t)!); c.fillPath()
    let flesh = CGMutablePath()
    flesh.move(to: P(s, lx, ly)); flesh.addArc(center: P(s, lx, ly), radius: s * (lr - 0.03), startAngle: .pi * 0.5, endAngle: .pi * 1.05, clockwise: false); flesh.closeSubpath()
    c.setFillColor(rgb(0xC6E57A)); c.addPath(flesh.copy(using: &t)!); c.fillPath()
    c.setStrokeColor(rgb(0xEAF5C4)); c.setLineWidth(s * 0.012)
    for a in [0.66, 0.82] as [CGFloat] {
        let seg = CGMutablePath(); seg.move(to: P(s, lx, ly))
        seg.addLine(to: CGPoint(x: s * (lx + cos(.pi * a) * (lr - 0.035)), y: s * (ly + sin(.pi * a) * (lr - 0.035))))
        c.addPath(seg.copy(using: &t)!); c.strokePath()
    }
}

let concepts: [(String, String, (CGContext, CGFloat) -> Void)] = [("a", "A · Taco", taco), ("b", "B · Avocado half", avocado), ("c", "C · Fish taco + lime", fishTaco)]
func icon(_ size: Int, _ f: (CGContext, CGFloat) -> Void) -> CGImage {
    canvas(size, size) { c in let s = CGFloat(size); ground(c, s); f(c, s) }
}
let sheet = canvas(1060, 3 * 600 + 40) { c in
    c.setFillColor(white); c.fill(CGRect(x: 0, y: 0, width: 1060, height: 3 * 600 + 40))
    for (i, (_, label, f)) in concepts.enumerated() {
        let y0 = CGFloat(3 * 600 + 40 - (i + 1) * 600)
        let mask = CGPath(roundedRect: CGRect(x: 0, y: 0, width: 1, height: 1), cornerWidth: 0.225, cornerHeight: 0.225, transform: nil)
        for (sz, x) in [(512, 40), (180, 600), (60, 840)] {
            let img = icon(sz, f)
            c.saveGState()
            var t = CGAffineTransform(scaleX: CGFloat(sz), y: CGFloat(sz)).translatedBy(x: CGFloat(x) / CGFloat(sz), y: (y0 + 40) / CGFloat(sz))
            c.addPath(mask.copy(using: &t)!); c.clip()
            c.draw(img, in: CGRect(x: CGFloat(x), y: y0 + 40, width: CGFloat(sz), height: CGFloat(sz)))
            c.restoreGState()
        }
        let attr = NSAttributedString(string: label, attributes: [.font: NSFont.systemFont(ofSize: 30, weight: .bold), .foregroundColor: NSColor(cgColor: ink)!])
        c.textPosition = CGPoint(x: 600, y: y0 + 470); CTLineDraw(CTLineCreateWithAttributedString(attr), c)
        let sub = NSAttributedString(string: "512 · 180 · 60 px", attributes: [.font: NSFont.systemFont(ofSize: 22, weight: .regular), .foregroundColor: NSColor(cgColor: ink)!])
        c.textPosition = CGPoint(x: 600, y: y0 + 432); CTLineDraw(CTLineCreateWithAttributedString(sub), c)
    }
}
save(sheet, "playbook/brand/concepts.png")
for (k, _, f) in concepts { save(icon(1024, f), "playbook/brand/concept-\(k)-1024.png") }
