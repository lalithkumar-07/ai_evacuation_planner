"""FastAPI dependency that resolves the caller's session id from the X-Session-Id header."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header

from backend.services.session_store import validate_session_id


def get_session_id(x_session_id: Annotated[str | None, Header()] = None) -> str:
    return validate_session_id(x_session_id)


SessionId = Annotated[str, Depends(get_session_id)]