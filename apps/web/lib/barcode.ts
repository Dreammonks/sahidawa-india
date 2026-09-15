/**
 * Decide whether scanned or typed text is a product barcode (EAN/UPC/GTIN) rather
 * than a batch number, so it can be routed to the product lookup.
 */

function hasValidGs1CheckDigit(code: string): boolean {
    let sum = 0;
    let weight = 3;
    for (let i = code.length - 2; i >= 0; i--) {
        sum += Number(code[i]) * weight;
        weight = weight === 3 ? 1 : 3;
    }
    return (10 - (sum % 10)) % 10 === Number(code[code.length - 1]);
}

export function isProductBarcode(text: string): boolean {
    const code = text.trim();
    if (!/^\d+$/.test(code)) return false;

    // 12–14 digit numbers are never batch numbers; accept them without the check
    // digit because this project's seed barcodes are not GS1-valid.
    if (code.length >= 12 && code.length <= 14) return true;

    // 8 digits collides with numeric batch numbers, so require a valid EAN-8 check digit.
    return code.length === 8 && hasValidGs1CheckDigit(code);
}

// EAN-13 as printed under the bars: "8 901138 511975", or unbroken. Groups may be
// separated by single spaces only, so phone numbers and prices are not stitched together.
const PRINTED_EAN13 = /(?<!\d)(\d)\s?(\d{6})\s?(\d{6})(?!\d)/g;

/**
 * Pull a GS1-valid EAN-13 out of OCR text. Used when camera or image barcode
 * decoding fails but the digits printed beneath the bars were still read.
 */
export function findProductBarcodeInText(text: string): string | null {
    for (const match of text.matchAll(PRINTED_EAN13)) {
        const code = `${match[1]}${match[2]}${match[3]}`;
        if (hasValidGs1CheckDigit(code)) return code;
    }
    return null;
}
