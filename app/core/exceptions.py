from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None):
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppException):
    status_code = 404
    detail = "Resource not found"


class ConflictError(AppException):
    status_code = 409
    detail = "Resource already exists"


class AuthenticationError(AppException):
    status_code = 401
    detail = "Authentication failed"


class ForbiddenError(AppException):
    status_code = 403
    detail = "Access forbidden"


class ValidationError(AppException):
    status_code = 422
    detail = "Validation error"


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
