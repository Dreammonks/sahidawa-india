# 2. Barcode Product Lookup

> **In short**
> - **Before:** scanning the barcode on a medicine pack in SahiDawa always gave an error.
> - **Now:** scan or type any barcode and SahiDawa says what the product is:
>   a medicine, an Ayurvedic or homeopathic product, or not a medicine at all.
>   If it doesn't know the barcode, it says so honestly.
> - **Tested** with photos of 7 real products bought from a pharmacy. All 7
>   barcodes were read and gave a sensible answer.
> - **Limit:** a barcode tells you *which product* it is, not whether *this
>   particular pack* is genuine.

---

## The problem

A barcode is the striped code printed on almost every pack. The numbers under
it identify the product.

When someone scanned that barcode in SahiDawa, it always failed. Four reasons:

1. **The scanner sent the barcode to the wrong check.** It was treated as a
   batch number, and the check that received it needs both a product name *and*
   a batch number. So it always answered with an error.
2. **SahiDawa had no way to look up a product by its barcode alone.**
3. **SahiDawa's data has no real barcodes.** One of its data collectors makes
   up barcode numbers, so they never match a real pack. Collecting more data
   doesn't solve this.
4. **The 7 test products weren't normal medicines:** 2 Ayurvedic, 1
   homeopathic, 2 personal-care products, 1 nutrition powder and 1 imported
   item. None was in SahiDawa's data.

**Goal:** every barcode should get an honest answer. Never an error, and never
a false "verified".

---

## How it works now

```
Scan, upload a photo, or type the barcode
                │
                ▼
     Does it look like a barcode?  ── no ──►  normal batch-number check
     (8, 12, 13 or 14 digits)
                │ yes
                ▼
  1. Look in the new product list      ── found ──►  show product, type, regulator
  2. Look in the medicines list        ── found ──►  show medicine + safety check
  3. Not found anywhere                ─────────►  say "unknown" and note it down
```

A few simple safety checks happen along the way:

- **Typing mistakes are caught.** The last digit of every barcode is a check
  digit worked out from the others. If someone types a number wrong, the check
  fails and SahiDawa says it's not a valid barcode.
- **The country is shown.** The first digits show which country registered the
  barcode (for example 890 = India). This is where the barcode was *registered*,
  not always where the product was made.
- **Unknown barcodes are recorded**, so the team can see which products people
  scan that SahiDawa doesn't have yet.
- **Repeat lookups are fast:** answers are remembered for one hour.

---

## What people see

For each result, SahiDawa shows a card with:
- the product name and brand;
- its **type**: medicine, Ayurvedic, homeopathic, food supplement, personal care;
- which **government body** regulates it;
- a plain-language note, for example: *"Licensed under AYUSH. The CDSCO brand
  registry does not cover it, so SahiDawa cannot check its authenticity yet."*;
- a box to type the **expiry date** by hand, which then says whether it's still valid.

### Who regulates what (why the note changes)

| Product type | Regulator | Can SahiDawa verify it? |
|---|---|---|
| Normal (allopathic) medicine | **CDSCO**, the national drug regulator | Yes, against the CDSCO registry |
| Ayurvedic or homeopathic | **AYUSH** ministry | Not yet: CDSCO's registry doesn't include them |
| Food and nutrition products | **FSSAI** | No: not a medicine |
| Pads, soaps and similar | **BIS** | No: not a medicine |

---

## Results with the 7 real products

Each product photo was uploaded on the scan page, and every barcode was read
from the photo.

| Product | Barcode | What SahiDawa said |
|---|---|---|
| Liv.52 (Himalaya) | 8901138511975 | Ayurvedic, regulated by AYUSH. Can't be verified by CDSCO |
| Karela tablets | 8906037151086 | Ayurvedic, regulated by AYUSH |
| Boericke & Tafel remedy | 8904188000864 | Homeopathic, regulated by AYUSH |
| Nutrition powder | 8904455004564 | Food product (FSSAI). Not a medicine |
| Whisper pads | 4987176319432 | Personal care (BIS). Not a medicine |
| Whisper XL pads | 4987176319517 | Personal care (BIS). Not a medicine |
| Imported product | 4103040895493 | **Unknown.** Registered in Germany. Recorded for review |

