import winston from "winston";

/**
 * Console-only structured logger.
 *
 * The API server's logger also wrote daily-rotated files and stamped each line
 * with a per-request id. Neither survives here: this service runs one endpoint,
 * and log collection belongs to whatever runs the container.
 */
const logger = winston.createLogger({
    level: process.env.LOG_LEVEL ?? "info",
    silent: process.env.NODE_ENV === "test",
    format: winston.format.combine(winston.format.timestamp(), winston.format.json()),
    transports: [new winston.transports.Console()],
});

export default logger;
