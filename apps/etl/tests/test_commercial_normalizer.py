import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.scrapers.commercial_medicine import CommercialMedicineNormalizer

CSV_HEADER = (
    "id,name,price(₹),Is_discontinued,manufacturer_name,type,"
    "pack_size_label,short_composition1,short_composition2"
)


def normalize_rows(tmp_path: Path, *rows: str) -> pd.DataFrame:
    csv_path = tmp_path / "commercial.csv"
    csv_path.write_text("\n".join([CSV_HEADER, *rows]) + "\n", encoding="utf-8")
    return CommercialMedicineNormalizer().normalize(csv_path)


@pytest.fixture
def augmentin(tmp_path):
    return normalize_rows(
        tmp_path,
        "1,Augmentin 625 Duo Tablet,223.42,FALSE,Glaxo SmithKline Pharmaceuticals Ltd,"
        "allopathy,strip of 10 tablets,Amoxycillin  (500mg) , Clavulanic Acid (125mg)",
    ).iloc[0]


def test_generic_name_has_no_empty_brackets_left_by_the_dose(augmentin):
    assert augmentin["generic_name"] == "Amoxycillin + Clavulanic Acid"


def test_strength_lists_one_dose_per_ingredient(augmentin):
    assert augmentin["strength"] == "500mg + 125mg"


def test_composition_collapses_repeated_spaces(augmentin):
    assert augmentin["composition"] == "Amoxycillin (500mg) + Clavulanic Acid (125mg)"


def test_pack_size_is_kept(augmentin):
    assert augmentin["pack_size"] == "strip of 10 tablets"


def test_liquid_dose_stays_a_single_ratio(tmp_path):
    row = normalize_rows(
        tmp_path,
        "3,Ascoril LS Drops,72,FALSE,Glenmark Pharmaceuticals Ltd,allopathy,"
        "bottle of 15 ml Oral Drops,Ambroxol (7.5mg/ml) , Levosalbutamol (0.25mg/5ml)",
    ).iloc[0]

    assert row["generic_name"] == "Ambroxol + Levosalbutamol"
    assert row["strength"] == "7.5mg/ml + 0.25mg/5ml"


def test_missing_price_is_null_not_zero(tmp_path):
    row = normalize_rows(
        tmp_path,
        "4,Nameless Price Tablet,,FALSE,Some Pharma Ltd,allopathy,strip of 10 tablets,Paracetamol (500mg),",
    ).iloc[0]

    assert pd.isna(row["mrp"])


def test_no_barcode_is_invented(augmentin):
    assert pd.isna(augmentin["barcode_id"])


def test_no_approval_or_alert_status_is_claimed(augmentin):
    assert "cdsco_approval_status" not in augmentin.index
    assert "is_counterfeit_alert" not in augmentin.index


def test_dosage_form_is_empty_when_the_source_names_none(tmp_path):
    row = normalize_rows(
        tmp_path,
        "5,Zinconia 50mg,99,FALSE,Some Pharma Ltd,allopathy,pack of 1,Zinc (50mg),",
    ).iloc[0]

    assert pd.isna(row["dosage_form"])


def test_oral_drops_are_not_called_eye_drops(tmp_path):
    row = normalize_rows(
        tmp_path,
        "60,Ascoril LS Drops,72,FALSE,Glenmark Pharmaceuticals Ltd,allopathy,"
        "bottle of 15 ml Oral Drops,Ambroxol (7.5mg/ml) , Levosalbutamol (0.25mg/ml)",
    ).iloc[0]

    assert row["dosage_form"] == "Drops"


def test_one_row_per_brand_and_manufacturer(tmp_path):
    df = normalize_rows(
        tmp_path,
        "1,Dolo 650 Tablet,30,FALSE,Micro Labs Ltd,allopathy,strip of 15 tablets,Paracetamol (650mg),",
        "2,Dolo 650 Tablet,30,FALSE,Micro Labs Ltd,allopathy,strip of 15 tablets,Paracetamol (650mg),",
        "3,Dolo 650 Tablet,31,FALSE,Other Labs Ltd,allopathy,strip of 15 tablets,Paracetamol (650mg),",
    )

    assert len(df) == 2


def test_upper_case_units_are_written_in_lower_case(tmp_path):
    row = normalize_rows(
        tmp_path,
        "7,Tenvir EM Tablet,120,FALSE,Cipla Ltd,allopathy,bottle of 30 tablets,Tenofovir (300 Mg) , Emtricitabine (200 MG)",
    ).iloc[0]

    assert row["strength"] == "300mg + 200mg"
    assert row["generic_name"] == "Tenofovir + Emtricitabine"
