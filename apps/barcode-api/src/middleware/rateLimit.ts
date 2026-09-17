import rateLimit, { MemoryStore, Store, Options, IncrementResponse } from "express-rate-limit";
import { RedisStore } from "rate-limit-redis";
import { redisClient } from "../utils/redis";
import logger from "../utils/logger";

// ── Store factory ──────────────────────────────────────────────────────────────
//
// Uses a Redis-backed store when the client is connected so counters are shared
// across replicas. Falls back to the in-process MemoryStore when Redis is
// unavailable, so the service still runs locally without one.
//
// Resolution is deliberately lazy: limiters are built at module load, before
// `connectRedis()` runs, so checking `redisClient.isOpen` up front would always
// pick MemoryStore. The real store is resolved on the first request instead.

class LazyStore implements Store {
    private readonly keyPrefix: string;
    private store: Store | undefined;
    private initOptions: Options | undefined;

    constructor(prefix: string) {
        this.keyPrefix = prefix;
    }

    init(options: Options): void {
        this.initOptions = options;
    }

    private resolve(): Store {
        if (!this.store) {
            if (redisClient.isOpen) {
                this.store = new RedisStore({
                    // Adapts the node-redis v4 client to the interface rate-limit-redis expects
                    sendCommand: (...args: string[]) => redisClient.sendCommand(args),
                    prefix: `rl:${this.keyPrefix}:`,
                });
                logger.info(`[rateLimit] Redis store active for prefix '${this.keyPrefix}'`);
            } else {
                this.store = new MemoryStore();
                logger.warn(
                    `[rateLimit] Redis not connected — ${this.keyPrefix} limiter falling back to MemoryStore. ` +
                        "Rate limiting will NOT be shared across replicas."
                );
            }
            if (this.initOptions && this.store.init) {
                void this.store.init(this.initOptions);
            }
        }
        return this.store;
    }

    increment(key: string): Promise<IncrementResponse> | IncrementResponse {
        return this.resolve().increment(key);
    }

    decrement(key: string): Promise<void> | void {
        return this.resolve().decrement(key);
    }

    resetKey(key: string): Promise<void> | void {
        return this.resolve().resetKey(key);
    }

    resetAll(): Promise<void> | void {
        return this.resolve().resetAll?.();
    }
}

export function buildStore(prefix: string): Store {
    return new LazyStore(prefix);
}

// The website allowed 15 lookups per 15 minutes, sized for one person browsing.
// A pharmacy counter working through a shelf passes that in under a minute, and
// callers behind one network address share a single budget, so the ceiling is
// configurable and defaults far higher. Revisit once per-client keys exist.
const WINDOW_MS = 15 * 60 * 1000;
const DEFAULT_MAX = process.env.NODE_ENV === "development" ? 1000 : 300;

export const barcodeLimiter = rateLimit({
    skip: () => process.env.NODE_ENV === "test",
    windowMs: WINDOW_MS,
    max: Number(process.env.BARCODE_RATE_LIMIT ?? DEFAULT_MAX),
    standardHeaders: true,
    legacyHeaders: false,
    validate: false,
    store: buildStore("barcode"),
    handler: (_req, res) => {
        res.status(429).json({
            error: "Too many barcode lookups. Please try again later.",
        });
    },
});

// Its own budget, so a service paging through alerts cannot use up barcode lookups.
export const alertsLimiter = rateLimit({
    skip: () => process.env.NODE_ENV === "test",
    windowMs: WINDOW_MS,
    max: Number(process.env.ALERTS_RATE_LIMIT ?? DEFAULT_MAX),
    standardHeaders: true,
    legacyHeaders: false,
    validate: false,
    store: buildStore("alerts"),
    handler: (_req, res) => {
        res.status(429).json({
            error: "Too many drug alert requests. Please try again later.",
        });
    },
});
