from decimal import Decimal
from typing import Union

def format_currency(amount: Union[Decimal, float, str, int]) -> str:
    try:
        decimal_amount = Decimal(str(amount))
        return f"{decimal_amount:,.2f}"
    except (ValueError, TypeError, AttributeError):
        return str(amount)
    
def parse_decimal(amount: Union[str, float, int]) -> Decimal:
    try:
        if isinstance(amount, str):
            amount = amount.replace(",", "")
        return Decimal(str(amount))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f"Count not convert {amount} to Decimal")