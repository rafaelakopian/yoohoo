import apiClient, { tenantUrl } from '../client'
import type { Collaborator, Invitation } from '@/types/auth'

export const collaborationsApi = {
  async list(): Promise<Collaborator[]> {
    const { data } = await apiClient.get<Collaborator[]>(tenantUrl('/collaborations/'))
    return data
  },

  async invite(payload: { email: string; group_id?: string | null }): Promise<Invitation> {
    const { data } = await apiClient.post<Invitation>(tenantUrl('/collaborations/invite'), payload)
    return data
  },

  async toggle(membershipId: string): Promise<Collaborator> {
    const { data } = await apiClient.put<Collaborator>(
      tenantUrl(`/collaborations/${membershipId}/toggle`),
    )
    return data
  },
}
