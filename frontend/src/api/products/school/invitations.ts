import apiClient, { tenantUrl } from '@/api/client'
import type { Invitation, MessageResponse } from '@/types/models'

export interface CreateInvitationData {
  email: string
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
  async list(status?: string): Promise<InvitationWithStatus[]> {
    const params = status ? { status } : {}
    const response = await apiClient.get<InvitationWithStatus[]>(
      tenantUrl('/access/invitations'),
      { params }
    )
    return response.data
  },

  async create(data: CreateInvitationData): Promise<Invitation> {
    const response = await apiClient.post<Invitation>(tenantUrl('/access/invitations'), data)
    return response.data
  },

  async createBulk(
    emails: string[],
    groupId?: string | null
  ): Promise<BulkInvitationResponse> {
    const response = await apiClient.post<BulkInvitationResponse>(
      tenantUrl('/access/invitations/bulk'),
      { emails, group_id: groupId || null }
    )
    return response.data
  },

  async resend(invitationId: string): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>(
      tenantUrl(`/access/invitations/${invitationId}/resend`)
    )
    return response.data
  },

  async revoke(invitationId: string): Promise<MessageResponse> {
    const response = await apiClient.delete<MessageResponse>(
      tenantUrl(`/access/invitations/${invitationId}`)
    )
    return response.data
  },
}
