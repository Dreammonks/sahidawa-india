# ADR 0007 - Reduce SahiDawa to a Data Pipeline and One Barcode API

* Status: accepted
* Deciders: Dream Monks
* Date: 2026-09-16

Technical Story: [Barcode API](../../apps/barcode-api/README.md)

## Context and Problem Statement

SahiDawa was built as a full citizen-facing product: a Next.js website, an
Express API with some sixty routes, a FastAPI AI/ML service, recall alerts and
notifications, all on top of a scraping pipeline and a Supabase database.

Dream Monks needs only the medicine data. Recall alerts and every user-facing
screen come from another service, Aushadhi IO, whose Android and React web apps
already have a barcode scanner. What those apps lack is a way to turn a scanned
barcode into a product.

## Decision Drivers

* Keep the data the pipeline collects fresh, with no product around it to maintain.
* Aushadhi IO must be able to look up a barcode from a phone.
* A phone app cannot be trusted with a database key: anything shipped inside an
  installed app can be extracted.

## Considered Options

* **Option 1: Keep the whole API server**, with every route except barcode unused.
* **Option 2: Barcode lookup as a database function**, called directly by the apps.
* **Option 3: A single-endpoint barcode service** beside the pipeline.

## Decision Outcome

Chosen option: **Option 3**. The repository keeps `apps/etl`, the database
schema as one migration, and `apps/barcode-api`, which serves
`GET /api/v1/products/barcode/:gtin` with the service-role key held on the server.
The website, the ML service, the rest of the API, the shared packages and their
workflows are removed. Tag `before-strip` marks the last commit that had them.

### Consequences

* **Good:**
  * The dependency tree and the attack surface shrink to what the data needs.
  * The database builds from one migration instead of 110 that never built one.
  * No database key leaves the server.
* **Bad:**
  * A server has to run somewhere for the barcode API.
  * Upstream SahiDawa changes can no longer be merged in.

This supersedes [ADR 0001](./0001-use-turborepo-for-monorepo.md) (two npm
workspaces no longer need Turborepo), [ADR 0004](./0004-use-langgraph-for-ml-triage.md)
(the ML service is gone) and [ADR 0005](./0005-use-nextjs-for-frontend.md)
(there is no frontend). [ADR 0003](./0003-use-redis-for-cache-aside-pattern.md)
still applies, now to the barcode API alone.

## Pros and Cons of the Options

### Option 1: Keep the whole API server

* **Good:** No code to move.
* **Bad:** Around 130 files of unused routes, their dependencies and their
  vulnerabilities stay deployed and exposed.

### Option 2: Barcode lookup as a database function

* **Good:** No server to run.
* **Bad:** The mobile app would call the database with a key shipped inside the
  installed binary, leaving row-level security as the only guard on every table.
