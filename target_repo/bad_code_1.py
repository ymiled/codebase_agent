from typing import List

TAX_RATE = 0.1

def calculate_total(prices: List[float]) -> float:
    try:
        total_cost = sum(price for price in prices)
        total_cost_with_tax = total_cost + (total_cost * TAX_RATE)
        return total_cost_with_tax
    except Exception as e:
        print(f"An error occurred: {e}")
        return None