# File: src/workflow/tasks.py
from __future__ import annotations

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
    """Worker stub for sending outreach email."""

    return {"status": "sent_stub", "payload": email_payload}
