import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("api.observability")
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": %(message)s}',
)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Correlation ID / Request ID
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        start_time = time.perf_counter()
        response: Response = await call_next(request)
        process_time = time.perf_counter() - start_time

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"

        # Structured log record
        log_payload = (
            f'{{"request_id": "{request_id}", "method": "{request.method}", '
            f'"path": "{request.url.path}", "status_code": {response.status_code}, '
            f'"process_time_sec": {process_time:.4f}}}'
        )
        logger.info(log_payload)

        return response
