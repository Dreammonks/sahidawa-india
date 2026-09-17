"""
SahiDawa — small, capped scrape demo
====================================
Pulls a LITTLE live data from every SahiDawa source using the project's own
scraper/normalizer/validator/loader classes, loads it into the local Supabase,
and prints a before/after report proving the data arrived.

Usage (from apps/etl, venv active):
    python demo_small_scrape.py --limit 10 --report ../../data/demo/report.md

Request volume is deliberately tiny: 1 CSV download per dataset, 1 CDSCO API
call, 1 store API page.
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Without sudo, Chromium's missing system libraries can be extracted into
# ~/.local/pw-libs (apt-get download + dpkg -x); Playwright's browser inherits this variable.
_PW_LIBS = Path.home() / ".local/pw-libs/root/usr/lib/x86_64-linux-gnu"
if _PW_LIBS.exists():
    os.environ["LD_LIBRARY_PATH"] = f"{_PW_LIBS}:{_PW_LIBS / 'nss'}:{os.environ.get('LD_LIBRARY_PATH', '')}"

import pandas as pd
import requests
from playwright.async_api import TimeoutError as PWTimeoutError, async_playwright

from src.loaders.supabase_loader import SupabaseLoader
from src.scrapers.cdsco import CDSCOScraper
from src.scrapers.commercial_medicine import CommercialMedicineNormalizer, CommercialMedicineScraper
from src.scrapers.jan_aushadhi import JanAushadhiNormalizer, JanAushadhiScraper
from src.scrapers.jan_aushadhi_stores import NEAR_BY_KENDRA_URL, JanAushadhiStoreScraper
from src.validators.cdsco_validator import CDSCOValidator

PIPELINE_NAME = "demo_small_scrape"
STORE_API_URL = "https://janaushadhi.gov.in:8443/api/v1/website/getAllKendraByStateDistrict"
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
COUNTED_TABLES = ["medicines", "pharmacies", "cdsco_reference", "etl_failed_rows"]
CDSCO_PAGE_SIZE = 50


def table_counts(client) -> dict[str, int]:
    return {t: client.table(t).select("*", count="exact").limit(1).execute().count for t in COUNTED_TABLES}


def run_step(name: str, fn, results: list[dict]):
    """Run one source independently so a single site being down doesn't hide the rest."""
    started = time.time()
    print(f"\n=== {name} ===", flush=True)
    try:
        outcome = fn()
        outcome.update({"source": name, "status": "ok", "seconds": round(time.time() - started, 1)})
    except Exception as exc:  # report every failure; this is a demo harness, not the pipeline
        outcome = {"source": name, "status": "failed", "error": f"{type(exc).__name__}: {exc}"[:300],
                   "seconds": round(time.time() - started, 1)}
    print(outcome, flush=True)
    results.append(outcome)
    return outcome


def cdsco_registry(rows: int) -> tuple[dict, pd.DataFrame]:
    # The CDSCO endpoint ignores iDisplayStart/iDisplayLength and returns the whole
    # registry on every call, so one request is enough; keep only a slice.
    records = CDSCOScraper()._fetch_single_page(1, 0, CDSCO_PAGE_SIZE)
    df = pd.DataFrame(records).head(rows)
    sample = df[["brand_name", "firm_name", "license_number"]].head(3).to_dict("records")
    return {"api_returned_rows": len(records), "requested_page_size": CDSCO_PAGE_SIZE,
            "kept": len(df), "sample": sample}, df


def jan_aushadhi_products(limit: int) -> tuple[dict, pd.DataFrame]:
    raw_path = asyncio.run(JanAushadhiScraper().scrape())
    df = JanAushadhiNormalizer().normalize(raw_path)
    total = len(df)
    df = df.head(limit)
    sample = df[["generic_name", "strength", "dosage_form", "mrp"]].head(3).to_dict("records")
    return {"fetched": total, "kept": len(df), "raw_file": raw_path.name, "sample": sample}, df


def commercial_products(limit: int) -> tuple[dict, pd.DataFrame]:
    raw_path = CommercialMedicineScraper().scrape()
    # The full file is ~254k rows; normalize only a slice so the demo stays quick.
    sample_path = raw_path.with_name(f"demo_sample_{limit}.csv")
    pd.read_csv(raw_path, nrows=limit * 3).to_csv(sample_path, index=False)
    df = CommercialMedicineNormalizer().normalize(sample_path).head(limit)
    sample = df[["brand_name", "manufacturer", "mrp", "barcode_id"]].head(3).to_dict("records")
    return {"kept": len(df), "raw_file": raw_path.name, "sample": sample}, df


