"""
SahiDawa — CDSCO Drug Alerts Scraper
====================================
Collects CDSCO's monthly drug alerts:

    nsq       — batches that failed a government quality test ("Not of
                Standard Quality"), published monthly since 2019
    spurious  — batches found to be fake, published monthly since 2025

SOURCE:
    https://cdsco.gov.in/opencms/opencms/en/Notifications/nsq-drugs/ embeds
    https://cdscoonline.gov.in/CDSCO/viewPublicNSQDrug, which loads its tables
    from the JSON endpoints used below. Until August 2025 the same alerts were
    scanned PDFs with no text; this source needs no OCR.

Every value is stored as CDSCO publishes it. Nothing is matched against the
medicines table: a batch alert names a product and a manufacturer, not one of
our rows, and a wrong link would flag the wrong medicine.
"""

import re
from datetime import datetime

import pandas as pd
import requests

from src.utils.logger import logger

BASE_URL = "https://cdscoonline.gov.in/CDSCO/"
ALERT_TABLES = {
    "nsq": "filteredNsqDrugTable",
    "spurious": "filteredSpuriousDrugTable",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)",
    "Referer": BASE_URL + "viewPublicNSQDrug",
    "X-Requested-With": "XMLHttpRequest",
}
REQUEST_TIMEOUT_SECONDS = 60
ALERT_KEY = ["alert_type", "product_name", "batch_number", "manufacturer", "reporting_month"]


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _month_start(published: str) -> str:
    """'JUL-2026' → '2026-07-01'. Raises ValueError for anything else."""
    return datetime.strptime(published.strip().title(), "%b-%Y").date().isoformat()


def normalize_record(record: dict, alert_type: str) -> dict | None:
    """One CDSCO row as a drug_alerts row, or None when it names no product."""
    product_name = _clean(record.get("str_product_name") or record.get("product_name_from_dtl"))
    if not product_name:
        return None

    return {
        "alert_type": alert_type,
        "product_name": product_name,
        "batch_number": _clean(record.get("str_batch_no")),
        "manufacturing_date": _clean(record.get("dt_manufacturing_date")),
        "expiry_date": _clean(record.get("dt_expiry_date")),
        "manufacturer": _clean(record.get("str_manufactured_by")),
        "reason": _clean(record.get("str_nsq_result")),
        "remarks": _clean(record.get("str_nsq_remarks")),
        "firm_reply": _clean(record.get("str_firm_reply")),
        "reporting_source": _clean(record.get("str_reporting_source")),
        "reported_by": _clean(record.get("str_reported_by_lab_or_state")),
        "reporting_month": _month_start(str(record.get("dt_reporting_month_year") or "")),
    }


class CDSCODrugAlertScraper:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def _get_json(self, endpoint: str, params: dict):
        response = self.session.get(
            BASE_URL + endpoint,
            params=params,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    def reporting_months(self, alert_type: str) -> list[str]:
        """Every month CDSCO has published for this alert type, newest first, as 'Jul-2026'."""
        months = []
        for year in self._get_json("reportingYears", {"tab": alert_type}):
            for month in self._get_json("reportingMonths", {"year": year, "tab": alert_type}):
                months.append(f"{month}-{year}")
        return sorted(months, key=_month_start, reverse=True)

    def fetch_month(self, alert_type: str, month: str) -> list[dict]:
        payload = self._get_json(
            ALERT_TABLES[alert_type],
            {"month": month, "source": "All", "tab": alert_type},
        )
        records = payload.get("aaData") or []
        # The endpoint returns a whole month in one response today. If CDSCO starts
        # paging it, stop rather than store a month with alerts silently missing.
        total = int(payload.get("iTotalRecords") or len(records))
        if len(records) < total:
            raise RuntimeError(f"CDSCO returned {len(records)} of {total} {alert_type} alerts for {month}")
        return records

    def scrape(self, latest_months: int | None = 3) -> pd.DataFrame:
        """
        Alerts from the latest `latest_months` published months of each type,
        or the full history when `latest_months` is None.
        """
        rows = []
        for alert_type in ALERT_TABLES:
            months = self.reporting_months(alert_type)
            if latest_months is not None:
                months = months[:latest_months]
            for month in months:
                records = self.fetch_month(alert_type, month)
                normalized = [normalize_record(r, alert_type) for r in records]
                rows.extend(r for r in normalized if r)
                logger.info(f"[DrugAlerts] {alert_type} {month}: {len(records)} alerts")

        df = pd.DataFrame(rows)
        if df.empty:
            return df
        before = len(df)
        df = df.drop_duplicates(subset=ALERT_KEY)
        logger.info(f"[DrugAlerts] {len(df)} alerts ({before - len(df)} duplicates removed)")
        return df
