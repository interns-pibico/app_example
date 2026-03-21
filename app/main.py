from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.__version__ import __version__
from app.core.config import get_settings
from app.core.exceptions import AppException, app_exception_handler
from app.core.logging import get_logger, setup_logging
from app.middleware.i18n import I18nMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.routers import v1_router
from app.routers.pages import router as pages_router
from app.routers.asturias_api import router as asturias_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger = get_logger(__name__)
    logger.info("Application starting", version=__version__)
    yield
    logger.info("Application shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()

    application = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    application.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(I18nMiddleware)

    application.add_exception_handler(AppException, app_exception_handler)

    application.mount("/static", StaticFiles(directory="app/static"), name="static")

    application.include_router(pages_router)
    application.include_router(v1_router)
    application.include_router(asturias_router)

    return application


app = create_app()

