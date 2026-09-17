import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.scrapers.jan_aushadhi import JanAushadhiNormalizer

CSV_HEADER = '"Sr No","Drug Code","Generic Name","Unit Size","MRP","Group Name"'


def normalize_rows(tmp_path: Path, *rows: str) -> pd.DataFrame:
    csv_path = tmp_path / "janaushadhi.csv"
    csv_path.write_text("\n".join([CSV_HEADER, *rows]) + "\n", encoding="utf-8-sig")
    return JanAushadhiNormalizer().normalize(csv_path)


def test_composition_is_the_published_name_without_form_words(tmp_path):
    row = normalize_rows(
        tmp_path,
        '"1","1","Aceclofenac 100mg and Paracetamol 325mg Tablets","10\'s","10.32","Analgesic"',
    ).iloc[0]

    assert row["composition"] == "Aceclofenac 100mg and Paracetamol 325mg"


def test_drug_code_and_unit_size_are_kept(tmp_path):
    row = normalize_rows(
        tmp_path,
        '"2","2","Aceclofenac Tablets IP 100 mg","10\'s","8.25","Analgesic"',
    ).iloc[0]

    assert row["source_product_code"] == "2"
    assert row["pack_size"] == "10's"


def test_strengths_of_the_same_medicine_stay_separate_products(tmp_path):
    df = normalize_rows(
        tmp_path,
        '"1","1514","Abiraterone Acetate Tablets 250mg","120\'s","6000","Oncology"',
        '"2","2010","Abiraterone Acetate Tablets 500mg","60\'s","5100","Oncology"',
    )

    assert sorted(df["source_product_code"]) == ["1514", "2010"]
    assert set(df["generic_name"]) == {"Abiraterone Acetate"}


def test_same_medicine_in_two_pack_sizes_keeps_both_codes(tmp_path):
    df = normalize_rows(
        tmp_path,
        '"1","10","Paracetamol Tablets IP 500 mg","10\'s","9.5","Analgesic"',
        '"2","11","Paracetamol Tablets IP 500 mg","15\'s","14","Analgesic"',
    )

    assert len(df) == 2


def test_liquid_dose_per_volume_is_one_strength(tmp_path):
    row = normalize_rows(
        tmp_path,
        '"1","239","Cetirizine Syrup IP 5 mg per 5 ml","60 ml","13.41","Anti-Histaminic"',
    ).iloc[0]

    assert row["strength"] == "5mg/5ml"


def test_zero_price_is_stored_as_unknown(tmp_path):
    row = normalize_rows(
        tmp_path,
        '"1","2010","Abiraterone Acetate Tablets 500mg","60\'s","0","Oncology"',
    ).iloc[0]

    assert pd.isna(row["mrp"])
    assert pd.isna(row["jan_aushadhi_price"])


def test_nothing_the_list_does_not_say_is_filled_in(tmp_path):
    row = normalize_rows(
        tmp_path,
        '"1","1","Aceclofenac 100mg and Paracetamol 325mg Tablets","10\'s","10.32","Analgesic"',
    ).iloc[0]

    assert pd.isna(row["manufacturer"])
    assert "schedule" not in row.index
    assert "cdsco_approval_status" not in row.index
    assert "is_counterfeit_alert" not in row.index


def test_pack_count_alone_does_not_make_a_tablet(tmp_path):
    row = normalize_rows(
        tmp_path,
        '"1","2126","Absorbent Cotton Wool IP 200g","1\'s","63.75","Surgical"',
    ).iloc[0]

    assert pd.isna(row["dosage_form"])


def test_drops_are_not_assumed_to_be_eye_drops(tmp_path):
    row = normalize_rows(
        tmp_path,
        '"1","300","Paracetamol Paediatric Drops 100mg per ml","15 ml","12","Analgesic"',
    ).iloc[0]

    assert row["dosage_form"] == "Drops"
