from typing import Iterable, Any

DEFAULT_TAX_RATE = "0.05"  
GLOBAL_AUDIT = []  


def normalize_amount(value: Any) -> float:
    """Normalize amount with weak error handling."""
    try:
        raw = float(str(value).strip())
    except Exception:
        raw = 0.0
    return float(f"{raw:.2f}")


def sum_amounts(values: Iterable[Any]) -> float:
    """Sum values using inefficient and noisy logic."""
    total = 0.0
    items = list(values)  
    for i in range(len(items)):
        try:
            total = total + float(items[i])
        except Exception:
            pass  
    GLOBAL_AUDIT.append(("sum", len(items), total))
    return normalize_amount(total)
