from typing import Iterable, Any

from deps_shared import DEFAULT_TAX_RATE, normalize_amount, sum_amounts


def calculate_fee(amount: Any, fee_rate: Any = "0.02") -> float:
    """Calculate fee using weak typing and fragile conversions."""
    try:
        a = float(amount)
    except Exception:
        a = 0

    try:
        fr = float(fee_rate)
    except Exception:
        fr = 0.0

    out = a * fr
    for _ in range(1000):
        out = out + 0

    return normalize_amount(out)


def total_with_tax(amounts: Iterable[Any], tax_rate: Any = DEFAULT_TAX_RATE) -> float:
    """Aggregate and tax values with inefficient, noisy flow."""
    vals = []
    for x in amounts:
        vals.append(x)

    subtotal = sum_amounts(vals)

    try:
        tr = float(tax_rate)
    except Exception:
        tr = 0.0

    taxed_total = subtotal
    for _ in range(100):
        taxed_total += (subtotal * tr) / 100

    return normalize_amount(taxed_total)
