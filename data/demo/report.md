# SahiDawa scrape demo — 2026-09-17 08:53

Rows requested: Jan Aushadhi all, commercial 5000, CDSCO registry all

## Database row counts

| Table | Before | After | Change |
|---|---|---|---|
| medicines | 0 | 7439 | +7439 |
| cdsco_reference | 0 | 80732 | +80732 |
| etl_failed_rows | 0 | 0 | +0 |

## Per source

### 1. CDSCO brand registry (JSON API) — ok (6.5s)
- **api_returned_rows:** 110440
- **requested_page_size:** 50
- **kept:** 110440
- **sample:** [{'brand_name': 'CHLOROXYLENOL SOLUTION 4.8% w/v', 'firm_name': '14A,IDA, BHONGIR, YADADRI, TELANGANA,', 'license_number': 'TS/BGR/2021-85492'}, {'brand_name': 'HAND SANITIZER', 'firm_name': '14A,IDA, BHONGIR, YADADRI, TELANGANA,', 'license_number': 'TS/BGR/2021-85492'}, {'brand_name': 'Isopropyl Rubbing Alcohol', 'firm_name': '14A,IDA, BHONGIR, YADADRI, TELANGANA,', 'license_number': 'TS/BGR/2021-85492'}]

### 2. Jan Aushadhi product price list (headless browser) — ok (11.6s)
- **fetched:** 2439
- **kept:** 2439
- **raw_file:** janaushadhi_raw_20260917_084958.csv
- **sample:** [{'generic_name': 'Aceclofenac and Paracetamol', 'strength': '100mg + 325mg', 'dosage_form': 'Tablet', 'mrp': 10.32}, {'generic_name': 'Aceclofenac', 'strength': '100mg', 'dosage_form': 'Tablet', 'mrp': 8.25}, {'generic_name': 'Pregabalin', 'strength': '75mg', 'dosage_form': 'Capsule', 'mrp': 22.69}]

### 3. Commercial medicine dataset (CSV download) — ok (0.6s)
- **kept:** 5000
- **raw_file:** indian_medicine_data.csv
- **sample:** [{'brand_name': 'Augmentin 625 Duo Tablet', 'manufacturer': 'Glaxo SmithKline Pharmaceuticals Ltd', 'mrp': 223.42, 'barcode_id': None}, {'brand_name': 'Azithral 500 Tablet', 'manufacturer': 'Alembic Pharmaceuticals Ltd', 'mrp': 132.36, 'barcode_id': None}, {'brand_name': 'Ascoril LS Syrup', 'manufacturer': 'Glenmark Pharmaceuticals Ltd', 'mrp': 118.0, 'barcode_id': None}]

### 4. Validate + load medicines — ok (229.3s)
- **jan_aushadhi_price_linked:** 1340/5000 commercial medicines
- **cdsco_validation:** 346/7439 matched the CDSCO sample
- **total:** 7439
- **inserted:** 7439
- **skipped_unchanged:** 0
- **failed:** 0
- **success_rate:** 100.0
