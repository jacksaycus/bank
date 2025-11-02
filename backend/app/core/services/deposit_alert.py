from datetime import datetime
from decimal import Decimal

from backend.app.core.config import settings
from backend.app.core.emails.base import EmailTemplate

class DepositAlertEmail(EmailTemplate):
    template_name = "deposit_alert.html"
    template_name_plain = "deposit_alert.txt"
    subject = "Deposit Alert"

async def send_deposit_alert(
        email: str,
        full_name: str,
        action: str,
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
        "action": action,
        "amount": amount,
        "account_name": account_name,
        "account_number": account_number,
        "currency": currency,
        "description" : description,
        "transaction_date": transaction_date,
        "reference" : reference,
        "balance" : balance,
        "site_name" : settings.SITE_NAME,
        "suport_email" : settings.SUPPORT_EMAIL,
    }
    await DepositAlertEmail.send_email(email_to=email, context=context)