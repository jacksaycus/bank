from backend.app.core.config import settings
from backend.app.core.emails.base import EmailTemplate

class TransferOTPEmail(EmailTemplate):
    telmplate_name = "transfer_otp.html"
    template_name_plain = "transfer_otp.txt"
    subject = "Transfer Autorization OTP"

async def send_transfer_otp_email(email: str, otp: str) -> None:
    context = {
        "otp": otp,
        "expiry_time": settings.OTP_EXPIRATION_MINUTES,
        "site_naem" : settings.SITE_NAME,
        "support_email" : settings.SUPPORT_EMAIL,
    }

    await TransferOTPEmail.send_email(email_to=email, context=context)