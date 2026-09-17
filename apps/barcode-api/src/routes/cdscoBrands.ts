import { Router, Request, Response } from "express";
import { dataLimiter } from "../middleware/rateLimit";
import { cdscoBrandRepository, CdscoBrandQuery } from "../repositories/cdscoBrand.repository";
import logger from "../utils/logger";
import { invalid, Parsed, Query, readInteger, readText, SEARCH_FORMAT } from "../utils/queryParams";

const router = Router();

// Same rule the pipeline uses to mark a medicine CDSCO-verified (cdsco_validator.py MATCH_THRESHOLD).
const MATCH_THRESHOLD = 90;
const DEFAULT_MATCHES = 5;
const MAX_MATCHES = 20;

function parseQuery(raw: Query): Parsed<CdscoBrandQuery> {
    const brand = readText(raw.brand, SEARCH_FORMAT);
    if (!brand) return invalid("brand is required: 2 to 100 letters, numbers or spaces.");

    const limit = readInteger(raw.limit, DEFAULT_MATCHES, 1, MAX_MATCHES);
    if (limit === null) return invalid(`limit must be a whole number from 1 to ${MAX_MATCHES}.`);

    const query: CdscoBrandQuery = { brand, limit };
    const manufacturer = readText(raw.manufacturer, SEARCH_FORMAT);
    if (manufacturer === null)
        return invalid("manufacturer must be 2 to 100 letters, numbers or spaces.");
    if (manufacturer !== undefined) query.manufacturer = manufacturer;

    return { ok: true, value: query };
}

/**
 * @openapi
 * /api/v1/cdsco-brands:
 *   get:
 *     summary: Check a brand against the CDSCO brand registry
 *     description: >
 *       Returns the closest registry entries, best first. match_score blends brand
 *       similarity (70%) and manufacturer similarity (30%). is_match compares match_score
 *       to match_threshold, or product_score when no manufacturer is given (matched_on says which).
 *     parameters:
 *       - { in: query, name: brand, required: true, schema: { type: string } }
 *       - { in: query, name: manufacturer, schema: { type: string } }
 *       - { in: query, name: limit, schema: { type: integer, default: 5, maximum: 20 } }
 */
router.get("/", dataLimiter, async (req: Request, res: Response) => {
    const parsed = parseQuery(req.query);
    if (!parsed.ok) {
        res.status(400).json({ status: "invalid", error: parsed.error });
        return;
    }

    // match_score gives the manufacturer 30%. With no manufacturer to compare it
    // tops out at 70, so a brand-only check is judged on the brand score alone.
    const hasManufacturer = parsed.value.manufacturer !== undefined;

    try {
        const matches = await cdscoBrandRepository.match(parsed.value);
        res.json({
            status: "ok",
            match_threshold: MATCH_THRESHOLD,
            matched_on: hasManufacturer ? "brand_and_manufacturer" : "brand",
            matches: matches.map((m) => ({
                ...m,
                is_match: (hasManufacturer ? m.match_score : m.product_score) >= MATCH_THRESHOLD,
            })),
        });
    } catch (err) {
        logger.error({
            message: "CDSCO brand lookup failed",
            route: "/api/v1/cdsco-brands",
            error: err instanceof Error ? err.message : String(err),
        });
        res.status(500).json({
            status: "error",
            error: "Could not check the CDSCO registry. Please try again.",
        });
    }
});

export default router;
