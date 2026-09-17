import { Request } from "express";

export const DEFAULT_LIMIT = 20;
export const MAX_LIMIT = 100;
export const MAX_OFFSET = 10_000;

// % is allowed because product names contain it ("Cream 0.1%"); repositories match it literally.
export const SEARCH_FORMAT = /^[\p{L}\p{N} .,&+\-/()'%]{2,100}$/u;
export const UUID_FORMAT = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type Query = Request["query"];
export type Parsed<T> = { ok: true; value: T } | { ok: false; error: string };

export const invalid = <T>(error: string): Parsed<T> => ({ ok: false, error });

/** A whole number within [min, max], the fallback when absent, or null when invalid. */
export function readInteger(
    raw: unknown,
    fallback: number,
    min: number,
    max: number
): number | null {
    if (raw === undefined) return fallback;
    const value = Number(raw);
    return Number.isInteger(value) && value >= min && value <= max ? value : null;
}

/** The trimmed text when it matches, undefined when absent, or null when invalid. */
export function readText(raw: unknown, format: RegExp): string | null | undefined {
    if (raw === undefined) return undefined;
    const text = String(raw).trim();
    return format.test(text) ? text : null;
}

export function readPage(raw: Query): Parsed<{ limit: number; offset: number }> {
    const limit = readInteger(raw.limit, DEFAULT_LIMIT, 1, MAX_LIMIT);
    if (limit === null) return invalid(`limit must be a whole number from 1 to ${MAX_LIMIT}.`);
    const offset = readInteger(raw.offset, 0, 0, MAX_OFFSET);
    if (offset === null) return invalid(`offset must be a whole number from 0 to ${MAX_OFFSET}.`);
    return { ok: true, value: { limit, offset } };
}

/** ilike treats % and _ as wildcards; a user typing them must match them literally. */
export function escapeLike(value: string): string {
    return value.replace(/[\\%_]/g, (ch) => `\\${ch}`);
}
