import secrets
from datetime import datetime, timedelta
from typing import Tuple

from argon2 import PasswordHasher

def generate_visa_card_number() -> str:
    prefix = "4"

    partial_number = prefix + "".join(secrets.choice("0123456789") for _ in range(14))

    total = 0

    for i, digit in enumerate(reversed(partial_number)):
        digit = int(digit)
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -=9
        total += digit

    check_digit = (10 - (total % 10)) % 10

    return f"{partial_number}{check_digit}"

def generate_cvv() -> Tuple[str, str]:
    cvv = "".join(secrets.choice("0123456789") for _ in range(3))

    ph = PasswordHasher()

    cvv_hash = ph.hash(cvv)

    return cvv, cvv_hash

def verrify_cvv(cvv: str, cvv_hash:str) -> bool:
    try:
        ph = PasswordHasher()
        return ph.verify(cvv_hash, cvv)
    except Exception:
        return False
    
def generate_card_expiry_date() -> datetime:
    current_date = datetime.now()
    expiry_date = current_date + timedelta(days=365 * 3)

    if expiry_date.month == 12:
        expiry_date = expiry_date.replace(year=expiry_date.year + 1, month=1, day=1)
    else:
        expiry_date = expiry_date.replace(month=expiry_date.month + 1, day=1)

    expiry_date = expiry_date - timedelta(days=1)

    return expiry_date
