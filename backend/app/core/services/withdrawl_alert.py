from datetime import datetime
from decimal import Decimal

from backend.app.core.config import settings
from backend.app.core.emails.base import EmailTemplate

class WithdrawalAlertEmail(EmailTemplate):
    template_name = "withdrawal_alert.html"
    template_name_plain = "withdrawal_alert.txt"
    subject = "Withdrawal Alert"


async def send_withdrwal_alert(
        email: str,
        full_name: str,
        amount: Decimal,
        account_name: str,
        account_number: str,
        currency: str,
        description: str,
        transaction_date: datetime,
        reference: str,
        balance: Decimal,

) -> None:
    context = {
        "full_name": full_name,
        "amount" : amount,
        "account_name" : account_name,
        "account_number" : account_number,
        "crrrency" : currency,
        "description" : description,
        "transaction_date" : transaction_date.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "reference": reference,
        "balance" : balance,
        "site_name" : settings.SITE_NAME,
        "support_email": settings.SUPPORT_EMAIL,
    }

    await WithdrawalAlertEmail.send_email(email_to=email, context=context)