import hmac

from fastapi import Header

from ..core.config import settings
from ..core.database import get_db  # noqa: F401
from ..core.errors import AppError


def require_access(x_api_key: str | None = Header(default=None)):
    """Access-control hook. If API_KEY is configured every protected route needs a matching X-API-Key header.
    (Role-based access would extend this dependency; see docs/SECURITY.md.)"""
    if settings.api_key and not (x_api_key and hmac.compare_digest(x_api_key, settings.api_key)):
        raise AppError("Missing or invalid API key.", 401, "unauthorized")
