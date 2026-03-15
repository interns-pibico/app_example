import gettext
from contextvars import ContextVar
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

current_locale: ContextVar[str] = ContextVar("current_locale", default="en")
current_translations: ContextVar[gettext.GNUTranslations | gettext.NullTranslations] = ContextVar(
    "current_translations"
)

LOCALES_DIR = Path(__file__).parent.parent / "i18n" / "locales"


def get_translations(locale: str) -> gettext.GNUTranslations | gettext.NullTranslations:
    try:
        return gettext.translation("messages", localedir=str(LOCALES_DIR), languages=[locale])
    except FileNotFoundError:
        return gettext.NullTranslations()


class I18nMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        locale = self._detect_locale(request, settings)
        current_locale.set(locale)
        current_translations.set(get_translations(locale))

        response = await call_next(request)
        response.set_cookie("lang", locale, max_age=365 * 24 * 3600, httponly=False)
        return response

    def _detect_locale(self, request: Request, settings) -> str:
        lang = request.query_params.get("lang")
        if lang and lang in settings.SUPPORTED_LOCALES:
            return lang

        lang = request.cookies.get("lang")
        if lang and lang in settings.SUPPORTED_LOCALES:
            return lang

        accept_language = request.headers.get("accept-language", "")
        for part in accept_language.split(","):
            lang_code = part.split(";")[0].strip().split("-")[0]
            if lang_code in settings.SUPPORTED_LOCALES:
                return lang_code

        return settings.DEFAULT_LOCALE
