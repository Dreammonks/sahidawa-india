# 3. How SahiDawa Collects Its Data

> **In short**
> - SahiDawa doesn't type medicine data in by hand. Small programs called
>   **scrapers** copy it from government and public websites automatically,
>   every day.
> - It uses **5 sources**: the national drug registry, government recall
>   notices, the Jan Aushadhi medicine price list, Jan Aushadhi shop
>   locations, and a public medicine dataset.
> - A small live test on 14 September 2026 worked for **4 of the 5 sources**.
>   Recall notices need an AI key we don't have.
> - The test found **8 problems**. One data source was completely broken; it
>   is now fixed.

---

## The big picture

Imagine a helper who, every night:
1. visits several government websites;
2. downloads their medicine lists, prices, shop addresses and recall notices;
3. tidies the data (consistent names, units split out);
4. checks each medicine against the official government registry;
5. files everything neatly into SahiDawa's database.

That helper is the **data pipeline**. It runs by itself on GitHub every night,
so the website always has fresh data.

---

## The 5 data sources

| # | Source | Who runs it | What SahiDawa gets | How it's collected |
|---|---|---|---|---|
| 1 | **Drug brand registry** | CDSCO (national drug regulator) | Approved medicine brands and their makers | Reads the data service behind the website directly: fast and reliable |
| 2 | **Recall notices** | CDSCO | Medicines recalled or found "not of standard quality" | Downloads the notice PDFs, then uses AI to pull out the details |
| 3 | **Medicine price list** | Jan Aushadhi | Low-cost government generics and their prices | Opens the website in a hidden browser, because the page only works in a real browser |
| 4 | **Shop locations** | Jan Aushadhi | Addresses and map points of government medicine shops | Hidden browser gets access, then asks the site's data service |
| 5 | **Medicine dataset** | Public dataset on GitHub | Branded medicines, makers, prices | Downloads a spreadsheet file |

---

## How the pipeline works, step by step

```
 1. Collect   →   2. Tidy   →   3. Connect   →   4. Check   →   5. Save
```

| Step | Plain meaning |
|---|---|
| **1. Collect** | Download raw data from each source |
| **2. Tidy** | Clean it up. Example: "Aceclofenac Tablets IP 100 mg" becomes name *Aceclofenac*, strength *100 mg*, form *Tablet* |
| **3. Connect** | Relate records from different sources to each other |
| **4. Check** | Compare each medicine with the official CDSCO registry. A close match on name and maker (90 out of 100 or better) marks it as verified |
| **5. Save** | Store it in the database safely |

### The "save" step is the most careful part

It's more than a copy. It:
- **tries again** if the internet hiccups, but not if the data itself is bad;
- **skips** records that haven't changed, so nightly runs stay quick;
- **never wipes good data.** If a website leaves a field empty one day, the old
  value is kept;
- **keeps a list of failed records**, so they can be retried later instead of lost.

This part alone is about 1,070 lines of code, roughly as much as all four
collectors put together, and it has over 1,100 lines of tests. Anyone rebuilding this should plan most of the
effort here.

### Recall notices use an AI helper

Recall notices are PDF files. A separate AI "agent" downloads each PDF, reads
it, pulls out the medicine name, batch and maker, removes duplicates, and
saves the alert. Each notice gets a unique fingerprint, so the same notice is
never saved twice. **This step needs a Gemini or Groq AI key**, which isn't
set up yet.

### When it runs

| When | What |
|---|---|
| Every night (02:00 UTC) | The main pipeline |
| Every Sunday (03:00 UTC) | Shop locations |
| Any time | Can be started by hand on GitHub |

---

## The live test (14 September 2026)

**What was done:** SahiDawa's own collectors were run once against the real
websites, but capped at a tiny amount (10 records per source) and saved into
a local test database, not the live site.

**Why so small:** to prove the data arrives without putting load on
government servers.

### Results

