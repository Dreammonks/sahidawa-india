import express, { NextFunction, Request, Response } from "express";
import cors from "cors";
import helmet from "helmet";
import productsRouter from "./routes/products";
import drugAlertsRouter from "./routes/drugAlerts";
import medicinesRouter from "./routes/medicines";
import cdscoBrandsRouter from "./routes/cdscoBrands";
import { docsRouter, openapiSpec } from "./docs";
import logger from "./utils/logger";

const app = express();

// Behind a proxy or load balancer the client address arrives in X-Forwarded-For.
// The rate limiter keys on it, so an unset value would put every caller in one bucket.
app.set("trust proxy", Number(process.env.TRUST_PROXY_HOPS ?? 1));

app.use(helmet());

const allowedOrigins = (process.env.ALLOWED_ORIGINS ?? "")
    .split(",")
    .map((o) => o.trim())
    .filter(Boolean);

app.use(
    cors({
        origin: allowedOrigins.length > 0 ? allowedOrigins : false,
        methods: ["GET"],
        maxAge: 86400,
    })
);

app.use(express.json({ limit: "16kb" }));

/**
 * @openapi
 * /health:
 *   get:
 *     tags:
 *       - Service
 *     summary: Is the service up
 *     responses:
 *       200:
 *         description: The service is running
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/HealthResponse'
 */
app.get("/health", (_req: Request, res: Response) => {
    res.json({ status: "ok", service: "sahidawa-api" });
});

// The document itself, for generating clients; the page that reads it is /api/docs.
app.get("/api/docs.json", (_req: Request, res: Response) => {
    res.json(openapiSpec);
});

app.use("/api/docs", docsRouter);

app.use("/api/v1/products", productsRouter);
app.use("/api/v1/drug-alerts", drugAlertsRouter);
app.use("/api/v1/medicines", medicinesRouter);
app.use("/api/v1/cdsco-brands", cdscoBrandsRouter);

app.use((req: Request, res: Response) => {
    res.status(404).json({ status: "error", error: `No route for ${req.method} ${req.path}` });
});

app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
    logger.error({ message: "Unhandled error", error: err.message });
    res.status(500).json({ status: "error", error: "Something went wrong. Please try again." });
});

export default app;
