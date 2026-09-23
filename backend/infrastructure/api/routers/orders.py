from uuid import UUID

from fastapi import APIRouter, Body, Depends, Response

from backend.application.use_cases.approve_order import ApproveOrder
from backend.application.use_cases.create_orders import CreateOrders
from backend.application.use_cases.download_order_export import DownloadOrderExport
from backend.application.use_cases.export_order import ExportOrder
from backend.application.use_cases.get_order import GetOrder
from backend.application.use_cases.get_calculation_run import GetCalculationRun
from backend.domain.entities.catalog import User
from backend.infrastructure.api import dependencies as deps
from backend.infrastructure.api.errors import ERROR_RESPONSES, invoke, require_result
from backend.infrastructure.api.schemas.workflows import CreateOrdersRequest, ExportResponse, OrderResponse, RequestModel

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
router = APIRouter(prefix="/api/orders", tags=["orders"],
                   dependencies=[Depends(deps.get_current_user)], responses=ERROR_RESPONSES)


@router.post("", response_model=list[OrderResponse], status_code=201)
def create_orders(body: CreateOrdersRequest, user: User = Depends(deps.require_writer),
                  use_case: CreateOrders = Depends(deps.get_create_orders),
                  get_run: GetCalculationRun = Depends(deps.get_calculation_run)):
    require_result(invoke(get_run.execute, body.calculation_run_id))
    return [OrderResponse.model_validate(row) for row in invoke(use_case.execute, body.calculation_run_id, user_id=user.id)]


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: UUID, use_case: GetOrder = Depends(deps.get_order)):
    return OrderResponse.model_validate(invoke(use_case.execute, order_id))


@router.post("/{order_id}/approve", response_model=OrderResponse)
def approve_order(order_id: UUID, body: RequestModel | None = Body(default=None),
                  user: User = Depends(deps.require_writer), use_case: ApproveOrder = Depends(deps.get_approve_order)):
    return OrderResponse.model_validate(invoke(use_case.execute, order_id, user_id=user.id))


@router.post("/{order_id}/export", response_model=ExportResponse, status_code=201)
def create_export(order_id: UUID, body: RequestModel | None = Body(default=None),
                  user: User = Depends(deps.require_writer), use_case: ExportOrder = Depends(deps.get_export_order)):
    result = invoke(use_case.execute, order_id, user_id=user.id)
    return ExportResponse.model_validate(result.metadata)


@router.get("/{order_id}/export", response_class=Response,
            responses={200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}}}})
def download_export(order_id: UUID, use_case: DownloadOrderExport = Depends(deps.get_download_export)):
    result = invoke(use_case.execute, order_id)
    return Response(result.content, media_type=XLSX, headers={
        "Content-Disposition": f'attachment; filename="order-{order_id}.xlsx"',
        "ETag": f'"{result.metadata.file_checksum}"', "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })
