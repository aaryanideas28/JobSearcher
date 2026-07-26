from __future__ import annotations

<<<<<<< HEAD
import asyncio
import base64
=======
import base64
from email.message import EmailMessage
from pathlib import Path
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
from typing import Any

from config.settings import get_settings
from src.utils.pdf_compiler import PDFCompiler
from src.utils.scraper_utils import retry_network
from src.workflow.state import AgentState

try:
    from celery import Celery
except ImportError:  # pragma: no cover
    class Celery:  # type: ignore[no-redef]
        """Import-time Celery shim for environments without a worker dependency."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args, self.kwargs = args, kwargs

        def task(self, *args: Any, **kwargs: Any) -> Any:
            def decorator(func: Any) -> Any:
                func.delay = func
                func.apply_async = lambda args=None, kwargs=None: func(*(args or ()), **(kwargs or {}))
                return func
            return decorator

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:  # pragma: no cover
    Credentials = None  # type: ignore[assignment]
    build = None  # type: ignore[assignment]
    HttpError = Exception  # type: ignore[assignment,misc]


settings = get_settings()
celery_app = Celery("resume_automation", broker=settings.celery_broker_url, backend=settings.celery_result_backend)


<<<<<<< HEAD
@celery_app.task(name="render_workflow_documents_task")
def render_workflow_documents_task(state_payload: dict[str, Any]) -> dict[str, Any]:
    """Celery worker entrypoint for resume and cover-letter PDF generation."""

    state = AgentState.model_validate(state_payload)
    compiler = PDFCompiler()
    paths: dict[str, str] = {"resume": str(compiler.compile_agent_state(state, "resume"))}
    if state.cover_letter.strip():
        paths["cover_letter"] = str(compiler.compile_agent_state(state, "cover_letter"))
    return {"status": "rendered", "session_id": state.session_id, "paths": paths}


def _raw_mime_payload(email_payload: dict[str, Any]) -> str:
    """Validate and canonicalize a URL-safe Base64 MIME payload for Gmail."""

    raw = email_payload.get("raw") or email_payload.get("base64_mime") or email_payload.get("mime_base64")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("email_payload requires a Base64 MIME value in raw, base64_mime, or mime_base64.")
    compact = raw.strip().replace("\n", "").replace("\r", "")
    padded = compact + ("=" * (-len(compact) % 4))
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError("email_payload contains invalid Base64 MIME content.") from exc
    return base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")


@retry_network(attempts=3, min_wait_seconds=1.0, max_wait_seconds=15.0)
def _send_gmail_raw(raw_mime: str) -> dict[str, Any]:
    """Send a prebuilt Base64 MIME message with Gmail's API."""

    if Credentials is None or build is None:
        raise RuntimeError("google-api-python-client is not installed.")
    if not settings.google_client_id or not settings.google_client_secret or not settings.google_refresh_token:
        raise RuntimeError("Google OAuth credentials are not configured for Gmail dispatch.")
=======
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

>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
    credentials = Credentials(
        token=None,
        refresh_token=settings.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
<<<<<<< HEAD
    response = build("gmail", "v1", credentials=credentials, cache_discovery=False).users().messages().send(
        userId="me", body={"raw": raw_mime}
    ).execute()
    return {"id": response.get("id"), "thread_id": response.get("threadId")}


@celery_app.task(name="dispatch_gmail_task")
def dispatch_gmail_task(email_payload: dict[str, Any]) -> dict[str, Any]:
    """Send a Base64 MIME email through Gmail from a Celery worker."""

    raw_mime = _raw_mime_payload(email_payload)
    result = _send_gmail_raw(raw_mime)
    return {"status": "sent", "gmail": result, "session_id": email_payload.get("session_id")}


# Preserve the original task import path while performing real Gmail dispatch.
send_email_outreach_task = dispatch_gmail_task


async def enqueue_document_render(state: AgentState) -> str | None:
    """Queue PDF rendering without blocking the FastAPI event loop."""

    result = await asyncio.to_thread(render_workflow_documents_task.delay, state.model_dump(mode="json"))
    return getattr(result, "id", None)


async def enqueue_gmail_dispatch(email_payload: dict[str, Any]) -> str | None:
    """Queue Gmail dispatch without blocking the FastAPI event loop."""

    result = await asyncio.to_thread(dispatch_gmail_task.delay, email_payload)
    return getattr(result, "id", None)
=======
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
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
