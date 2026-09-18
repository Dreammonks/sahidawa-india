import path from "path";
import { Router, Request, Response, NextFunction } from "express";
import swaggerJsdoc from "swagger-jsdoc";
import swaggerUi from "swagger-ui-express";
import { schemas } from "./schemas";

// Routes are scanned from source in development and from the build in production,
// so both globs are listed; swagger-jsdoc ignores the one that matches nothing.
const routeFiles = ["../routes/*.ts", "../routes/*.js", "../app.ts", "../app.js"].map((p) =>
    path.join(__dirname, p)
);

export const openapiSpec = swaggerJsdoc({
    definition: {
        openapi: "3.0.3",
        info: {
            title: "SahiDawa API",
            version: "1.0.0",
            description:
                "Medicine, barcode and CDSCO data for services that build on SahiDawa. " +
                "Every endpoint is read-only; nothing here reads the database directly.",
        },
        // Relative, so requests go to whatever host served this page — localhost,
        // a tunnel or a deployment — instead of a hard-coded one.
        servers: [{ url: "/", description: "This server" }],
        tags: [
            { name: "Medicine Scanner", description: "Barcode lookup" },
            { name: "Medicines", description: "Search and read medicine data" },
            { name: "Drug Alerts", description: "CDSCO quality and counterfeit alerts" },
            { name: "CDSCO Registry", description: "Check a brand against the registry" },
            { name: "Service", description: "Liveness" },
        ],
        components: { schemas },
    },
    apis: routeFiles,
});

// Swagger UI ships inline styles and an inline init script, which the strict
// Content-Security-Policy set for the rest of the service blocks. Relaxing it
// for this one path keeps the API's own policy untouched; the page renders no
// user data and takes no input beyond the query parameters it sends back here.
function docsCsp(_req: Request, res: Response, next: NextFunction) {
    res.setHeader(
        "Content-Security-Policy",
        [
            "default-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "script-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "connect-src 'self'",
        ].join("; ")
    );
    next();
}

const uiOptions: swaggerUi.SwaggerUiOptions = {
    customSiteTitle: "SahiDawa API",
    swaggerOptions: {
        docExpansion: "list",
        displayRequestDuration: true,
        tryItOutEnabled: true,
        // ngrok answers browser-looking requests with an interstitial page. Without
        // this header a "Try it out" call gets that HTML instead of the JSON.
        requestInterceptor: (req: { headers: Record<string, string> }) => {
            req.headers["ngrok-skip-browser-warning"] = "true";
            return req;
        },
    },
};

export const docsRouter = Router();

docsRouter.use(docsCsp);
docsRouter.use(swaggerUi.serve);
docsRouter.get("/", swaggerUi.setup(openapiSpec, uiOptions));
