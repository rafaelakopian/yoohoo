import apiClient, { tenantUrl } from '@/api/client'
import type { Student, StudentCreate, StudentImportResponse, TeacherStudentAssignment } from '@/types/models'

interface ListResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

export const studentsApi = {
  async list(params?: {
    search?: string
    active?: boolean
    page?: number
    per_page?: number
  }): Promise<ListResponse<Student>> {
    const response = await apiClient.get<ListResponse<Student>>(tenantUrl('/students/'), { params })
    return response.data
  },

  async listMyStudents(params?: {
    search?: string
    page?: number
    per_page?: number
  }): Promise<ListResponse<Student>> {
    const response = await apiClient.get<ListResponse<Student>>(tenantUrl('/students/my-students'), { params })
    return response.data
  },

  async listUnassigned(params?: {
    page?: number
    per_page?: number
  }): Promise<ListResponse<Student>> {
    const response = await apiClient.get<ListResponse<Student>>(tenantUrl('/students/unassigned'), { params })
    return response.data
  },

  async create(data: StudentCreate): Promise<Student> {
    const response = await apiClient.post<Student>(tenantUrl('/students/'), data)
    return response.data
  },

  async get(id: string): Promise<Student> {
    const response = await apiClient.get<Student>(tenantUrl(`/students/${id}`))
    return response.data
  },

  async update(id: string, data: Partial<StudentCreate> & { is_active?: boolean }): Promise<Student> {
    const response = await apiClient.put<Student>(tenantUrl(`/students/${id}`), data)
    return response.data
  },

  async delete(id: string): Promise<Student> {
    const response = await apiClient.delete<Student>(tenantUrl(`/students/${id}`))
    return response.data
  },

  async import(file: File): Promise<StudentImportResponse> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await apiClient.post<StudentImportResponse>(tenantUrl('/students/import'), formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  // --- Teacher-Student Assignments ---

  async listTeachers(studentId: string): Promise<{ items: TeacherStudentAssignment[] }> {
    const response = await apiClient.get<{ items: TeacherStudentAssignment[] }>(tenantUrl(`/students/${studentId}/teachers`))
    return response.data
  },

  async assignTeacher(studentId: string, data: { user_id: string; notes?: string }): Promise<TeacherStudentAssignment> {
    const response = await apiClient.post<TeacherStudentAssignment>(tenantUrl(`/students/${studentId}/teachers`), data)
    return response.data
  },

  async unassignTeacher(studentId: string, teacherUserId: string): Promise<void> {
    await apiClient.delete(tenantUrl(`/students/${studentId}/teachers/${teacherUserId}`))
  },

  async transferStudent(studentId: string, data: { from_teacher_user_id: string; to_teacher_user_id: string }): Promise<TeacherStudentAssignment> {
    const response = await apiClient.post<TeacherStudentAssignment>(tenantUrl(`/students/${studentId}/transfer`), data)
    return response.data
  },

  async selfAssign(studentId: string): Promise<TeacherStudentAssignment> {
    const response = await apiClient.post<TeacherStudentAssignment>(tenantUrl(`/students/self-assign/${studentId}`))
    return response.data
  },
}