The last product was deliberately left out of the test data, to show what
happens with an unknown barcode.

**Didn't work:** reading the batch number and expiry date *from the photo*.
On these packs the text is printed sideways. Typing the expiry date by hand
works: entering `03/2028` shows "Valid".

---

## Two older bugs fixed along the way

1. **Photo uploads never finished their check.** On the scan page, uploading a
   photo set off a chain of events that cancelled its own safety check. People
   saw nothing happen. It's now cancelled only when the page is closed.
2. **Expiry dates were read wrongly.** Many packs print two dates side by side
   with no label, like `04/2025-03/2028` (made in April 2025, expires March
   2028). SahiDawa took the first date, so good stock looked expired. It now
   takes the **later** date, which is always the expiry.

---

## Is it tested?

| Check | Result |
|---|---|
| 26 new automatic tests for the API | ✅ All pass |
| 25 new automatic tests for the website | ✅ All pass |
| Website code checker (TypeScript) | ✅ No errors |
| All 7 real product photos in the browser | ✅ All gave the right kind of answer |

Some tests were already failing before this work, and nothing here touches
them: 3 in `medicineParser.test.ts` and 6 in `scanVerifyBrand.test.ts`.

---

## What this does NOT do

- **It can't tell a fake pack from a real one.** Every bottle of the same
  product has the same barcode, so a fake copy shows it too. Catching fakes
  needs batch-level data from manufacturers, or the newer QR codes some
  medicines carry.
- **It only knows 6 products so far.** They were typed in by hand from the
  photos and are clearly labelled as demo data. Real use needs a proper source
  of barcode data.
- **Ayurvedic and homeopathic products can't be verified yet**, because the
  government registry SahiDawa uses doesn't cover them.

---

## Try it yourself

**For developers.** First load the new table and the demo products into the database (one time):
```bash
DB=supabase_db_sahidawa-india
docker exec -i $DB psql -U postgres -d postgres -v ON_ERROR_STOP=1 < supabase/migrations/20260914000000_create_product_barcodes.sql
docker exec -i $DB psql -U postgres -d postgres -v ON_ERROR_STOP=1 < supabase/demo/product_barcodes_from_photos.sql
docker exec -i $DB psql -U postgres -d postgres -qc "NOTIFY pgrst, 'reload schema';"
```

Then open http://localhost:3000/en/scan and type one of these barcodes in the box:

| Type this | To see |
|---|---|
| `8901138511975` | An Ayurvedic product |
| `4987176319432` | A product that isn't a medicine |
| `8901234567890` | A normal medicine (Dolo 650, from the sample data) |
| `4103040895493` | An unknown barcode |
| `12345` | A number that isn't a barcode |

The API can also be called directly, e.g. http://localhost:4000/api/v1/products/barcode/8901138511975

---

## Technical details (for developers)

**Branch:** `feature/barcode-product-lookup`

| Commit | Change |
|---|---|
| `457f80a8` | Fix: scan page cancelled its own verification |
| `6e71b700` | New API endpoint `GET /api/v1/products/barcode/:gtin` and its database table |
| `c7154939` | Fix: expiry is the later of two printed dates |
| `60ad9e03` | Website: new result card, barcodes sent to the new lookup |
| `894e3caa` | Demo product data from the photos |

| Area | Files |
|---|---|
| Database | `supabase/migrations/20260914000000_create_product_barcodes.sql` (tables `product_barcodes`, `unknown_barcode_scans`, function `record_unknown_barcode`); demo data in `supabase/demo/product_barcodes_from_photos.sql` |
| API | `routes/products.ts`, `services/productLookup.service.ts`, `repositories/productBarcode.repository.ts`, `utils/gtin.ts` |
| Website | `lib/barcode.ts`, `lib/api/products.ts`, `hooks/useMedicineVerification.ts`, `hooks/useMedicineImageUpload.ts`, `components/scanner/results/ProductLookupResult.tsx` |

---

## Questions to decide

- [ ] Is the wording right for products that aren't medicines, and for unknown barcodes?
- [ ] Should this feature be offered to the original SahiDawa project?
- [ ] Where could real barcode data come from: GS1 India (the official barcode body), pharmacy suppliers, or manufacturers?
