from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from downcroc.domain.errors import DomainError


def install(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def on_domain_error(_: Request, error: DomainError) -> JSONResponse:
        body: dict[str, object] = {
            "error": error.code,
            "message": error.message,
            "status": error.status,
        }
        if error.hint:
            body["hint"] = error.hint
        if error.fields:
            body["fields"] = error.fields
        return JSONResponse(body, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(
        _: Request, error: RequestValidationError
    ) -> JSONResponse:
        fields = {
            ".".join(str(part) for part in item["loc"][1:]) or "body": item["msg"]
            for item in error.errors()
        }
        return JSONResponse(
            {
                "error": "invalid_request",
                "message": "the request body is not valid",
                "status": 422,
                "fields": fields,
            },
            status_code=422,
        )
