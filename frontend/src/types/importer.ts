// --- Generic Import System types ---

export interface ImportFieldInfo {
  name: string
  label: string
  required: boolean
}

export interface ImportPreviewResponse {
  batch_id: string
  file_name: string
  total_rows: number
  detected_headers: string[]
  suggested_mapping: Record<string, string>
  available_fields: ImportFieldInfo[]
  preview_rows: Record<string, string | null>[]
}

export interface ImportExecuteRequest {
  column_mapping: Record<string, string>
  duplicate_strategy: 'skip' | 'enrich' | 'replace'
}

export interface ImportBatchResponse {
  id: string
  entity_type: string
  file_name: string
  status: string
  total_rows: number
  imported_count: number
  updated_count: number
  skipped_count: number
  error_count: number
  duplicate_strategy: string | null
  imported_by: string
  created_at: string
  rolled_back_at: string | null
}

export interface ImportRecordResponse {
  id: string
  row_number: number
  status: string
  raw_data: Record<string, string | null>
  mapped_data: Record<string, string | null> | null
  entity_id: string | null
  duplicate_of: string | null
  error_message: string | null
}

export interface ImportBatchDetailResponse {
  batch: ImportBatchResponse
  records: ImportRecordResponse[]
  total_records: number
  page: number
  per_page: number
}

export interface ImportHistoryResponse {
  items: ImportBatchResponse[]
  total: number
  page: number
  per_page: number
}
