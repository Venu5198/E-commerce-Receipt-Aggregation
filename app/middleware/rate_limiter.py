import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window in-memory rate limiter per client IP."""

    def __init__(
        self,
        app,
        max_requests: int = 120,
        window_seconds: int = 60,
        exempt_paths: tuple[str, ...] = ("/health", "/docs", "/openapi.json", "/redoc"),
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exempt_paths = exempt_paths
        self._clients: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Exempt internal/doc routes
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window_seconds

        # Prune timestamps older than window
        timestamps = [t for t in self._clients[client_ip] if t > window_start]
        self._clients[client_ip] = timestamps

        if len(timestamps) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - timestamps[0]))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RateLimitExceeded",
                    "detail": "Too many requests. Please try again later.",
                    "retry_after_seconds": max(retry_after, 1),
                },
                headers={
                    "Retry-After": str(max(retry_after, 1)),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        self._clients[client_ip].append(now)
        remaining = self.max_requests - len(self._clients[client_ip])

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        return response
