import os

import resend
from dotenv import load_dotenv

load_dotenv()
resend.api_key = os.environ["RESEND_API_KEY"]
MAIL_FROM = os.environ.get("MAIL_FROM") or os.environ.get("EMAIL_FROM", "onboarding@resend.dev")


def send_email(to: str, subject: str, html: str, text: str | None = None) -> str:
   # Send one email and return its Resend id.
    params = {"from": MAIL_FROM, "to": [to], "subject": subject, "html": html}
    if text:
        params["text"] = text
    result = resend.Emails.send(params)
    return result["id"]