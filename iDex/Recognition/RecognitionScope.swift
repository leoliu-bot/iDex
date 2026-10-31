import Foundation

/// The UI reports the labels actually shipped with the selected model.
enum RecognitionScope {
    private struct Label: Decodable {
        let id: Int
    }

    static let speciesIDs: Set<Int> = {
        guard let url = Bundle.main.url(forResource: "pokemon_labels", withExtension: "json"),
              let labels = try? JSONDecoder().decode([Label].self, from: Data(contentsOf: url)) else { return [] }
        return Set(labels.map(\.id))
    }()
}
