import XCTest
@testable import CaliforniaEats

/// Where launch time goes, on the biggest region file (printed, not asserted: the shared Mac's load varies).
final class LoadTimingTests: XCTestCase {
    func testDecodeVersusPlaceInit() throws {
        let folder = try XCTUnwrap(AppModel.bundledData)
        let index = try JSONDecoder().decode(DataIndex.self, from: Data(contentsOf: folder.appendingPathComponent("index.json")))
        let data = try Data(contentsOf: folder.appendingPathComponent("places-la.json"))
        var t = Date()
        let region = try JSONDecoder().decode(RegionData.self, from: data)
        let decode = Date().timeIntervalSince(t)
        t = Date()
        let places = region.places.map { Place($0, region: region, index: index) }
        let build = Date().timeIntervalSince(t)
        print("LA: \(places.count) places, \(data.count / 1024) KB: decode \(String(format: "%.2f", decode)) s, Place init \(String(format: "%.2f", build)) s")
    }
}
