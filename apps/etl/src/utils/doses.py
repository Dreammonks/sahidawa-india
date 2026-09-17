"""
Dose parsing shared by the Jan Aushadhi and commercial normalizers.

Both sources must write strengths the same way ("125mg/5ml + 50mg"), because
commercial medicines are linked to Jan Aushadhi prices by generic name and
strength. One module keeps the two from drifting apart.
"""

import re

_UNIT = r"(mg|mcg|gm|g|ml|iu|units?|%)"

# A dose, optionally per a quantity: "500mg", "30mg/5ml", "5 mg per 5 ml", "10 mg per10ml".
DOSE_PATTERN = re.compile(
    rf"(\d+(?:\.\d+)?)\s*{_UNIT}(?:\s*(?:/|\bper)\s*(\d+(?:\.\d+)?)?\s*{_UNIT})?",
    re.IGNORECASE,
)

# "(500mg)" — the brackets go with the dose, or "Amoxycillin ()" is left behind.
BRACKETED_DOSE = re.compile(r"\([^)]*\d[^)]*\)")

# "per 5ml" or "per ml" that follows a word, as in "Paracetamol 125mg Suspension per 5ml".
_PER_VOLUME = re.compile(r"(\S+)\s+per\s*(\d+(?:\.\d+)?)?\s*(ml|gm|g)\b", re.IGNORECASE)
_ENDS_WITH_DOSE = re.compile(rf"(?:\d|\b){_UNIT}$", re.IGNORECASE)

# "per vial", "per actuation": a pack unit, not part of the medicine's name.
_PER_PACK_UNIT = re.compile(
    r"\bper\s*(?:\d+(?:\.\d+)?\s*)?(?:vials?|sachets?|actuations?|doses?|puffs?|units?)\b",
    re.IGNORECASE,
)


def _split_detached_volume(text: str) -> tuple[str, str | None]:
    """Remove a 'per <volume>' that is not attached to a dose; return it separately."""
    for match in _PER_VOLUME.finditer(text):
        if not _ENDS_WITH_DOSE.search(match.group(1)):
            volume = f"{match.group(2) or ''}{match.group(3).lower()}"
            return text[: match.end(1)] + text[match.end():], volume
    return text, None


def format_strength(text: str) -> str | None:
    """Every dose in the text, lower-case units, joined with ' + '; None when there is none."""
    text, volume = _split_detached_volume(text)
    doses = []
    for value, unit, per_value, per_unit in DOSE_PATTERN.findall(text):
        dose = f"{value}{unit.lower()}"
        if per_unit:
            dose += f"/{per_value}{per_unit.lower()}"
        elif volume:
            dose += f"/{volume}"
        doses.append(dose)
    return " + ".join(doses) if doses else None


def strip_doses(text: str) -> str:
    """The text with every dose, bracketed dose and detached volume removed."""
    text, _ = _split_detached_volume(text)
    text = _PER_PACK_UNIT.sub(" ", text)
    text = DOSE_PATTERN.sub(" ", BRACKETED_DOSE.sub(" ", text))
    return re.sub(r"\s+", " ", text).strip()
