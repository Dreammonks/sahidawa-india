import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.scrapers.jan_aushadhi_stores import JanAushadhiStoreScraper


def store_row(**overrides) -> dict:
    row = {
        "kendra_code": "PMBJK00012",
        "name": "Test Contact",
        "state": "Andhra Pradesh",
        "district": "Annamayya",
        "pincode": "516360",
        "address": "Shop 1, Main Road",
        "phone": "9000000000",
        "lat": 13.9,
        "lng": 79.1,
    }
    row.update(overrides)
    return row


def normalize(*rows: dict) -> pd.DataFrame:
    return JanAushadhiStoreScraper()._normalize(pd.DataFrame(list(rows)))


def test_store_code_and_pincode_are_kept():
    row = normalize(store_row()).iloc[0]

    assert row["store_code"] == "PMBJK00012"
    assert row["pincode"] == "516360"


def test_missing_pincode_is_null():
    row = normalize(store_row(pincode="")).iloc[0]

    assert pd.isna(row["pincode"])


def test_no_verification_or_approval_is_claimed():
    row = normalize(store_row()).iloc[0]

    assert "is_verified" not in row.index
    assert "status" not in row.index
