import { Router, Request, Response } from "express";
import { dataLimiter } from "../middleware/rateLimit";
import {
    medicineRepository,
    MedicineListQuery,
    MedicineSource,
} from "../repositories/medicine.repository";
import logger from "../utils/logger";
import {
    invalid,
    Parsed,
    Query,
    readPage,
    readText,
    SEARCH_FORMAT,
    UUID_FORMAT,
} from "../utils/queryParams";

const router = Router();

const SOURCES: MedicineSource[] = ["janaushadhi", "commercial"];

type ListRequest = MedicineListQuery & { search?: string };

function parseList(raw: Query): Parsed<ListRequest> {
    const page = readPage(raw);
    if (!page.ok) return page;
    const query: ListRequest = { ...page.value };

    const search = readText(raw.search, SEARCH_FORMAT);
    if (search === null) return invalid("search must be 2 to 100 letters, numbers or spaces.");
    if (search !== undefined) query.search = search;

    if (raw.source !== undefined) {
        const source = String(raw.source) as MedicineSource;
        if (!SOURCES.includes(source)) return invalid("source must be janaushadhi or commercial.");
        query.source = source;
    }
    return { ok: true, value: query };
}

function serverError(res: Response, route: string, err: unknown) {
    logger.error({
        message: "Medicine lookup failed",
        route,
        error: err instanceof Error ? err.message : String(err),
    });
    res.status(500).json({ status: "error", error: "Could not load medicines. Please try again." });
}

/**
 * @openapi
 * /api/v1/medicines:
 *   get:
 *     summary: List medicines, or search them by brand, generic name or ingredient
 *     parameters:
 *       - { in: query, name: search, schema: { type: string }, description: "Name or ingredient; small typos are tolerated. Results come best match first." }
 *       - { in: query, name: source, schema: { type: string, enum: [janaushadhi, commercial] } }
 *       - { in: query, name: limit, schema: { type: integer, default: 20, maximum: 100 } }
 *       - { in: query, name: offset, schema: { type: integer, default: 0 } }
 */
router.get("/", dataLimiter, async (req: Request, res: Response) => {
    const parsed = parseList(req.query);
    if (!parsed.ok) {
        res.status(400).json({ status: "invalid", error: parsed.error });
        return;
    }
    const { search, ...listQuery } = parsed.value;

    try {
        const page = search
            ? await medicineRepository.search({ ...listQuery, search })
            : await medicineRepository.list(listQuery);
        res.json({
            status: "ok",
            total: page.total,
            limit: listQuery.limit,
            offset: listQuery.offset,
            medicines: page.medicines,
        });
    } catch (err) {
        serverError(res, "/api/v1/medicines", err);
    }
});

/**
 * @openapi
 * /api/v1/medicines/{id}:
 *   get:
 *     summary: One medicine, including its Jan Aushadhi equivalent price when one is known
 */
router.get("/:id", dataLimiter, async (req: Request, res: Response) => {
    const id = String(req.params.id ?? "");
    if (!UUID_FORMAT.test(id)) {
        res.status(400).json({ status: "invalid", error: "id must be a medicine id (UUID)." });
        return;
    }

    try {
        const medicine = await medicineRepository.findById(id);
        if (!medicine) {
            res.status(404).json({ status: "not_found", error: "No medicine with this id." });
            return;
        }
        res.json({ status: "ok", medicine });
    } catch (err) {
        serverError(res, "/api/v1/medicines/:id", err);
    }
});

export default router;
