"""Print one API response from scripts/demo.sh as a short, readable table.

Usage: curl -s <url> | python3 scripts/demo_show.py medicines|names|alerts|brands
"""

import json
import sys


def medicines(data: dict) -> None:
    # Show medicines that have a Jan Aushadhi equivalent first: that is the comparison.
    rows = sorted(data["medicines"], key=lambda m: m["jan_aushadhi_price"] is None)[:5]
    print(f"  {data['total']} matches; {len(rows)} shown, those with a Jan Aushadhi price first")
    for m in rows:
        ja_price = m["jan_aushadhi_price"] if m["jan_aushadhi_price"] is not None else "-"
        print(
            f"  {m['brand_name'] or m['generic_name']:<36} {m['strength'] or '':<12} "
            f"MRP {m['mrp']!s:>8}   Jan Aushadhi price {ja_price}"
        )


def names(data: dict) -> None:
    found = ", ".join(m["brand_name"] or m["generic_name"] for m in data["medicines"])
    print(f"  {data['total']} matches, for example: {found}")


def alerts(data: dict) -> None:
    print(f"  {data['total']} alerts")
    for a in data["alerts"]:
        print(
            f"  {a['reporting_month'][:7]}  {a['alert_type']:<8} batch {a['batch_number'] or '-':<14} "
            f"{a['product_name'][:45]}"
        )


def brands(data: dict) -> None:
    for m in data["matches"]:
        print(
            f"  {m['brand_name']:<24} {m['manufacturer'][:30]:<30} "
            f"score {m['match_score']:>5.1f}  match: {m['is_match']}"
        )


VIEWS = {"medicines": medicines, "names": names, "alerts": alerts, "brands": brands}

if __name__ == "__main__":
    response = json.load(sys.stdin)
    if response.get("status") != "ok":
        print(f"  {response}")
    else:
        VIEWS[sys.argv[1]](response)
