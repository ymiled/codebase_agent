import pytest
from target_repo.bad_code_2 import calculate_total

def test_calculate_total_empty_list():
    with pytest.raises(ValueError):
        calculate_total([])

def test_calculate_total_single_element():
    assert calculate_total([10.0]) == 10.0

def test_calculate_total_multiple_elements():
    assert calculate_total([10.0, 20.0, 30.0]) == 60.0