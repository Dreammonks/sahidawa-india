import { findProductBarcodeInText, isProductBarcode } from "../lib/barcode";

describe("findProductBarcodeInText", () => {
    it("finds the human-readable digits printed under a barcode, split into groups", () => {
        expect(findProductBarcodeInText("SAI IND-5060781\n8 901138 511975 >\nRs.215.00")).toBe(
            "8901138511975"
        );
        expect(findProductBarcodeInText("4 987176 319432")).toBe("4987176319432");
    });

    it("finds an unbroken 13 digit code", () => {
        expect(findProductBarcodeInText("barcode 8904455004564 end")).toBe("8904455004564");
    });

    it("ignores digit runs whose check digit is wrong (likely OCR misreads)", () => {
        expect(findProductBarcodeInText("8 901138 511974")).toBeNull();
    });

    it("does not stitch unrelated numbers such as phone numbers and prices together", () => {
        expect(findProductBarcodeInText("Ph. No.: 0120-4016500\nMRP 666.48")).toBeNull();
        expect(findProductBarcodeInText("no digits here")).toBeNull();
    });
});

describe("isProductBarcode", () => {
    it.each([
        "4103040895493",
        "8901138511975",
        "4987176319432",
        "8906037151086",
        "8904188000864",
        "4987176319517",
        "8904455004564",
    ])("treats real EAN-13 pack barcode %s as a product barcode", (code) => {
        expect(isProductBarcode(code)).toBe(true);
    });

    it("treats 12, 13 and 14 digit codes as barcodes even with a non-GS1 check digit", () => {
        // Seed data barcodes in this project do not carry valid check digits.
        expect(isProductBarcode("8901111111111")).toBe(true);
        expect(isProductBarcode("036000291452")).toBe(true);
        expect(isProductBarcode("00012345600012")).toBe(true);
    });

    it("only treats 8 digit codes as barcodes when the check digit is valid", () => {
        expect(isProductBarcode("96385074")).toBe(true);
        // 8-digit numeric batch number printed on the Liv.52 label
        expect(isProductBarcode("11250460")).toBe(false);
    });

    it("leaves batch numbers and other text to the batch verification flow", () => {
        expect(isProductBarcode("B23059")).toBe(false);
        expect(isProductBarcode("ENC26014")).toBe(false);
        expect(isProductBarcode("12345")).toBe(false);
        expect(isProductBarcode("")).toBe(false);
    });

    it("ignores surrounding whitespace", () => {
        expect(isProductBarcode(" 8901138511975 ")).toBe(true);
    });
});
