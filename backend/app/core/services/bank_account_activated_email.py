from backend.app.core.config import settings
from backend.app.core.emails.base import EmailTemplate

class AccountActivatedEmail(EmailTemplate):
    template_name = "account_activated.html"
    template_name_plain = "account_activeted.txt"
    subject = "Your Bank Account Has been Activated"

async def send_account_activated_email(
        email: str,
        full_name: str,
        account_number: str,
        account_name: str,
        account_type: str,
        currency: str,

) -> None:
    context = {
        "full_name": full_name,
        "account_number": account_number,
        "account_type" : account_type,
        "currency" : currency,
        "site_name" : settings.SITE_NAME,
        "support_email" : settings.SUPPORT_EMAIL,
    }

    await AccountActivatedEmail.send_email(email_to=email, context=context)