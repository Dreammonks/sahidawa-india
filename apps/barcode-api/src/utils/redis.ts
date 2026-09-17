import Redis from "ioredis";
import logger from "./logger";

const redisUrl = process.env.REDIS_URL;

function isValidUrl(str: string): boolean {
    try {
        new URL(str);
        return true;
    } catch {
        return false;
    }
}

// lazyConnect: nothing connects until connectRedis() runs at startup.
const client =
    redisUrl && isValidUrl(redisUrl)
        ? new Redis(redisUrl, { lazyConnect: true, maxRetriesPerRequest: null })
        : new Redis({ lazyConnect: true, maxRetriesPerRequest: null });

client.on("error", (err) => {
    logger.error("Redis Client Error", err);
});

client.on("connect", () => {
    logger.info("Redis Client Connected successfully");
});

/**
 * The parts of Redis this service uses: the barcode lookup cache and the rate
 * limiter's shared counters.
 */
export const redisClient = {
    get isOpen() {
        return client.status === "ready";
    },

    get: (key: string) => client.get(key),

    set: (key: string, value: string, options: { EX: number }) =>
        client.set(key, value, "EX", options.EX),

    // rate-limit-redis sends raw commands.
    sendCommand: (args: string[]) =>
        client.call(args[0], ...args.slice(1)) as Promise<
            boolean | number | string | (boolean | number | string)[]
        >,
};

export async function connectRedis(): Promise<void> {
    if (!redisUrl) {
        logger.warn("REDIS_URL is not set. Redis caching will be unavailable.");
        return;
    }
    if (!redisClient.isOpen) {
        try {
            await client.connect();
        } catch (err) {
            logger.error("Failed to connect to Redis", err);
        }
    }
}
