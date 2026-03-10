import logging
import typing
from deps_shared import some_function

logger = logging.getLogger(__name__)

def calculate_fee(amount: str) -> float:
    try:
        amount = float(amount)
    except ValueError as e:
        logger.error('Invalid amount: %s', amount, exc_info=e)
        return 0
    fee = amount * 0.1
    return fee

def total_with_tax(amount: str) -> float:
    try:
        amount = float(amount)
    except ValueError as e:
        logger.error('Invalid amount: %s', amount, exc_info=e)
        return 0
    tax = amount * 0.2
    total = amount + tax
    return total
