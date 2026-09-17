"""
Give commercial medicines the price of the same medicine at Jan Aushadhi.
"""

import pandas as pd


def _normalize_generic_name(name: str) -> str:
    n = str(name).lower().strip()
    n = n.replace("amoxycillin", "amoxicillin")
    n = n.replace("clavulanic acid", "clavulanate")
    n = n.replace("clavulanic", "clavulanate")
    return n


def _text_key(value: str | float | None) -> str:
    return str(value).lower().strip().replace(" ", "") if pd.notna(value) else ""


def link_jan_aushadhi_prices(df_ja: pd.DataFrame, df_comm: pd.DataFrame) -> list[float | None]:
    """
    Return, for each commercial row in order, the Jan Aushadhi price of the same
    generic name at the same strength, or None.

    Matching on name alone is deliberately not done: it would price a 500mg
    tablet at the 250mg generic's price.
    """
    exact: dict[tuple[str, str, str], float] = {}
    by_strength: dict[tuple[str, str], float] = {}

    for _, row in df_ja.iterrows():
        if pd.isna(row["mrp"]):
            continue
        gen = _normalize_generic_name(row["generic_name"])
        strength = _text_key(row["strength"])
        form = _text_key(row["dosage_form"])
        exact.setdefault((gen, strength, form), row["mrp"])
        by_strength.setdefault((gen, strength), row["mrp"])

    prices: list[float | None] = []
    for _, row in df_comm.iterrows():
        gen = _normalize_generic_name(row["generic_name"])
        strength = _text_key(row["strength"])
        form = _text_key(row["dosage_form"])
        price = exact.get((gen, strength, form))
        if price is None:
            price = by_strength.get((gen, strength))
        prices.append(price)
    return prices
