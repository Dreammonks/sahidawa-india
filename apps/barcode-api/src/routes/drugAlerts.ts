import { Router, Request, Response } from "express";
import { dataLimiter } from "../middleware/rateLimit";
import {
    drugAlertRepository,
    DrugAlertQuery,
    DrugAlertType,
} from "../repositories/drugAlert.repository";
import logger from "../utils/logger";
import { invalid, Parsed, Query, readPage, readText, SEARCH_FORMAT } from "../utils/queryParams";

const router = Router();

const ALERT_TYPES: DrugAlertType[] = ["nsq", "spurious"];
const MONTH_FORMAT = /^\d{4}-(0[1-9]|1[0-2])$/;
const BATCH_FORMAT = /^[A-Za-z0-9\-/.]{1,50}$/;

function parseQuery(raw: Query): Parsed<DrugAlertQuery> {
    const page = readPage(raw);
    if (!page.ok) return page;
    const query: DrugAlertQuery = { ...page.value };

    const search = readText(raw.search, SEARCH_FORMAT);
    if (search === null) return invalid("search must be 2 to 100 letters, numbers or spaces.");
    if (search !== undefined) query.search = search;

    const batch = readText(raw.batch, BATCH_FORMAT);
    if (batch === null) return invalid("batch must be up to 50 letters, numbers, - / or .");
    if (batch !== undefined) query.batch = batch;

    if (raw.type !== undefined) {
        const type = String(raw.type) as DrugAlertType;
        if (!ALERT_TYPES.includes(type)) return invalid("type must be nsq or spurious.");
        query.type = type;
    }

    const month = readText(raw.month, MONTH_FORMAT);
    if (month === null) return invalid("month must look like 2026-07.");
    if (month !== undefined) query.month = month;

    return { ok: true, value: query };
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
router.get("/", dataLimiter, async (req: Request, res: Response) => {
    const parsed = parseQuery(req.query);
    if (!parsed.ok) {
        res.status(400).json({ status: "invalid", error: parsed.error });
        return;
    }

    try {
        const { total, alerts } = await drugAlertRepository.search(parsed.value);
        res.json({
            status: "ok",
            total,
            limit: parsed.value.limit,
            offset: parsed.value.offset,
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
