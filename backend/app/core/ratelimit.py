"""slowapi rate limiting with a graceful 429 envelope."""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.security import decode_token


def _key(request: Request) -> str:
    """Rate-limit per authenticated user when possible, else per IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            sub = decode_token(auth.split(" ", 1)[1]).get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:  # noqa: BLE001
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_key, default_limits=[])


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = 60
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "data": None,
            "error": "rate_limit",
            "message": "Too many requests. Your agent will be able to act again shortly.",
            "code": "rate_limit",
            "retry_after_seconds": retry_after,
            "meta": {"timestamp": None, "agent_id": None},
        },
        headers={"Retry-After": str(retry_after)},
    )
