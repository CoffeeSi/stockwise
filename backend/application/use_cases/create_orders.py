from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4

from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.application.use_cases.bulk_accept_recommendations import RecommendationSelectionConflictError
from backend.domain.entities.enums import RecommendationStatus
from backend.domain.entities.purchase_order import PurchaseOrder, PurchaseOrderItem
from backend.domain.entities.recommendation import Recommendation, utc_now
from backend.domain.repositories.recommendation_repository import RecommendationConflictError
from backend.domain.value_objects.supplier_snapshot import snapshot_price


class CreateOrders:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, calculation_run_id: UUID, *, user_id: UUID,
                recommendation_ids: Sequence[UUID] | None = None) -> tuple[PurchaseOrder, ...]:
        """Create only new drafts for one run; an already consumed selection returns ()."""
        if not isinstance(user_id, UUID):
            raise ValueError("user_id must be a user UUID")
        if recommendation_ids is not None and (
            not recommendation_ids or len(set(recommendation_ids)) != len(recommendation_ids)
        ):
            raise ValueError("recommendation IDs must be nonempty and unique")
        orders = []
        with self._uow_factory() as uow:
            if uow.calculation_runs.get(calculation_run_id) is None:
                raise LookupError("calculation run was not found")
            groups: dict[tuple[UUID, UUID], list[Recommendation]] = defaultdict(list)
            if recommendation_ids is None:
                selected = uow.recommendations.list_orderable(calculation_run_id)
            else:
                selected = []
                conflicting = []
                for item_id in recommendation_ids:
                    row = uow.recommendations.get(item_id)
                    if (row is None or row.calculation_run_id != calculation_run_id
                            or row.status is not RecommendationStatus.ACCEPTED):
                        conflicting.append(item_id)
                    else:
                        selected.append(row)
                if conflicting:
                    raise RecommendationSelectionConflictError(conflicting)
            now = utc_now()
            # Claim in stable global ID order to avoid deadlocks between batch creators.
            for recommendation in sorted(selected, key=lambda row: row.id):
                version = recommendation.version
                recommendation.mark_converted_to_order(changed_at=now)
                try:
                    uow.recommendations.mark_converted(recommendation, expected_version=version)
                except RecommendationConflictError as error:
                    raise RecommendationSelectionConflictError([recommendation.id]) from error
                groups[(recommendation.supplier_id, recommendation.warehouse_id)].append(recommendation)
            for (supplier_id, warehouse_id), recommendations in sorted(groups.items()):
                order_id = uuid4()
                order = PurchaseOrder(id=order_id, order_number=f"PO-{order_id.hex}",
                                      supplier_id=supplier_id, warehouse_id=warehouse_id,
                                      created_from_run_id=calculation_run_id, created_by=user_id, created_at=now)
                for recommendation in recommendations:
                    price, _currency = snapshot_price(recommendation.calculation_details)
                    total = None if price is None else (price * recommendation.effective_quantity).quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP,
                    )
                    order.add_item(PurchaseOrderItem(
                        recommendation_id=recommendation.id, product_id=recommendation.product_id,
                        recommended_quantity=recommendation.recommended_quantity,
                        approved_quantity=recommendation.effective_quantity,
                        unit_price=price, total_amount=total,
                    ))
                orders.append(uow.orders.add(order))
            if orders:
                uow.commit()
        return tuple(orders)
