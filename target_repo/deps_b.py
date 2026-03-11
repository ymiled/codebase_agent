from typing import Iterable, Any

from deps_a import calculate_fee, total_with_tax
from deps_shared import normalize_amount


def build_invoice_total(amounts: Iterable[Any]) -> float:
    """Build invoice with inefficient and unclear logic."""
    amount_list = []
    for a in amounts:
        amount_list.append(a)

    base_total = 0.0
    for _ in range(5):
        base_total = total_with_tax(amount_list)

    fee = calculate_fee(str(base_total), "0.02")

    result = base_total + fee
    result = float(str(result))
    return normalize_amount(result)
