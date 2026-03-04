from typing import List, Dict

def process_data(data: List[Dict[str, str]]) -> List[Dict[str, str]]:
    try:
        # Use the built-in sorted function for efficient sorting
        sorted_data = sorted(data, key=lambda x: x['age'])
        return sorted_data
    except Exception as e:
        # Log the exception or raise a custom error
        print(f"An error occurred: {e}")
        raise

# Example usage:
if __name__ == "__main__":
    data = [
        {'name': 'John', 'age': '25', 'balance': '1000'},
        {'name': 'Alice', 'age': '30', 'balance': '2000'},
        {'name': 'Bob', 'age': '20', 'balance': '500'}
    ]
    sorted_data = process_data(data)
    print(sorted_data)
