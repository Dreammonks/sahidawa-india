import request from "supertest";
import app from "../src/app";

jest.mock("../src/repositories/medicine.repository", () => ({
    medicineRepository: {
        list: jest.fn(),
        search: jest.fn(),
        findById: jest.fn(),
    },
}));

import { medicineRepository } from "../src/repositories/medicine.repository";

const repo = medicineRepository as unknown as Record<string, jest.Mock>;

const MEDICINE_ID = "11111111-1111-4111-8111-111111111111";

const medicineFixture = (overrides: Record<string, unknown> = {}) => ({
    id: MEDICINE_ID,
    source: "commercial",
    source_product_code: null,
    brand_name: "Azithral 500 Tablet",
    generic_name: "Azithromycin",
    manufacturer: "Alembic Pharmaceuticals Ltd",
    composition: "Azithromycin (500mg)",
    strength: "500mg",
    dosage_form: "Tablet",
    pack_size: "strip of 5 tablets",
    mrp: 132.36,
    jan_aushadhi_price: null,
    is_cdsco_verified: false,
    cdsco_match_score: 41.2,
    matched_cdsco_product: null,
    matched_cdsco_manufacturer: null,
    updated_at: "2026-09-17T06:00:00Z",
    ...overrides,
});

describe("GET /api/v1/medicines", () => {
    beforeEach(() => {
        jest.clearAllMocks();
        repo.list.mockResolvedValue({ total: 1, medicines: [medicineFixture()] });
        repo.search.mockResolvedValue({
            total: 1,
            medicines: [{ ...medicineFixture(), match_score: 1 }],
        });
    });

    it("lists medicines page by page when there is no search", async () => {
        const res = await request(app).get(
            "/api/v1/medicines?source=janaushadhi&limit=5&offset=10"
        );

        expect(res.status).toBe(200);
        expect(res.body).toEqual({
            status: "ok",
            total: 1,
            limit: 5,
            offset: 10,
            medicines: [medicineFixture()],
        });
        expect(repo.list).toHaveBeenCalledWith({ source: "janaushadhi", limit: 5, offset: 10 });
        expect(repo.search).not.toHaveBeenCalled();
    });

    it("searches by name when a search is given", async () => {
        const res = await request(app).get("/api/v1/medicines?search=azithral");

        expect(res.status).toBe(200);
        expect(res.body.medicines[0].match_score).toBe(1);
        expect(repo.search).toHaveBeenCalledWith({ search: "azithral", limit: 20, offset: 0 });
        expect(repo.list).not.toHaveBeenCalled();
    });

    it.each([
        ["an unknown source", "?source=pharmacy"],
        ["a one-letter search", "?search=a"],
        ["a limit above 100", "?limit=500"],
    ])("rejects %s with 400", async (_label, query) => {
        const res = await request(app).get(`/api/v1/medicines${query}`);

        expect(res.status).toBe(400);
        expect(res.body.status).toBe("invalid");
    });

    it("hides database errors behind a generic 500", async () => {
        repo.list.mockRejectedValue(new Error("connection refused"));

        const res = await request(app).get("/api/v1/medicines");

        expect(res.status).toBe(500);
        expect(res.body).toEqual({
            status: "error",
            error: "Could not load medicines. Please try again.",
        });
    });
});

describe("GET /api/v1/medicines/:id", () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    it("returns one medicine", async () => {
        repo.findById.mockResolvedValue(medicineFixture());

        const res = await request(app).get(`/api/v1/medicines/${MEDICINE_ID}`);

        expect(res.status).toBe(200);
        expect(res.body).toEqual({ status: "ok", medicine: medicineFixture() });
    });

    it("returns 404 for an id that does not exist", async () => {
        repo.findById.mockResolvedValue(null);

        const res = await request(app).get(`/api/v1/medicines/${MEDICINE_ID}`);

        expect(res.status).toBe(404);
        expect(res.body.status).toBe("not_found");
    });

    it("returns 400 for an id that is not a UUID", async () => {
        const res = await request(app).get("/api/v1/medicines/123");

        expect(res.status).toBe(400);
        expect(repo.findById).not.toHaveBeenCalled();
    });
});
