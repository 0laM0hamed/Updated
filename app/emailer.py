import os
import resend
from dotenv import load_dotenv

load_dotenv()

async def send_email(to: str, subject: str, html: str) -> str:
    """Send one email through Resend and return its message id."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set in .env")
    resend.api_key = api_key
    params: resend.Emails.SendParams = {
        "from": os.environ.get("EMAIL_FROM", "Tracker <onboarding@resend.dev>"),
        "to": [to],
        "subject": subject,
        "html": html,
    }
    result = await resend.Emails.send_async(params)
    return result["id"]
