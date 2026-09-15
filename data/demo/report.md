# SahiDawa small scrape demo — 2026-09-14 12:11

Row limit per dataset: 10

## Database row counts

| Table | Before | After | Change |
|---|---|---|---|
| medicines | 90 | 90 | +0 |
| pharmacies | 76 | 86 | +10 |
| cdsco_reference | 80720 | 80720 | +0 |
| drug_alerts | 0 | 0 | +0 |
| etl_failed_rows | 0 | 0 | +0 |

## Per source

### 1. CDSCO brand registry (JSON API) — ok (4.4s)
- **api_returned_rows:** 110428
- **requested_page_size:** 50
- **kept:** 200
- **sample:** [{'brand_name': 'CHLOROXYLENOL SOLUTION 4.8% w/v', 'firm_name': '14A,IDA, BHONGIR, YADADRI, TELANGANA,', 'license_number': 'TS/BGR/2021-85492'}, {'brand_name': 'HAND SANITIZER', 'firm_name': '14A,IDA, BHONGIR, YADADRI, TELANGANA,', 'license_number': 'TS/BGR/2021-85492'}, {'brand_name': 'Isopropyl Rubbing Alcohol', 'firm_name': '14A,IDA, BHONGIR, YADADRI, TELANGANA,', 'license_number': 'TS/BGR/2021-85492'}]

### 2. Jan Aushadhi product price list (headless browser) — ok (9.6s)
- **fetched:** 2431
- **kept:** 10
- **raw_file:** janaushadhi_raw_20260914_121040.csv
- **sample:** [{'generic_name': 'Aceclofenac and Paracetamol', 'strength': '100mg + 325mg', 'dosage_form': 'Tablet', 'mrp': 10.32}, {'generic_name': 'Aceclofenac', 'strength': '100mg', 'dosage_form': 'Tablet', 'mrp': 8.25}, {'generic_name': 'Pregabalin', 'strength': '75mg', 'dosage_form': 'Capsule', 'mrp': 22.69}]

### 3. Commercial medicine dataset (CSV download) — ok (0.0s)
- **kept:** 10
- **raw_file:** indian_medicine_data.csv
- **sample:** [{'brand_name': 'Augmentin 625 Duo Tablet', 'manufacturer': 'Glaxo SmithKline Pharmaceuticals Ltd', 'mrp': 223.42, 'barcode_id': '8900430408020'}, {'brand_name': 'Azithral 500 Tablet', 'manufacturer': 'Alembic Pharmaceuticals Ltd', 'mrp': 132.36, 'barcode_id': '8908801245649'}, {'brand_name': 'Ascoril LS Syrup', 'manufacturer': 'Glenmark Pharmaceuticals Ltd', 'mrp': 118.0, 'barcode_id': '8901732517038'}]

### 4. Validate + load medicines — ok (0.5s)
- **cdsco_validation:** 2/20 matched the CDSCO sample
- **total:** 20
- **inserted:** 17
- **skipped_unchanged:** 3
- **failed:** 0
- **success_rate:** 100.0

### 5. Jan Aushadhi stores (token + API) — ok (18.6s)
- **fetched:** 10
- **kept:** 10
- **sample:** [{'name': 'PMBJK00012', 'district': 'Annamayya', 'state': 'Andhra Pradesh'}, {'name': 'PMBJK00017', 'district': 'Annamayya', 'state': 'Andhra Pradesh'}, {'name': 'PMBJK00024', 'district': 'Guntur', 'state': 'Andhra Pradesh'}]
- **total:** 10
- **inserted:** 10
- **skipped_unchanged:** 0
- **failed:** 0
- **success_rate:** 100.0

### 6. CDSCO recall alert PDF (download + text) — ok (11.5s)
- **pdf_links_on_page:** 300
- **pdfs_checked:** [{'kb': 1449, 'text_chars': 0}, {'kb': 2244, 'text_chars': 0}, {'kb': 1148, 'text_chars': 0}, {'kb': 654, 'text_chars': 3200}]
- **text_preview:** File No. : COS-'! 1 01 1 ( 1 1ll 2812024-eoltice Government of lndia Directorate General of Health Services Central Drugs Standard Control Organisation (Cosmetics Division) FDA Bhawan, Kotla Road, New Delhi-'l 10002 Dated: I t2 AiJo 2025 Co rriqend um ln continuation to this office letter dated 20.0
- **note:** AI extraction into drug_alerts not run (no Gemini/Groq key); nothing inserted
