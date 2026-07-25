# File: src/workflow/tasks.py
from __future__ import annotations

import base64
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from config.settings import get_settings

try:
    from celery import Celery
except ImportError:  # pragma: no cover - dependency bootstrap fallback
    class Celery:  # type: ignore[no-redef]
        """Small Celery-compatible shim for import-only environments."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        def task(self, *args: Any, **kwargs: Any) -> Any:
            _ = (args, kwargs)

            def decorator(func: Any) -> Any:
                return func

            return decorator


settings = get_settings()

celery_app = Celery(
    "resume_automation",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@celery_app.task(name="send_email_outreach_task")
def send_email_outreach_task(email_payload: dict[str, Any]) -> dict[str, Any]:
    """Send outreach email through Gmail when OAuth is configured."""

    if not _gmail_configured():
        return {
            "status": "skipped_no_google_oauth_config",
            "payload": email_payload,
            "message": "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN to send real email.",
        }

    try:
        service = _build_gmail_service()
        message = _build_mime_message(email_payload)
        result = service.users().messages().send(userId="me", body={"raw": message}).execute()
    except Exception as exc:  # pragma: no cover - depends on Google API runtime
        return {"status": "failed", "error": str(exc), "payload": email_payload}

    return {
        "status": "sent",
        "provider": "gmail",
        "provider_message_id": result.get("id"),
        "payload": email_payload,
    }


def _gmail_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and settings.google_refresh_token)


def _build_gmail_service() -> Any:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials(
        token=None,
        refresh_token=settings.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    return build("gmail", "v1", credentials=credentials)


def _build_mime_message(email_payload: dict[str, Any]) -> str:
    message = EmailMessage()
    message["To"] = str(email_payload["recipient_email"])
    message["From"] = settings.email_sender
    message["Subject"] = str(email_payload["subject"])
    message.set_content(str(email_payload["body"]))

    for attachment in email_payload.get("attachments", []):
        path = Path(str(attachment))
        if not path.exists() or not path.is_file():
            continue
        message.add_attachment(
            path.read_bytes(),
            maintype="application",
            subtype="pdf" if path.suffix.lower() == ".pdf" else "octet-stream",
            filename=path.name,
        )

    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
