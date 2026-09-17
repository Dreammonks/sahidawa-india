# ADR 0003 - Use Redis for Cache-Aside Pattern

* Status: accepted
* Deciders: SahiDawa Core Team
* Date: 2026-07-14

Technical Story: [Barcode lookup cache](../../apps/barcode-api/src/utils/redis.ts)

## Context and Problem Statement

When citizens scan medicine packages or look up drug data, SahiDawa verifies the barcode or batch number against the CDSCO master dataset in the Supabase PostgreSQL database. Running every search directly against the database would introduce high latency (especially for network-bound API calls) and overwhelm the PostgreSQL connection pool, risking service outages under heavy load. We need a caching solution to keep database queries minimal and response times low.

## Decision Drivers

* Minimizing lookup latency for common medicines.
* Reducing the query load on Supabase Postgres.
* Storing temporary, high-throughput session state data and rate limit counters.
* Simple cache invalidation and warming strategies.

## Considered Options

* **Option 1: In-Memory Application Cache** (Local Node.js/FastAPI memory cache like node-cache).
* **Option 2: Redis (Cache-Aside Pattern)** (Using a dedicated Redis server to cache queries and seed hot data).
* **Option 3: Directly Querying Database** (No cache layer, letting PostgreSQL handle indexing and queries directly).

## Decision Outcome

Chosen option: **Option 2: Redis (Cache-Aside Pattern)**. When a drug lookup occurs, the system first checks Redis. On a cache miss, it queries PostgreSQL, writes the result to Redis, and returns the response. Additionally, the cache is warmed at startup with "hot drugs" from a predefined seed list.

### Consequences

* **Good:**
  * Sub-millisecond lookup response times on cache hits.
  * Dramatic reduction in database read operations, keeping resource usage within free tier limits.
  * Allows robust rate-limiting and temporary IP/session tracking (via `@upstash/redis` and `@upstash/ratelimit`).
  * Dedicated redis client (`redis` package) supports clustering and TTL expiration policies.
* **Bad:**
  * Introduces Cache Invalidation logic complexity (must invalidate or update Redis keys when master medicine data changes).
  * Adds an additional architectural component (Redis instance) that must be maintained and paid for (e.g. Upstash or local container).

## Pros and Cons of the Options

### Option 1: In-Memory Application Cache

* **Good:** No network latency for cache hits; extremely easy to implement.
* **Bad:** Cache is local to the server process; since SahiDawa has separate Express API (`apps/api`), FastAPI ML (`apps/ml`), and Next.js (`apps/web`) instances, local caches cannot be shared, leading to data inconsistency.

### Option 3: Directly Querying Database

* **Good:** Single component stack; zero risk of stale cache values.
* **Bad:** High lookup latency; quick exhaustion of database connection limits; no centralized rate-limiting layer.
