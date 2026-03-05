import apiClient, { tenantUrl } from '@/api/client'
import type {
  AttendanceRecord,
  AttendanceCreate,
  AttendanceBulkCreate,
  AttendanceBulkResponse,
} from '@/types/models'

interface ListResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

export const attendanceApi = {
  async list(params?: {
    student_id?: string
    date_from?: string
    date_to?: string
    page?: number
    per_page?: number
  }): Promise<ListResponse<AttendanceRecord>> {
    const response = await apiClient.get<ListResponse<AttendanceRecord>>(tenantUrl('/attendance/'), { params })
    return response.data
  },

  async create(data: AttendanceCreate): Promise<AttendanceRecord> {
    const response = await apiClient.post<AttendanceRecord>(tenantUrl('/attendance/'), data)
    return response.data
  },

  async bulkCreate(data: AttendanceBulkCreate): Promise<AttendanceBulkResponse> {
    const response = await apiClient.post<AttendanceBulkResponse>(tenantUrl('/attendance/bulk'), data)
    return response.data
  },

  async get(id: string): Promise<AttendanceRecord> {
    const response = await apiClient.get<AttendanceRecord>(tenantUrl(`/attendance/${id}`))
    return response.data
  },

  async update(id: string, data: Partial<AttendanceCreate>): Promise<AttendanceRecord> {
    const response = await apiClient.put<AttendanceRecord>(tenantUrl(`/attendance/${id}`), data)
    return response.data
  },

  async delete(id: string): Promise<AttendanceRecord> {
    const response = await apiClient.delete<AttendanceRecord>(tenantUrl(`/attendance/${id}`))
    return response.data
  },
}
