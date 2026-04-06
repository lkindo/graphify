import Foundation
import UIKit

protocol Processor {
    func process() -> [String]
}

class DataProcessor: Processor {
    private var items: [String] = []

    init() {}

    func addItem(_ item: String) {
        items.append(item)
    }

    func process() -> [String] {
        return validate(items)
    }

    private func validate(_ data: [String]) -> [String] {
        return data.filter { !$0.isEmpty }
    }
}

struct Config {
    let baseUrl: String
    let timeout: Int
}

func createProcessor() -> DataProcessor {
    return DataProcessor()
}
