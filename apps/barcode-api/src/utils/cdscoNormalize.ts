// A copy of the name cleaning in apps/etl/src/validators/cdsco_validator.py
// (_normalize_text, _normalize_manufacturer). The CDSCO registry is stored
// normalised by that code, so a lookup must normalise the same way or an exact
// brand scores low. Change both together; tests/cdscoNormalize.test.ts pins the output.

// Python's string.punctuation: removed outright, not replaced by a space.
const PUNCTUATION = /[!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]/g;
const DOSE = /\b\d+\s?(mg|ml|mcg|g|gm)\b/g;

const REMOVABLE_TOKENS = new Set([
    "tablet",
    "tablets",
    "tab",
    "capsule",
    "capsules",
    "cap",
    "syrup",
    "suspension",
    "solution",
    "inj",
    "injection",
    "cream",
    "ointment",
    "drops",
    "oral",
    "ip",
    "mg",
    "ml",
    "gm",
    "g",
    "mcg",
]);

const CORPORATE_SUFFIXES = new Set([
    "pvt",
    "pvt.",
    "private",
    "limited",
    "ltd",
    "ltd.",
    "inc",
    "corp",
    "corporation",
    "pharmaceuticals",
    "pharma",
    "labs",
    "laboratories",
    "healthcare",
]);

function tokens(text: string): string[] {
    return text.split(/\s+/).filter(Boolean);
}

export function normalizeBrand(text: string): string {
    const cleaned = text.toLowerCase().replace(PUNCTUATION, "").replace(DOSE, " ");
    return tokens(cleaned)
        .filter((t) => !REMOVABLE_TOKENS.has(t))
        .join(" ");
}

export function normalizeManufacturer(text: string): string {
    const cleaned = text.toLowerCase().replace(PUNCTUATION, "");
    return tokens(cleaned)
        .filter((t) => !CORPORATE_SUFFIXES.has(t))
        .join(" ");
}
