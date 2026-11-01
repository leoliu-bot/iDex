import Foundation

/// The UI reports the labels actually shipped with the selected model.
enum RecognitionScope {
    private struct Label: Decodable {
        let id: Int
    }

    static let entryIDs: Set<Int> = {
        guard let url = Bundle.main.url(forResource: "pokemon_labels", withExtension: "json"),
              let labels = try? JSONDecoder().decode([Label].self, from: Data(contentsOf: url)) else { return [] }
        return Set(labels.map(\.id))
    }()

    static var speciesIDs: Set<Int> {
        Set(entryIDs.compactMap { PokemonCatalog.shared.pokemon(id: $0)?.nationalID })
    }

    static let confirmableEntryIDs: Set<Int> = {
        struct Contract: Decodable { let confirmedEntryIDs: [Int]? }
        guard let url = Bundle.main.url(forResource: "recognition-manifest", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let contract = try? JSONDecoder().decode(Contract.self, from: data) else { return [] }
        return contract.confirmedEntryIDs.map(Set.init) ?? entryIDs
    }()

    private static let appearanceAliases: [Int: Int] = {
        guard let url = Bundle.main.url(forResource: "appearance-aliases", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let values = try? JSONDecoder().decode([String: Int].self, from: data) else { return [:] }
        return Dictionary(uniqueKeysWithValues: values.compactMap { key, value in Int(key).map { ($0, value) } })
    }()

    static func sameAppearance(as pokemon: Pokemon) -> [Pokemon] {
        let canonical = appearanceAliases[pokemon.id] ?? pokemon.id
        return PokemonCatalog.shared.entries.filter {
            $0.id != pokemon.id && (appearanceAliases[$0.id] ?? $0.id) == canonical
        }
    }
}
