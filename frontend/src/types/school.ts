export interface Tenant {
  id: string
  name: string
  slug: string
  is_active: boolean
  is_provisioned: boolean
  owner_id: string | null
  created_at: string
}

export interface TenantSettings {
  id: string
  tenant_id: string
  school_name: string | null
  school_address: string | null
  school_phone: string | null
  school_email: string | null
  timezone: string
  academic_year_start_month: number
  extra_settings: Record<string, unknown> | null
}

export interface Student {
  id: string
  first_name: string
  last_name: string | null
  email: string | null
  phone: string | null
  date_of_birth: string | null
  lesson_day: string | null
  lesson_duration: number | null
  lesson_time: string | null
  level: string | null
  notes: string | null
  guardian_name: string | null
  guardian_relationship: string | null
  guardian_phone: string | null
  guardian_phone_work: string | null
  guardian_email: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface StudentCreate {
  first_name: string
  last_name?: string | null
  email?: string | null
  phone?: string | null
  date_of_birth?: string | null
  lesson_day?: string | null
  lesson_duration?: number | null
  lesson_time?: string | null
  level?: string | null
  notes?: string | null
  guardian_name?: string | null
  guardian_relationship?: string | null
  guardian_phone?: string | null
  guardian_phone_work?: string | null
  guardian_email?: string | null
}

export interface StudentImportResponse {
  imported: number
  skipped: number
  errors: string[]
}

export type AttendanceStatus = 'present' | 'absent' | 'sick' | 'excused'

export interface AttendanceRecord {
  id: string
  student_id: string
  lesson_date: string
  status: AttendanceStatus
  recorded_by_user_id: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface AttendanceCreate {
  student_id: string
  lesson_date: string
  status: AttendanceStatus
  notes?: string | null
}

export interface AttendanceBulkCreate {
  lesson_date: string
  records: Array<{
    student_id: string
    status: AttendanceStatus
    notes?: string | null
  }>
}

export interface AttendanceBulkResponse {
  created: number
  updated: number
  errors: string[]
}

export type LessonStatus = 'scheduled' | 'completed' | 'cancelled' | 'rescheduled'
export type DayOfWeek = 1 | 2 | 3 | 4 | 5 | 6 | 7

export interface LessonSlot {
  id: string
  student_id: string
  day_of_week: DayOfWeek
  start_time: string
  duration_minutes: number
  location: string | null
  teacher_user_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface LessonInstance {
  id: string
  lesson_slot_id: string | null
  student_id: string
  lesson_date: string
  start_time: string
  duration_minutes: number
  status: LessonStatus
  teacher_user_id: string | null
  substitute_teacher_user_id: string | null
  substitution_reason: string | null
  cancellation_reason: string | null
  rescheduled_to_date: string | null
  rescheduled_to_time: string | null
  created_at: string
  updated_at: string
}

export interface Holiday {
  id: string
  name: string
  start_date: string
  end_date: string
  description: string | null
  is_recurring: boolean
  created_at: string
  updated_at: string
}

export interface CalendarDayEntry {
  id: string
  student_name: string
  lesson_date: string
  start_time: string
  duration_minutes: number
  status: LessonStatus
  teacher_user_id: string | null
  substitute_teacher_user_id: string | null
}

// --- Teacher-Student Assignment ---

export interface TeacherStudentAssignment {
  id: string
  user_id: string
  student_id: string
  assigned_by_user_id: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface CalendarWeekResponse {
  week_start: string
  week_end: string
  lessons: CalendarDayEntry[]
  holidays: Holiday[]
}

export interface GenerateLessonsResponse {
  generated: number
  skipped: number
  errors: string[]
}

export type NotificationType = 'lesson_reminder' | 'absence_alert' | 'schedule_change' | 'attendance_report'
export type NotificationStatus = 'pending' | 'sent' | 'failed' | 'skipped'

export interface NotificationPreference {
  id: string
  notification_type: NotificationType
  is_enabled: boolean
  send_to_guardian: boolean
  send_to_teacher: boolean
  send_to_admin: boolean
  extra_config: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface NotificationLog {
  id: string
  notification_type: NotificationType
  channel: string
  recipient_email: string
  recipient_name: string | null
  subject: string
  status: NotificationStatus
  error_message: string | null
  context_data: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface InAppNotification {
  id: string
  user_id: string
  title: string
  message: string
  notification_type: NotificationType
  is_read: boolean
  context_data: Record<string, unknown> | null
  created_at: string
}
