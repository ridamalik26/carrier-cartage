"""Email delivery (Section 10).

Plain SMTP username/password does not work for an organizational Microsoft
account since Microsoft deprecated Basic Auth for SMTP AUTH (April 2026).
Primary path: Microsoft Graph API client-credentials OAuth flow. Fallback
path: Gmail SMTP with an app password, for a dedicated Gmail sending account.

Only ever called for contractors where overall_score < 80% (enforced by the
caller in main.py, and re-checked here as a guard) — and only after a human
has approved the send via the review queue (Section 10/12 design requirement:
no auto-send).
"""
from __future__ import annotations

import base64
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

import httpx
import msal

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]


@dataclass
class SendResult:
    cc_number: int
    email: str
    success: bool
    error: str | None = None


def _fallback_recipients() -> list[str]:
    raw = os.environ.get("FALLBACK_RECIPIENT_EMAILS", "")
    return [e.strip() for e in raw.split(",") if e.strip()]


def _resolve_recipient(contractor_email: str | None) -> tuple[str, bool]:
    """Returns (recipient_email, used_fallback)."""
    if contractor_email and "@" in contractor_email:
        return contractor_email, False
    fallback = _fallback_recipients()
    if fallback:
        return fallback[0], True
    raise ValueError("No contractor email on file and no FALLBACK_RECIPIENT_EMAILS configured")


def _get_graph_token() -> str:
    app = msal.ConfidentialClientApplication(
        client_id=os.environ["GRAPH_CLIENT_ID"],
        client_credential=os.environ["GRAPH_CLIENT_SECRET"],
        authority=f"https://login.microsoftonline.com/{os.environ['GRAPH_TENANT_ID']}",
    )
    result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
    if "access_token" not in result:
        raise RuntimeError(f"Failed to acquire Graph token: {result.get('error_description')}")
    return result["access_token"]


def _send_via_graph(recipient: str, subject: str, body: str, attachment_bytes: bytes, attachment_name: str) -> None:
    token = _get_graph_token()
    sender = os.environ["GRAPH_SENDER_UPN"]

    message = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": recipient}}],
            "attachments": [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": attachment_name,
                "contentBytes": base64.b64encode(attachment_bytes).decode("ascii"),
            }],
        },
        "saveToSentItems": "true",
    }

    resp = httpx.post(
        f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=message,
        timeout=30.0,
    )
    resp.raise_for_status()


def _send_via_gmail_smtp(recipient: str, subject: str, body: str, attachment_bytes: bytes, attachment_name: str) -> None:
    user = os.environ["GMAIL_SMTP_USER"]
    password = os.environ["GMAIL_SMTP_APP_PASSWORD"]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = recipient
    msg.set_content(body)

    msg.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=attachment_name,
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)


def send_report_email(
    cc_number: int,
    name: str,
    overall_score: float,
    contractor_email: str | None,
    report_bytes: bytes,
    report_name: str,
    period: str,
) -> SendResult:
    if overall_score >= 0.80:
        return SendResult(cc_number, contractor_email or "", False, error="overall_score >= 80%, not eligible")

    try:
        recipient, used_fallback = _resolve_recipient(contractor_email)
    except ValueError as e:
        return SendResult(cc_number, "", False, error=str(e))

    subject = f"Cartage Contractor Performance Notice — {name} ({cc_number}) — {period}"
    body = (
        f"Dear {name},\n\n"
        f"Your Cartage Contractor performance score for {period} was "
        f"{round(overall_score * 100, 2)}%, below the 80% compliance threshold. "
        f"Please find the attached violation summary report.\n\n"
        f"Regards,\nFleet Compliance Team"
    )
    if used_fallback:
        body = f"[No email on file for {name} ({cc_number}) — routed to fallback recipient]\n\n" + body

    provider = os.environ.get("EMAIL_PROVIDER", "graph")
    try:
        if provider == "gmail_smtp":
            _send_via_gmail_smtp(recipient, subject, body, report_bytes, report_name)
        else:
            _send_via_graph(recipient, subject, body, report_bytes, report_name)
        return SendResult(cc_number, recipient, True)
    except Exception as e:  # noqa: BLE001 - surfaced to the review-queue UI, not swallowed
        return SendResult(cc_number, recipient, False, error=str(e))
