/**
 * GS1 barcode (GTIN) helpers for EAN-8, UPC-A, EAN-13 and GTIN-14.
 */

const GTIN_LENGTHS = new Set([8, 12, 13, 14]);

export function isGtinFormat(code: string): boolean {
    return /^\d+$/.test(code) && GTIN_LENGTHS.has(code.length);
}

export function isValidGtin(code: string): boolean {
    if (!isGtinFormat(code)) return false;

    const digits = code.split("").map(Number);
    const checkDigit = digits.pop() as number;
    // GS1 mod-10: weights alternate 3,1,3… starting from the digit next to the check digit.
    const sum = digits
        .reverse()
        .reduce((total, digit, index) => total + digit * (index % 2 === 0 ? 3 : 1), 0);

    return (10 - (sum % 10)) % 10 === checkDigit;
}

interface PrefixRange {
    from: number;
    to: number;
    region: string;
}

// The prefix names the GS1 member organisation that issued the number, not the
// country of manufacture.
const GS1_PREFIX_RANGES: PrefixRange[] = [
    { from: 0, to: 139, region: "USA / Canada" },
    { from: 400, to: 440, region: "Germany" },
    { from: 450, to: 459, region: "Japan" },
    { from: 490, to: 499, region: "Japan" },
    { from: 500, to: 509, region: "United Kingdom" },
    { from: 690, to: 699, region: "China" },
    { from: 890, to: 890, region: "India" },
];

export function gs1PrefixRegion(code: string): string | null {
    // UPC-A (12 digits) is an EAN-13 with an implicit leading zero.
    const normalized = code.length === 12 ? `0${code}` : code;
    const offset = normalized.length === 14 ? 1 : 0;
    const prefix = Number(normalized.slice(offset, offset + 3));
    if (Number.isNaN(prefix)) return null;

    return GS1_PREFIX_RANGES.find((r) => prefix >= r.from && prefix <= r.to)?.region ?? null;
}
