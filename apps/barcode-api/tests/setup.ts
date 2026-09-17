process.env.SUPABASE_URL = process.env.SUPABASE_URL || "http://localhost:54321";
process.env.SUPABASE_SERVICE_ROLE_KEY =
    process.env.SUPABASE_SERVICE_ROLE_KEY || "test-service-role-key";

// Supabase's realtime client reaches for a global WebSocket that Node does not define.
(global as any).WebSocket = class {};

jest.mock("../src/utils/redis", () => ({
    redisClient: {
        isOpen: true,
        get: jest.fn(),
        set: jest.fn().mockResolvedValue("OK"),
        connect: jest.fn(),
        on: jest.fn(),
        sendCommand: jest.fn(),
    },
    connectRedis: jest.fn(),
}));

jest.mock("../src/middleware/rateLimit", () => ({
    buildStore: jest.fn(() => ({
        increment: jest.fn().mockResolvedValue({ totalHits: 1, resetTime: Date.now() + 60000 }),
        decrement: jest.fn().mockResolvedValue(undefined),
        resetKey: jest.fn().mockResolvedValue(undefined),
        resetAll: jest.fn().mockResolvedValue(undefined),
    })),
    barcodeLimiter: jest.fn((_req: unknown, _res: unknown, next: () => void) => next()),
    alertsLimiter: jest.fn((_req: unknown, _res: unknown, next: () => void) => next()),
}));
