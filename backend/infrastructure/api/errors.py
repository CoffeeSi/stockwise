from collections.abc import Callable
from typing import TypeVar

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.application.ports.export_artifacts import ExportArtifactUnavailableError
from backend.application.use_cases.import_file import InvalidImportFileError
from backend.application.use_cases.export_order import OrderExportReferenceError
from backend.application.use_cases.bulk_accept_recommendations import RecommendationSelectionConflictError
from backend.domain.entities.recommendation import RecommendationQuantityError
from backend.domain.entities.background_job import IdempotencyConflictError
from backend.domain.services.budget import BudgetInputError
from backend.domain.errors import InvalidEntityStateError
from backend.domain.repositories.import_repository import DuplicateImportError, InvalidImportStatusTransitionError
from backend.domain.repositories.order_repository import (
    OrderNotFoundError, DuplicateOrderNumberError, RecommendationAlreadyOrderedError, InvalidOrderPersistenceStateError,
)
from backend.domain.repositories.recommendation_repository import RecommendationConflictError, RecommendationNotFoundError
from backend.infrastructure.excel.readers import ExcelImportValidationError, REQUIRED
from backend.infrastructure.persistence.import_gateway import ImportUserNotFoundError
from .schemas.errors import ErrorResponse, error_response

T = TypeVar("T")
ERROR_RESPONSES = {code: {"model": ErrorResponse} for code in (403, 404, 409, 422, 500, 503)}


def safe_issues(issues) -> list[dict]:
    known = {name for names in REQUIRED.values() for name in names}
    result = []
    for issue in (issues or [])[:50]:
        if not isinstance(issue, dict):
            continue
        if "missing_columns" in issue:
            result.append({"missing_columns": [name for name in issue["missing_columns"] if name in known]})
        elif issue.get("code") == "ai_mapping_unavailable":
            result.append({"message": "Не удалось распознать столбцы через OpenAI. Проверьте OPENAI_API_KEY и структуру файла."})
        elif type(issue.get("row")) is int:
            result.append({"row": issue["row"], "message": "invalid row values"})
        else:
            result.append({"message": "invalid workbook columns"})
    return result


def invoke(operation: Callable[..., T], *args, **kwargs) -> T:
    """Translate known use-case failures; unexpected exceptions remain server errors."""
    try:
        return operation(*args, **kwargs)
    except IdempotencyConflictError:
        raise HTTPException(409, detail={"code": "idempotency_conflict", "message": "Idempotency key belongs to another request"}) from None
    except BudgetInputError as error:
        messages = {
            "budget_price_missing": "Every positive recommendation must have a saved price and currency",
            "budget_currency_mismatch": "A budget requires a single matching purchase currency",
            "budget_currency_missing": "Specify the budget currency when no positive priced recommendations exist",
            "invalid_budget": "Budget must be finite and positive",
        }
        raise HTTPException(422, detail={"code": error.code, "message": messages.get(error.code, "Invalid budget inputs")}) from None
    except RecommendationSelectionConflictError as error:
        raise HTTPException(409, detail={
            "code": "selection_conflict",
            "message": "Selected recommendations are unavailable, changed, or already ordered",
            "recommendation_ids": [str(value) for value in error.recommendation_ids],
        }) from None
    except RecommendationQuantityError as error:
        raise HTTPException(422, detail={
            "code": "invalid_order_quantity", "message": "Quantity must be zero or meet MOQ and package size",
            "recommendation_id": str(error.recommendation_id),
            "moq": str(error.moq), "package_size": str(error.package_size),
        }) from None
    except (RecommendationNotFoundError, OrderNotFoundError, ImportUserNotFoundError):
        raise HTTPException(404, detail={"code": "not_found"}) from None
    except (RecommendationConflictError, InvalidEntityStateError, InvalidOrderPersistenceStateError,
            DuplicateOrderNumberError, RecommendationAlreadyOrderedError, InvalidImportStatusTransitionError,
            OrderExportReferenceError):
        raise HTTPException(409, detail={"code": "state_conflict"}) from None
    except DuplicateImportError:
        raise HTTPException(409, detail={"code": "duplicate_import"}) from None
    except ExcelImportValidationError as error:
        issues = safe_issues(error.issues)
        raise HTTPException(422, detail={
            "code": "invalid_import_data", "status": "failed", "row_count": 0,
            "import_batch_id": str(error.batch_id) if hasattr(error, "batch_id") else None,
            "validation_errors": issues,
        }) from None
    except InvalidImportFileError:
        raise HTTPException(422, detail={"code": "invalid_import_file"}) from None
    except PermissionError:
        raise HTTPException(403, detail={"code": "forbidden"}) from None
    except LookupError as error:
        if type(error) is not LookupError:
            raise
        raise HTTPException(404, detail={"code": "not_found"}) from None
    except ValueError:
        raise HTTPException(422, detail={"code": "invalid_input"}) from None


def require_result(value: T | None) -> T:
    if value is None:
        raise HTTPException(404, detail={"code": "not_found"})
    return value


def install_error_handlers(app: FastAPI) -> None:
    async def unavailable(request: Request, error: Exception):
        return JSONResponse(status_code=503, content=error_response(
            code="service_unavailable", message="Service unavailable",
            request_id=request.state.request_id,
        ))

    async def internal_error(request: Request, error: Exception):
        return JSONResponse(status_code=500, content=error_response(
            code="internal_error", message="Internal server error",
            request_id=request.state.request_id,
        ))

    app.add_exception_handler(ExportArtifactUnavailableError, unavailable)
    app.add_exception_handler(SQLAlchemyError, unavailable)
    app.add_exception_handler(IntegrityError, internal_error)
