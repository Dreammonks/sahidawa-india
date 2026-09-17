# SahiDawa

Medicine data for Bharat. This project collects it, stores it, and serves it
over HTTP: **what product is this barcode?** and **which medicine batches has
CDSCO flagged?**

It has no user interface. Aushadhi IO's apps and other services get the data
through the API; nothing reads the database directly.

```
Government and public websites
         │  daily (medicines, drug alerts) · weekly (shops)
         ▼
   scraping pipeline  ──►  database  ──►  API  ──►  Aushadhi IO apps
     (apps/etl)                   (apps/barcode-api)    and other services
```

## What is here

| Path | What it does |
|---|---|
| `apps/etl` | Five scrapers — Jan Aushadhi prices, a commercial medicine dataset, the CDSCO brand registry, CDSCO drug alerts, Jan Aushadhi shop locations — plus cleaning, CDSCO matching and loading |
| `apps/barcode-api` | `GET /api/v1/products/barcode/:gtin` and `GET /api/v1/drug-alerts`. See its own README |
| `supabase/` | The complete schema, in a single migration |
| `.github/workflows/` | The nightly and weekly scrape, tests, CodeQL |

## Running it

A working database from nothing:

```bash
npx supabase start
npx supabase db reset      # applies the one migration
```

Then load some real data:

```bash
cd apps/etl
python -m venv .venv && .venv/bin/pip install -e ".[dev]" -r requirements.txt
SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... .venv/bin/python demo_small_scrape.py --limit 20
```

`demo_small_scrape.py` takes a deliberately tiny slice from every source and
prints a before-and-after row count, so you can see data arrive. The full runs
are `run_all.py` for medicines, `run_alerts.py` for drug alerts (`--all` loads
every month since 2019) and `run_stores.py` for shops.

The barcode API:

```bash
npm install
npm run dev     # needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
npm test
```

## Reading the data

**Other services use the API, never the database.** Only this project's own
server holds the database key. Row level security is on for every table and
the public `anon` key is refused, because it ships inside apps and anyone can
extract it. `pharmacies` also holds contact names and phone numbers.

When a service needs data the API does not serve yet, add an endpoint to
`apps/barcode-api` rather than opening the database.

Tables: `medicines`, `drug_alerts`, `pharmacies`, `cdsco_reference`,
`product_barcodes`, `unknown_barcode_scans`, `etl_failed_rows`. The database
also has a medicine name search, `search_medicines_text('dolo', 5)`, which no
endpoint serves yet.

## Two things that will surprise you

**The barcode catalogue is nearly empty.** `product_barcodes` holds six rows,
entered by hand from photographs, none of them medicines. Nothing fills it
automatically yet, so most real scans return `unknown`. `unknown_barcode_scans`
counts exactly which barcodes people scanned and missed — that is the list to
work through, in order of demand.

**Only what a source states is stored.** None of the sources publish
barcodes, so `medicines.barcode_id` is empty. Jan Aushadhi rows have no brand or
manufacturer, and nothing fills in a schedule, a CDSCO approval status or a
dosage form the source does not name. An empty column means the source does not
say, not that the value is false or zero; a price of 0 is stored as unknown.
`is_cdsco_verified` and the match columns are filled only by the CDSCO check,
and a registry name is recorded only when it actually matched.

## History

This was a full product — website, API server, an AI service, recall alerts,
notifications. All of that moved to Aushadhi IO, and what remains is the data
and the one endpoint that serves it. `docs/project-history.md` and `docs/adr/`
keep the record; `supabase/legacy-schema-from-api.sql` is the old schema the
single migration was rebuilt from.

## Licence

MIT. See `LICENSE`.
