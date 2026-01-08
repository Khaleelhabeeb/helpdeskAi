import os
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from datetime import datetime

# Configure API key
configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = os.getenv("BREVO_API_KEY")

api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
    sib_api_v3_sdk.ApiClient(configuration)
)

def send_email(subject, html_content, to_email, to_name=None):
    email = sib_api_v3_sdk.SendSmtpEmail(
        subject=subject,
        html_content=html_content,
        sender={"name": "HelpDeskAi", "email": "no-reply@helpdeskai.web.app"},
        to=[{"email": to_email, "name": to_name}] if to_name else [{"email": to_email}]
    )

    try:
        api_instance.send_transac_email(email)
        return True
    except ApiException as e:
        print("Brevo email error:", e)
        return False
