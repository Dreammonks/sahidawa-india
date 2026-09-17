import request from "supertest";
import app from "../src/app";

jest.mock("../src/repositories/drugAlert.repository", () => ({
    drugAlertRepository: {
        search: jest.fn(),
    },
}));

import { drugAlertRepository } from "../src/repositories/drugAlert.repository";

const repo = drugAlertRepository as unknown as { search: jest.Mock };

const alertFixture = (overrides: Record<string, unknown> = {}) => ({
    id: "22222222-2222-2222-2222-222222222222",
    alert_type: "nsq",
    product_name: "Pantoprazole Tablets IP",
    batch_number: "PEP5001",
    manufacturing_date: "Feb-2025",
    expiry_date: "Jan-2027",
    manufacturer: "Finecure Pharmaceuticals Ltd.",
    reason: "Dissolution test",
    remarks: null,
    firm_reply: null,
    reporting_source: "State Lab",
    reported_by: "SDT&RL, Bhubaneswar",
    reporting_month: "2026-07-01",
    ...overrides,
});

const list = (query = "") => request(app).get(`/api/v1/drug-alerts${query}`);

describe("GET /api/v1/drug-alerts", () => {
    beforeEach(() => {
        jest.clearAllMocks();
        repo.search.mockResolvedValue({ total: 1, alerts: [alertFixture()] });
    });

    it("returns the latest alerts with default paging", async () => {
        const res = await list();

        expect(res.status).toBe(200);
        expect(res.body).toEqual({
            status: "ok",
            total: 1,
            limit: 20,
            offset: 0,
            alerts: [alertFixture()],
        });
        expect(repo.search).toHaveBeenCalledWith({ limit: 20, offset: 0 });
    });

    it("passes every filter through", async () => {
        await list("?search=pantoprazole&batch=PEP5001&type=nsq&month=2026-07&limit=10&offset=20");

        expect(repo.search).toHaveBeenCalledWith({
            search: "pantoprazole",
            batch: "PEP5001",
            type: "nsq",
            month: "2026-07",
            limit: 10,
            offset: 20,
        });
    });

    it("accepts a percent sign in a product name search", async () => {
        const res = await list("?search=0.1%25");

        expect(res.status).toBe(200);
        expect(repo.search).toHaveBeenCalledWith({ search: "0.1%", limit: 20, offset: 0 });
    });

    it.each([
        ["an unknown alert type", "?type=recall"],
        ["a month that does not exist", "?month=2026-13"],
        ["a month in the wrong format", "?month=Jul-2026"],
        ["a limit of zero", "?limit=0"],
        ["a limit above 100", "?limit=101"],
        ["a negative offset", "?offset=-1"],
        ["a one-letter search", "?search=a"],
        ["a batch number with symbols", "?batch=PEP%3B5001"],
    ])("rejects %s with 400", async (_label, query) => {
        const res = await list(query);

        expect(res.status).toBe(400);
        expect(res.body.status).toBe("invalid");
        expect(repo.search).not.toHaveBeenCalled();
    });

    it("hides database errors behind a generic 500", async () => {
        repo.search.mockRejectedValue(new Error("relation drug_alerts does not exist"));

        const res = await list();

        expect(res.status).toBe(500);
        expect(res.body).toEqual({
            status: "error",
            error: "Could not load drug alerts. Please try again.",
        });
    });
});
