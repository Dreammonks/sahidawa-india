/**
 * Response shapes for the OpenAPI document.
 *
 * These mirror the repository row types. When a repository's column list
 * changes, change the matching schema here — nothing checks them against
 * each other at build time.
 */

const nullableString = { type: "string", nullable: true } as const;
const nullableNumber = { type: "number", nullable: true } as const;
const nullableBoolean = { type: "boolean", nullable: true } as const;

const medicine = {
    type: "object",
    description: "A medicine from either source. Fields the source does not fill are null.",
    properties: {
        id: { type: "string", format: "uuid" },
        source: { type: "string", enum: ["janaushadhi", "commercial"] },
        source_product_code: nullableString,
        brand_name: nullableString,
        generic_name: { type: "string" },
        manufacturer: nullableString,
        composition: nullableString,
        strength: { ...nullableString, example: "125mg/5ml" },
        dosage_form: nullableString,
        pack_size: nullableString,
        mrp: nullableNumber,
        jan_aushadhi_price: {
            ...nullableNumber,
            description: "Price of the Jan Aushadhi equivalent, when one is linked.",
        },
        is_cdsco_verified: nullableBoolean,
        cdsco_match_score: { ...nullableNumber, description: "0–100, from the pipeline." },
        matched_cdsco_product: nullableString,
        matched_cdsco_manufacturer: nullableString,
        updated_at: { type: "string", format: "date-time" },
    },
} as const;

const drugAlert = {
    type: "object",
    description: "One CDSCO alert, exactly as CDSCO published it.",
    properties: {
        id: { type: "string", format: "uuid" },
        alert_type: {
            type: "string",
            enum: ["nsq", "spurious"],
            description: "nsq = failed a quality test; spurious = found to be fake.",
        },
        product_name: { type: "string" },
        batch_number: nullableString,
        manufacturing_date: { ...nullableString, format: "date" },
        expiry_date: { ...nullableString, format: "date" },
        manufacturer: nullableString,
        reason: { ...nullableString, description: "Why the batch was flagged." },
        remarks: nullableString,
        firm_reply: nullableString,
        reporting_source: nullableString,
        reported_by: nullableString,
        reporting_month: {
            type: "string",
            format: "date",
            description: "First day of the month CDSCO reported it.",
            example: "2026-07-01",
        },
    },
} as const;

const cdscoBrandMatch = {
    type: "object",
    properties: {
        brand_name: { type: "string", example: "DOLO 650" },
        manufacturer: { type: "string", example: "Micro labs Ltd." },
        product_score: { type: "number", description: "Brand similarity, 0–100." },
        manufacturer_score: { type: "number", description: "Manufacturer similarity, 0–100." },
        match_score: { type: "number", description: "0.7 × brand + 0.3 × manufacturer." },
        is_match: {
            type: "boolean",
            description:
                "Compared against match_threshold — see matched_on for which score was used.",
        },
    },
} as const;

const product = {
    type: "object",
    description: "A catalogue row. A product is not always a medicine.",
    properties: {
        gtin: { type: "string", example: "8901138511975" },
        product_name: { type: "string" },
        brand: nullableString,
        manufacturer: nullableString,
        marketed_by: nullableString,
        category: {
            type: "string",
            example: "ayurvedic",
            description: "allopathic, ayurvedic, homeopathic, personal_care, nutraceutical.",
        },
        regulator: { ...nullableString, example: "AYUSH" },
        is_medicine: { type: "boolean" },
        pack_size: nullableString,
        mrp: nullableNumber,
        data_source: nullableString,
        source_note: nullableString,
    },
} as const;

const barcodeMedicine = {
    type: "object",
    nullable: true,
    description: "The medicine linked to this barcode, when there is one.",
    properties: {
        id: { type: "string", format: "uuid" },
        barcode_id: nullableString,
        brand_name: nullableString,
        generic_name: nullableString,
        manufacturer: nullableString,
        batch_number: nullableString,
        expiry_date: { ...nullableString, format: "date" },
        cdsco_approval_status: nullableString,
        is_counterfeit_alert: nullableBoolean,
        is_cdsco_verified: nullableBoolean,
        cdsco_match_score: nullableNumber,
        mrp: nullableNumber,
    },
} as const;

const verification = {
    type: "object",
    description:
        "Whether CDSCO medicine verification applies to this product, and the verdict when it does. " +
        "A medicine carrying a counterfeit alert is reported as not verified, and the note says so.",
    properties: {
        applicable: { type: "boolean" },
        verified: { type: "boolean", description: "Absent when applicable is false." },
        note: { type: "string" },
    },
} as const;

export const schemas = {
    Medicine: medicine,
    MedicineSearchHit: {
        allOf: [
            medicine,
            {
                type: "object",
                properties: {
                    match_score: { type: "number", description: "Search relevance, best first." },
                },
            },
        ],
    },
    DrugAlert: drugAlert,
    CdscoBrandMatch: cdscoBrandMatch,
    Product: product,
    BarcodeMedicine: barcodeMedicine,
    Verification: verification,

    MedicineListResponse: {
        type: "object",
        properties: {
            status: { type: "string", example: "ok" },
            total: { type: "integer", description: "Rows matching the query, not just this page." },
            limit: { type: "integer" },
            offset: { type: "integer" },
            medicines: { type: "array", items: { $ref: "#/components/schemas/MedicineSearchHit" } },
        },
    },
    MedicineResponse: {
        type: "object",
        properties: {
            status: { type: "string", example: "ok" },
            medicine: { $ref: "#/components/schemas/Medicine" },
        },
    },
    DrugAlertListResponse: {
        type: "object",
        properties: {
            status: { type: "string", example: "ok" },
            total: { type: "integer" },
            limit: { type: "integer" },
            offset: { type: "integer" },
            alerts: { type: "array", items: { $ref: "#/components/schemas/DrugAlert" } },
        },
    },
    CdscoBrandResponse: {
        type: "object",
        properties: {
            status: { type: "string", example: "ok" },
            match_threshold: { type: "integer", example: 90 },
            matched_on: {
                type: "string",
                enum: ["brand", "brand_and_manufacturer"],
                description:
                    "Which score is_match used. With no manufacturer the blend tops out at 70, " +
                    "so the brand score is judged on its own.",
            },
            matches: { type: "array", items: { $ref: "#/components/schemas/CdscoBrandMatch" } },
        },
    },
    ProductLookupResponse: {
        oneOf: [
            {
                type: "object",
                title: "found",
                properties: {
                    status: { type: "string", example: "found" },
                    gtin: { type: "string" },
                    region: { ...nullableString, description: "From the GS1 prefix." },
                    product: { $ref: "#/components/schemas/Product" },
                    medicine: { $ref: "#/components/schemas/BarcodeMedicine" },
                    verification: { $ref: "#/components/schemas/Verification" },
                },
            },
            {
                type: "object",
                title: "unknown",
                properties: {
                    status: { type: "string", example: "unknown" },
                    gtin: { type: "string" },
                    region: nullableString,
                    message: { type: "string" },
                },
            },
        ],
    },
    HealthResponse: {
        type: "object",
        properties: {
            status: { type: "string", example: "ok" },
            service: { type: "string", example: "sahidawa-api" },
        },
    },
    ErrorResponse: {
        type: "object",
        properties: {
            status: { type: "string", enum: ["invalid", "error", "not_found"] },
            error: { type: "string", description: "Safe to show a user; details stay in the log." },
        },
    },
};
