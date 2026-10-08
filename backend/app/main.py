"""应用入口。路由只挂前缀，业务在各服务函数里。"""

from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import auth, claims, files, items, jobs, matches, notifications, reports
from app.errors import (
    FieldError,
    Forbidden,
    FoundAlreadyReturned,
    InvalidState,
    NotFound,
    Unauthenticated,
    ValidationError,
    VersionConflict,
)

app = FastAPI(title="Campus Lost and Found")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(items.router, prefix="/api/v1")
app.include_router(matches.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(claims.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")


def _error(status: int, code: str, message: str, **extra: object) -> JSONResponse:
    body: dict[str, object] = {"code": code, "message": message}
    body.update(extra)
    return JSONResponse(status_code=status, content={"error": body})


@app.exception_handler(Unauthenticated)
async def unauthenticated_handler(_request: Request, exc: Unauthenticated) -> JSONResponse:
    return _error(401, "unauthenticated", str(exc))


@app.exception_handler(Forbidden)
async def forbidden_handler(_request: Request, exc: Forbidden) -> JSONResponse:
    return _error(403, "forbidden", str(exc))


@app.exception_handler(NotFound)
async def not_found_handler(_request: Request, exc: NotFound) -> JSONResponse:
    return _error(404, "not_found", str(exc))


@app.exception_handler(VersionConflict)
async def version_handler(_request: Request, exc: VersionConflict) -> JSONResponse:
    return _error(409, "version_conflict", str(exc), current_version=exc.current_version)


@app.exception_handler(FoundAlreadyReturned)
async def found_returned_handler(_request: Request, exc: FoundAlreadyReturned) -> JSONResponse:
    return _error(409, "found_already_returned", str(exc))


@app.exception_handler(InvalidState)
async def invalid_state_handler(_request: Request, exc: InvalidState) -> JSONResponse:
    return _error(409, "invalid_state", str(exc))


@app.exception_handler(ValidationError)
async def validation_handler(_request: Request, exc: ValidationError) -> JSONResponse:
    return _error(422, "validation_error", str(exc), fields=[asdict(field) for field in exc.fields])


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    fields: list[FieldError] = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ()) if part not in ("body", "query", "path")]
        err_type = str(err.get("type", ""))
        if err_type == "missing":
            code = "required"
        elif "too_long" in err_type:
            code = "too_long"
        else:
            code = "unknown_enum"
        fields.append(FieldError(".".join(loc) or "body", code))
    return _error(422, "validation_error", "字段不合法", fields=[asdict(field) for field in fields])
