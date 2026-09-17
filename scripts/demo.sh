#!/usr/bin/env bash
#
# End-to-end demonstration: empty database → scraped data → API answers.
#
#   ./scripts/demo.sh
#
# Needs a running local Supabase (npx supabase start) and the ETL virtualenv
# at apps/etl/.venv.
#
# How much data to load (0 = everything):
#   JA_ROWS=0            the full Jan Aushadhi list (~2,400 medicines)
#   COMMERCIAL_ROWS=5000 commercial medicines (the full dataset is ~250,000)
#   CDSCO_ROWS=0         the full CDSCO brand registry (~110,000 entries)
#   ALERT_MONTHS=all     every month of drug alerts since 2019, or a number
#
# A quick run: JA_ROWS=10 COMMERCIAL_ROWS=10 CDSCO_ROWS=300 ALERT_MONTHS=1 ./scripts/demo.sh

set -euo pipefail
cd "$(dirname "$0")/.."

API_PORT="${API_PORT:-4100}"
JA_ROWS="${JA_ROWS:-0}"
COMMERCIAL_ROWS="${COMMERCIAL_ROWS:-5000}"
CDSCO_ROWS="${CDSCO_ROWS:-0}"
ALERT_MONTHS="${ALERT_MONTHS:-all}"
API="localhost:$API_PORT/api/v1"

rule() { printf '\n\033[1m── %s ─────────────────────────────────────────\033[0m\n' "$1"; }
psql_q() { docker exec supabase_db_sahidawa-india psql -U postgres -d postgres "$@"; }
ask() {
    printf '\n\033[1m%s\033[0m\n  GET %s\n' "$1" "$2"
    curl -s "localhost:$API_PORT$2" | python3 -m json.tool 2>/dev/null | head -"${3:-14}"
}

eval "$(npx supabase status -o env | sed 's/^/export /' | sed 's/^export API_URL/export SUPABASE_URL/;s/^export SERVICE_ROLE_KEY/export SUPABASE_SERVICE_ROLE_KEY/')"

rule "1. Build the whole database from one migration"
ls supabase/migrations
npx supabase db reset 2>&1 | grep -E 'Applying|Finished'

rule "2. What that migration created"
psql_q -c "select tablename from pg_tables where schemaname = 'public' order by 1;"

rule "3. Run the pipeline against live government sources"
( cd apps/etl && .venv/bin/python demo_small_scrape.py \
    --ja-rows "$JA_ROWS" --commercial-rows "$COMMERCIAL_ROWS" --cdsco-rows "$CDSCO_ROWS" ) \
    2>&1 | grep -E 'Row counts|Summary —|status.: .(ok|failed)' || true
if [ "$ALERT_MONTHS" = "all" ]; then ALERT_SCOPE="--all"; else ALERT_SCOPE="--months $ALERT_MONTHS"; fi
( cd apps/etl && .venv/bin/python run_alerts.py $ALERT_SCOPE ) 2>&1 | grep -E 'Fetched|Loaded' || true

rule "4. The data arrived — and nothing failed"
psql_q -c "select
    (select count(*) from medicines where source = 'janaushadhi')      as jan_aushadhi,
    (select count(*) from medicines where source = 'commercial')       as commercial,
    (select count(jan_aushadhi_price) from medicines where source = 'commercial') as with_ja_price,
    (select count(*) from drug_alerts)     as drug_alerts,
    (select count(*) from cdsco_reference) as cdsco_registry,
    (select count(*) from etl_failed_rows) as failed_rows;"

rule "5. Load the barcode catalogue (six products, entered by hand)"
docker exec -i supabase_db_sahidawa-india psql -U postgres -d postgres -q < supabase/demo/product_barcodes_from_photos.sql
psql_q -c "select gtin, product_name, category, is_medicine from product_barcodes order by category;"

rule "6. Start the API"
( cd apps/barcode-api && PORT="$API_PORT" npx ts-node-dev --transpile-only src/index.ts ) \
    > /tmp/demo-api.log 2>&1 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
    curl -sf -m 1 "localhost:$API_PORT/health" >/dev/null 2>&1 && break
    sleep 1
done
curl -s "localhost:$API_PORT/health"; echo

rule "7. Barcode lookup — what Aushadhi IO's scanner gets back"
ask "A catalogued product — Ayurvedic, so CDSCO verification does not apply" /api/v1/products/barcode/8901138511975 20
ask "A barcode nobody has catalogued — logged for review" /api/v1/products/barcode/8901030865275 8
ask "A mistyped barcode — caught by the GS1 check digit" /api/v1/products/barcode/8901138511974 6

show() {
    printf '\n\033[1m%s\033[0m\n  GET %s\n' "$1" "$2"
    curl -s "localhost:$API_PORT$2" | python3 scripts/demo_show.py "$3"
}

rule "8. Medicines — search by name, typos allowed, with the Jan Aushadhi price"
show "Branded azithromycin next to its Jan Aushadhi generic price" \
    "/api/v1/medicines?search=azithromycin&source=commercial&limit=30" medicines
show "A typo still finds it: 'paracetmol'" "/api/v1/medicines?search=paracetmol&limit=3" names

rule "9. Drug alerts — batches CDSCO flagged"
show "Alerts for paracetamol, newest first" "/api/v1/drug-alerts?search=paracetamol&limit=5" alerts

rule "10. CDSCO brand registry — is this brand registered?"
show "Check 'Dolo 650' by 'Micro Labs'" \
    "/api/v1/cdsco-brands?brand=dolo%20650&manufacturer=micro%20labs&limit=3" brands

rule "Done"
echo "Pipeline → database → API, from an empty database, in one run. ($API)"
