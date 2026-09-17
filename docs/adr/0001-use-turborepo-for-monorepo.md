# ADR 0001 - Use Turborepo for Monorepo Management

* Status: superseded by [ADR-0007](0007-reduce-to-data-pipeline-and-barcode-api.md)
* Deciders: SahiDawa Core Team
* Date: 2026-07-14

Technical Story: [System Design Documentation](../architecture/system-design.md)

## Context and Problem Statement

The SahiDawa project comprises multiple distinct components, including the Next.js frontend (`apps/web`), the Node.js/Express API backend (`apps/api`), the Python/FastAPI ML service (`apps/ml`), and shared packages like `@sahidawa/shared`, `@sahidawa/types`, and `@sahidawa/validators`. 
Managing dependencies, running tests/builds, and coordinating tasks across these separate packages and applications without a unified monorepo orchestration tool leads to redundant package downloads, slow build pipelines, code duplication, and inconsistent development setups. We need a way to manage these workspaces cleanly and efficiently.

## Decision Drivers

* High-performance build caching and execution speed.
* Code sharing and reuse via local packages.
* Unified versioning and clean workspace dependency management.
* Developer experience and ease of running dev environments.

## Considered Options

* **Option 1: Multi-Repository Setup** (Keep frontend, API, and ML services in separate git repositories).
* **Option 2: Basic NPM Workspaces** (Single monorepo without a task orchestrator/runner).
* **Option 3: Turborepo with NPM Workspaces** (Single monorepo managed by Turborepo for orchestration and caching).

## Decision Outcome

Chosen option: **Option 3: Turborepo with NPM Workspaces**, because it provides local caching of build/test outputs, allows defined pipelines and dependency graphs between tasks, and manages dependency hoisting correctly at the root folder.

### Consequences

* **Good:**
  * Shared dependencies are hoisted to the root level (`package-lock.json`), reducing duplication.
  * Task orchestrator (`turbo`) caches inputs/outputs to prevent rebuilding unmodified files.
  * Easy import of internal packages (`@sahidawa/shared`, etc.) into `apps/web` and `apps/api`.
  * Single command to launch the entire development stack (e.g. running from root).
* **Bad:**
  * Requires developers to run packages from the root using workspace-scoped commands (e.g. `npm install <package> -w web`) rather than running `npm install` inside individual app subfolders directly.
  * Introduces Turborepo dependency and configuration (`turbo.json`) to maintain.

## Pros and Cons of the Options

### Option 1: Multi-Repository Setup

* **Good:** Independent version history, smaller individual codebases.
* **Bad:** High friction when updating shared types or schemas; manual orchestration required to run frontend and APIs side-by-side.

### Option 2: Basic NPM Workspaces

* **Good:** Simple setup without external orchestrators.
* **Bad:** No build cache; no parallel task pipeline capability, leading to slower build times as the repo scales.
