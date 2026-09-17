import { normalizeBrand, normalizeManufacturer } from "../src/utils/cdscoNormalize";

// Expected values are the outputs of apps/etl/src/validators/cdsco_validator.py
// (_normalize_text and _normalize_manufacturer). The registry is stored
// normalised by that code, so the API must produce identical text.
describe("normalizeBrand", () => {
    it.each([
        ["Dolo 650 Tablet", "dolo 650"],
        ["DOLO-650", "dolo650"],
        ["Crocin 500 mg Tablets", "crocin"],
        ["Paracetamol 650mg", "paracetamol"],
        ["Hand Sanitizer", "hand sanitizer"],
        ["Rosuvas F 20 Tablets", "rosuvas f 20"],
    ])("%s → %s", (input, expected) => {
        expect(normalizeBrand(input)).toBe(expected);
    });
});

describe("normalizeManufacturer", () => {
    it.each([
        ["Micro labs Ltd.", "micro"],
        ["micro labs", "micro"],
        ["Sun Pharmaceutical Industries Ltd", "sun pharmaceutical industries"],
        ["GlaxoSmithKline Pharmaceuticals Pvt. Ltd", "glaxosmithkline"],
        ["Cipla Limited", "cipla"],
    ])("%s → %s", (input, expected) => {
        expect(normalizeManufacturer(input)).toBe(expected);
    });
});
