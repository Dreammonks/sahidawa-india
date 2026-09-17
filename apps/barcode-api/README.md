# SahiDawa barcode API

Resolves a product barcode (GTIN) to a product. One endpoint, one job.

It exists so that client apps never hold a Supabase key. The barcode catalogue
and the unknown-barcode queue both have row level security enabled and grant
nothing to `anon`, so lookups need the service role — which stays on this
server.

## The endpoint

```
GET /api/v1/products/barcode/:gtin
```

Accepts EAN-8, UPC-A, EAN-13 and GTIN-14. Resolution order:

1. the `product_barcodes` catalogue;
2. failing that, `medicines.barcode_id`;
3. failing that, the barcode is recorded in `unknown_barcode_scans` for review.

Responses carry a `status` of `found`, `unknown` or `invalid`. A `found`
response also states whether CDSCO medicine verification applies — it does not
for AYUSH, FSSAI or BIS products, and the response says so rather than implying
the product is unverified.

`GET /health` returns `{ "status": "ok" }`.

## Environment

| Variable | Required | Meaning |
|---|---|---|
| `SUPABASE_URL` | yes | Project holding `medicines` and the barcode tables |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Service-role key. Never ship this to a client |
| `REDIS_URL` | no | Caches lookups for an hour. The service is correct without it |
| `PORT` | no | Default `4100` |
| `LOG_LEVEL` | no | Default `info` |
| `ALLOWED_ORIGINS` | no | Comma-separated browser origins. Empty allows none; native apps are unaffected |
| `BARCODE_RATE_LIMIT` | no | Lookups per client address per 15 minutes. Default `300` |
| `TRUST_PROXY_HOPS` | no | Proxy hops in front of the service. Default `1` |

Put these in `.env` next to this file. Never commit it.

## Running

```bash
npm install
npm run dev     # ts-node-dev on PORT
npm test        # jest
npm run build   # tsc to dist/
npm start       # node dist/index.js
```

## Two things to know before building against this

**The catalogue is nearly empty.** `product_barcodes` holds six rows, entered by
hand from photographs, and none of them are medicines. Nothing fills the table
automatically yet. Most real scans will come back `unknown`.

**No medicine has a barcode yet.** None of the pipeline's sources publish
barcodes, so `medicines.barcode_id` is empty and step 2 above never matches
today. It is kept for when a real barcode source exists.

The `unknown_barcode_scans` table is the intended fix: it counts exactly which
barcodes real users scanned and missed, so the catalogue can be filled in order
of demand.

## Access

The endpoint currently has no authentication — it was a public website feature.
As a standalone service that means anyone can call it, and every miss writes a
row to `unknown_barcode_scans`. Decide the access model before exposing it
publicly.
