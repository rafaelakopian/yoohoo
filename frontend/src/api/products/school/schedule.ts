import apiClient, { tenantUrl } from '@/api/client'
import type {
  LessonSlot,
  LessonInstance,
  Holiday,
  CalendarWeekResponse,
  GenerateLessonsResponse,
} from '@/types/models'

interface ListResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

// --- Slots ---

export const slotApi = {
  async list(params?: Record<string, string | number | boolean>): Promise<ListResponse<LessonSlot>> {
    const response = await apiClient.get<ListResponse<LessonSlot>>(tenantUrl('/schedule/slots/'), { params })
    return response.data
  },

  async create(data: {
    student_id: string
    day_of_week: number
    start_time: string
    duration_minutes?: number
    location?: string
    teacher_user_id?: string
  }): Promise<LessonSlot> {
    const response = await apiClient.post<LessonSlot>(tenantUrl('/schedule/slots/'), data)
    return response.data
  },

  async get(id: string): Promise<LessonSlot> {
    const response = await apiClient.get<LessonSlot>(tenantUrl(`/schedule/slots/${id}`))
    return response.data
  },

  async update(id: string, data: Partial<LessonSlot>): Promise<LessonSlot> {
    const response = await apiClient.put<LessonSlot>(tenantUrl(`/schedule/slots/${id}`), data)
    return response.data
  },

  async delete(id: string): Promise<LessonSlot> {
    const response = await apiClient.delete<LessonSlot>(tenantUrl(`/schedule/slots/${id}`))
    return response.data
  },
}

// --- Lessons (Instances) ---

export const lessonApi = {
  async list(params?: Record<string, string | number>): Promise<ListResponse<LessonInstance>> {
    const response = await apiClient.get<ListResponse<LessonInstance>>(tenantUrl('/schedule/lessons/'), { params })
    return response.data
  },

  async create(data: {
    student_id: string
    lesson_date: string
    start_time: string
    duration_minutes?: number
    lesson_slot_id?: string
  }): Promise<LessonInstance> {
    const response = await apiClient.post<LessonInstance>(tenantUrl('/schedule/lessons/'), data)
    return response.data
  },

  async generate(start_date: string, end_date: string): Promise<GenerateLessonsResponse> {
    const response = await apiClient.post<GenerateLessonsResponse>(tenantUrl('/schedule/lessons/generate'), {
      start_date,
      end_date,
    })
    return response.data
  },

  async get(id: string): Promise<LessonInstance> {
    const response = await apiClient.get<LessonInstance>(tenantUrl(`/schedule/lessons/${id}`))
    return response.data
  },

  async update(id: string, data: Partial<LessonInstance>): Promise<LessonInstance> {
    const response = await apiClient.put<LessonInstance>(tenantUrl(`/schedule/lessons/${id}`), data)
    return response.data
  },

  async cancel(id: string, reason?: string): Promise<LessonInstance> {
    const params = reason ? { reason } : {}
    const response = await apiClient.post<LessonInstance>(tenantUrl(`/schedule/lessons/${id}/cancel`), null, { params })
    return response.data
  },

  async reschedule(id: string, data: { new_date: string; new_time: string; reason?: string }): Promise<LessonInstance> {
    const response = await apiClient.post<LessonInstance>(tenantUrl(`/schedule/lessons/${id}/reschedule`), data)
    return response.data
  },

  async assignSubstitute(id: string, data: { substitute_teacher_user_id: string; reason?: string }): Promise<LessonInstance> {
    const response = await apiClient.post<LessonInstance>(tenantUrl(`/schedule/lessons/${id}/substitute`), data)
    return response.data
  },
}

// --- Holidays ---

export const holidayApi = {
  async list(params?: Record<string, string | number>): Promise<ListResponse<Holiday>> {
    const response = await apiClient.get<ListResponse<Holiday>>(tenantUrl('/schedule/holidays/'), { params })
    return response.data
  },

  async create(data: {
    name: string
    start_date: string
    end_date: string
    description?: string
    is_recurring?: boolean
  }): Promise<Holiday> {
    const response = await apiClient.post<Holiday>(tenantUrl('/schedule/holidays/'), data)
    return response.data
  },

  async get(id: string): Promise<Holiday> {
    const response = await apiClient.get<Holiday>(tenantUrl(`/schedule/holidays/${id}`))
    return response.data
  },

  async update(id: string, data: Partial<Holiday>): Promise<Holiday> {
    const response = await apiClient.put<Holiday>(tenantUrl(`/schedule/holidays/${id}`), data)
    return response.data
  },

  async delete(id: string): Promise<Holiday> {
    const response = await apiClient.delete<Holiday>(tenantUrl(`/schedule/holidays/${id}`))
    return response.data
  },
}

// --- Calendar ---

export const calendarApi = {
  async getWeek(start: string): Promise<CalendarWeekResponse> {
    const response = await apiClient.get<CalendarWeekResponse>(tenantUrl('/schedule/calendar/week'), {
      params: { start },
    })
    return response.data
  },
}
