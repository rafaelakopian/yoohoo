import apiClient from '../client'
import type {
  TokenResponse,
  User,
  RegisterResponse,
  MessageResponse,
  LoginResponse,
  ChangePasswordResponse,
  SessionInfo,
  InviteInfo,
  TwoFactorSetupResponse,
  TwoFactorBackupCodes,
} from '@/types/models'

export const authApi = {
  async register(data: { email: string; password: string; full_name: string }): Promise<RegisterResponse> {
    const response = await apiClient.post<RegisterResponse>('/auth/register', data)
    return response.data
  },

  async login(email: string, password: string): Promise<LoginResponse> {
    const response = await apiClient.post<LoginResponse>('/auth/login', { email, password })
    return response.data
  },

  async verifyEmail(token: string): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>('/auth/verify-email', { token })
    return response.data
  },

  async resendVerification(email: string): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>('/auth/resend-verification', { email })
    return response.data
  },

  async refresh(refreshToken: string): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    })
    return response.data
  },

  async logout(refreshToken: string): Promise<void> {
    await apiClient.post('/auth/logout', { refresh_token: refreshToken })
  },

  async me(): Promise<User> {
    const response = await apiClient.get<User>('/auth/me')
    return response.data
  },

  async updateProfile(data: { full_name?: string }): Promise<User> {
    const response = await apiClient.patch<User>('/auth/profile', data)
    return response.data
  },

  async requestEmailChange(newEmail: string, password: string): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>('/auth/request-email-change', {
      new_email: newEmail,
      password,
    })
    return response.data
  },

  async confirmEmailChange(token: string): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>('/auth/confirm-email-change', { token })
    return response.data
  },

  // --- Password ---
  async forgotPassword(email: string): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>('/auth/forgot-password', { email })
    return response.data
  },

  async resetPassword(token: string, newPassword: string): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>('/auth/reset-password', {
      token,
      new_password: newPassword,
    })
    return response.data
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<ChangePasswordResponse> {
    const response = await apiClient.post<ChangePasswordResponse>('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    return response.data
  },

  // --- Sessions ---
  async listSessions(): Promise<SessionInfo[]> {
    const response = await apiClient.get<SessionInfo[]>('/auth/sessions')
    return response.data
  },

  async revokeSession(sessionId: string): Promise<MessageResponse> {
    const response = await apiClient.delete<MessageResponse>(`/auth/sessions/${sessionId}`)
    return response.data
  },

  async logoutAll(): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>('/auth/logout-all')
    return response.data
  },

  // --- Invite ---
  async getInviteInfo(token: string): Promise<InviteInfo> {
    const response = await apiClient.get<InviteInfo>('/auth/invite-info', { params: { token } })
    return response.data
  },

  async acceptInvite(data: { token: string; password?: string; full_name?: string }): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>('/auth/accept-invite', data)
    return response.data
  },

  // --- 2FA ---
  async setup2FA(): Promise<TwoFactorSetupResponse> {
    const response = await apiClient.post<TwoFactorSetupResponse>('/auth/2fa/setup')
    return response.data
  },

  async verifySetup2FA(code: string): Promise<TwoFactorBackupCodes> {
    const response = await apiClient.post<TwoFactorBackupCodes>('/auth/2fa/verify-setup', { code })
    return response.data
  },

  async disable2FA(password: string): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>('/auth/2fa/disable', { password })
    return response.data
  },

  async regenerateBackupCodes(password: string): Promise<TwoFactorBackupCodes> {
    const response = await apiClient.post<TwoFactorBackupCodes>('/auth/2fa/regenerate-backup-codes', { password })
    return response.data
  },

  async deleteAccount(password: string): Promise<MessageResponse> {
    const response = await apiClient.post<MessageResponse>('/auth/delete-account', { password })
    return response.data
  },

  async verify2FA(twoFactorToken: string, code: string): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/2fa/verify', {
      two_factor_token: twoFactorToken,
      code,
    })
    return response.data
  },
}
