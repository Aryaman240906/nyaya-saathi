"""
Middleware stack — request tracing, error handling, timing.

Provides:
- Request ID injection (X-Request-ID header)
- Global error handler (structured JSON errors)
- Request timing (X-Response-Time header)
"""
from __future__ import annotations
import logging
import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique request ID for tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Measure and log request duration."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"

        # Log slow requests
        if duration_ms > 5000:
            logger.warning(
                "SLOW REQUEST: %s %s took %.0fms",
                request.method, request.url.path, duration_ms,
            )
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handler — returns structured JSON for all errors."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                "Unhandled error [%s] %s %s: %s",
                request_id, request.method, request.url.path, str(e),
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "detail": str(e) if logger.isEnabledFor(logging.DEBUG) else "An unexpected error occurred",
                    "request_id": request_id,
                },
            )


def register_middleware(app: FastAPI):
    """Register all middleware in the correct order (LIFO — last added runs first)."""
    # Order matters: timing wraps everything, then error handler, then request ID
    app.add_middleware(TimingMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RequestIDMiddleware)
