from __future__ import annotations

from collections.abc import Sequence
from dataclasses import fields
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from backend.domain.entities.enums import RecommendationStatus, Urgency
from backend.domain.entities.recommendation import Recommendation, RecommendationAdjustment
from backend.domain.repositories.recommendation_repository import RecommendationConflictError
from backend.domain.value_objects.recommendation_display import RecommendationDisplay
from backend.infrastructure.persistence.calculation_run_repository import _json
from backend.infrastructure.persistence.models.calculation import RecommendationModel
from backend.infrastructure.persistence.models.catalog import CategoryModel, ProductModel, SupplierModel, WarehouseModel
from .models.orders import PurchaseOrderItemModel, RecommendationAdjustmentModel


def _entity(model, entity_type):
    values = {field.name: getattr(model, field.name) for field in fields(entity_type)}
    for key, value in values.items():
        if isinstance(value, datetime) and value.utcoffset() is None:
            values[key] = value.replace(tzinfo=timezone.utc)
    return entity_type(**values)


def _not_ordered():
    return ~select(PurchaseOrderItemModel.id).where(
        PurchaseOrderItemModel.recommendation_id == RecommendationModel.id,
    ).exists()


class SqlAlchemyRecommendationRepository:
    SORT_FIELDS = {
        "risk_score": RecommendationModel.risk_score,
        "recommended_quantity": RecommendationModel.recommended_quantity,
        "created_at": RecommendationModel.created_at,
        "urgency": RecommendationModel.urgency,
        "product_id": RecommendationModel.product_id,
    }

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, recommendation_id: UUID) -> Recommendation | None:
        model = self._session.get(RecommendationModel, recommendation_id)
        return self._to_domain(model) if model is not None else None

    def list_for_run(
        self, run_id: UUID, *, supplier_id: UUID | None = None,
        warehouse_id: UUID | None = None, urgency: Urgency | None = None,
        status: RecommendationStatus | None = None, category_id: UUID | None = None,
        search: str | None = None,
        sort_by: str = "risk_score", descending: bool = True,
        limit: int = 50, offset: int = 0,
    ) -> tuple[list[Recommendation], int]:
        if sort_by not in self.SORT_FIELDS:
            raise ValueError(f"unsupported recommendation sort field: {sort_by}")
        if limit <= 0 or offset < 0:
            raise ValueError("limit must be positive and offset nonnegative")
        query = select(RecommendationModel).join(
            ProductModel, RecommendationModel.product_id == ProductModel.id,
        ).where(RecommendationModel.calculation_run_id == run_id)
        if supplier_id is not None:
            query = query.where(RecommendationModel.supplier_id == supplier_id)
        if warehouse_id is not None:
            query = query.where(RecommendationModel.warehouse_id == warehouse_id)
        if urgency is not None:
            query = query.where(RecommendationModel.urgency == urgency)
        if status is not None:
            query = query.where(RecommendationModel.status == status)
        if category_id is not None:
            query = query.where(ProductModel.category_id == category_id)
        if search and search.strip():
            # Treat wildcard characters as literal SKU/name characters.
            term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.where(or_(ProductModel.sku.ilike(f"%{term}%", escape="\\"),
                                    ProductModel.name.ilike(f"%{term}%", escape="\\")))
        total = self._session.scalar(select(func.count()).select_from(query.subquery())) or 0
        column = self.SORT_FIELDS[sort_by]
        ordered = column.desc() if descending else column.asc()
        models = self._session.scalars(query.order_by(ordered, RecommendationModel.id).limit(limit).offset(offset)).all()
        return [self._to_domain(model) for model in models], total

    def get_display_data(self, recommendation_ids: Sequence[UUID]) -> dict[UUID, RecommendationDisplay]:
        if not recommendation_ids:
            return {}
        rows = self._session.execute(select(
            RecommendationModel.id, ProductModel.sku, ProductModel.name, ProductModel.unit,
            SupplierModel.name, WarehouseModel.name, ProductModel.category_id, CategoryModel.name,
        ).select_from(RecommendationModel)
          .join(ProductModel, RecommendationModel.product_id == ProductModel.id)
          .join(SupplierModel, RecommendationModel.supplier_id == SupplierModel.id)
          .join(WarehouseModel, RecommendationModel.warehouse_id == WarehouseModel.id)
          .outerjoin(CategoryModel, ProductModel.category_id == CategoryModel.id)
          .where(RecommendationModel.id.in_(recommendation_ids)))
        return {row[0]: RecommendationDisplay(*row) for row in rows}

    def add_many(self, recommendations: list[Recommendation]) -> None:
        for item in recommendations:
            self._session.add(RecommendationModel(
                id=item.id, calculation_run_id=item.calculation_run_id,
                product_id=item.product_id, warehouse_id=item.warehouse_id,
                supplier_id=item.supplier_id, forecast_quantity=item.forecast_quantity,
                current_stock=item.current_stock,
                in_transit_quantity=item.in_transit_quantity,
                material_requirement_quantity=item.material_requirement_quantity,
                safety_stock=item.safety_stock,
                shortage_quantity=item.shortage_quantity,
                quantity_before_rounding=item.quantity_before_rounding,
                moq=item.moq, package_size=item.package_size,
                recommended_quantity=item.recommended_quantity,
                effective_quantity=item.effective_quantity,
                risk_score=item.risk_score, urgency=item.urgency,
                status=item.status, explanation=item.explanation,
                calculation_details=_json(dict(item.calculation_details)),
                version=item.version, created_at=item.created_at, updated_at=item.updated_at,
            ))
        self._session.flush()

    def count_for_run(self, run_id: UUID) -> int:
        return self._session.scalar(select(func.count()).select_from(RecommendationModel).where(
            RecommendationModel.calculation_run_id == run_id
        )) or 0

    def count_for_runs(self, run_ids: Sequence[UUID]) -> dict[UUID, int]:
        if not run_ids:
            return {}
        return dict(self._session.execute(select(
            RecommendationModel.calculation_run_id, func.count(RecommendationModel.id),
        ).where(RecommendationModel.calculation_run_id.in_(run_ids))
          .group_by(RecommendationModel.calculation_run_id)).all())

    @staticmethod
    def _to_domain(model: RecommendationModel) -> Recommendation:
        created_at = model.created_at
        updated_at = model.updated_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return Recommendation(
            id=model.id, calculation_run_id=model.calculation_run_id,
            product_id=model.product_id, warehouse_id=model.warehouse_id,
            supplier_id=model.supplier_id, forecast_quantity=model.forecast_quantity,
            current_stock=model.current_stock,
            in_transit_quantity=model.in_transit_quantity,
            material_requirement_quantity=model.material_requirement_quantity,
            safety_stock=model.safety_stock,
            shortage_quantity=model.shortage_quantity,
            quantity_before_rounding=model.quantity_before_rounding,
            moq=model.moq, package_size=model.package_size,
            recommended_quantity=model.recommended_quantity,
            effective_quantity=model.effective_quantity,
            risk_score=model.risk_score, urgency=model.urgency,
            status=model.status, explanation=model.explanation,
            calculation_details=dict(model.calculation_details),
            version=model.version, created_at=created_at, updated_at=updated_at,
        )

    def list_orderable(self, calculation_run_id: UUID) -> tuple[Recommendation, ...]:
        rows = self._session.scalars(select(RecommendationModel).where(
            RecommendationModel.calculation_run_id == calculation_run_id,
            RecommendationModel.status == RecommendationStatus.ACCEPTED,
            RecommendationModel.effective_quantity > 0, _not_ordered(),
        ).order_by(RecommendationModel.id))
        return tuple(self._to_domain(row) for row in rows)

    def save_adjustment(self, recommendation: Recommendation, adjustment: RecommendationAdjustment,
                        *, expected_version: int) -> None:
        if (recommendation.version != expected_version + 1 or
                recommendation.status is not RecommendationStatus.ADJUSTED or
                adjustment.recommendation_id != recommendation.id or
                adjustment.new_quantity != recommendation.effective_quantity or
                adjustment.changed_at != recommendation.updated_at):
            raise ValueError("Adjustment does not match the recommendation transition")
        statement = update(RecommendationModel).where(
            RecommendationModel.id == recommendation.id,
            RecommendationModel.version == expected_version,
            RecommendationModel.effective_quantity == adjustment.previous_quantity,
            RecommendationModel.status.in_((RecommendationStatus.SUGGESTED,
                                            RecommendationStatus.ADJUSTED, RecommendationStatus.ACCEPTED)),
            _not_ordered(),
        ).values(effective_quantity=recommendation.effective_quantity,
                 version=RecommendationModel.version + 1, status=RecommendationStatus.ADJUSTED,
                 updated_at=adjustment.changed_at)
        self._compare_and_swap(statement, recommendation.id)
        self._session.add(RecommendationAdjustmentModel(
            **{field.name: getattr(adjustment, field.name) for field in fields(adjustment)},
        ))
        self._session.flush()

    def mark_converted(self, recommendation: Recommendation, *, expected_version: int) -> None:
        if (recommendation.version != expected_version + 1 or
                recommendation.status is not RecommendationStatus.CONVERTED_TO_ORDER):
            raise ValueError("Expected an accepted-to-order domain transition")
        self._compare_and_swap(update(RecommendationModel).where(
            RecommendationModel.id == recommendation.id,
            RecommendationModel.version == expected_version,
            RecommendationModel.status == RecommendationStatus.ACCEPTED,
            RecommendationModel.effective_quantity == recommendation.effective_quantity,
            RecommendationModel.effective_quantity > 0, _not_ordered(),
        ).values(status=RecommendationStatus.CONVERTED_TO_ORDER,
                 version=RecommendationModel.version + 1, updated_at=recommendation.updated_at), recommendation.id)

    def save_acceptance(self, recommendation: Recommendation, *, expected_version: int) -> None:
        if (recommendation.version != expected_version + 1 or
                recommendation.status is not RecommendationStatus.ACCEPTED or
                recommendation.effective_quantity <= 0):
            raise ValueError("Expected a positive suggested/adjusted-to-accepted transition")
        self._compare_and_swap(update(RecommendationModel).where(
            RecommendationModel.id == recommendation.id,
            RecommendationModel.version == expected_version,
            RecommendationModel.status.in_((RecommendationStatus.SUGGESTED, RecommendationStatus.ADJUSTED)),
            RecommendationModel.effective_quantity == recommendation.effective_quantity,
            RecommendationModel.effective_quantity > 0, _not_ordered(),
        ).values(status=RecommendationStatus.ACCEPTED,
                 calculation_details=_json(dict(recommendation.calculation_details)),
                 version=RecommendationModel.version + 1,
                 updated_at=recommendation.updated_at), recommendation.id)

    def _compare_and_swap(self, statement, recommendation_id: UUID) -> None:
        result = self._session.execute(statement.execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise RecommendationConflictError(f"Recommendation {recommendation_id} was changed or ordered")
        self._session.expire_all()

    def list_adjustments(self, recommendation_id: UUID) -> tuple[RecommendationAdjustment, ...]:
        rows = self._session.scalars(select(RecommendationAdjustmentModel).where(
            RecommendationAdjustmentModel.recommendation_id == recommendation_id,
        ).order_by(RecommendationAdjustmentModel.changed_at, RecommendationAdjustmentModel.id))
        return tuple(_entity(row, RecommendationAdjustment) for row in rows)
