import request from "supertest";
import app from "../src/app";

jest.mock("../src/repositories/cdscoBrand.repository", () => ({
    cdscoBrandRepository: {
        match: jest.fn(),
    },
}));

import { cdscoBrandRepository } from "../src/repositories/cdscoBrand.repository";

const repo = cdscoBrandRepository as unknown as { match: jest.Mock };

describe("GET /api/v1/cdsco-brands", () => {
    beforeEach(() => {
        jest.clearAllMocks();
        repo.match.mockResolvedValue([
            {
                brand_name: "DOLO 650",
                manufacturer: "MICRO LABS LTD",
                product_score: 100,
                manufacturer_score: 95,
                match_score: 98.5,
            },
            {
                brand_name: "DOLOPAR",
                manufacturer: "MICRO LABS LTD",
                product_score: 60,
                manufacturer_score: 95,
                match_score: 70.5,
            },
        ]);
    });

    it("returns the closest registry entries and marks which ones count as a match", async () => {
        const res = await request(app).get(
            "/api/v1/cdsco-brands?brand=dolo%20650&manufacturer=micro%20labs&limit=2"
        );

        expect(res.status).toBe(200);
        expect(res.body).toEqual({
            status: "ok",
            match_threshold: 90,
            matched_on: "brand_and_manufacturer",
            matches: [
                {
                    brand_name: "DOLO 650",
                    manufacturer: "MICRO LABS LTD",
                    product_score: 100,
                    manufacturer_score: 95,
                    match_score: 98.5,
                    is_match: true,
                },
                {
                    brand_name: "DOLOPAR",
                    manufacturer: "MICRO LABS LTD",
                    product_score: 60,
                    manufacturer_score: 95,
                    match_score: 70.5,
                    is_match: false,
                },
            ],
        });
        expect(repo.match).toHaveBeenCalledWith({
            brand: "dolo 650",
            manufacturer: "micro labs",
            limit: 2,
        });
    });

    it("judges a brand-only check on the brand score, since there is no manufacturer to compare", async () => {
        repo.match.mockResolvedValue([
            {
                brand_name: "HAND SANITIZER",
                manufacturer: "SOME FIRM",
                product_score: 100,
                manufacturer_score: 0,
                match_score: 70,
            },
        ]);

        const res = await request(app).get("/api/v1/cdsco-brands?brand=hand%20sanitizer");

        expect(repo.match).toHaveBeenCalledWith({ brand: "hand sanitizer", limit: 5 });
        expect(res.body.matched_on).toBe("brand");
        expect(res.body.matches[0].is_match).toBe(true);
    });

    it.each([
        ["no brand", ""],
        ["a one-letter brand", "?brand=d"],
        ["a limit above 20", "?brand=dolo&limit=21"],
    ])("rejects %s with 400", async (_label, query) => {
        const res = await request(app).get(`/api/v1/cdsco-brands${query}`);

        expect(res.status).toBe(400);
        expect(res.body.status).toBe("invalid");
        expect(repo.match).not.toHaveBeenCalled();
    });
});
