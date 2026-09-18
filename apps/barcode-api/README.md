# SahiDawa API

Serves SahiDawa's data over HTTP: medicines, CDSCO drug alerts, the CDSCO
brand registry, and product lookup by barcode. Every endpoint is read-only
`GET`; list endpoints page with `limit` (1 to 100, default 20) and `offset`.

It exists so that no app or service ever holds a Supabase key. Every table has
row level security enabled and grants nothing to `anon`, so reads need the
service role, which stays on this server.

## Medicines

```
GET /api/v1/medicines
GET /api/v1/medicines/:id
```

Medicines from Jan Aushadhi's price list and a commercial medicine dataset.

| Query | Example | Meaning |
|---|---|---|
| `search` | `paracetmol` | Brand, generic name or ingredient. Small typos are tolerated; best match first, with a `match_score` from 0 to 1 |
| `source` | `janaushadhi` or `commercial` | One source only |

Without `search`, medicines are listed alphabetically by generic name.

Each medicine has: `brand_name`, `generic_name`, `manufacturer`, `composition`,
`strength`, `dosage_form`, `pack_size`, `mrp`, `source`, `source_product_code`
(Jan Aushadhi's Drug Code), `jan_aushadhi_price` (for a commercial medicine,
the price of the same generic at the same strength on Jan Aushadhi's list),
and the CDSCO check result `is_cdsco_verified` with `cdsco_match_score`. An
empty field means the source does not give it.

`GET /api/v1/medicines/:id` returns one medicine, or 404.

## CDSCO brand registry

```
GET /api/v1/cdsco-brands?brand=dolo 650&manufacturer=micro labs
```

The closest entries in CDSCO's brand registry, best first, up to `limit` (1 to
20, default 5). Each has `product_score`, `manufacturer_score` and
`match_score` (0 to 100), and `is_match`, which uses the same threshold (90) as
the pipeline. With a manufacturer, `is_match` uses `match_score`; without one,
it uses `product_score`, and `matched_on` says which.

## Barcode lookup

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

## Drug alerts

```
GET /api/v1/drug-alerts
```

CDSCO's monthly lists of medicine batches that failed a government quality
test (`nsq`, since 2019) or were found to be fake (`spurious`, since 2025).
Every field is exactly as CDSCO published it. Loaded daily by
`apps/etl/run_alerts.py`.

| Query | Example | Meaning |
|---|---|---|
| `search` | `paracetamol` | Part of the product name |
| `batch` | `PEP5001` | Exact batch number, any letter case |
| `type` | `nsq` or `spurious` | One kind of alert |
| `month` | `2026-07` | The month CDSCO reported it |
| `limit` | `20` | Results per page, 1 to 100 (default 20) |
| `offset` | `40` | Results to skip, for the next page |

```json
{
  "status": "ok",
  "total": 1,
  "limit": 20,
  "offset": 0,
  "alerts": [
    {
      "alert_type": "nsq",
      "product_name": "Pantoprazole Tablets IP",
      "batch_number": "PEP5001",
      "manufacturing_date": "Feb-2025",
      "expiry_date": "Jan-2027",
      "manufacturer": "Finecure Pharmaceuticals Ltd. PF-5 & 6, Sanand Industrial Estate-II, ...",
      "reason": "Dissolution test",
      "reporting_source": "State Lab",
      "reported_by": "SDT&RL, Bhubaneswar",
      "reporting_month": "2026-07-01"
    }
  ]
}
```

Alerts are not linked to rows in `medicines`: an alert names a product and a
manufacturer as written on the pack, and a wrong link would flag the wrong
medicine. To check a pack, search by its batch number.

`GET /health` returns `{ "status": "ok" }`.

## Browsing the API

`GET /api/docs` is a Swagger page built from the annotations on the routes, with
every parameter and response documented and a button that calls the endpoint.
`GET /api/docs.json` is the same document as OpenAPI 3.0.3, for generating a
client. Both describe whichever host serves them, so they work behind a tunnel
or a deployment without being reconfigured.

## Environment

| Variable | Required | Meaning |
|---|---|---|
| `SUPABASE_URL` | yes | Project holding `medicines` and the barcode tables |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Service-role key. Never ship this to a client |
| `REDIS_URL` | no | Caches lookups for an hour. The service is correct without it |
| `PORT` | no | Default `4100` |
| `LOG_LEVEL` | no | Default `info` |
| `ALLOWED_ORIGINS` | no | Comma-separated browser origins. Empty allows none; native apps are unaffected |
| `BARCODE_RATE_LIMIT` | no | Barcode lookups per client address per 15 minutes. Default `300` |
| `DATA_RATE_LIMIT` | no | Medicine, drug alert and CDSCO registry requests per client address per 15 minutes. Default `300` |
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

The endpoints currently have no authentication. Anyone who can reach the
server can call them, and every barcode miss writes a row to
`unknown_barcode_scans`. Decide the access model before exposing it publicly.
