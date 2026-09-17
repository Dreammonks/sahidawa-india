import dotenv from "dotenv";

dotenv.config();

import app from "./app";
import logger from "./utils/logger";
import { connectRedis } from "./utils/redis";

const PORT = Number(process.env.PORT ?? 4100);

async function start(): Promise<void> {
    // Redis only caches lookups; the service answers correctly without it.
    await connectRedis().catch((err: unknown) => {
        logger.warn({ message: "Redis unavailable, continuing without cache", error: String(err) });
    });

    app.listen(PORT, () => {
        logger.info({ message: `SahiDawa API listening on port ${PORT}` });
    });
}

start().catch((err: unknown) => {
    logger.error({ message: "Failed to start", error: String(err) });
    process.exit(1);
});
