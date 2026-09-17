import { Router, Request, Response } from "express";
import { alertsLimiter } from "../middleware/rateLimit";
import {
    drugAlertRepository,
    DrugAlertQuery,
    DrugAlertType,
} from "../repositories/drugAlert.repository";
import logger from "../utils/logger";

const router = Router();

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 100;
const MAX_OFFSET = 10_000;
const ALERT_TYPES: DrugAlertType[] = ["nsq", "spurious"];
const MONTH_FORMAT = /^\d{4}-(0[1-9]|1[0-2])$/;
// % is allowed because product names contain it ("Cream 0.1%"); the repository matches it literally.
const SEARCH_FORMAT = /^[\p{L}\p{N} .,&+\-/()'%]{2,100}$/u;
const BATCH_FORMAT = /^[A-Za-z0-9\-/.]{1,50}$/;

type Parsed = { ok: true; query: DrugAlertQuery } | { ok: false; error: string };

function readInteger(raw: unknown, fallback: number, min: number, max: number): number | null {
    if (raw === undefined) return fallback;
    const value = Number(raw);
    return Number.isInteger(value) && value >= min && value <= max ? value : null;
}

function parseQuery(raw: Request["query"]): Parsed {
    const limit = readInteger(raw.limit, DEFAULT_LIMIT, 1, MAX_LIMIT);
    if (limit === null)
        return { ok: false, error: `limit must be a whole number from 1 to ${MAX_LIMIT}.` };

    const offset = readInteger(raw.offset, 0, 0, MAX_OFFSET);
    if (offset === null)
        return { ok: false, error: `offset must be a whole number from 0 to ${MAX_OFFSET}.` };

    const query: DrugAlertQuery = { limit, offset };

    if (raw.search !== undefined) {
        const search = String(raw.search).trim();
        if (!SEARCH_FORMAT.test(search)) {
            return { ok: false, error: "search must be 2 to 100 letters, numbers or spaces." };
        }
        query.search = search;
    }
    if (raw.batch !== undefined) {
        const batch = String(raw.batch).trim();
        if (!BATCH_FORMAT.test(batch)) {
            return { ok: false, error: "batch must be up to 50 letters, numbers, - / or ." };
        }
        query.batch = batch;
    }
    if (raw.type !== undefined) {
        const type = String(raw.type) as DrugAlertType;
        if (!ALERT_TYPES.includes(type))
            return { ok: false, error: "type must be nsq or spurious." };
        query.type = type;
    }
    if (raw.month !== undefined) {
        const month = String(raw.month);
        if (!MONTH_FORMAT.test(month)) return { ok: false, error: "month must look like 2026-07." };
        query.month = month;
    }
    return { ok: true, query };
}

/**
 * @openapi
 * /api/v1/drug-alerts:
 *   get:
 *     summary: CDSCO drug alerts — batches that failed a quality test (nsq) or were found fake (spurious)
 *     parameters:
 *       - { in: query, name: search, schema: { type: string }, description: Part of the product name }
 *       - { in: query, name: batch, schema: { type: string }, description: Exact batch number, any letter case }
 *       - { in: query, name: type, schema: { type: string, enum: [nsq, spurious] } }
 *       - { in: query, name: month, schema: { type: string, example: "2026-07" }, description: Month CDSCO reported it }
 *       - { in: query, name: limit, schema: { type: integer, default: 20, maximum: 100 } }
 *       - { in: query, name: offset, schema: { type: integer, default: 0 } }
 *     responses:
 *       200: { description: "Alerts, newest reporting month first, with the total matching count" }
 *       400: { description: A query parameter is invalid }
 *       500: { description: Lookup failed }
 */
router.get("/", alertsLimiter, async (req: Request, res: Response) => {
    const parsed = parseQuery(req.query);
    if (!parsed.ok) {
        res.status(400).json({ status: "invalid", error: parsed.error });
        return;
    }

    try {
        const { total, alerts } = await drugAlertRepository.search(parsed.query);
        res.json({
            status: "ok",
            total,
            limit: parsed.query.limit,
            offset: parsed.query.offset,
            alerts,
        });
    } catch (err) {
        logger.error({
            message: "Drug alert lookup failed",
            route: "/api/v1/drug-alerts",
            error: err instanceof Error ? err.message : String(err),
        });
        res.status(500).json({
            status: "error",
            error: "Could not load drug alerts. Please try again.",
        });
    }
});

export default router;
