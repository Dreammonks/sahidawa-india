import { isGtinFormat, isValidGtin, gs1PrefixRegion } from "../src/utils/gtin";

describe("isGtinFormat", () => {
    it("accepts digit strings of barcode lengths regardless of check digit", () => {
        expect(isGtinFormat("8901111111111")).toBe(true);
        expect(isGtinFormat("12345678")).toBe(true);
    });

    it("rejects non-digit strings and other lengths", () => {
        expect(isGtinFormat("B23059")).toBe(false);
        expect(isGtinFormat("12345")).toBe(false);
    });
});

// Barcodes read from the photos supplied for the demo.
const PHOTO_BARCODES = [
    "4103040895493",
    "8901138511975",
    "4987176319432",
    "8906037151086",
    "8904188000864",
    "4987176319517",
    "8904455004564",
];

describe("isValidGtin", () => {
    it.each(PHOTO_BARCODES)("accepts real EAN-13 barcode %s", (code) => {
        expect(isValidGtin(code)).toBe(true);
    });

    it("rejects a barcode with a wrong check digit", () => {
        expect(isValidGtin("8901138511974")).toBe(false);
        expect(isValidGtin("1234567890123")).toBe(false);
    });

    it("accepts valid EAN-8, UPC-A and GTIN-14 lengths", () => {
        expect(isValidGtin("96385074")).toBe(true);
        expect(isValidGtin("036000291452")).toBe(true);
        expect(isValidGtin("00012345600012")).toBe(true);
    });

    it("rejects non-digits, empty input and unsupported lengths", () => {
        expect(isValidGtin("")).toBe(false);
        expect(isValidGtin("89011385119A5")).toBe(false);
        expect(isValidGtin("B23059")).toBe(false);
        expect(isValidGtin("123456789")).toBe(false);
    });
});

describe("gs1PrefixRegion", () => {
    it("maps common GS1 prefixes to the issuing region", () => {
        expect(gs1PrefixRegion("8901138511975")).toBe("India");
        expect(gs1PrefixRegion("4103040895493")).toBe("Germany");
        expect(gs1PrefixRegion("4987176319432")).toBe("Japan");
    });

    it("returns null for prefixes outside the known map", () => {
        expect(gs1PrefixRegion("7001234567895")).toBeNull();
    });
});
