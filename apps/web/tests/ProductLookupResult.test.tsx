import { renderToStaticMarkup } from "react-dom/server";

import { ProductLookupResult } from "../components/scanner/results/ProductLookupResult";
import type { ProductLookupResponse } from "../lib/api/products";

const noop = () => {};

const ayurvedic: ProductLookupResponse = {
    status: "found",
    gtin: "8901138511975",
    region: "India",
    product: {
        gtin: "8901138511975",
        product_name: "Liv.52 (Himalaya)",
        brand: "Himalaya",
        manufacturer: null,
        marketed_by: "Himalaya Wellness Company",
        category: "ayurvedic",
        regulator: "AYUSH",
        is_medicine: true,
        pack_size: "100 tablets",
        mrp: "215.00",
        data_source: "demo_manual_from_photos",
        source_note: "Brand inferred from ingredient list",
    },
    medicine: null,
    verification: {
        applicable: false,
        note: "Licensed under AYUSH. The CDSCO brand registry does not cover it.",
    },
};

function render(result: ProductLookupResponse, labelInfo?: { batch?: string; expiry?: string }) {
    return renderToStaticMarkup(
        <ProductLookupResult
            result={result}
            labelInfo={labelInfo}
            onScanAgain={noop}
            onShare={noop}
            shareLabel="Share"
        />
    );
}

describe("ProductLookupResult", () => {
    it("shows the product, its category, regulator and why verification does not apply", () => {
        const markup = render(ayurvedic);

        expect(markup).toContain("Liv.52 (Himalaya)");
        expect(markup).toContain("Ayurvedic");
        expect(markup).toContain("AYUSH");
        expect(markup).toContain("Himalaya Wellness Company");
        expect(markup).toContain("215.00");
        expect(markup).toContain("Verification not applicable");
        expect(markup).toContain("CDSCO brand registry does not cover it");
    });

    it("flags demo catalogue rows as not coming from an official source", () => {
        expect(render(ayurvedic)).toContain("Demo catalogue entry");
    });

    it("marks non-medicine products clearly", () => {
        const markup = render({
            ...ayurvedic,
            product: {
                ...ayurvedic.product,
                product_name: "Whisper sanitary pads",
                category: "personal_care",
                regulator: "BIS",
                is_medicine: false,
            },
        });

        expect(markup).toContain("Personal care");
        expect(markup).toContain("Not a medicine");
    });

    it("shows a verified verdict when a linked CDSCO medicine is verified", () => {
        const markup = render({
            ...ayurvedic,
            product: {
                ...ayurvedic.product,
                category: "allopathic",
                regulator: "CDSCO",
                data_source: "medicines",
            },
            verification: {
                applicable: true,
                verified: true,
                note: "Matched against the CDSCO brand registry.",
            },
        });

        expect(markup).toContain("CDSCO verified");
        expect(markup).not.toContain("Demo catalogue entry");
    });

    it("shows batch and expiry read from the label", () => {
        const markup = render(ayurvedic, { batch: "ENC26014", expiry: "07/2027" });

        expect(markup).toContain("ENC26014");
        expect(markup).toContain("07/2027");
    });

    it("explains an unknown barcode and that it was logged", () => {
        const markup = render({
            status: "unknown",
            gtin: "4103040895493",
            region: "Germany",
            message:
                "This barcode is not in SahiDawa's database yet. It has been logged for review.",
        });

        expect(markup).toContain("4103040895493");
        expect(markup).toContain("Not in SahiDawa");
        expect(markup).toContain("GS1 Germany");
        expect(markup).toContain("logged for review");
    });
});
