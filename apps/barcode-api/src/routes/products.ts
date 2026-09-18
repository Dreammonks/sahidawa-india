import { Router, Request, Response } from "express";
import { barcodeLimiter } from "../middleware/rateLimit";
import { productLookupService } from "../services/productLookup.service";
import { isGtinFormat } from "../utils/gtin";
import logger from "../utils/logger";

const router = Router();

/**
 * @openapi
 * /api/v1/products/barcode/{gtin}:
 *   get:
 *     tags:
 *       - Medicine Scanner
 *     summary: Look up a product by its printed barcode
 *     description: >
 *       Resolves an EAN-8, UPC-A, EAN-13 or GTIN-14 barcode to a product. Checks the
 *       product catalogue, then medicines.barcode_id. Unknown barcodes are logged for
 *       review. The response states whether CDSCO medicine verification applies to
 *       the product category (e.g. not for AYUSH or personal care products).
 *     parameters:
 *       - in: path
 *         name: gtin
 *         required: true
 *         schema:
 *           type: string
 *           example: "8901138511975"
 *     responses:
 *       200:
 *         description: Product found, or barcode unknown (status field distinguishes)
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ProductLookupResponse'
 *       400:
 *         description: Not a barcode (wrong length or non-digits), or a bad check digit
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       500:
 *         description: Lookup failed
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 */
router.get("/barcode/:gtin", barcodeLimiter, async (req: Request, res: Response) => {
    const gtin = String(req.params.gtin ?? "").trim();

    if (!isGtinFormat(gtin)) {
        res.status(400).json({
            status: "invalid",
            gtin,
            error: "Not a product barcode. Expected 8, 12, 13 or 14 digits.",
        });
        return;
    }

    try {
        const result = await productLookupService.lookupByBarcode(gtin);
        res.status(result.status === "invalid" ? 400 : 200).json(result);
    } catch (err) {
        logger.error({
            message: "Product barcode lookup failed",
            route: "/api/v1/products/barcode",
            error: err instanceof Error ? err.message : String(err),
        });
        res.status(500).json({
            status: "error",
            error: "Product lookup failed. Please try again.",
        });
    }
});

export default router;
