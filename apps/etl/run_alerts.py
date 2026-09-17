"""
SahiDawa — CDSCO Drug Alerts Runner
===================================
Loads CDSCO's drug alerts (failed quality tests and spurious batches) into the
drug_alerts table.

USAGE:
    cd apps/etl
    python run_alerts.py              # the latest 3 published months (daily job)
    python run_alerts.py --months 12  # the latest 12 months
    python run_alerts.py --all        # every month since 2019 (first load)
    python run_alerts.py --dry-run    # fetch and count, write nothing

Running it again is safe: an alert already stored is updated, not duplicated.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.loaders.supabase_loader import SupabaseLoader
from src.scrapers.cdsco_drug_alerts import CDSCODrugAlertScraper
from src.utils.logger import logger

PIPELINE_NAME = "cdsco_drug_alerts"
DEFAULT_MONTHS = 3


def run(latest_months: int | None, dry_run: bool) -> int:
    df = CDSCODrugAlertScraper().scrape(latest_months=latest_months)
    if df.empty:
        logger.warning("[DrugAlerts] CDSCO returned no alerts; nothing to load")
        return 0

    counts = df["alert_type"].value_counts().to_dict()
    logger.info(f"[DrugAlerts] Fetched {len(df)} alerts: {counts}")
    if dry_run:
        return 0

    stats = SupabaseLoader(pipeline_name=PIPELINE_NAME).load(df, table="drug_alerts")
    logger.info(
        f"[DrugAlerts] Loaded — written: {stats['inserted']}, "
        f"unchanged: {stats.get('skipped_unchanged', 0)}, failed: {stats['failed']}"
    )
    return 1 if stats["failed"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Load CDSCO drug alerts into SahiDawa")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--months", type=int, default=DEFAULT_MONTHS,
                       help=f"Latest published months to load (default {DEFAULT_MONTHS})")
    scope.add_argument("--all", action="store_true", help="Load every published month")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and count, write nothing")
    args = parser.parse_args()

    if args.months < 1:
        parser.error("--months must be at least 1")

    sys.exit(run(latest_months=None if args.all else args.months, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
