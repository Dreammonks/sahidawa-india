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


def test_doses_in_brackets_leave_a_clean_name_and_lower_case_units(tmp_path):
    row = normalize_rows(
        tmp_path,
        "\"1\",\"2873\",\"Dolutegravir (50 Mg) + Emtricitabine (200 Mg) + Tenofovir Alafenamide (25 Mg) Tablets\",\"30s\",\"0\",\"Anti-retroviral\"",
    ).iloc[0]

    assert row["generic_name"] == "Dolutegravir + Emtricitabine + Tenofovir Alafenamide"
    assert row["strength"] == "50mg + 200mg + 25mg"


def test_a_volume_stated_after_the_form_applies_to_every_dose(tmp_path):
    row = normalize_rows(
        tmp_path,
        "\"1\",\"955\",\"Mefenamic Acid 50mg and Paracetamol 125mg Suspension per 5ml\",\"60 ml\",\"10.31\",\"Analgesic\"",
    ).iloc[0]

    assert row["generic_name"] == "Mefenamic Acid and Paracetamol"
    assert row["strength"] == "50mg/5ml + 125mg/5ml"


def test_per_written_without_a_space_still_joins_dose_and_volume(tmp_path):
    row = normalize_rows(tmp_path, "\"1\",\"77\",\"Cisplatin Injection IP 10 mg per10ml\",\"1s\",\"90\",\"Oncology\"").iloc[0]

    assert row["generic_name"] == "Cisplatin"
    assert row["strength"] == "10mg/10ml"


def test_per_a_pack_unit_is_dropped_from_the_name(tmp_path):
    row = normalize_rows(
        tmp_path,
        "\"1\",\"78\",\"Tiotropium Bromide Inhalation 9mcg per actuation\",\"1s\",\"90\",\"Respiratory\"",
    ).iloc[0]

    assert row["generic_name"] == "Tiotropium Bromide Inhalation"
    assert row["strength"] == "9mcg"


def test_per_ml_without_a_number_applies_to_every_dose(tmp_path):
    row = normalize_rows(
        tmp_path,
        "\"1\",\"79\",\"Etophyllin 84.7mg and Theophylline 25.3mg Injection per ml\",\"2 ml\",\"9\",\"Respiratory\"",
    ).iloc[0]

    assert row["generic_name"] == "Etophyllin and Theophylline"
    assert row["strength"] == "84.7mg/ml + 25.3mg/ml"


def test_a_presentation_phrase_leaves_no_dangling_words(tmp_path):
    row = normalize_rows(
        tmp_path,
        '"1","3001","Romiplostim Powder and Solvent for solution for Injection 250mcg per 0.5 vial","1s","0","Oncology"',
    ).iloc[0]

    assert row["generic_name"] == "Romiplostim"


def test_a_missing_pack_size_is_not_read_as_the_word_nan(tmp_path, monkeypatch):
    seen = []
    original = JanAushadhiNormalizer._stated_form
    monkeypatch.setattr(
        JanAushadhiNormalizer, "_stated_form", lambda self, text: seen.append(text) or original(self, text)
    )

    normalize_rows(tmp_path, '"1","3002","Paclitaxel Protein Bound Particles","","0","Oncology"')

    assert seen and all("nan" not in text.lower().split() for text in seen)
