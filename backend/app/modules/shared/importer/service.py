"""Generic import service — entity-type agnostic.

Uses the importer registry to look up handlers and finders per entity type.
Handles preview, execute, rollback, and history for any registered entity.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.shared.importer import FieldInfo, get_config
from app.modules.shared.importer.file_parser import parse_file
from app.modules.shared.importer.models import ImportBatch, ImportRecord
from app.modules.shared.importer.schemas import (
    FieldInfoSchema,
    ImportBatchDetailResponse,
    ImportBatchResponse,
    ImportHistoryResponse,
    ImportPreviewResponse,
    ImportRecordResponse,
)
from app.modules.shared.importer.synonyms import SYNONYMS

logger = structlog.get_logger()


class ImportService:
    """Entity-type-agnostic import service."""

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    async def preview(
        self,
        file_data: bytes,
        file_name: str,
        file_type: str,
        entity_type: str,
        imported_by_id: uuid.UUID,
        db: AsyncSession,
    ) -> ImportPreviewResponse:
        config = get_config(entity_type)
        result = parse_file(file_data, file_type)

        mapping = self._auto_map(result.headers, config.fields)

        batch = ImportBatch(
            entity_type=entity_type,
            file_name=file_name,
            file_type=file_type,
            status="preview",
            total_rows=result.total_rows,
            column_mapping=mapping,
            imported_by=imported_by_id,
        )
        db.add(batch)
        await db.flush()  # Flush to populate batch.id

        # Store raw rows as ImportRecords in pending state
        for row_num, row_data in enumerate(result.rows, start=1):
            record = ImportRecord(
                batch_id=batch.id,
                row_number=row_num,
                status="pending",
                raw_data=row_data,
            )
            db.add(record)

        await db.flush()

        logger.info(
            "import.preview_created",
            batch_id=str(batch.id),
            entity_type=entity_type,
            total_rows=result.total_rows,
            auto_mapped=len(mapping),
        )

        return ImportPreviewResponse(
            batch_id=batch.id,
            file_name=file_name,
            total_rows=result.total_rows,
            detected_headers=result.headers,
            suggested_mapping=mapping,
            available_fields=[
                FieldInfoSchema(name=f.name, label=f.label, required=f.required)
                for f in config.fields
            ],
            preview_rows=result.rows[:5],
        )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(
        self,
        batch_id: uuid.UUID,
        column_mapping: dict[str, str],
        duplicate_strategy: str,
        db: AsyncSession,
    ) -> ImportBatchResponse:
        batch = await self._get_batch(batch_id, db)
        if batch.status != "preview":
            raise ValueError("Import kan alleen worden uitgevoerd vanuit preview-status.")

        config = get_config(batch.entity_type)

        batch.column_mapping = column_mapping
        batch.duplicate_strategy = duplicate_strategy
        batch.status = "processing"
        await db.flush()

        # Load all pending records
        result = await db.execute(
            select(ImportRecord)
            .where(ImportRecord.batch_id == batch_id)
            .order_by(ImportRecord.row_number)
        )
        records = list(result.scalars().all())

        imported = 0
        updated = 0
        skipped = 0
        errors = 0

        for record in records:
            try:
                # Map raw data to entity fields
                mapped = self._apply_mapping(record.raw_data, column_mapping)
                record.mapped_data = mapped

                # Skip rows missing required fields
                # full_name satisfies first_name (split happens in handler)
                missing = [
                    f.label for f in config.fields
                    if f.required and not mapped.get(f.name)
                    and not (f.name == "first_name" and mapped.get("full_name"))
                ]
                if missing:
                    record.status = "error"
                    record.error_message = f"Verplicht veld ontbreekt: {', '.join(missing)}"
                    errors += 1
                    continue

                # Find duplicates
                existing_id, existing_data = await config.finder(mapped, db)

                if existing_id:
                    record.duplicate_of = existing_id

                # Call handler
                entity_id, status, previous_data = await config.handler(
                    mapped, existing_id, duplicate_strategy, existing_data, db,
                )

                record.entity_id = entity_id
                record.status = status
                record.previous_data = previous_data

                if status == "imported":
                    imported += 1
                elif status == "updated":
                    updated += 1
                elif status == "skipped":
                    skipped += 1

            except Exception as exc:
                logger.warning(
                    "import.row_error",
                    batch_id=str(batch_id),
                    row=record.row_number,
                    exc_info=True,
                )
                record.status = "error"
                record.error_message = str(exc)[:500]
                errors += 1

        batch.imported_count = imported
        batch.updated_count = updated
        batch.skipped_count = skipped
        batch.error_count = errors
        batch.status = "completed"
        await db.flush()

        logger.info(
            "import.execute_completed",
            batch_id=str(batch_id),
            imported=imported,
            updated=updated,
            skipped=skipped,
            errors=errors,
        )

        return self._batch_to_response(batch)

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    async def rollback(
        self,
        batch_id: uuid.UUID,
        rolled_back_by: uuid.UUID,
        db: AsyncSession,
    ) -> None:
        batch = await self._get_batch(batch_id, db)
        if batch.status != "completed":
            raise ValueError("Alleen voltooide imports kunnen worden teruggedraaid.")

        config = get_config(batch.entity_type)

        result = await db.execute(
            select(ImportRecord)
            .where(
                ImportRecord.batch_id == batch_id,
                ImportRecord.status.in_(["imported", "updated"]),
            )
            .order_by(ImportRecord.row_number)
        )
        records = list(result.scalars().all())

        for record in records:
            try:
                await config.handler(
                    record.mapped_data or {},
                    record.entity_id,
                    "rollback",
                    record.previous_data,
                    db,
                )
                record.status = "rolled_back"
            except Exception:
                logger.warning(
                    "import.rollback_row_error",
                    batch_id=str(batch_id),
                    row=record.row_number,
                    exc_info=True,
                )

        batch.status = "rolled_back"
        batch.rolled_back_at = func.now()
        batch.rolled_back_by = rolled_back_by
        await db.flush()

        logger.info("import.rolled_back", batch_id=str(batch_id))

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def list_history(
        self,
        entity_type: str,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 20,
    ) -> ImportHistoryResponse:
        base_query = select(ImportBatch).where(
            ImportBatch.entity_type == entity_type,
            ImportBatch.status != "preview",
        )

        # Count
        count_q = select(func.count()).select_from(base_query.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        # Paginate
        query = (
            base_query
            .order_by(ImportBatch.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await db.execute(query)
        batches = list(result.scalars().all())

        return ImportHistoryResponse(
            items=[self._batch_to_response(b) for b in batches],
            total=total,
            page=page,
            per_page=per_page,
        )

    async def get_batch_detail(
        self,
        batch_id: uuid.UUID,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 50,
    ) -> ImportBatchDetailResponse:
        batch = await self._get_batch(batch_id, db)

        # Count records
        count_q = select(func.count()).where(ImportRecord.batch_id == batch_id)
        total_records = (await db.execute(count_q)).scalar() or 0

        # Paginate records
        records_q = (
            select(ImportRecord)
            .where(ImportRecord.batch_id == batch_id)
            .order_by(ImportRecord.row_number)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await db.execute(records_q)
        records = list(result.scalars().all())

        return ImportBatchDetailResponse(
            batch=self._batch_to_response(batch),
            records=[
                ImportRecordResponse(
                    id=r.id,
                    row_number=r.row_number,
                    status=r.status,
                    raw_data=r.raw_data,
                    mapped_data=r.mapped_data,
                    entity_id=r.entity_id,
                    duplicate_of=r.duplicate_of,
                    error_message=r.error_message,
                )
                for r in records
            ],
            total_records=total_records,
            page=page,
            per_page=per_page,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_batch(self, batch_id: uuid.UUID, db: AsyncSession) -> ImportBatch:
        result = await db.execute(
            select(ImportBatch).where(ImportBatch.id == batch_id)
        )
        batch = result.scalar_one_or_none()
        if not batch:
            raise ValueError("Import batch niet gevonden.")
        return batch

    def _auto_map(
        self, headers: list[str], fields: list[FieldInfo]
    ) -> dict[str, str]:
        """Auto-map file headers to entity fields using synonym matching."""
        mapping: dict[str, str] = {}
        used_fields: set[str] = set()

        for header in headers:
            header_lower = header.lower().strip()
            if not header_lower:
                continue

            best_field: str | None = None

            # 1. Exact match on field name
            for f in fields:
                if f.name not in used_fields and f.name == header_lower:
                    best_field = f.name
                    break

            # 2. Synonym exact match
            if not best_field:
                for field_name, synonyms in SYNONYMS.items():
                    if field_name in used_fields:
                        continue
                    if header_lower in synonyms:
                        # Verify field is registered
                        if any(f.name == field_name for f in fields):
                            best_field = field_name
                            break

            # 3. Synonym contains match
            if not best_field:
                for field_name, synonyms in SYNONYMS.items():
                    if field_name in used_fields:
                        continue
                    for syn in synonyms:
                        if syn in header_lower or header_lower in syn:
                            if any(f.name == field_name for f in fields):
                                best_field = field_name
                                break
                    if best_field:
                        break

            if best_field:
                mapping[header] = best_field
                used_fields.add(best_field)

        return mapping

    def _apply_mapping(
        self, raw_data: dict[str, Any], column_mapping: dict[str, str]
    ) -> dict[str, Any]:
        """Apply column mapping to transform raw file data to entity fields."""
        mapped: dict[str, Any] = {}
        for file_col, field_name in column_mapping.items():
            value = raw_data.get(file_col)
            if value is not None and str(value).strip():
                mapped[field_name] = str(value).strip()
        return mapped

    def _batch_to_response(self, batch: ImportBatch) -> ImportBatchResponse:
        return ImportBatchResponse(
            id=batch.id,
            entity_type=batch.entity_type,
            file_name=batch.file_name,
            status=batch.status,
            total_rows=batch.total_rows,
            imported_count=batch.imported_count,
            updated_count=batch.updated_count,
            skipped_count=batch.skipped_count,
            error_count=batch.error_count,
            duplicate_strategy=batch.duplicate_strategy,
            imported_by=batch.imported_by,
            created_at=batch.created_at,
            rolled_back_at=batch.rolled_back_at,
        )
