import request from "supertest";
import app from "../src/app";

jest.mock("../src/repositories/productBarcode.repository", () => ({
    productBarcodeRepository: {
        findByGtin: jest.fn(),
        findMedicineById: jest.fn(),
        findMedicineByBarcode: jest.fn(),
        recordUnknown: jest.fn(),
    },
}));

jest.mock("../src/utils/redis", () => ({
    redisClient: {
        isOpen: false,
        get: jest.fn(),
        set: jest.fn(),
    },
}));

import { productBarcodeRepository } from "../src/repositories/productBarcode.repository";
import { redisClient } from "../src/utils/redis";

const repo = productBarcodeRepository as unknown as Record<string, jest.Mock>;
const redis = redisClient as unknown as { isOpen: boolean; get: jest.Mock; set: jest.Mock };

const productFixture = (overrides: Record<string, unknown> = {}) => ({
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
    medicine_id: null,
    data_source: "demo_manual_from_photos",
    source_note: "Brand inferred from ingredient list",
    ...overrides,
});

const medicineFixture = (overrides: Record<string, unknown> = {}) => ({
    id: "11111111-1111-1111-1111-111111111111",
    barcode_id: "8901111111111",
    brand_name: "Augmentin 625 Duo",
    generic_name: "Amoxicillin + Clavulanic Acid",
    manufacturer: "GlaxoSmithKline plc",
    batch_number: "B23059",
    expiry_date: null,
    cdsco_approval_status: "approved",
    is_counterfeit_alert: false,
    is_cdsco_verified: true,
    mrp: "223.00",
    ...overrides,
});

const lookup = (gtin: string) => request(app).get(`/api/v1/products/barcode/${gtin}`);

describe("GET /api/v1/products/barcode/:gtin", () => {
    beforeEach(() => {
        jest.clearAllMocks();
        redis.isOpen = false;
        redis.get.mockResolvedValue(null);
        repo.findByGtin.mockResolvedValue(null);
        repo.findMedicineById.mockResolvedValue(null);
        repo.findMedicineByBarcode.mockResolvedValue(null);
        repo.recordUnknown.mockResolvedValue(undefined);
    });

    it("returns 400 for input that is not a barcode at all", async () => {
        const res = await lookup("B23059");

        expect(res.status).toBe(400);
        expect(res.body.status).toBe("invalid");
        expect(repo.findByGtin).not.toHaveBeenCalled();
        expect(repo.findMedicineByBarcode).not.toHaveBeenCalled();
    });

    it("returns 400 for a bad check digit without looking it up or logging it", async () => {
        const res = await lookup("1234567890123");

        expect(res.status).toBe(400);
        expect(res.body.status).toBe("invalid");
        expect(repo.findByGtin).not.toHaveBeenCalled();
        expect(repo.findMedicineByBarcode).not.toHaveBeenCalled();
        expect(repo.recordUnknown).not.toHaveBeenCalled();
    });

    it("returns an Ayurvedic catalogue product with verification not applicable", async () => {
        repo.findByGtin.mockResolvedValue(productFixture());

        const res = await lookup("8901138511975");

        expect(res.status).toBe(200);
        expect(res.body.status).toBe("found");
        expect(res.body.region).toBe("India");
        expect(res.body.product.product_name).toBe("Liv.52 (Himalaya)");
        expect(res.body.product.category).toBe("ayurvedic");
        expect(res.body.verification.applicable).toBe(false);
        expect(res.body.verification.note).toMatch(/AYUSH/);
        expect(res.body.verification.verified).toBeUndefined();
    });

    it("says medicine verification does not apply to a personal care product", async () => {
        repo.findByGtin.mockResolvedValue(
            productFixture({
                gtin: "4987176319432",
                product_name: "Whisper sanitary pads",
                category: "personal_care",
                regulator: "BIS",
                is_medicine: false,
            })
        );

        const res = await lookup("4987176319432");

        expect(res.status).toBe(200);
        expect(res.body.product.is_medicine).toBe(false);
        expect(res.body.region).toBe("Japan");
        expect(res.body.verification.applicable).toBe(false);
        expect(res.body.verification.note).toMatch(/not a medicine/i);
    });

    it("falls back to medicines.barcode_id for a valid GTIN missing from the catalogue", async () => {
        repo.findMedicineByBarcode.mockResolvedValue(
            medicineFixture({ barcode_id: "8901138511975" })
        );

        const res = await lookup("8901138511975");

        expect(repo.findByGtin).toHaveBeenCalledWith("8901138511975");
        expect(res.body.status).toBe("found");
        expect(res.body.verification.verified).toBe(true);
        expect(repo.recordUnknown).not.toHaveBeenCalled();
    });

    it("attaches the linked medicine when a catalogue row has a medicine_id", async () => {
        repo.findByGtin.mockResolvedValue(
            productFixture({
                category: "allopathic",
                regulator: "CDSCO",
                medicine_id: "11111111-1111-1111-1111-111111111111",
            })
        );
        repo.findMedicineById.mockResolvedValue(medicineFixture());

        const res = await lookup("8901138511975");

        expect(repo.findMedicineById).toHaveBeenCalledWith("11111111-1111-1111-1111-111111111111");
        expect(res.body.medicine.id).toBe("11111111-1111-1111-1111-111111111111");
        expect(res.body.verification.verified).toBe(true);
    });

    it("reports a counterfeit alert instead of calling the medicine unchecked", async () => {
        repo.findByGtin.mockResolvedValue(
            productFixture({
                category: "allopathic",
                regulator: "CDSCO",
                medicine_id: "11111111-1111-1111-1111-111111111111",
            })
        );
        repo.findMedicineById.mockResolvedValue(medicineFixture({ is_counterfeit_alert: true }));

        const res = await lookup("8901138511975");

        expect(res.body.verification.applicable).toBe(true);
        expect(res.body.verification.verified).toBe(false);
        expect(res.body.verification.note).toMatch(/counterfeit or recall alert/i);
    });

    it("records an unknown barcode for review and reports it as unknown", async () => {
        const res = await lookup("4103040895493");

        expect(res.status).toBe(200);
        expect(res.body.status).toBe("unknown");
        expect(res.body.region).toBe("Germany");
        expect(repo.recordUnknown).toHaveBeenCalledWith("4103040895493");
    });

    it("still answers unknown when recording the scan fails", async () => {
        repo.recordUnknown.mockRejectedValue(new Error("rpc missing"));

        const res = await lookup("4103040895493");

        expect(res.status).toBe(200);
        expect(res.body.status).toBe("unknown");
    });

    it("serves a cached found result without querying the database", async () => {
        redis.isOpen = true;
        redis.get.mockResolvedValue(
            JSON.stringify({ status: "found", gtin: "8901138511975", cached: true })
        );

        const res = await lookup("8901138511975");

        expect(res.status).toBe(200);
        expect(res.body.cached).toBe(true);
        expect(repo.findByGtin).not.toHaveBeenCalled();
    });

    it("caches found results for one hour", async () => {
        redis.isOpen = true;
        repo.findByGtin.mockResolvedValue(productFixture());

        await lookup("8901138511975");

        expect(redis.set).toHaveBeenCalledWith(
            "product_barcode:8901138511975",
            expect.any(String),
            { EX: 3600 }
        );
    });

    it("returns a generic 500 when the database lookup throws", async () => {
        repo.findByGtin.mockRejectedValue(new Error("connection refused"));

        const res = await lookup("8901138511975");

        expect(res.status).toBe(500);
        expect(JSON.stringify(res.body)).not.toMatch(/connection refused/);
    });
});
