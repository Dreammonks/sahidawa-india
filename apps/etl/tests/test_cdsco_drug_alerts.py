import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.scrapers.cdsco_drug_alerts import CDSCODrugAlertScraper, normalize_record

NSQ_RECORD = {
    "str_product_name": "Pantoprazole Tablets IP",
    "str_batch_no": "PEP5001",
    "dt_manufacturing_date": "Feb-2025",
    "dt_expiry_date": "Jan-2027",
    "str_manufactured_by": "Finecure Pharmaceuticals Ltd.  PF-5 & 6, Sanand",
    "str_nsq_result": "Dissolution test",
    "str_reporting_source": "State Lab",
    "str_reported_by_lab_or_state": "SDT&RL, Bhubaneswar",
    "dt_reporting_month_year": "JUL-2026",
}

SPURIOUS_RECORD = {
    "product_name_from_dtl": "Rosuvas F 20 Tablets",
    "str_batch_no": "SIF2736A",
    "dt_manufacturing_date": "Dec-2024",
    "dt_expiry_date": "May-2027",
    "str_manufactured_by": "Under Investigation",
    "str_nsq_result": "Assay of Fenofibrate",
    "str_reporting_source": "Not applicable",
    "str_reported_by_lab_or_state": "Drugs Inspector Telangana",
    "dt_reporting_month_year": "JUN-2025",
    "str_nsq_remarks": "The product is purported to be spurious.",
    "str_firm_reply": "The impugned batch was not manufactured by them.",
    "str_spurious_manufactured_by": None,
    "str_spurious_manufacturer_name": None,
}


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    """Answers CDSCO's endpoints from a table; records every call."""

    def __init__(self, months_by_tab, records_by_month):
        self.months_by_tab = months_by_tab
        self.records_by_month = records_by_month
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url.rsplit("/", 1)[-1], dict(params or {})))
        endpoint = url.rsplit("/", 1)[-1]
        tab = (params or {}).get("tab")
        if endpoint == "reportingYears":
            return FakeResponse(sorted({y for y, _ in self.months_by_tab[tab]}))
        if endpoint == "reportingMonths":
            return FakeResponse([m for y, m in self.months_by_tab[tab] if y == params["year"]])
        rows = self.records_by_month.get((tab, params["month"]), [])
        return FakeResponse({"iTotalRecords": len(rows), "aaData": rows})


def test_an_nsq_record_is_stored_as_published():
    row = normalize_record(NSQ_RECORD, "nsq")

    assert row == {
        "alert_type": "nsq",
        "product_name": "Pantoprazole Tablets IP",
        "batch_number": "PEP5001",
        "manufacturing_date": "Feb-2025",
        "expiry_date": "Jan-2027",
        "manufacturer": "Finecure Pharmaceuticals Ltd. PF-5 & 6, Sanand",
        "reason": "Dissolution test",
        "remarks": None,
        "firm_reply": None,
        "reporting_source": "State Lab",
        "reported_by": "SDT&RL, Bhubaneswar",
        "reporting_month": "2026-07-01",
    }


def test_a_spurious_record_keeps_remarks_and_the_firm_reply():
    row = normalize_record(SPURIOUS_RECORD, "spurious")

    assert row["alert_type"] == "spurious"
    assert row["product_name"] == "Rosuvas F 20 Tablets"
    assert row["remarks"] == "The product is purported to be spurious."
    assert row["firm_reply"] == "The impugned batch was not manufactured by them."
    assert row["reporting_month"] == "2025-06-01"


def test_a_record_without_a_product_name_is_skipped():
    assert normalize_record({**NSQ_RECORD, "str_product_name": "  "}, "nsq") is None


def test_only_the_latest_months_are_fetched_by_default():
    session = FakeSession(
        months_by_tab={
            "nsq": [("2026", "May"), ("2026", "Jun"), ("2026", "Jul"), ("2025", "Dec")],
            "spurious": [("2026", "Jul")],
        },
        records_by_month={
            ("nsq", "Jul-2026"): [NSQ_RECORD],
            ("spurious", "Jul-2026"): [{**SPURIOUS_RECORD, "dt_reporting_month_year": "JUL-2026"}],
        },
    )

    df = CDSCODrugAlertScraper(session=session).scrape(latest_months=2)

    fetched = [p["month"] for name, p in session.calls if name.startswith("filtered")]
    assert sorted(fetched) == ["Jul-2026", "Jul-2026", "Jun-2026"]
    assert sorted(df["alert_type"]) == ["nsq", "spurious"]


def test_all_months_are_fetched_for_a_full_history():
    session = FakeSession(
        months_by_tab={"nsq": [("2019", "Jan"), ("2026", "Jul")], "spurious": []},
        records_by_month={},
    )

    CDSCODrugAlertScraper(session=session).scrape(latest_months=None)

    fetched = [p["month"] for name, p in session.calls if name.startswith("filtered")]
    assert sorted(fetched) == ["Jan-2019", "Jul-2026"]


def test_the_same_alert_listed_twice_in_a_month_is_kept_once():
    session = FakeSession(
        months_by_tab={"nsq": [("2026", "Jul")], "spurious": []},
        records_by_month={("nsq", "Jul-2026"): [NSQ_RECORD, dict(NSQ_RECORD)]},
    )

    df = CDSCODrugAlertScraper(session=session).scrape(latest_months=1)

    assert len(df) == 1


def test_a_month_cut_short_by_paging_stops_the_run():
    class PagedSession(FakeSession):
        def get(self, url, params=None, headers=None, timeout=None):
            if url.endswith("filteredNsqDrugTable"):
                return FakeResponse({"iTotalRecords": 500, "aaData": [NSQ_RECORD]})
            return super().get(url, params, headers, timeout)

    session = PagedSession(months_by_tab={"nsq": [("2026", "Jul")], "spurious": []}, records_by_month={})

    with pytest.raises(RuntimeError, match="1 of 500"):
        CDSCODrugAlertScraper(session=session).scrape(latest_months=1)


def test_an_unreadable_reporting_month_raises():
    with pytest.raises(ValueError):
        normalize_record({**NSQ_RECORD, "dt_reporting_month_year": "sometime"}, "nsq")
