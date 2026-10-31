import CoreML
import Foundation
import Testing
import CryptoKit

@Suite("Selected local FP32 classifier")
@MainActor
struct SelectedModelTests {
    @Test func bundledModelIsTheVerifiedFP32Checkpoint() throws {
        struct Contract: Decodable {
            let modelResource: String
            let classCount: Int
            let checkpointSHA256: String
            let labelsSHA256: String
        }
        let contractURL = try #require(Bundle.main.url(forResource: "recognition-manifest", withExtension: "json"))
        let contract = try JSONDecoder().decode(Contract.self, from: Data(contentsOf: contractURL))
        let url = try #require(Bundle.main.url(forResource: contract.modelResource, withExtension: "mlmodelc"))
        let configuration = MLModelConfiguration()
        #if targetEnvironment(simulator)
        configuration.computeUnits = .cpuOnly
        #else
        configuration.computeUnits = .all
        #endif
        let model = try MLModel(contentsOf: url, configuration: configuration)
        let image = try #require(model.modelDescription.inputDescriptionsByName["image"]?.imageConstraint)
        #expect(image.pixelsWide == 224 && image.pixelsHigh == 224)
        let logits = try #require(model.modelDescription.outputDescriptionsByName["logits"]?.multiArrayConstraint)
        #expect(logits.shape.map(\.intValue) == [1, contract.classCount])
        #expect(logits.dataType == .float32)
        let metadata = try #require(model.modelDescription.metadata[.creatorDefinedKey] as? [String: String])
        #expect(metadata["checkpoint_sha256"] == contract.checkpointSHA256)
        #expect(metadata["app_labels_sha256"] == contract.labelsSHA256)
        let labelsURL = try #require(Bundle.main.url(forResource: "pokemon_labels", withExtension: "json"))
        let digest = SHA256.hash(data: try Data(contentsOf: labelsURL)).map { String(format: "%02x", $0) }.joined()
        #expect(digest == contract.labelsSHA256)
    }
}
