import logging

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from src.config.settings import settings
from src.api.routers import auth, chat, report, admin, knowledge, upload, track
import os

# Ensure application loggers at INFO are not filtered out by root logger defaults.
# We intentionally do NOT configure handlers here (uvicorn manages handlers).
logging.getLogger().setLevel(logging.INFO)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

logger = logging.getLogger("healthy_rag")


def _sanitize_validation_errors(errors: list[dict]) -> list[dict]:
    """Remove sensitive fields from validation errors before logging."""
    sanitized: list[dict] = []
    for err in errors or []:
        if not isinstance(err, dict):
            continue
        # Pydantic v2 includes `input` which may contain secrets (password/code).
        # Also remove `ctx` because it may contain non-JSON-serializable objects
        # (e.g. ValueError instances) and may leak details we don't need.
        keep: dict = {k: v for k, v in err.items() if k not in {"input", "ctx"}}
        sanitized.append(keep)
    return sanitized


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request, exc: RequestValidationError):
    """Log 422 details for troubleshooting (without leaking secrets)."""
    try:
        client_ip = request.client.host if request.client else None
    except Exception:
        client_ip = None

    errors = _sanitize_validation_errors(exc.errors())
    logger.warning(
        "Request validation failed path=%s method=%s ip=%s errors=%s",
        getattr(request.url, "path", ""),
        getattr(request, "method", ""),
        client_ip,
        errors,
    )

    # Preserve FastAPI default response format.
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
)

# 挂载静态文件目录（在 /app/static）
static_dir = "/app/static"
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth"])
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["Chat"])
app.include_router(report.router, prefix=f"{settings.API_V1_STR}/report", tags=["Report"])
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}", tags=["Admin"])  # 注意：admin router 自带了 /admin 前缀
app.include_router(knowledge.router, prefix=f"{settings.API_V1_STR}/knowledge", tags=["Knowledge"])
app.include_router(upload.router, prefix=f"{settings.API_V1_STR}/upload", tags=["Upload"])
app.include_router(track.router, prefix=f"{settings.API_V1_STR}/track", tags=["Track"])

@app.get("/")
async def root():
    return {"message": "Welcome to Healthy RAG API"}

