"""Generic import router factory.

Creates a FastAPI APIRouter with 5 endpoints for any registered entity type.
Can be mounted on the student router (per-module) or as a standalone
framework router on the tenant parent.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_dependency import TenantAuditHelper, get_tenant_audit
from app.dependencies import get_tenant_db
from app.modules.platform.auth.dependencies import require_permission
from app.modules.platform.auth.models import User
from app.modules.shared.importer import get_config
from app.modules.shared.importer.schemas import (
    ImportBatchDetailResponse,
    ImportBatchResponse,
    ImportExecuteRequest,
    ImportHistoryResponse,
    ImportPreviewResponse,
)
from app.modules.shared.importer.service import ImportService

logger = structlog.get_logger()

# XLSX magic bytes (ZIP/OOXML: PK\x03\x04)
_XLSX_MAGIC = b"\x50\x4b\x03\x04"

# Allowed MIME types
_ALLOWED_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
    "application/csv",
}


def _detect_file_type(file: UploadFile, contents: bytes) -> str:
    """Detect whether file is xlsx or csv."""
    if file.content_type and "csv" in file.content_type:
        return "csv"
    if file.filename and file.filename.lower().endswith(".csv"):
        return "csv"
    if len(contents) >= 4 and contents[:4] == _XLSX_MAGIC:
        return "xlsx"
    # Fallback: try csv if not xlsx
    if file.filename and file.filename.lower().endswith((".xlsx", ".xls")):
        return "xlsx"
    return "csv"


def create_import_router(entity_type: str) -> APIRouter:
    """Create an import router bound to a specific entity type.

    Returns an APIRouter with prefix "/import" and 5 endpoints.
    Permission is looked up from the importer registry at request time.
    """
    router = APIRouter(prefix="/import", tags=["import"])

    async def _get_service() -> ImportService:
        return ImportService()

    @router.post("/preview", response_model=ImportPreviewResponse)
    async def preview_import(
        request: Request,
        file: UploadFile = File(...),
        current_user: User = Depends(require_permission(
            get_config(entity_type).permission, hidden=True
        )),
        db: AsyncSession = Depends(get_tenant_db),
        service: ImportService = Depends(_get_service),
        audit: TenantAuditHelper = Depends(get_tenant_audit),
    ):
        """Upload a file and get a preview with auto-mapped columns."""
        # Validate MIME type
        if file.content_type and file.content_type not in _ALLOWED_MIMES:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="Alleen Excel (.xlsx) of CSV bestanden zijn toegestaan.",
            )

        contents = await file.read()

        # Validate file size (max 5MB)
        if len(contents) > 5 * 1024 * 1024:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Bestand is te groot (max 5MB).")

        # Validate xlsx magic bytes if xlsx
        file_type = _detect_file_type(file, contents)
        if file_type == "xlsx" and (len(contents) < 4 or contents[:4] != _XLSX_MAGIC):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="Ongeldig bestandsformaat — alleen .xlsx of .csv bestanden.",
            )

        result = await service.preview(
            file_data=contents,
            file_name=file.filename or "unknown",
            file_type=file_type,
            entity_type=entity_type,
            imported_by_id=current_user.id,
            db=db,
        )

        await audit.log(
            f"{entity_type}.import_preview",
            entity_type="import_batch",
            entity_id=result.batch_id,
            file_name=file.filename,
            total_rows=result.total_rows,
        )

        return result

    @router.post("/{batch_id}/execute", response_model=ImportBatchResponse)
    async def execute_import(
        batch_id: uuid.UUID,
        data: ImportExecuteRequest,
        current_user: User = Depends(require_permission(
            get_config(entity_type).permission, hidden=True
        )),
        db: AsyncSession = Depends(get_tenant_db),
        service: ImportService = Depends(_get_service),
        audit: TenantAuditHelper = Depends(get_tenant_audit),
    ):
        """Execute an import with the given column mapping and duplicate strategy."""
        result = await service.execute(
            batch_id=batch_id,
            column_mapping=data.column_mapping,
            duplicate_strategy=data.duplicate_strategy,
            db=db,
        )

        await audit.log(
            f"{entity_type}.import_executed",
            entity_type="import_batch",
            entity_id=batch_id,
            imported=result.imported_count,
            updated=result.updated_count,
            skipped=result.skipped_count,
            errors=result.error_count,
        )

        return result

    @router.get("/history", response_model=ImportHistoryResponse)
    async def list_import_history(
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        current_user: User = Depends(require_permission(
            get_config(entity_type).permission, hidden=True
        )),
        db: AsyncSession = Depends(get_tenant_db),
        service: ImportService = Depends(_get_service),
    ):
        """List past imports for this entity type."""
        return await service.list_history(
            entity_type=entity_type, db=db, page=page, per_page=per_page
        )

    @router.get("/history/{batch_id}", response_model=ImportBatchDetailResponse)
    async def get_import_detail(
        batch_id: uuid.UUID,
        page: int = Query(1, ge=1),
        per_page: int = Query(50, ge=1, le=200),
        current_user: User = Depends(require_permission(
            get_config(entity_type).permission, hidden=True
        )),
        db: AsyncSession = Depends(get_tenant_db),
        service: ImportService = Depends(_get_service),
    ):
        """Get details of a specific import batch, including per-row results."""
        return await service.get_batch_detail(
            batch_id=batch_id, db=db, page=page, per_page=per_page
        )

    @router.post("/history/{batch_id}/rollback", status_code=200)
    async def rollback_import(
        batch_id: uuid.UUID,
        current_user: User = Depends(require_permission(
            get_config(entity_type).permission, hidden=True
        )),
        db: AsyncSession = Depends(get_tenant_db),
        service: ImportService = Depends(_get_service),
        audit: TenantAuditHelper = Depends(get_tenant_audit),
    ):
        """Roll back a completed import."""
        await service.rollback(
            batch_id=batch_id,
            rolled_back_by=current_user.id,
            db=db,
        )

        await audit.log(
            f"{entity_type}.import_rolled_back",
            entity_type="import_batch",
            entity_id=batch_id,
        )

        return {"detail": "Import succesvol teruggedraaid."}

    return router
