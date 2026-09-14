import os
import logging
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

logger = logging.getLogger(__name__)

# Configure API key
configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = os.getenv("BREVO_API_KEY")

api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
    sib_api_v3_sdk.ApiClient(configuration)
)

def send_email(subject, html_content, to_email, to_name=None):
    sender_email = (os.getenv("BREVO_SENDER_EMAIL") or "no-reply@frelo.com.ng").strip()
    sender_name = (os.getenv("BREVO_SENDER_NAME") or "HelpDeskAI").strip() or "HelpDeskAI"
    email = sib_api_v3_sdk.SendSmtpEmail(
        subject=subject,
        html_content=html_content,
        sender={"name": sender_name, "email": sender_email},
        to=[{"email": to_email, "name": to_name}] if to_name else [{"email": to_email}]
    )

    try:
        api_instance.send_transac_email(email)
        return True
    except ApiException:
        logger.exception("brevo_email_failed to_email=%s subject=%s", to_email, subject)
        return False
