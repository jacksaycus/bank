from datetime import datetime

from backend.app.core.config import settings
from backend.app.core.emails.base import EmailTemplate

class VirtualCardBlockedEmail(EmailTemplate):
    template_name = "card_blocked.html"
    template_name_plain = "card_blocked.txt"
    subject = "Your Virtual Card Has Been Blocked"


async def send_csrd_blocked_email(
        email: str,
        full_name: str,
        card_type: str,
        masked_card_number: str,
        blcok_reason: str,
        block_reason_description: str,
        blocked_at: datetime,
) -> None:
    context = {
        "full_name" : full_name,
        "card_type" : card_type,
        "masked_card_number": masked_card_number,
        "block_reason" : blcok_reason,
        "block_reason_description": block_reason_description,
        "site_name" : settings.SITE_NAME,
        "support_email" : settings.SUPPORT_EMAIL,
        "blocked_at" : blocked_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    await VirtualCardBlockedEmail.send_email(email_to=email, context=context)