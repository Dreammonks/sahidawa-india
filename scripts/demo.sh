#!/usr/bin/env bash
#
# End-to-end demonstration: empty database → scraped data → barcode answers.
#
#   ./scripts/demo.sh
#
# Needs a running local Supabase (npx supabase start) and the ETL virtualenv
# at apps/etl/.venv. Takes about four minutes, most of it waiting on
# janaushadhi.gov.in.

set -euo pipefail
cd "$(dirname "$0")/.."

API_PORT="${API_PORT:-4100}"
LIMIT="${LIMIT:-10}"

rule() { printf '\n\033[1m── %s ─────────────────────────────────────────\033[0m\n' "$1"; }
psql_q() { docker exec supabase_db_sahidawa-india psql -U postgres -d postgres "$@"; }

eval "$(npx supabase status -o env | sed 's/^/export /' | sed 's/^export API_URL/export SUPABASE_URL/;s/^export SERVICE_ROLE_KEY/export SUPABASE_SERVICE_ROLE_KEY/')"

rule "1. Build the whole database from one migration"
ls supabase/migrations
npx supabase db reset 2>&1 | grep -E 'Applying|Finished'

rule "2. What that migration created"
psql_q -c "select tablename from pg_tables
           where schemaname='public' and tablename <> 'spatial_ref_sys' order by 1;"

rule "3. The database is empty"
psql_q -c "select
    (select count(*) from medicines)       as medicines,
    (select count(*) from pharmacies)      as pharmacies,
    (select count(*) from cdsco_reference) as cdsco_reference;"

rule "4. Run the pipeline against live government sources"
( cd apps/etl && .venv/bin/python demo_small_scrape.py --limit "$LIMIT" --cdsco-rows 300 ) \
    2>&1 | grep -E 'Row counts|Summary —|status.: .(ok|failed)' || true

rule "5. The data arrived — and nothing failed"
psql_q -c "select
    (select count(*) from medicines)       as medicines,
    (select count(*) from pharmacies)      as pharmacies,
    (select count(*) from cdsco_reference) as cdsco_reference,
    (select count(*) from etl_failed_rows) as failed_rows;"

rule "6. Medicine search runs inside the database, no API needed"
psql_q -c "select brand_name, round(similarity::numeric, 2) as match
           from search_medicines_text('Azithral', 3);"

rule "7. Load the barcode catalogue (six products, entered by hand)"
docker exec -i supabase_db_sahidawa-india psql -U postgres -d postgres -q < supabase/demo/product_barcodes_from_photos.sql
psql_q -c "select gtin, product_name, category, is_medicine from product_barcodes order by category;"

rule "8. Start the barcode API"
( cd apps/barcode-api && PORT="$API_PORT" npx ts-node-dev --transpile-only src/index.ts ) \
    > /tmp/demo-barcode-api.log 2>&1 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
    curl -sf -m 1 "localhost:$API_PORT/health" >/dev/null 2>&1 && break
    sleep 1
done
curl -s "localhost:$API_PORT/health"; echo

ask() {
    printf '\n\033[1m%s\033[0m\n' "$1"
    curl -s "localhost:$API_PORT/api/v1/products/barcode/$2" \
        | python3 -m json.tool 2>/dev/null | head -"${3:-14}"
}

rule "9. What Aushadhi IO's scanner will get back"
ask "A catalogued product — Ayurvedic, so CDSCO verification does not apply" 8901138511975 20
ask "A barcode nobody has catalogued — logged for review" 8901030865275 8
ask "A mistyped barcode — caught by the GS1 check digit" 8901138511974 6
ask "Not a barcode at all" 123 6

curl -s -o /dev/null "localhost:$API_PORT/api/v1/products/barcode/8901030865275"

rule "10. Unknown scans queue up, so we know what to catalogue next"
psql_q -c "select gtin, scan_count, last_seen_at from unknown_barcode_scans
           order by scan_count desc;"

rule "Done"
echo "Pipeline → database → API, from an empty database, in one run."
