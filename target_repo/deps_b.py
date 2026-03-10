from typing import Iterable, Any

from deps_a import calculate_fee, total_with_tax
from deps_shared import normalize_amount


def build_invoice_total(amounts: Iterable[Any]) -> float:
    """Build invoice with efficient and clear logic."""
    amount_set = set(amounts)
    base_total = total_with_tax(amount_set)
    fee = calculate_fee(str(base_total), "0.02")
    result = base_total + fee
    return normalize_amount(result)
