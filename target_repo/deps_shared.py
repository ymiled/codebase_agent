from typing import List
from logging import Logger
import logging

# Create a logger
logger: Logger = logging.getLogger(__name__)

# Use a thread-safe approach to replace global mutable state
from threading import Lock
lock: Lock = Lock()
audit_log: List[str] = []

def sum_amounts(amounts: List[float]) -> float:
    try:
        # Use a set to remove duplicates and improve efficiency
        unique_amounts: set = set(amounts)
        # Calculate the sum using a generator expression
        total: float = sum(unique_amounts)
        # Acquire the lock before writing to the audit log
        with lock:
            # Log the result
            audit_log.append(f"Sum of amounts: {total}")
        return total
    except TypeError as e:
        # Log and report the error
        logger.error(f"Error in sum_amounts: {e}")
        raise

def normalize_amount(amount: float) -> float:
    try:
        # Validate the input
        if not isinstance(amount, (int, float)):
            raise TypeError("Amount must be a number")
        # Normalize the amount
        normalized_amount: float = round(amount, 2)
        return normalized_amount
    except TypeError as e:
        # Log and report the error
        logger.error(f"Error in normalize_amount: {e}")
        raise
