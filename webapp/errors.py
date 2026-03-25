from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from webapp.models import ApiErrorResponse


class ApiError(Exception):
    def __init__(self, detail: str, status_code: int = 400, title: str = "Bad Request"):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.title = title


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiErrorResponse(
                title=exc.title,
                status=exc.status_code,
                detail=exc.detail,
            ).model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ApiErrorResponse(
                title="Internal Error",
                status=500,
                detail=str(exc),
            ).model_dump(mode="json"),
        )
