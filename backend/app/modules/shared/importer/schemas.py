"""Pydantic schemas for the generic import system."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FieldInfoSchema(BaseModel):
    name: str
    label: str
    required: bool = False


class ImportPreviewResponse(BaseModel):
    batch_id: uuid.UUID
    file_name: str
    total_rows: int
    detected_headers: list[str]
    suggested_mapping: dict[str, str]
    available_fields: list[FieldInfoSchema]
    preview_rows: list[dict[str, Any]]


class ImportExecuteRequest(BaseModel):
    column_mapping: dict[str, str] = Field(
        ..., description="Map of file column name → entity field name"
    )
    duplicate_strategy: Literal["skip", "enrich", "replace"] = "skip"


class ImportBatchResponse(BaseModel):
    id: uuid.UUID
    entity_type: str
    file_name: str
    status: str
    total_rows: int
    imported_count: int
    updated_count: int
    skipped_count: int
    error_count: int
    duplicate_strategy: str | None
    imported_by: uuid.UUID
    created_at: datetime
    rolled_back_at: datetime | None

    model_config = {"from_attributes": True}


class ImportRecordResponse(BaseModel):
    id: uuid.UUID
    row_number: int
    status: str
    raw_data: dict[str, Any]
    mapped_data: dict[str, Any] | None
    entity_id: uuid.UUID | None
    duplicate_of: uuid.UUID | None
    error_message: str | None

    model_config = {"from_attributes": True}


class ImportBatchDetailResponse(BaseModel):
    batch: ImportBatchResponse
    records: list[ImportRecordResponse]
    total_records: int
    page: int
    per_page: int


class ImportHistoryResponse(BaseModel):
    items: list[ImportBatchResponse]
    total: int
    page: int
    per_page: int
