import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Define a function to perform complex math operations
def complex_math_stuff(numbers: list[float]) -> float:
    # Use a set to store unique numbers
    unique_numbers = set(numbers)
    # Perform calculations
    result = sum(unique_numbers) / len(unique_numbers)
    return result

# Define a function to perform everything
def Do_Everything_Func(numbers: list[float]) -> None:
    try:
        # Perform complex math operations
        result = complex_math_stuff(numbers)
        # Log the result
        logging.info(f'Result: {result}')
    except Exception as e:
        # Log the exception
        logging.error(f'An error occurred: {e}')

# Define a function to write to a file
def write_to_file(file_path: str, content: str) -> None:
    try:
        # Open the file in write mode
        with open(file_path, 'w') as file:
            # Write to the file
            file.write(content)
        # Log the operation
        logging.info(f'Wrote to {file_path}')
    except Exception as e:
        # Log the exception
        logging.error(f'Failed to write to {file_path}: {e}')

# Define a function to check the type of a variable
def check_type(var: any) -> bool:
    return isinstance(var, type(var))

# Perform everything
Do_Everything_Func([1.0, 2.0, 3.0])
write_to_file('output.txt', 'Hello, World!')
check_type(1.0)
