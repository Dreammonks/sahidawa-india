import { medicineRepository } from "../src/repositories/medicine.repository";
import { supabase } from "../src/db/client";

jest.mock("../src/db/client", () => ({
    supabase: { from: jest.fn() },
}));

type Result = { data?: unknown; error?: unknown; count?: number | null };

const rangeResult: { current: Result } = { current: {} };
const countResult: { current: Result } = { current: {} };
const headCalls: boolean[] = [];

/**
 * Enough of the Supabase query builder for `list`: a chain that ends either in
 * `.range(...)` or in awaiting the builder itself (the head count).
 */
function mockSupabase() {
    (supabase.from as jest.Mock).mockImplementation(() => ({
        select: (_columns: string, options: { head?: boolean }) => {
            headCalls.push(options.head === true);
            const builder: Record<string, unknown> = {};
            builder.eq = () => builder;
            builder.order = () => builder;
            builder.range = () => Promise.resolve(rangeResult.current);
            builder.then = (resolve: (value: Result) => unknown) => resolve(countResult.current);
            return builder;
        },
    }));
}

describe("medicineRepository.list", () => {
    beforeEach(() => {
        headCalls.length = 0;
        mockSupabase();
    });

    it("returns the page and the total when the range holds rows", async () => {
        rangeResult.current = { data: [{ id: "a" }], error: null, count: 7439 };

        const page = await medicineRepository.list({ limit: 10, offset: 0 });

        expect(page).toEqual({ total: 7439, medicines: [{ id: "a" }] });
        expect(headCalls).toEqual([false]);
    });

    it("returns an empty page, not an error, when the offset is past the last row", async () => {
        rangeResult.current = {
            data: null,
            error: {
                code: "PGRST103",
                message: "Requested range not satisfiable",
                details: "An offset of 7500 was requested, but there are only 7439 rows.",
            },
            count: null,
        };
        countResult.current = { count: 7439, error: null };

        const page = await medicineRepository.list({ limit: 10, offset: 7500 });

        expect(page).toEqual({ total: 7439, medicines: [] });
        expect(headCalls).toEqual([false, true]);
    });

    it("still throws any other database error", async () => {
        rangeResult.current = {
            data: null,
            error: { code: "PGRST116", message: "something else went wrong" },
            count: null,
        };

        await expect(medicineRepository.list({ limit: 10, offset: 0 })).rejects.toMatchObject({
            code: "PGRST116",
        });
    });
});