| Source | Did data arrive? | What happened |
|---|---|---|
| Drug brand registry | ✅ Yes | 110,428 records received in 4 seconds; **80,720** unique ones saved |
| Recall notices | ⚠️ Partly | 300 notices found; PDFs download, but 3 of the 4 checked were scanned images with no readable text; not saved (no AI key) |
| Medicine price list | ✅ Yes, **after a fix** | 2,431 medicines received; 10 saved |
| Shop locations | ✅ Yes | 10 shops saved, with map positions |
| Medicine dataset | ✅ Yes | 10 medicines saved |
| **Save step** | ✅ Yes | 20 medicines saved, **0 failures** |

### Before and after in the database

| What | Before | After |
|---|---|---|
| Medicines | 70 | **90** |
| Official registry records | 0 | **80,720** |
| Shops | 36 | +10 on every run, even for the same shops (see problem 4) |
| Recall alerts | 0 | 0 |
| Failed records | 0 | 0 |

### Proof it reaches the website

On the SahiDawa home page, typing **"Allegra"** in the medicine search now
also suggests **"Allegra 120mg Tablet"**, which came from this test.

---

## Problems found

| # | Problem | Why it matters | Status |
|---|---|---|---|
| 1 | **The Jan Aushadhi price list moved to a new web address.** The old address still "loads", but shows a "page not found" screen | That collector got nothing and gave no warning | ✅ **Fixed**: address updated |
| 2 | **The drug registry ignores "send me page 2".** Every request returns all ~110,000 records | The collector asks for ~1,100 pages, so it would download the whole registry ~1,100 times: very slow and heavy on a government server | ❌ Not fixed; needs a decision |
| 3 | **The database was missing columns the save step needs** (strength, dosage form, schedule, source) | Every medicine save would fail | ⚠️ Fixed on the test laptop only; needs a proper fix in the project |
| 4 | **Shops are added again on every run** | A full weekly run would keep adding ~20,600 duplicate shops | ❌ Not fixed |
| 5 | **Most recall PDFs are scanned pictures** | There's no text to read without OCR or AI | ❌ Needs OCR or an AI key |
| 6 | **Few medicines get "verified"** (2 of 20). Generic names are compared with a list of brand names, and words like "Tablet" lower the match score | "Verified" badges will be rare | ❌ The matching needs a review |
| 7 | **The medicine dataset's barcodes are made up** by the collector | They never match a real pack (see guide 2) | Known |
| 8 | **The hidden browser needed extra system files** on Linux | It wouldn't start | ⚠️ Worked around; proper fix is `sudo apt install libnss3 libnspr4 libasound2t64` |

---

## Run the test yourself

**For developers**, inside WSL, from the project folder:
```bash
cd apps/etl
python -m venv .venv && . .venv/bin/activate      # first time only
pip install -e . pdfplumber beautifulsoup4       # first time only
python demo_small_scrape.py --limit 10 --cdsco-rows 200
```

- It takes about 40 seconds.
- It prints each source as it runs, then the database counts before and after.
- It writes a report to `data/demo/report.md`.
- The database must have the missing columns from problem 3.

**To look at the data:** open http://localhost:54323, go to **SQL Editor**,
and paste the queries from `data/demo/quick_queries.sql`. The first one shows
all 5 sources in a single table.

---

## Technical details (for developers)

**Branch:** `feature/etl-small-scrape-demo`

| Commit | Change |
|---|---|
| `c8d58b5d` | Fix: new Jan Aushadhi price list address (`apps/etl/src/scrapers/jan_aushadhi.py`) |
| `9d8bde17` | Demo script `apps/etl/demo_small_scrape.py`, report and SQL queries in `data/demo/` |

**Where the code lives:**

| What | File |
|---|---|
| Runs the whole pipeline | `apps/etl/run_all.py` |
| Collectors | `apps/etl/src/scrapers/` (`cdsco.py`, `jan_aushadhi.py`, `jan_aushadhi_stores.py`, `commercial_medicine.py`) |
| Registry check | `apps/etl/src/validators/cdsco_validator.py` |
| Save step | `apps/etl/src/loaders/supabase_loader.py` |
| Recall notice AI agent | `apps/ml/agent/cdsco_alert_agent.py` |
| Nightly schedule | `.github/workflows/etl-cron.yml` |

The project's own technical guide is `docs/etl-pipeline.md`.
