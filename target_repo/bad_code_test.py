import pytest
from target_repo.bad_code import process_data

def test_process_data():
    data = [
        {'name': 'John', 'age': '25', 'balance': '1000'},
        {'name': 'Alice', 'age': '30', 'balance': '2000'},
        {'name': 'Bob', 'age': '20', 'balance': '500'}
    ]
    expected_output = [
        {'name': 'Bob', 'age': '20', 'balance': '500'},
        {'name': 'John', 'age': '25', 'balance': '1000'},
        {'name': 'Alice', 'age': '30', 'balance': '2000'}
    ]
    assert process_data(data) == expected_output

def test_process_data_empty():
    data = []
    expected_output = []
    assert process_data(data) == expected_output

def test_process_data_single_element():
    data = [{'name': 'John', 'age': '25', 'balance': '1000'}]
    expected_output = [{'name': 'John', 'age': '25', 'balance': '1000'}]
    assert process_data(data) == expected_output
