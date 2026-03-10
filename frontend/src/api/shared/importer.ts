import apiClient, { tenantUrl } from '@/api/client'
import type {
  ImportPreviewResponse,
  ImportBatchResponse,
  ImportBatchDetailResponse,
  ImportHistoryResponse,
} from '@/types/models'

export const importerApi = {
  async preview(entityType: string, file: File): Promise<ImportPreviewResponse> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await apiClient.post<ImportPreviewResponse>(
      tenantUrl(`/${entityType}/import/preview`),
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    return response.data
  },

  async execute(
    entityType: string,
    batchId: string,
    columnMapping: Record<string, string>,
    duplicateStrategy: 'skip' | 'enrich' | 'replace',
  ): Promise<ImportBatchResponse> {
    const response = await apiClient.post<ImportBatchResponse>(
      tenantUrl(`/${entityType}/import/${batchId}/execute`),
      { column_mapping: columnMapping, duplicate_strategy: duplicateStrategy },
    )
    return response.data
  },

  async getHistory(
    entityType: string,
    page: number = 1,
    perPage: number = 20,
  ): Promise<ImportHistoryResponse> {
    const response = await apiClient.get<ImportHistoryResponse>(
      tenantUrl(`/${entityType}/import/history`),
      { params: { page, per_page: perPage } },
    )
    return response.data
  },

  async getBatchDetail(
    entityType: string,
    batchId: string,
    page: number = 1,
    perPage: number = 50,
  ): Promise<ImportBatchDetailResponse> {
    const response = await apiClient.get<ImportBatchDetailResponse>(
      tenantUrl(`/${entityType}/import/history/${batchId}`),
      { params: { page, per_page: perPage } },
    )
    return response.data
  },

  async rollback(entityType: string, batchId: string): Promise<void> {
    await apiClient.post(tenantUrl(`/${entityType}/import/history/${batchId}/rollback`))
  },
}
