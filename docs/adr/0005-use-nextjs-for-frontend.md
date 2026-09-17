# ADR 0005 - Use Next.js for Frontend

* Status: superseded by [ADR-0007](0007-reduce-to-data-pipeline-and-barcode-api.md)
* Deciders: SahiDawa Core Team
* Date: 2026-07-14

Technical Story: [Frontend Package Configuration](../../apps/web/package.json)

## Context and Problem Statement

SahiDawa is designed for citizens in India, including rural areas where internet connections can be slow, intermittent, or offline. We need a web framework that:
1. Renders pages fast (with Server-Side Rendering (SSR) for initial load performance and search engine visibility).
2. Natively supports Progressive Web App (PWA) configurations (service workers, background sync, offline asset caching).
3. Easily handles multilingual routing and translation structures for 22 regional Indian languages.
4. Integrates with modern components, barcode scanning libraries, and responsive UI setups.

## Decision Drivers

* SEO and initial load speed.
* Offline-first support (PWA).
* Deep integration with React 19 features (Server Components, Actions, Suspense).
* High-performance styling workflow.

## Considered Options

* **Option 1: Single Page Application (SPA) with React (Vite)** (Client-side rendered bundle, requiring manually configured server routing and static hosting).
* **Option 2: Next.js (App Router)** (React framework with built-in server-side rendering, layout hierarchy, and routing optimization).
* **Option 3: Remix** (Edge-focused SSR React framework).

## Decision Outcome

Chosen option: **Option 2: Next.js (App Router)** (using exact version `16.2.9`), configured with React `19.2.7` and Tailwind CSS `v4.0.0` for styling. This setup allows server-side rendering of static sections while enabling rich client-side scanning and audio rendering capabilities. We utilize `@ducanh2912/next-pwa` for PWA offline caching.

### Consequences

* **Good:**
  * Fast First Contentful Paint (FCP) due to Server-Side Rendering (SSR) of core routes.
  * Simple localization routing and language-switching structures using `next-intl`.
  * Tailwind CSS v4 delivers fast build performance, native CSS variables, and modern styling utilities.
  * Native React 19 Server Components minimize client-side bundle sizes.
* **Bad:**
  * Increased hosting complexity compared to a purely static Vite app (requires a Node.js runtime or Vercel serverless adapters).
  * Breaking changes or strict routing directory patterns of the App Router can complicate configuration compared to legacy pages routers.

## Pros and Cons of the Options

### Option 1: Single Page Application (SPA) with React (Vite)

* **Good:** Simple static file deployment (e.g., standard CDN); fast client-side navigation.
* **Bad:** Poor SEO indexing on dynamic pages; slower initial load times on low-bandwidth rural networks since the browser must download and execute the entire JS bundle before rendering anything.

### Option 3: Remix

* **Good:** Excellent loader/action data mutation patterns.
* **Bad:** Smaller ecosystem and PWA setup support packages compared to Next.js; less familiarity among contributors.
