"""
SahiDawa — Commercial Medicine Scraper + Normalizer
===================================================
Fetches commercial medicine data from the public Indian Medicine Dataset repository,
normalizes it, and maps it to our medicines table schema.
"""

import os
import re
from pathlib import Path
import pandas as pd
import requests

from src.utils.logger import logger

DATASET_URL = "https://raw.githubusercontent.com/junioralive/Indian-Medicine-Dataset/main/DATA/indian_medicine_data.csv"
RAW_DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "raw" / "commercial"

# A dose, optionally per a quantity: "500mg", "30mg/5ml", "7.5mg/ml".
# Must match the Jan Aushadhi normalizer's pattern, or strengths stop lining up
# when commercial medicines are linked to Jan Aushadhi prices.
DOSE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|iu|units?|%)"
    r"(?:\s*(?:/|\bper\b)\s*(\d+(?:\.\d+)?)?\s*(mg|mcg|g|ml|iu|units?|%))?",
    re.IGNORECASE,
)
BRACKETED_DOSE = re.compile(r"\([^)]*\d[^)]*\)")

STATED_FORMS = [
    (r"\btablets?\b", "Tablet"),
    (r"\bcapsules?\b", "Capsule"),
    (r"\b(syrup|suspension|liquid)\b", "Liquid"),
    (r"\b(injection|vial|ampoule)s?\b", "Injectable"),
    (r"\bdrops?\b", "Drops"),
    (r"\bointment\b", "Ointment"),
    (r"\bcream\b", "Cream"),
    (r"\bgel\b", "Gel"),
    (r"\binhaler\b", "Inhaler"),
]

class CommercialMedicineScraper:
    """
    Downloads the open-source Indian Medicine Dataset CSV.
    """

    def __init__(self):
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def scrape(self, force: bool = False) -> Path:
        save_path = RAW_DATA_DIR / "indian_medicine_data.csv"
        if save_path.exists() and not force:
            logger.info(f"[CommercialScraper] Local dataset already exists at {save_path} — skipping download.")
            return save_path

        logger.info(f"[CommercialScraper] Downloading commercial medicine database from {DATASET_URL}...")
        try:
            response = requests.get(DATASET_URL, timeout=60)
            response.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(response.content)
            logger.info(f"[CommercialScraper] Downloaded successfully and saved to {save_path} ({save_path.stat().st_size / 1024 / 1024:.2f} MB)")
            return save_path
        except Exception as e:
            if save_path.exists():
                logger.warning(f"[CommercialScraper] Download failed: {e}. Falling back to existing local file.")
                return save_path
            raise e


class CommercialMedicineNormalizer:
    """
    Normalizes the raw commercial CSV into a DataFrame matching our Supabase schema.
    """

    def normalize(self, raw_csv_path: Path) -> pd.DataFrame:
        logger.info(f"[CommercialNormalizer] Reading raw CSV from {raw_csv_path}")
        df = pd.read_csv(raw_csv_path, encoding="utf-8")
        logger.info(f"[CommercialNormalizer] Loaded {len(df)} records. Columns: {list(df.columns)}")

        # Drop rows that don't have a name
        df = df.dropna(subset=["name"])
        df["name"] = df["name"].str.strip()
        df = df[df["name"] != ""]

        df["brand_name"] = df["name"]
        df["manufacturer"] = df["manufacturer_name"].str.strip()

        def combine_compositions(row):
            comp1 = str(row["short_composition1"]).strip() if pd.notna(row["short_composition1"]) else ""
            comp2 = str(row["short_composition2"]).strip() if pd.notna(row["short_composition2"]) else ""
            if comp1 and comp2:
                return f"{comp1} + {comp2}"
            return comp1 or comp2 or None

        df["composition"] = df.apply(combine_compositions, axis=1).str.replace(r"\s+", " ", regex=True)

        # Generic name is the composition with every dose removed. Doses sit in
        # brackets ("Amoxycillin (500mg)"), so the brackets go with them.
        def extract_generic_name(comp):
            if pd.isna(comp):
                return None
            cleaned_parts = []
            for part in comp.split("+"):
                cleaned = DOSE_PATTERN.sub("", BRACKETED_DOSE.sub("", part))
                cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
                if cleaned:
                    cleaned_parts.append(cleaned)
            return " + ".join(cleaned_parts) if cleaned_parts else comp

        df["generic_name"] = df["composition"].apply(extract_generic_name)

        # A missing or zero price is unknown, not free.
        price_col = "price(₹)" if "price(₹)" in df.columns else "price"
        if price_col in df.columns:
            prices = pd.to_numeric(df[price_col], errors="coerce")
            df["mrp"] = prices.where(prices > 0)
        else:
            df["mrp"] = None

        df["pack_size"] = df.get("pack_size_label", pd.Series(dtype=str)).str.strip()

        # Filter out discontinued items
        if "Is_discontinued" in df.columns:
            df = df[df["Is_discontinued"] != True]

        df["source"] = "commercial"
        df["jan_aushadhi_price"] = None
        # The dataset has no barcodes. Invented ones would collide with real packs.
        df["barcode_id"] = None

        def _extract_strength(name: str) -> str | None:
            if pd.isna(name):
                return None
            doses = [
                f"{val}{unit}" + (f"/{per_val}{per_unit}" if per_unit else "")
                for val, unit, per_val, per_unit in DOSE_PATTERN.findall(name)
            ]
            return " + ".join(doses) if doses else None

        df["strength"] = df["composition"].apply(_extract_strength)

        # Only a form the pack label or brand name actually states; otherwise empty.
        def _stated_dosage_form(row):
            text = f"{row.get('pack_size_label', '')} {row.get('brand_name', '')}".lower()
            for pattern, form in STATED_FORMS:
                if re.search(pattern, text):
                    return form
            return None

        df["dosage_form"] = df.apply(_stated_dosage_form, axis=1)

        before = len(df)
        df = df.drop_duplicates(subset=["brand_name", "manufacturer"])
        logger.info(f"[CommercialNormalizer] Removed {before - len(df)} duplicates. Final: {len(df)} records")

        output_cols = [
            "barcode_id", "brand_name", "generic_name", "manufacturer",
            "composition", "strength", "dosage_form", "pack_size", "mrp", "jan_aushadhi_price",
            "source",
        ]
        return df[output_cols]
