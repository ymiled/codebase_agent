import logging

def do_something(state: list) -> None:
    try:
        # Fix O(n^2) loops with Sets
        unique_state = set(state)
        # Add type hints and improve naming
        for item in unique_state:
            if isinstance(item, str):
                logging.info(f"Processing string: {item}")
            elif isinstance(item, int):
                logging.info(f"Processing integer: {item}")
    except (TypeError, ValueError) as e:
        logging.error(e)

    # Wrap ALL file writes with structured logging
    try:
        logging.info('Writing report to temp_report.txt')
        with open('temp_report.txt', 'w') as f:
            f.write('Report content')
        logging.info('Report written successfully')
    except OSError as e:
        logging.error(e)

if __name__ == '__main__':
    state = [1, 2, 3, 'a', 'b', 'c']
    do_something(state)
