def calculate_total(prices: list[float]) -> float:
    if not prices:
        raise ValueError("Prices list cannot be empty")
    total_cost: float = 0.0
    for price in prices:
        total_cost += price
    return total_cost