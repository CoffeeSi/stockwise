from __future__ import annotations

import json

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.application.dto.imports import ImportFileCommand, ParsedImport
from backend.domain.entities.imports import ImportBatch
from backend.domain.enums import (
    GrowthSource,
    ImportSourceType,
    ImportStatus,
    MaterialRequirementStatus,
    StockoutSource,
    TransactionType,
    TransitStatus,
)
from backend.domain.repositories.import_repository import InvalidImportStatusTransitionError
from backend.infrastructure.persistence.import_repository import SqlAlchemyImportRepository
from backend.infrastructure.persistence.models.catalog import (
    CategoryModel,
    ProductModel,
    SupplierModel,
    SupplierProductModel,
    UserModel,
    WarehouseModel,
)
from backend.infrastructure.persistence.models.imports import (
    GrowthAssumptionModel,
    InventorySnapshotModel,
    InTransitItemModel,
    MaterialRequirementModel,
    MonthlySalesModel,
    SalesTransactionModel,
    SeasonalityCoefficientModel,
    StockoutPeriodModel,
)


class ImportUserNotFoundError(ValueError):
    pass


class SqlAlchemyImportGateway:
    """Transaction coordinator and write-side adapter for one imported file."""

    def __init__(self, session_factory: sessionmaker[Session],
                 complete_hook: Callable[[Session, int], None] | None = None) -> None:
        self._session_factory = session_factory
        self._complete_hook = complete_hook

    def start(self, command: ImportFileCommand, *, checksum: str) -> ImportBatch:
        with self._session_factory.begin() as session:
            if session.get(UserModel, command.imported_by) is None:
                raise ImportUserNotFoundError(
                    f"import user {command.imported_by} was not found"
                )
            repository = SqlAlchemyImportRepository(session)
            batch = repository.create_batch(
                ImportBatch(
                    source_type=command.source_type,
                    file_name=command.file_name.strip(),
                    file_checksum=checksum,
                    status=ImportStatus.PENDING,
                    imported_by=command.imported_by,
                    imported_at=self._now(),
                )
            )
            return repository.mark_processing(batch.id)

    def complete(self, batch: ImportBatch, parsed: ParsedImport) -> ImportBatch:
        if parsed.source_type is not batch.source_type:
            raise ValueError("parsed source type does not match import batch")
        with self._session_factory.begin() as session:
            repository = SqlAlchemyImportRepository(session)
            current = repository.get(batch.id)
            if current is None:
                raise ValueError(f"import batch {batch.id} was not found")
            if current.status is not ImportStatus.PROCESSING:
                raise InvalidImportStatusTransitionError(
                    current.status.value, ImportStatus.COMPLETED.value
                )
            row_count = self._write_rows(session, batch.id, parsed)
            completed = repository.mark_completed(
                batch.id, row_count=row_count, warnings=parsed.warnings,
            )
            if self._complete_hook is not None:
                self._complete_hook(session, row_count)
            return completed

    def fail(
        self,
        batch: ImportBatch,
        *,
        error_details: Mapping[str, Any],
    ) -> ImportBatch:
        with self._session_factory.begin() as session:
            repository = SqlAlchemyImportRepository(session)
            current = repository.get(batch.id)
            if current is None:
                raise ValueError(f"import batch {batch.id} was not found")
            if current.status is ImportStatus.FAILED:
                return current
            details = {
                "error_type": str(error_details.get("error_type", "ImportError"))[:100],
                "message": str(error_details.get("message", "import failed"))[:2000],
            }
            if "validation_errors" in error_details:
                details["validation_errors"] = json.loads(json.dumps(
                    error_details["validation_errors"], default=str,
                ))
            return repository.mark_failed(batch.id, error_details=details)

    def _write_rows(
        self,
        session: Session,
        batch_id: UUID,
        parsed: ParsedImport,
    ) -> int:
        for row in parsed.rows:
            self._write_row(session, batch_id, parsed.source_type, row)
        session.flush()
        return len(parsed.rows)

    def _write_row(
        self,
        session: Session,
        batch_id: UUID,
        source: ImportSourceType,
        row: dict[str, Any],
    ) -> None:
        product = None
        warehouse = None
        supplier = None
        category = None
        if row.get("category_code"):
            category = self._category(session, row)
        if row.get("sku"):
            product = self._product(session, row, category_id=category.id if category else None)
        if row.get("warehouse_code"):
            warehouse = self._warehouse(session, row)
        if row.get("supplier_code"):
            supplier = self._supplier(session, row)

        if source is ImportSourceType.SALES:
            session.add(
                SalesTransactionModel(
                    id=uuid4(),
                    import_batch_id=batch_id,
                    source_row_number=row["source_row_number"],
                    external_document_number=row.get("external_document_number"),
                    sold_at=row["sold_at"],
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    anonymous_customer_id=row.get("anonymous_customer_id"),
                    transaction_type=TransactionType(row["transaction_type"]),
                    original_transaction_id=None,
                    quantity=row["quantity"],
                    unit_price=row.get("unit_price"),
                    total_amount=row.get("total_amount"),
                )
            )
        elif source is ImportSourceType.MONTHLY_SALES:
            session.add(
                MonthlySalesModel(
                    id=uuid4(),
                    import_batch_id=batch_id,
                    source_row_number=row["source_row_number"],
                    product_id=product.id,
                    warehouse_id=warehouse.id if warehouse else None,
                    period_start=row["period_start"],
                    period_end=row["period_end"],
                    quantity=row["quantity"],
                )
            )
        elif source is ImportSourceType.INVENTORY:
            session.add(
                InventorySnapshotModel(
                    id=uuid4(),
                    import_batch_id=batch_id,
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    snapshot_at=row["snapshot_at"],
                    quantity_on_hand=row["quantity_on_hand"],
                    quantity_reserved=row["quantity_reserved"],
                    quantity_available=row["quantity_available"],
                )
            )
        elif source is ImportSourceType.STOCKOUT:
            session.add(
                StockoutPeriodModel(
                    id=uuid4(),
                    import_batch_id=batch_id,
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    started_at=row["started_at"],
                    ended_at=row.get("ended_at"),
                    source=StockoutSource(row["source"]),
                    confidence=row.get("confidence"),
                )
            )
        elif source is ImportSourceType.IN_TRANSIT:
            session.add(
                InTransitItemModel(
                    id=uuid4(),
                    import_batch_id=batch_id,
                    external_order_number=row.get("external_order_number"),
                    supplier_id=supplier.id,
                    product_id=product.id,
                    destination_warehouse_id=warehouse.id,
                    quantity=row["quantity"],
                    expected_at=row.get("expected_at"),
                    status=TransitStatus(row["status"]),
                )
            )
        elif source is ImportSourceType.SEASONALITY:
            session.add(
                SeasonalityCoefficientModel(
                    id=uuid4(),
                    import_batch_id=batch_id,
                    product_id=product.id if product else None,
                    category_id=category.id if category else None,
                    month=row["month"],
                    coefficient=row["coefficient"],
                    valid_from=row["valid_from"],
                    valid_to=row.get("valid_to"),
                    version=row["version"],
                )
            )
        elif source is ImportSourceType.SUPPLIER_TERMS:
            self._supplier_terms(session, supplier.id, product.id, row)
        elif source is ImportSourceType.GROWTH:
            session.add(
                GrowthAssumptionModel(
                    id=uuid4(),
                    import_batch_id=batch_id,
                    product_id=product.id if product else None,
                    category_id=category.id if category else None,
                    warehouse_id=warehouse.id if warehouse else None,
                    growth_rate=row["growth_rate"],
                    valid_from=row["valid_from"],
                    valid_to=row.get("valid_to"),
                    source=GrowthSource(row["source"]),
                )
            )
        elif source is ImportSourceType.MATERIAL_REQUIREMENTS:
            session.add(
                MaterialRequirementModel(
                    id=uuid4(),
                    import_batch_id=batch_id,
                    external_document_number=row.get("external_document_number"),
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    required_quantity=row["required_quantity"],
                    required_at=row["required_at"],
                    status=MaterialRequirementStatus(row["status"]),
                )
            )
        else:
            raise ValueError(f"unsupported import source: {source.value}")

    @staticmethod
    def _category(session: Session, row: dict[str, Any]) -> CategoryModel:
        code = str(row["category_code"])
        model = session.scalar(select(CategoryModel).where(CategoryModel.code == code))
        if model is None:
            model = CategoryModel(
                id=uuid4(),
                code=code,
                name=str(row.get("category_name") or code),
                is_active=True,
            )
            session.add(model)
            session.flush()
        return model

    @staticmethod
    def _product(
        session: Session,
        row: dict[str, Any],
        *,
        category_id: UUID | None,
    ) -> ProductModel:
        sku = str(row["sku"])
        model = session.scalar(select(ProductModel).where(ProductModel.sku == sku))
        if model is None:
            model = ProductModel(
                id=uuid4(),
                sku=sku,
                name=str(row.get("product_name") or sku),
                unit=str(row.get("unit") or "pcs"),
                category_id=category_id,
                is_active=True,
            )
            session.add(model)
            session.flush()
        return model

    @staticmethod
    def _warehouse(session: Session, row: dict[str, Any]) -> WarehouseModel:
        code = str(row["warehouse_code"])
        model = session.scalar(select(WarehouseModel).where(WarehouseModel.code == code))
        if model is None:
            model = WarehouseModel(
                id=uuid4(),
                code=code,
                name=str(row.get("warehouse_name") or code),
                is_active=True,
            )
            session.add(model)
            session.flush()
        return model

    @staticmethod
    def _supplier(session: Session, row: dict[str, Any]) -> SupplierModel:
        code = str(row["supplier_code"])
        model = session.scalar(select(SupplierModel).where(SupplierModel.code == code))
        if model is None:
            model = SupplierModel(
                id=uuid4(),
                code=code,
                name=str(row.get("supplier_name") or code),
                is_active=True,
            )
            session.add(model)
            session.flush()
        return model

    @staticmethod
    def _supplier_terms(
        session: Session,
        supplier_id: UUID,
        product_id: UUID,
        row: dict[str, Any],
    ) -> SupplierProductModel:
        model = session.scalar(
            select(SupplierProductModel).where(
                SupplierProductModel.supplier_id == supplier_id,
                SupplierProductModel.product_id == product_id,
            )
        )
        values = {
            "moq": row["moq"],
            "package_size": row["package_size"],
            "lead_time_days": row["lead_time_days"],
            "purchase_price": row.get("purchase_price"),
            "currency": row.get("currency"),
            "priority": row["priority"],
            "is_primary": row["is_primary"],
            "is_active": True,
        }
        if model is None:
            model = SupplierProductModel(
                id=uuid4(),
                supplier_id=supplier_id,
                product_id=product_id,
                **values,
            )
            session.add(model)
            session.flush()
        else:
            for name, value in values.items():
                setattr(model, name, value)
        return model

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)
