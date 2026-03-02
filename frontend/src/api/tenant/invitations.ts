import apiClient from '../client'
import type { Invitation, MessageResponse } from '@/types/models'

export interface CreateInvitationData {
  email: string
  role?: string | null
  group_id?: string | null
}

export interface BulkInvitationResult {
  email: string
  success: boolean
  error?: string | null
  invitation?: Invitation | null
}

export interface BulkInvitationResponse {
  created: number
  failed: number
  results: BulkInvitationResult[]
}

export interface InvitationWithStatus extends Invitation {
  status: 'pending' | 'accepted' | 'revoked' | 'expired'
  accepted_at?: string | null
}

export const invitationsApi = {
  async list(tenantId: string, status?: string): Promise<InvitationWithStatus[]> {
    const params = status ? { status } : {}
    const response = await apiClient.get<InvitationWithStatus[]>(
      `/schools/${tenantId}/invitations`,
      { params }
    )
    return response.data
  },

  async create(tenantId: string, data: CreateInvitationData): Promise<Invitation> {
    const response = await apiClient.post<Invitation>(`/schools/${tenantId}/invitations`, data)
    return response.data
  },

  async createBulk(
    tenantId: string,
    emails: string[],
    groupId?: string | null
  ): Promise<BulkInvitationResponse> {
    const response = await apiClient.post<BulkInvitationResponse>(
      `/schools/${tenantId}/invitations/bulk`,
      { emails, group_id: groupId || null }
    )
    return response.data
  },

  async resend(tenantId: string, invitationId: string): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>(
      `/schools/${tenantId}/invitations/${invitationId}/resend`
    )
    return response.data
  },

  async revoke(tenantId: string, invitationId: string): Promise<MessageResponse> {
    const response = await apiClient.delete<MessageResponse>(
      `/schools/${tenantId}/invitations/${invitationId}`
    )
    return response.data
  },
}