async def _fetch_store_page(limit: int) -> list[dict]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context(user_agent=BROWSER_UA, ignore_https_errors=True)
        page = await context.new_page()
        token: dict[str, str] = {}

        def capture(request):
            auth = request.headers.get("authorization", "")
            if "Bearer" in auth:
                token.setdefault("value", auth)

        page.on("request", capture)
        try:
            await page.goto(NEAR_BY_KENDRA_URL, wait_until="networkidle", timeout=45000)
        except PWTimeoutError:
            pass
        await page.wait_for_timeout(3000)
        if "value" not in token:
            await browser.close()
            raise RuntimeError("Could not capture the site's authorization token")

        response = await context.request.post(
            STORE_API_URL,
            data={"pageIndex": 0, "pageSize": limit, "stateId": 0, "districtId": 0, "pinCode": 0, "storeCode": ""},
            headers={"authorization": token["value"], "accept": "application/json",
                     "content-type": "application/json"},
        )
        body = await response.json()
        await browser.close()
    return body.get("responseBody", {}).get("addKendraResponseList", [])


def jan_aushadhi_stores(limit: int) -> tuple[dict, pd.DataFrame]:
    records = asyncio.run(_fetch_store_page(limit))
    rows = [{
        "kendra_code": r.get("storeCode"), "name": r.get("contactPerson") or r.get("kendraName"),
        "state": r.get("stateName"), "district": r.get("districtName"), "pincode": str(r.get("pinCode") or ""),
        "address": r.get("kendraAddress"), "phone": str(r.get("contactNumber") or ""),
        "lat": r.get("latitude"), "lng": r.get("longitude"),
    } for r in records]
    df = JanAushadhiStoreScraper()._normalize(pd.DataFrame(rows))
    # Contact person names and phone numbers are personal data; keep them out of the report.
    sample = df[["name", "district", "state"]].head(3).to_dict("records") if not df.empty else []
    for row in sample:
        row["name"] = str(row["name"]).split(" - ")[0]
    return {"fetched": len(records), "kept": len(df), "sample": sample}, df


def load(loader: SupabaseLoader, df: pd.DataFrame, table: str) -> dict:
    stats = loader.load(df, table=table)
    return {k: stats.get(k) for k in ("total", "inserted", "skipped_unchanged", "failed", "success_rate")}


def write_report(path: Path, before: dict, after: dict, results: list[dict], limit: int) -> None:
    lines = [f"# SahiDawa small scrape demo — {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Row limit per dataset: {limit}", "", "## Database row counts", "",
             "| Table | Before | After | Change |", "|---|---|---|---|"]
    lines += [f"| {t} | {before[t]} | {after[t]} | {after[t] - before[t]:+d} |" for t in COUNTED_TABLES]
    lines += ["", "## Per source", ""]
    for r in results:
        lines.append(f"### {r['source']} — {r['status']} ({r['seconds']}s)")
        lines += [f"- **{k}:** {v}" for k, v in r.items() if k not in ("source", "status", "seconds")]
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Small capped live scrape into local Supabase")
    parser.add_argument("--limit", type=int, default=10, help="rows kept per medicine/store dataset")
    parser.add_argument("--cdsco-rows", type=int, default=200, help="CDSCO registry rows kept for validation")
    parser.add_argument("--report", type=Path, default=Path(__file__).resolve().parents[2] / "data" / "demo" / "report.md")
    args = parser.parse_args()

    loader = SupabaseLoader(pipeline_name=PIPELINE_NAME)
    before = table_counts(loader.client)
    print("Row counts before:", before)
    results: list[dict] = []
    frames: dict[str, pd.DataFrame] = {}

    def keep(name: str, step):
        def inner():
            summary, df = step()
            frames[name] = df
            return summary
        return inner

    run_step("1. CDSCO brand registry (JSON API)", keep("cdsco", lambda: cdsco_registry(args.cdsco_rows)), results)
    run_step("2. Jan Aushadhi product price list (headless browser)", keep("ja", lambda: jan_aushadhi_products(args.limit)), results)
    run_step("3. Commercial medicine dataset (CSV download)", keep("commercial", lambda: commercial_products(args.limit)), results)

    def validate_and_load():
        medicines = pd.concat([frames[k] for k in ("ja", "commercial") if k in frames], ignore_index=True)
        if medicines.empty:
            raise RuntimeError("No medicine rows scraped")
        verified = "not run (no CDSCO sample)"
        if "cdsco" in frames:
            validator = CDSCOValidator(supabase_client=loader.client)
            validator.load_reference(frames["cdsco"])
            medicines["_search_name"] = medicines["brand_name"].fillna(medicines["generic_name"])
            medicines = validator.validate(medicines, product_col="_search_name", manufacturer_col="manufacturer")
            medicines = medicines.drop(columns=["_search_name"])
            verified = f"{int(medicines['is_cdsco_verified'].sum())}/{len(medicines)} matched the CDSCO sample"
        return {"cdsco_validation": verified, **load(loader, medicines, "medicines")}

    def stores_and_load():
        summary, stores = jan_aushadhi_stores(args.limit)
        return {**summary, **load(loader, stores, "pharmacies")}

    run_step("4. Validate + load medicines", validate_and_load, results)
    run_step("5. Jan Aushadhi stores (token + API)", stores_and_load, results)

    after = table_counts(loader.client)
    print("Row counts after:", after)
    write_report(args.report, before, after, results, args.limit)


if __name__ == "__main__":
    main()
