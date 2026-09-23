from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.infrastructure.config.settings import CorsSettings, Settings
from backend.infrastructure.api.routers.ai import router as ai_router
from backend.infrastructure.api.routers.auth import router as auth_router
from backend.infrastructure.api.routers.catalogs import router as catalogs_router
from backend.infrastructure.api.routers.order_workflow import router as order_workflow_router
from backend.infrastructure.api.routers.analytics import router as analytics_router
from backend.infrastructure.api.routers.scenarios import router as scenarios_router
from backend.infrastructure.api.routers.health import router as health_router
from backend.infrastructure.api.routers.imports import router as imports_router
from backend.infrastructure.api.routers.orders import router as orders_router
from backend.infrastructure.api.exceptions import ApiError
from backend.infrastructure.api.schemas.errors import error_response
from backend.infrastructure.api.routers.calculation_runs import router as calculation_runs_router
from backend.infrastructure.api.routers.recommendations import router as recommendations_router
from backend.infrastructure.api.errors import install_error_handlers
from backend.infrastructure.excel.artifact_store import FileExportArtifactStore
from backend.infrastructure.persistence.database import Database
from backend.infrastructure.background_worker import BackgroundWorker


def create_app(settings: Settings | None = None) -> FastAPI:
    cors_config = settings if settings is not None else CorsSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings if settings is not None else Settings()
        app.state.settings = config
        database = Database(config.database_url, echo=config.db_echo)
        worker = BackgroundWorker(database, config.import_spool_directory, config)
        try:
            app.state.database = database
            app.state.export_artifacts = FileExportArtifactStore(config.order_export_directory)
            app.state.background_worker = worker
            worker.start()
            yield
        finally:
            worker.stop()
            database.dispose()

    app = FastAPI(title="Warehouse replenishment", lifespan=lifespan)
    install_error_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_config.frontend_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Content-Disposition", "ETag"],
    )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        try:
            request_id = str(UUID(supplied))
        except ValueError:
            request_id = str(uuid4())
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            response = JSONResponse(
                status_code=500,
                content=error_response(
                    code="internal_error", message="Internal server error",
                    request_id=request_id,
                ),
            )
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        if isinstance(error.detail, dict):
            detail = dict(error.detail)
            code = str(detail.pop("code", f"http_{error.status_code}"))
            message = str(detail.pop("message", code.replace("_", " ")))
        else:
            code = f"http_{error.status_code}"
            message = str(error.detail)
            detail = {}
        return JSONResponse(
            status_code=error.status_code,
            content=error_response(
                code=code, message=message,
                request_id=request.state.request_id, context=detail,
            ),
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        issues = [
            {"loc": [str(part) for part in issue["loc"]],
             "type": issue["type"], "message": issue["msg"]}
            for issue in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_response(
                code="request_validation_error", message="Invalid request",
                request_id=request.state.request_id,
                context={"issues": issues},
            ),
        )

    @app.exception_handler(ApiError)
    async def api_error(request: Request, error: ApiError):
        return JSONResponse(
            status_code=error.status_code,
            content=error_response(
                code=error.code, message=error.message,
                request_id=request.state.request_id,
                context=error.context,
            ),
        )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(ai_router)
    app.include_router(imports_router)
    app.include_router(catalogs_router)
    app.include_router(analytics_router)
    app.include_router(scenarios_router)
    app.include_router(order_workflow_router)
    app.include_router(calculation_runs_router)
    app.include_router(recommendations_router)
    app.include_router(orders_router)

    # Versioned liveness endpoint used by Docker and orchestration.
    @app.get("/api/v1/health", tags=["system"])
    async def health_check():
        return {"status": "ok", "service": "procurement-backend"}

    return app


app = create_app()
