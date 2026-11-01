import Testing
@testable import iDex

@MainActor
struct FormCatalogTests {
    @Test func alternateFormsHaveStableIdentitiesAndNationalNumbers() throws {
        let catalog = PokemonCatalog.shared
        #expect(catalog.speciesEntries.count == 1025)
        #expect(catalog.additionalFormCount == 554)
        #expect(Set(catalog.entries.map(\.id)).count == catalog.entries.count)
        let alola = try #require(catalog.entries.first { $0.formIdentifier == "ninetales-alola" })
        #expect(alola.id != 38 && alola.nationalID == 38 && alola.number == "038")
        #expect(alola.types == ["ice", "fairy"])
        #expect(alola.stats.first { $0.name == "speed" }?.value == 109)
        #expect(catalog.search("阿罗拉九尾", language: .zhHans).contains { $0.id == alola.id })
        #expect(catalog.search("#038", language: .en).contains { $0.id == alola.id })
        #expect(alola.spokenEntry(in: .zhHans).contains("编号38。"))
        let white = try #require(catalog.entries.first { $0.formIdentifier == "kyurem-white" })
        #expect(white.nationalID == 646 && white.types == ["dragon", "ice"])
        #expect(white.stats.first { $0.name == "special-attack" }?.value == 170)
        #expect(white.chineseDescription.contains("莱希拉姆"))
        #expect(catalog.forms(for: white).first?.id == 646)
    }
}
