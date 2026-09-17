# SahiDawa small scrape demo — 2026-09-17 05:32

Row limit per dataset: 10

## Database row counts

| Table | Before | After | Change |
|---|---|---|---|
| medicines | 0 | 20 | +20 |
| pharmacies | 0 | 10 | +10 |
| cdsco_reference | 0 | 278 | +278 |
| etl_failed_rows | 0 | 0 | +0 |

## Per source

### 1. CDSCO brand registry (JSON API) — ok (6.9s)
- **api_returned_rows:** 110440
- **requested_page_size:** 50
- **kept:** 300
- **sample:** [{'brand_name': 'CHLOROXYLENOL SOLUTION 4.8% w/v', 'firm_name': '14A,IDA, BHONGIR, YADADRI, TELANGANA,', 'license_number': 'TS/BGR/2021-85492'}, {'brand_name': 'HAND SANITIZER', 'firm_name': '14A,IDA, BHONGIR, YADADRI, TELANGANA,', 'license_number': 'TS/BGR/2021-85492'}, {'brand_name': 'Isopropyl Rubbing Alcohol', 'firm_name': '14A,IDA, BHONGIR, YADADRI, TELANGANA,', 'license_number': 'TS/BGR/2021-85492'}]

### 2. Jan Aushadhi product price list (headless browser) — ok (13.5s)
- **fetched:** 2439
- **kept:** 10
- **raw_file:** janaushadhi_raw_20260917_053236.csv
- **sample:** [{'generic_name': 'Aceclofenac and Paracetamol', 'strength': '100mg + 325mg', 'dosage_form': 'Tablet', 'mrp': 10.32}, {'generic_name': 'Aceclofenac', 'strength': '100mg', 'dosage_form': 'Tablet', 'mrp': 8.25}, {'generic_name': 'Pregabalin', 'strength': '75mg', 'dosage_form': 'Capsule', 'mrp': 22.69}]

### 3. Commercial medicine dataset (CSV download) — ok (0.0s)
- **kept:** 10
- **raw_file:** indian_medicine_data.csv
- **sample:** [{'brand_name': 'Augmentin 625 Duo Tablet', 'manufacturer': 'Glaxo SmithKline Pharmaceuticals Ltd', 'mrp': 223.42, 'barcode_id': None}, {'brand_name': 'Azithral 500 Tablet', 'manufacturer': 'Alembic Pharmaceuticals Ltd', 'mrp': 132.36, 'barcode_id': None}, {'brand_name': 'Ascoril LS Syrup', 'manufacturer': 'Glenmark Pharmaceuticals Ltd', 'mrp': 118.0, 'barcode_id': None}]

### 4. Validate + load medicines — ok (0.4s)
- **cdsco_validation:** 0/20 matched the CDSCO sample
- **total:** 20
- **inserted:** 20
- **skipped_unchanged:** 0
- **failed:** 0
- **success_rate:** 100.0

### 5. Jan Aushadhi stores (token + API) — ok (17.5s)
- **fetched:** 10
- **kept:** 10
- **sample:** [{'name': 'PMBJK00012', 'district': 'Annamayya', 'state': 'Andhra Pradesh'}, {'name': 'PMBJK00017', 'district': 'Annamayya', 'state': 'Andhra Pradesh'}, {'name': 'PMBJK00024', 'district': 'Guntur', 'state': 'Andhra Pradesh'}]
- **total:** 10
- **inserted:** 10
- **skipped_unchanged:** 0
- **failed:** 0
- **success_rate:** 100.0
