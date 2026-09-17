# Contributing to SahiDawa

SahiDawa is a medicine data pipeline with one barcode lookup API. There is no
user interface here; read the [README](./README.md) first for what the project
does and what it deliberately does not.

By contributing you agree to the [Code of Conduct](./CODE_OF_CONDUCT.md).

---

## What lives where

| Path | Stack | What it does |
| --- | --- | --- |
| `apps/etl` | Python 3.10+, Playwright, pandas | Scrapers, cleaning, CDSCO matching, loading into Supabase |
| `apps/barcode-api` | Node 22, Express 5, TypeScript | `GET /api/v1/products/barcode/:gtin` |
| `supabase/migrations` | Postgres | The schema. One migration builds the whole database |
| `.github/workflows` | GitHub Actions | Nightly and weekly scrapes, tests, CodeQL |

Anything older — the website, the ML service, the full API — was removed. Tag
`before-strip` marks the last commit that had it.

---

## Setting up

### Requirements

| Tool | Version |
| --- | --- |
| Node.js | 22 (see `.nvmrc`) |
| Python | 3.10 or newer |
| Docker | Needed by the Supabase CLI |
| Supabase CLI | Run through `npx supabase` |

### Database

```bash
npx supabase start
npx supabase db reset      # builds the schema from supabase/migrations
```

### Environment

Copy `.env.example` to `.env` at the repo root for the pipeline, and to
`apps/barcode-api/.env` for the API. Both need `SUPABASE_URL` and
`SUPABASE_SERVICE_ROLE_KEY`; `npx supabase status` prints the local values.
Never commit a `.env` file.

### Pipeline

```bash
cd apps/etl
python -m venv .venv
.venv/bin/pip install -e ".[dev]" -r requirements.txt
.venv/bin/playwright install chromium
.venv/bin/python demo_small_scrape.py --ja-rows 20 --commercial-rows 20 --cdsco-rows 300   # a small slice
```

The full runs are `run_all.py` (medicines) and `run_alerts.py` (drug alerts).

### API

```bash
npm install
npm run dev
curl http://localhost:4100/api/v1/products/barcode/8901234567890
```

Once Supabase is running and `apps/etl/.venv` exists, `scripts/demo.sh` does the
rest in one go: empty database, scraped data, API answers. It loads the full Jan
Aushadhi list, 5,000 commercial medicines, the full CDSCO registry and every
month of drug alerts; the sizes are settings at the top of the script.

---

## Before you open a pull request

```bash
# Pipeline
cd apps/etl && .venv/bin/python -m pytest tests -q

# API
npm test
npx tsc --noEmit -p apps/barcode-api
npm run lint:circular

# Schema and dependencies
npm run check:migrations
npm run audit:all
```

The git hooks run part of this for you: `pre-commit` formats staged files with
Prettier and scans for import cycles when TypeScript changed; `pre-push` runs
`npm run audit:all`. `audit:python` needs `pip-audit` installed
(`pip install pip-audit`) and skips itself otherwise.

### Changing the schema

1. Add a **new** migration: `npx supabase migration new <what-it-does>`. Never
   edit one that has already been applied to a shared database.
2. Update `supabase/schema-target.json` with any table or column the pipeline or
   the API now depends on.
3. Run `npx supabase db reset` and `npm run check:migrations`. Both must pass.

### Adding a data source

A new scraper goes in `apps/etl/src/scrapers/`, is wired into `run_all.py` or
`run_alerts.py`, and loads through `SupabaseLoader` so failed rows land in
`etl_failed_rows`. Running it twice must not duplicate rows. Add tests that stub
the network; no test may call a live site.

---

## Coding standards

**Python** — type hints on public functions, docstrings where the reason is not
obvious, no bare `except:`, `pathlib` for paths.

**TypeScript** — no `any`, `async`/`await` over `.then()`, validate every
request input at the route, never expose internal error details in a response.

**Both** — keep secrets out of code, logs and test fixtures.

---

## Commits and pull requests

Commits follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>
```

| Type | Use for |
| --- | --- |
| `feat` | New behaviour |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding or fixing tests |
| `refactor` | Restructure with no behaviour change |
| `perf` | Performance improvement |
| `chore` | Tooling, dependencies, housekeeping |

Examples:

```
feat(etl): add a scraper for the GTIN catalogue
fix(barcode-api): return 400 for a barcode with a bad check digit
```

Pull requests:

- Branch from an up-to-date `main`: `feat/…`, `fix/…`, `docs/…`.
- Touch only the files the change needs. Check `git status` before committing.
- Fill in the PR template, and paste test output or the request and response you
  checked as proof.
- One approving review is needed to merge.

---

## Reporting problems

Use the issue templates. For a security problem, follow [SECURITY.md](./SECURITY.md)
instead of opening a public issue.
