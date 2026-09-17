"""
SahiDawa — live scrape demo
===========================
Pulls live data from every SahiDawa medicine source using the project's own
scraper/normalizer/validator/loader classes, loads it into the local Supabase,
and prints a before/after report proving the data arrived.

Usage (from apps/etl, venv active):
    python demo_small_scrape.py                           # full JA list, 5,000 commercial, full registry
    python demo_small_scrape.py --ja-rows 10 --commercial-rows 10 --cdsco-rows 300   # quick run

A row count of 0 means every row. Each source is still one download.
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Without sudo, Chromium's missing system libraries can be extracted into
# ~/.local/pw-libs (apt-get download + dpkg -x); Playwright's browser inherits this variable.
_PW_LIBS = Path.home() / ".local/pw-libs/root/usr/lib/x86_64-linux-gnu"
if _PW_LIBS.exists():
    os.environ["LD_LIBRARY_PATH"] = f"{_PW_LIBS}:{_PW_LIBS / 'nss'}:{os.environ.get('LD_LIBRARY_PATH', '')}"

import pandas as pd

from src.loaders.supabase_loader import SupabaseLoader
from src.scrapers.cdsco import CDSCOScraper
from src.scrapers.commercial_medicine import CommercialMedicineNormalizer, CommercialMedicineScraper
from src.scrapers.jan_aushadhi import JanAushadhiNormalizer, JanAushadhiScraper
from src.utils.price_linking import link_jan_aushadhi_prices
from src.validators.cdsco_validator import CDSCOValidator

PIPELINE_NAME = "demo_small_scrape"
COUNTED_TABLES = ["medicines", "cdsco_reference", "etl_failed_rows"]
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


def first_rows(df: pd.DataFrame, rows: int) -> pd.DataFrame:
    return df.head(rows) if rows else df


def cdsco_registry(rows: int) -> tuple[dict, pd.DataFrame]:
    # The CDSCO endpoint ignores iDisplayStart/iDisplayLength and returns the whole
    # registry on every call, so one request is enough.
    records = CDSCOScraper()._fetch_single_page(1, 0, CDSCO_PAGE_SIZE)
    df = first_rows(pd.DataFrame(records), rows)
    sample = df[["brand_name", "firm_name", "license_number"]].head(3).to_dict("records")
    return {"api_returned_rows": len(records), "requested_page_size": CDSCO_PAGE_SIZE,
            "kept": len(df), "sample": sample}, df


def jan_aushadhi_products(rows: int) -> tuple[dict, pd.DataFrame]:
    raw_path = asyncio.run(JanAushadhiScraper().scrape())
    df = JanAushadhiNormalizer().normalize(raw_path)
    kept = first_rows(df, rows)
    sample = kept[["generic_name", "strength", "dosage_form", "mrp"]].head(3).to_dict("records")
    # The full list is returned: commercial prices are linked against all of it.
    return {"fetched": len(df), "kept": len(kept), "raw_file": raw_path.name, "sample": sample}, df


def commercial_products(rows: int) -> tuple[dict, pd.DataFrame]:
    raw_path = CommercialMedicineScraper().scrape()
    if rows:
        # The full file is ~254k rows. Read three times what is kept, because
        # discontinued and duplicate rows are dropped during normalizing.
        sample_path = raw_path.with_name(f"demo_sample_{rows}.csv")
        pd.read_csv(raw_path, nrows=rows * 3).to_csv(sample_path, index=False)
        raw_path_to_normalize = sample_path
    else:
        raw_path_to_normalize = raw_path
    df = first_rows(CommercialMedicineNormalizer().normalize(raw_path_to_normalize), rows)
    sample = df[["brand_name", "manufacturer", "mrp", "barcode_id"]].head(3).to_dict("records")
    return {"kept": len(df), "raw_file": raw_path.name, "sample": sample}, df


def load(loader: SupabaseLoader, df: pd.DataFrame, table: str) -> dict:
    stats = loader.load(df, table=table)
    return {k: stats.get(k) for k in ("total", "inserted", "skipped_unchanged", "failed", "success_rate")}


def write_report(path: Path, before: dict, after: dict, results: list[dict], sizes: str) -> None:
    lines = [f"# SahiDawa scrape demo — {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Rows requested: {sizes}", "", "## Database row counts", "",
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
    parser.add_argument("--ja-rows", type=int, default=0, help="Jan Aushadhi medicines to load (0 = all)")
    parser.add_argument("--commercial-rows", type=int, default=5000, help="commercial medicines to load (0 = all)")
    parser.add_argument("--cdsco-rows", type=int, default=0, help="CDSCO registry rows to load (0 = all)")
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
    run_step("2. Jan Aushadhi product price list (headless browser)", keep("ja", lambda: jan_aushadhi_products(args.ja_rows)), results)
    run_step("3. Commercial medicine dataset (CSV download)", keep("commercial", lambda: commercial_products(args.commercial_rows)), results)

    def validate_and_load():
        linked = "not run (Jan Aushadhi list or commercial rows missing)"
        if "ja" in frames and "commercial" in frames:
            prices = link_jan_aushadhi_prices(frames["ja"], frames["commercial"])
            frames["commercial"]["jan_aushadhi_price"] = prices
            linked = f"{sum(p is not None for p in prices)}/{len(prices)} commercial medicines"
        parts = [first_rows(frames["ja"], args.ja_rows)] if "ja" in frames else []
        parts += [frames["commercial"]] if "commercial" in frames else []
        medicines = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
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
        return {"jan_aushadhi_price_linked": linked, "cdsco_validation": verified,
                **load(loader, medicines, "medicines")}

    run_step("4. Validate + load medicines", validate_and_load, results)

    after = table_counts(loader.client)
    print("Row counts after:", after)
    sizes = (f"Jan Aushadhi {args.ja_rows or 'all'}, commercial {args.commercial_rows or 'all'}, "
             f"CDSCO registry {args.cdsco_rows or 'all'}")
    write_report(args.report, before, after, results, sizes)


if __name__ == "__main__":
    main()
