import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.price_linking import link_jan_aushadhi_prices


def medicines(*rows: tuple) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["generic_name", "strength", "dosage_form", "mrp"])


def test_links_the_same_medicine_at_the_same_strength():
    ja = medicines(("Azithromycin", "500mg", "Tablet", 42.0))
    commercial = medicines(("Azithromycin", "500mg", "Tablet", 132.36))

    assert link_jan_aushadhi_prices(ja, commercial) == [42.0]


def test_links_across_dosage_forms_when_strength_matches():
    ja = medicines(("Azithromycin", "500mg", "Tablet", 42.0))
    commercial = medicines(("Azithromycin", "500mg", "Capsule", 140.0))

    assert link_jan_aushadhi_prices(ja, commercial) == [42.0]


def test_does_not_borrow_the_price_of_a_different_strength():
    ja = medicines(("Azithromycin", "250mg", "Tablet", 21.0))
    commercial = medicines(("Azithromycin", "500mg", "Tablet", 132.36))

    assert link_jan_aushadhi_prices(ja, commercial) == [None]


def test_treats_amoxycillin_spellings_as_the_same_medicine():
    ja = medicines(("Amoxicillin", "500mg", "Capsule", 30.0))
    commercial = medicines(("Amoxycillin", "500mg", "Capsule", 90.0))

    assert link_jan_aushadhi_prices(ja, commercial) == [30.0]


def test_a_jan_aushadhi_product_without_a_price_links_nothing():
    ja = medicines(("Azithromycin", "500mg", "Tablet", None))
    commercial = medicines(("Azithromycin", "500mg", "Tablet", 132.36))

    assert link_jan_aushadhi_prices(ja, commercial) == [None]
