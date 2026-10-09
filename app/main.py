from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config import settings
from app.db import db_manager
from app.routers import profiles, products, orders, invoices, receipts, auth
from app.middleware.observability import RequestTracingMiddleware
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.error_handler import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)


from app.services.cache_service import cache_service
from app.services.event_bus import event_bus


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize MongoDB, Redis, and RabbitMQ broker
    db_manager.connect(settings.MONGO_URI, settings.MONGO_DB_NAME)
    await cache_service.init_redis()
    await event_bus.init_broker()
    yield
    # Shutdown: Close connections cleanly
    await event_bus.close_broker()
    await cache_service.close_redis()
    db_manager.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="E-commerce Receipt Aggregation API",
        version="1.0.0",
        description="High-performance asynchronous API for aggregating profiles, orders, products, and invoices into unified receipts with full CRUD REST support.",
        lifespan=lifespan,
    )

    # 1. Tracing & Timing Middleware (Outer)
    app.add_middleware(RequestTracingMiddleware)

    # 2. Rate Limiting Middleware (120 requests/minute per client)
    app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)

    # 3. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 4. Centralized Exception Handlers
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # 5. Register Routers
    app.include_router(auth.router)
    app.include_router(profiles.router)
    app.include_router(products.router)
    app.include_router(orders.router)
    app.include_router(invoices.router)
    app.include_router(receipts.router)

    @app.get("/health", tags=["Health"])
    async def health_check():
        return {
            "status": "healthy",
            "database": settings.MONGO_DB_NAME,
            "version": "1.0.0",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
