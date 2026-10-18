from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import engine
from app.models import Base
from app.routers import (
    admin,
    analytics,
    auth,
    bakeries,
    cakes,
    categories,
    exports,
    messaging,
    notifications,
    orders,
    portfolio,
    public,
    upload,
)

from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import HTTPException as FastAPIHTTPException

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up DB connections on shutdown
    await engine.dispose()


app = FastAPI(
    title="Crumbly API",
    description="FastAPI backend for Crumbly marketplace",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail_str = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error": detail_str, "message": detail_str},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(FastAPIHTTPException)
async def fastapi_http_exception_handler(request: Request, exc: FastAPIHTTPException):
    detail_str = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error": detail_str, "message": detail_str},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0]["msg"] if exc.errors() else "Validation error"
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "error": first_error, "message": first_error},
    )


settings = get_settings()

# CORS configuration
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix = "/api"

# Register routers
app.include_router(auth.router, prefix=prefix)
app.include_router(bakeries.router, prefix=prefix)
app.include_router(cakes.router, prefix=prefix)
app.include_router(categories.router, prefix=prefix)
app.include_router(orders.router, prefix=prefix)
app.include_router(portfolio.router, prefix=prefix)
app.include_router(upload.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)
app.include_router(public.router, prefix=prefix)
app.include_router(messaging.router, prefix=prefix)
app.include_router(notifications.router, prefix=prefix)
app.include_router(exports.router, prefix=prefix)
app.include_router(analytics.router, prefix=prefix)


@app.get(f"{prefix}/health")
async def health_check():
    return {"status": "ok"}
