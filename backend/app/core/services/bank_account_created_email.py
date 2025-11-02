from backend.app.core.config import settings
from backend.app.core.emails.base import EmailTemplate

class AccountCreatedEmail(EmailTemplate):
    template_name = "account_created.html"
    template_name_plain = "account_created.txt"
    subject = "Welcome - Your Bank Account Has been Created"


async def send_account_created_email(
        email: str,
        full_name: str,
        account_number: str,
        account_name: str,
        account_type: str,
        currency: str,
        identification_type: str,
) -> None:
    context = {
        "full_name": full_name,
        "account_number": account_number,
        "account_name" : account_name,
        "account_type": account_type,
        "currency" : currency,
        "identifaction_type": identification_type,
        "site_name" : settings.SITE_NAME,
        "support_email" : settings.SUPPORT_EMAIL,
    }
    await AccountCreatedEmail.send_email(email_to=email, context=context)