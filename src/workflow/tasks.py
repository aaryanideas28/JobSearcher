# File: src/workflow/tasks.py
"""Celery task definitions for asynchronous outreach operations."""

from __future__ import annotations

import base64
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.config.settings import get_settings

try:
    from celery import Celery
except Exception:  # pragma: no cover - import fallback for very small installs

    class _TaskResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id

    class _TaskWrapper:
        def __init__(self, fn: Any) -> None:
            self.fn = fn

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return self.fn(*args, **kwargs)

        def delay(self, *args: Any, **kwargs: Any) -> _TaskResult:
            self.fn(*args, **kwargs)
            return _TaskResult(str(uuid4()))

    class Celery:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def task(self, fn: Any | None = None, **_kwargs: Any) -> Any:
            if fn is None:
                return lambda wrapped: _TaskWrapper(wrapped)
            return _TaskWrapper(fn)


settings = get_settings()
celery_app = Celery(
    "ai_resume_automation",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    broker_connection_retry_on_startup=True
)


@celery_app.task(name="send_email_outreach_task")
def send_email_outreach_task(email_payload: dict[str, Any]) -> dict[str, Any]:
    """Send an outreach email through SMTP or Gmail API, or return a setup hint if unconfigured."""
    settings = get_settings()

    # 1. SMTP Fallback
    if settings.smtp_host and settings.smtp_username and settings.smtp_password:
        try:
            import smtplib
            message = _build_email_message(email_payload)
            if "From" not in message:
                message["From"] = settings.email_sender or settings.smtp_username

            if settings.smtp_port == 465:
                with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as server:
                    server.login(settings.smtp_username, settings.smtp_password)
                    server.send_message(message)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port or 587) as server:
                    server.starttls()
                    server.login(settings.smtp_username, settings.smtp_password)
                    server.send_message(message)
            return {"status": "sent", "provider": "smtp"}
        except Exception as exc:
            return {"status": "failed", "provider": "smtp", "error": str(exc)}

    # 2. Gmail API OAuth
    required = [
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_refresh_token,
    ]
    
    def is_configured(val: str | None) -> bool:
        if not val:
            return False
        return not any(placeholder in val.lower() for placeholder in ["your-client-id", "your-client-secret", "your-refresh-token"])

    if not all(is_configured(val) for val in required):
        return {
            "status": "skipped_no_email_config",
            "payload": email_payload,
            "message": "Configure SMTP settings or Google OAuth credentials to enable email sending.",
        }

    try:
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
        service = build("gmail", "v1", credentials=credentials)
        message = _build_email_message(email_payload)
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        sent = service.users().messages().send(userId="me", body={"raw": encoded_message}).execute()
        return {"status": "sent", "provider": "gmail", "provider_message_id": sent.get("id")}
    except Exception as exc:  # pragma: no cover - depends on external Gmail service
        return {"status": "failed", "provider": "gmail", "error": str(exc)}


def _build_email_message(email_payload: dict[str, Any]) -> EmailMessage:
    """Build a MIME email message from an outreach payload."""
    message = EmailMessage()
    message["To"] = str(email_payload["recipient_email"])
    message["Subject"] = str(email_payload["subject"])
    message.set_content(str(email_payload["body"]))

    for attachment in email_payload.get("attachments", []):
        path = Path(str(attachment))
        if not path.exists() or not path.is_file():
            continue
        import mimetypes
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type and "/" in mime_type:
            maintype, subtype = mime_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        message.add_attachment(
            path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=path.name,
        )
    return message
