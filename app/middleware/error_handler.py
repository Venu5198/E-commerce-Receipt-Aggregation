import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("api.errors")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception('{"request_id": "%s", "error": "Unhandled internal error: %s"}', request_id, str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "detail": "An unexpected server error occurred.",
            "request_id": request_id,
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "detail": exc.detail,
            "request_id": request_id,
        },
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "detail": exc.errors(),
            "request_id": request_id,
        },
    )
