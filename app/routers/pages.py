from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from app.__version__ import __version__
from app.middleware.i18n import current_locale, current_translations

router = APIRouter()

env = Environment(
    loader=FileSystemLoader("app/templates"),
    extensions=["jinja2.ext.i18n"],
)


def _render(request: Request, template_name: str) -> HTMLResponse:
    locale = current_locale.get()
    trans = current_translations.get()
    env.install_gettext_translations(trans)
    template = env.get_template(template_name)
    html = template.render(
        request=request,
        app_version=__version__,
        current_locale=locale,
        url_for=request.url_for,
    )
    return HTMLResponse(html)

@router.get("/")
async def asturias(request: Request):
    return _render(request, "pages/asturias.html")


@router.get('/3dpreviewer')
async def previewer(request: Request):
    return _render(request, 'pages/3dpreviewer.html')
