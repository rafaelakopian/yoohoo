import apiClient, { tenantUrl } from '@/api/client'
import type { Member, MemberListResponse } from '@/types/school'

export interface MemberListParams {
  group?: string
  q?: string
  limit?: number
  offset?: number
}

export const membersApi = {
  async list(params?: MemberListParams): Promise<MemberListResponse> {
    const { data } = await apiClient.get<MemberListResponse>(tenantUrl('/members'), {
      params,
    })
    return data
  },
}

// Convenience: fetch teachers for dropdowns
export async function fetchTeachers(): Promise<Member[]> {
  const resp = await membersApi.list({ group: 'docent', limit: 100 })
  return resp.items
}
