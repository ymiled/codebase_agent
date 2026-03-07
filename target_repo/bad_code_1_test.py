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


def test_calculate_total():
    prices = [10.0, 20.0, 30.0]
    expected_total = sum(prices) + (sum(prices) * TAX_RATE)
    assert calculate_total(prices) == expected_total

def test_calculate_total_empty_list():
    prices = []
    expected_total = 0.0
    assert calculate_total(prices) == expected_total

def test_calculate_total_negative_prices():
    prices = [-10.0, -20.0, -30.0]
    expected_total = sum(prices) + (sum(prices) * TAX_RATE)
    assert calculate_total(prices) == expected_total