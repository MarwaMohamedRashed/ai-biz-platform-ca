"""
Notifications — Resend (email) + Twilio (SMS/WhatsApp)
=======================================================
Shared notification service used by all three products.

C#/.NET equivalent: an INotificationService registered in DI,
with concrete implementations for email and SMS channels.

Usage:
    from core.notifications import send_email, send_sms
    await send_email(to="owner@salon.ca", subject="New review!", body="...")
"""

import os
import logging
import resend

logger = logging.getLogger(__name__)

resend.api_key = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@yourdomain.ca")


async def send_email(to: str, subject: str, body_html: str) -> bool:
    """Send a transactional email via Resend (free tier: 100/day)."""
    try:
        resend.Emails.send({
            "from":    FROM_EMAIL,
            "to":      [to],
            "subject": subject,
            "html":    body_html,
        })
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


async def send_review_alert(business_email: str, reviewer: str, rating: int) -> bool:
    """Phase 1: Notify business owner about a new review."""
    stars = "★" * rating + "☆" * (5 - rating)
    return await send_email(
        to=business_email,
        subject=f"New {rating}-star review from {reviewer}",
        body_html=f"""
            <h2>New Google Review</h2>
            <p><strong>From:</strong> {reviewer}</p>
            <p><strong>Rating:</strong> {stars} ({rating}/5)</p>
            <p>Log in to your dashboard to approve a response.</p>
        """,
    )


# ─── SMS / WhatsApp (Phase 2 only) ───────────────────────────────────────────
# Uncomment when Phase 2 build begins
#
# from twilio.rest import Client
# twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
# TWILIO_FROM = os.getenv("TWILIO_PHONE_NUMBER")
#
# async def send_sms(to: str, body: str) -> bool:
#     """Send an SMS via Twilio (Phase 2 booking reminders)."""
#     try:
#         twilio_client.messages.create(body=body, from_=TWILIO_FROM, to=to)
#         return True
#     except Exception as e:
#         logger.error(f"SMS failed to {to}: {e}")
#         return False
