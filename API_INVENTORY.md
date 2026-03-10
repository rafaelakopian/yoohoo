# API Inventory — Yoohoo SaaS

> Gegenereerd: 2026-03-08
> Totaal: 178 routes (33 auth + 84 tenant-scoped + 82 platform + 2 webhooks + 7 infra)

---

## 1. AUTH (`/api/v1/auth`)

### 1.1 Core Auth

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| POST | `/auth/register` | `register` | Account aanmaken + verificatie-email via background task | `authApi.register()` → RegisterView | test_core | actief |
| POST | `/auth/verify-email` | `verify_email` | E-mailadres verifiëren met token | `authApi.verifyEmail()` → VerifyEmailView | test_core | actief |
| POST | `/auth/resend-verification` | `resend_verification` | Verificatie-email opnieuw versturen | `authApi.resendVerification()` → RegisterSuccessView | test_core | actief |
| POST | `/auth/login` | `login` | Inloggen → tokens of 2FA challenge (rate limited 10/300s) | `authStore.login()` → LoginView | test_core | actief |
| POST | `/auth/refresh` | `refresh` | Nieuw access token via refresh token (session_id binding) | `authApi.refresh()` → auth middleware | test_core | actief |
| POST | `/auth/logout` | `logout` | Refresh token revoking, sessie beëindigen (204) | `authStore.logout()` | test_core | actief |
| POST | `/auth/verify-login-session` | `verify_login_session` | Tijdelijke login sessie verifiëren (magic link) | `authApi.verifyLoginSession()` → VerifySessionView | test_core | actief |
| GET | `/auth/me` | `me` | Huidige user + memberships, groepen, permissies, 2FA status | `authStore.fetchUser()` | test_core | actief |
| PATCH | `/auth/profile` | `update_profile` | full_name of phone_number bijwerken + audit log | `authApi.updateProfile()` → AccountSettingsView | test_core | actief |
| POST | `/auth/request-email-change` | `request_email_change` | Email wijziging aanvragen, token naar nieuw adres (3/3600s) | `authApi.requestEmailChange()` → AccountSettingsView | test_core | actief |
| POST | `/auth/confirm-email-change` | `confirm_email_change` | Email wijziging bevestigen met token (10/3600s) | `authApi.confirmEmailChange()` → ConfirmEmailChangeView | test_core | actief |
| POST | `/auth/delete-account` | `delete_account` | Account soft-delete (vereist wachtwoord, 3/3600s) | `authApi.deleteAccount()` → AccountSettingsView | test_account_archive | actief |

### 1.2 Password

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| POST | `/auth/forgot-password` | `forgot_password` | Wachtwoord reset token aanvragen (3/3600s, anti-enumeratie) | `authApi.forgotPassword()` → ForgotPasswordView | test_core | actief |
| POST | `/auth/reset-password` | `reset_password` | Wachtwoord resetten met token (5/3600s) | `authApi.resetPassword()` → ResetPasswordView | test_core | actief |
| POST | `/auth/change-password` | `change_password` | Wachtwoord wijzigen (authenticated, revoket andere sessies) | `authApi.changePassword()` → AccountSettingsView | test_core | actief |

### 1.3 Sessions

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/auth/sessions` | `list_sessions` | Actieve sessies met device info (IP, User-Agent) | `authApi.listSessions()` → AccountSettingsView | test_auth_enhancements | actief |
| DELETE | `/auth/sessions/{session_id}` | `revoke_session` | Specifieke sessie revoking | `authApi.revokeSession()` → AccountSettingsView | test_auth_enhancements | actief |
| POST | `/auth/logout-all` | `logout_all` | Alle sessies revoking behalve huidige | `authApi.logoutAll()` → AccountSettingsView | test_auth_enhancements | actief |

### 1.4 2FA/TOTP

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| POST | `/auth/2fa/setup` | `setup_2fa` | TOTP secret + QR code genereren (5/3600s) | `authApi.setup2FA()` → AccountSettingsView | test_auth_enhancements | actief |
| POST | `/auth/2fa/verify-setup` | `verify_setup` | TOTP code verifiëren en 2FA activeren (10/300s) | `authApi.verifySetup2FA()` → AccountSettingsView | test_auth_enhancements | actief |
| POST | `/auth/2fa/disable` | `disable_2fa` | 2FA uitschakelen (vereist wachtwoord, 5/3600s) | `authApi.disable2FA()` → AccountSettingsView | test_auth_enhancements | actief |
| POST | `/auth/2fa/verify` | `verify_2fa` | 2FA code verifiëren bij login (TOTP/email/SMS, 10/300s) | `authStore.verify2FA()` → LoginView | test_auth_enhancements | actief |
| POST | `/auth/2fa/send-email-code` | `send_email_code` | 2FA recovery code via email (3/180s) | `authApi.send2FAEmailCode()` → LoginView | test_auth_enhancements | actief |
| POST | `/auth/2fa/send-sms-code` | `send_sms_code` | 2FA recovery code via SMS (3/180s) | `authApi.send2FASmsCode()` → LoginView | test_auth_enhancements | actief |
| POST | `/auth/2fa/phone/request-verify` | `request_phone_verification` | SMS code voor telefoon verificatie (3/300s) | `authApi.requestPhoneVerification()` → AccountSettingsView | test_auth_enhancements | actief |
| POST | `/auth/2fa/phone/verify` | `verify_phone` | Telefoonnummer verifiëren met SMS code (10/300s) | `authApi.verifyPhone()` → AccountSettingsView | test_auth_enhancements | actief |

### 1.5 Invitations (Public)

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/auth/invite-info?token=...` | `get_invite_info` | Uitnodigingsdetails ophalen vóór acceptatie (10/300s) | `authApi.getInviteInfo()` → AcceptInviteView | test_platform_invite | actief |
| POST | `/auth/accept-invite` | `accept_invite` | Uitnodiging accepteren: account aanmaken of bestaand koppelen (5/3600s) | `authApi.acceptInvite()` → AcceptInviteView | test_platform_invite | actief |

---

## 2. TENANT-SCOPED (`/api/v1/org/{slug}`)

### 2.1 Students

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/org/{slug}/students/` | `list_students` | Leerlingen ophalen met DataScope filtering (all/assigned/own) | `studentsApi.list()` → StudentsView | test_student | actief |
| POST | `/org/{slug}/students/` | `create_student` | Nieuwe leerling aanmaken | `studentsApi.create()` → StudentsView | test_student | actief |
| POST | `/org/{slug}/students/import` | `import_students` | Bulk import uit Excel (MIME/size/magic byte validatie) | `studentsApi.import()` → StudentsView | test_file_upload_security | actief |
| GET | `/org/{slug}/students/my-children` | `list_my_children` | Kinderen van huidige ouder ophalen | `studentsApi.listMyStudents()` → StudentsView | test_parent_student | actief |
| GET | `/org/{slug}/students/my-students` | `list_my_students` | Toegewezen leerlingen van huidige docent | `studentsApi.listMyStudents()` → StudentsView | test_teacher_assignment | actief |
| GET | `/org/{slug}/students/unassigned` | `list_unassigned_students` | Leerlingen zonder docent-toewijzing | `studentsApi.listUnassigned()` → StudentsView | test_teacher_assignment | actief |
| POST | `/org/{slug}/students/self-assign/{student_id}` | `self_assign_student` | Docent wijst zichzelf toe aan leerling | `studentsApi.selfAssign()` → StudentsView | test_teacher_assignment | actief |
| GET | `/org/{slug}/students/{student_id}` | `get_student` | Leerling details met DataScope check | `studentsApi.get()` → StudentsView | test_student | actief |
| PUT | `/org/{slug}/students/{student_id}` | `update_student` | Leerling bijwerken (partial update) | `studentsApi.update()` → StudentsView | test_student | actief |
| DELETE | `/org/{slug}/students/{student_id}` | `delete_student` | Leerling deactiveren (soft delete) | `studentsApi.delete()` → StudentsView | test_student | actief |
| GET | `/org/{slug}/students/{student_id}/parents` | `list_student_parents` | Ouder-koppelingen van leerling | frontend (admin) | test_parent_student | actief |
| POST | `/org/{slug}/students/{student_id}/parents` | `link_parent_to_student` | Ouder koppelen aan leerling | frontend (admin) | test_parent_student | actief |
| DELETE | `/org/{slug}/students/{student_id}/parents/{user_id}` | `unlink_parent_from_student` | Ouder-koppeling verwijderen | frontend (admin) | test_parent_student | actief |
| GET | `/org/{slug}/students/{student_id}/teachers` | `list_student_teachers` | Docent-koppelingen van leerling | `studentsApi.listTeachers()` → StudentsView | test_teacher_assignment | actief |
| POST | `/org/{slug}/students/{student_id}/teachers` | `assign_teacher_to_student` | Docent toewijzen aan leerling | `studentsApi.assignTeacher()` → StudentsView | test_teacher_assignment | actief |
| DELETE | `/org/{slug}/students/{student_id}/teachers/{teacher_user_id}` | `unassign_teacher_from_student` | Docent-koppeling verwijderen | `studentsApi.unassignTeacher()` → StudentsView | test_teacher_assignment | actief |
| POST | `/org/{slug}/students/{student_id}/transfer` | `transfer_student_between_teachers` | Leerling transfereren tussen docenten | `studentsApi.transferStudent()` → StudentsView | test_teacher_assignment | actief |

### 2.2 Attendance

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/org/{slug}/attendance/` | `list_attendance` | Aanwezigheidsrecords met DataScope filtering | `attendanceApi.list()` → AttendanceView | test_attendance | actief |
| POST | `/org/{slug}/attendance/` | `create_attendance` | Enkel aanwezigheidsrecord aanmaken | `attendanceApi.create()` → AttendanceView | test_attendance | actief |
| POST | `/org/{slug}/attendance/bulk` | `bulk_create_attendance` | Meerdere records in één keer | `attendanceApi.bulkCreate()` → AttendanceView | test_attendance | actief |
| GET | `/org/{slug}/attendance/{record_id}` | `get_attendance` | Enkel record ophalen met DataScope check | `attendanceApi.get()` → AttendanceView | test_attendance | actief |
| PUT | `/org/{slug}/attendance/{record_id}` | `update_attendance` | Record bijwerken (partial update) | `attendanceApi.update()` → AttendanceView | test_attendance | actief |
| DELETE | `/org/{slug}/attendance/{record_id}` | `delete_attendance` | Record verwijderen (hard delete) | `attendanceApi.delete()` → AttendanceView | test_attendance | actief |

### 2.3 Schedule

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/org/{slug}/schedule/slots/` | `list_slots` | Lesslots ophalen met optionele DataScope filtering | `slotApi.list()` → ScheduleView | test_schedule | actief |
| POST | `/org/{slug}/schedule/slots/` | `create_slot` | Nieuw lesslot aanmaken | `slotApi.create()` → ScheduleView | test_schedule | actief |
| GET | `/org/{slug}/schedule/slots/{slot_id}` | `get_slot` | Enkel lesslot ophalen | `slotApi.get()` → ScheduleView | test_schedule | actief |
| PUT | `/org/{slug}/schedule/slots/{slot_id}` | `update_slot` | Lesslot bijwerken | `slotApi.update()` → ScheduleView | test_schedule | actief |
| DELETE | `/org/{slug}/schedule/slots/{slot_id}` | `delete_slot` | Lesslot verwijderen | `slotApi.delete()` → ScheduleView | test_schedule | actief |
| GET | `/org/{slug}/schedule/lessons/` | `list_lessons` | Lesinstanties met datum/status filtering | `lessonApi.list()` → ScheduleView | test_schedule | actief |
| POST | `/org/{slug}/schedule/lessons/` | `create_lesson` | Enkele lesinstantie aanmaken | `lessonApi.create()` → ScheduleView | test_schedule | actief |
| POST | `/org/{slug}/schedule/lessons/generate` | `generate_lessons` | Meerdere lesinstanties genereren uit datumreeks | `lessonApi.generate()` → ScheduleView | test_schedule | actief |
| GET | `/org/{slug}/schedule/lessons/{instance_id}` | `get_lesson` | Enkele lesinstantie ophalen | `lessonApi.get()` → ScheduleView | test_schedule | actief |
| PUT | `/org/{slug}/schedule/lessons/{instance_id}` | `update_lesson` | Lesinstantie bijwerken | `lessonApi.update()` → ScheduleView | test_schedule | actief |
| POST | `/org/{slug}/schedule/lessons/{instance_id}/cancel` | `cancel_lesson` | Les annuleren met optionele reden | `lessonApi.cancel()` → ScheduleView | test_schedule | actief |
| POST | `/org/{slug}/schedule/lessons/{instance_id}/reschedule` | `reschedule_lesson` | Les verplaatsen naar nieuwe datum/tijd | `lessonApi.reschedule()` → ScheduleView | test_schedule | actief |
| POST | `/org/{slug}/schedule/lessons/{instance_id}/substitute` | `assign_substitute` | Vervangend docent toewijzen aan les | `lessonApi.assignSubstitute()` → ScheduleView | test_substitution | actief |
| GET | `/org/{slug}/schedule/holidays/` | `list_holidays` | Vakanties/vrije dagen ophalen | `holidayApi.list()` → HolidaysView | test_schedule | actief |
| POST | `/org/{slug}/schedule/holidays/` | `create_holiday` | Vakantieperiode aanmaken | `holidayApi.create()` → HolidaysView | test_schedule | actief |
| GET | `/org/{slug}/schedule/holidays/{holiday_id}` | `get_holiday` | Enkele vakantie ophalen | `holidayApi.get()` → HolidaysView | test_schedule | actief |
| PUT | `/org/{slug}/schedule/holidays/{holiday_id}` | `update_holiday` | Vakantie bijwerken | `holidayApi.update()` → HolidaysView | test_schedule | actief |
| DELETE | `/org/{slug}/schedule/holidays/{holiday_id}` | `delete_holiday` | Vakantie verwijderen | `holidayApi.delete()` → HolidaysView | test_schedule | actief |
| GET | `/org/{slug}/schedule/calendar/week` | `get_calendar_week` | Weekkalender met lessen voor datumreeks | `calendarApi.getWeek()` → ScheduleView | test_schedule | actief |

### 2.4 Notifications (School)

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/org/{slug}/notifications/preferences/` | `list_preferences` | School notificatie-voorkeuren ophalen (tenant DB) | `preferencesApi.list()` → NotificationSettingsView | test_notification | actief |
| POST | `/org/{slug}/notifications/preferences/initialize` | `initialize_preferences` | Default voorkeuren initialiseren voor alle types | `preferencesApi.initialize()` → store | test_notification | actief |
| PUT | `/org/{slug}/notifications/preferences/{notification_type}` | `update_preference` | Voorkeur voor specifiek type bijwerken | `preferencesApi.update()` → NotificationSettingsView | test_notification | actief |
| GET | `/org/{slug}/notifications/logs/` | `list_logs` | Notificatie-logs met DataScope filtering | `logsApi.list()` → NotificationSettingsView | test_notification | actief |
| GET | `/org/{slug}/notifications/logs/{log_id}` | `get_log` | Enkel notificatie-log ophalen | geen frontend caller | test_notification | actief |
| GET | `/org/{slug}/notifications/in-app/` | `list_in_app` | In-app notificaties voor huidige user | `inAppApi.list()` → NotificationBell | test_notification | actief |
| GET | `/org/{slug}/notifications/in-app/unread-count` | `get_unread_count` | Ongelezen notificatie-telling | `inAppApi.getUnreadCount()` → NotificationBell | test_notification | actief |
| PUT | `/org/{slug}/notifications/in-app/{notif_id}/read` | `mark_read` | Notificatie als gelezen markeren | `inAppApi.markRead()` → NotificationBell | test_notification | actief |
| PUT | `/org/{slug}/notifications/in-app/read-all` | `mark_all_read` | Alle notificaties als gelezen markeren | `inAppApi.markAllRead()` → NotificationBell | test_notification | actief |

### 2.5 Tuition Billing

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/org/{slug}/tuition/plans` | `list_plans` | Lesgeldplannen ophalen | `tuitionBillingApi.listPlans()` → TuitionPlansView | test_tuition | actief |
| POST | `/org/{slug}/tuition/plans` | `create_plan` | Nieuw lesgeldplan aanmaken | `tuitionBillingApi.createPlan()` → TuitionPlansView | test_tuition | actief |
| PUT | `/org/{slug}/tuition/plans/{plan_id}` | `update_plan` | Lesgeldplan bijwerken | `tuitionBillingApi.updatePlan()` → TuitionPlansView | test_tuition | actief |
| DELETE | `/org/{slug}/tuition/plans/{plan_id}` | `deactivate_plan` | Lesgeldplan deactiveren (soft delete) | `tuitionBillingApi.deactivatePlan()` → TuitionPlansView | test_tuition | actief |
| GET | `/org/{slug}/tuition/student-billing` | `list_student_billing` | Leerling-facturatieconfiguraties ophalen | `tuitionBillingApi.listStudentBilling()` → StudentBillingView | test_tuition | actief |
| GET | `/org/{slug}/tuition/student-billing/{student_id}` | `get_student_billing` | Facturatieconfig voor enkele leerling | `tuitionBillingApi.getStudentBilling()` → StudentBillingView | test_tuition | actief |
| POST | `/org/{slug}/tuition/student-billing` | `create_student_billing` | Lesgeldplan aan leerling toewijzen | `tuitionBillingApi.createStudentBilling()` → StudentBillingView | test_tuition | actief |
| PUT | `/org/{slug}/tuition/student-billing/{billing_id}` | `update_student_billing` | Leerling-facturatieconfig bijwerken | `tuitionBillingApi.updateStudentBilling()` → StudentBillingView | test_tuition | actief |
| GET | `/org/{slug}/tuition/invoices` | `list_invoices` | Lesgeld-facturen ophalen met filtering | `tuitionBillingApi.listInvoices()` → InvoicesView | test_tuition | actief |
| POST | `/org/{slug}/tuition/invoices/generate` | `generate_invoices` | Facturen genereren voor facturatieperiode | `tuitionBillingApi.generateInvoices()` → InvoicesView | test_tuition | actief |
| GET | `/org/{slug}/tuition/invoices/{invoice_id}` | `get_invoice` | Enkele factuur ophalen | `tuitionBillingApi.getInvoice()` → InvoicesView | test_tuition | actief |
| POST | `/org/{slug}/tuition/invoices/{invoice_id}/send` | `send_invoice` | Factuur per email versturen | `tuitionBillingApi.sendInvoice()` → InvoicesView | test_tuition | actief |

### 2.6 Permissions (Tenant-scoped)

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/org/{slug}/permissions/groups` | `list_groups` | Permissiegroepen voor tenant ophalen | `permissionsApi.listGroups()` → PermissionsView | test_permissions | actief |
| POST | `/org/{slug}/permissions/groups` | `create_group` | Nieuwe permissiegroep aanmaken | `permissionsApi.createGroup()` → PermissionsView | test_permissions | actief |
| GET | `/org/{slug}/permissions/groups/{group_id}` | `get_group` | Groep details + permissies | `permissionsApi.getGroup()` → PermissionDetailView | test_permissions | actief |
| PUT | `/org/{slug}/permissions/groups/{group_id}` | `update_group` | Groep naam/beschrijving/permissies bijwerken | `permissionsApi.updateGroup()` → PermissionDetailView | test_permissions | actief |
| DELETE | `/org/{slug}/permissions/groups/{group_id}` | `delete_group` | Groep verwijderen (niet default groepen) | `permissionsApi.deleteGroup()` → PermissionsView | test_permissions | actief |
| GET | `/org/{slug}/permissions/groups/{group_id}/users` | `list_group_users` | Users in groep ophalen | `permissionsApi.listGroupUsers()` → PermissionDetailView | test_permissions | actief |
| POST | `/org/{slug}/permissions/groups/{group_id}/users` | `assign_user_to_group` | User aan groep toewijzen | `permissionsApi.assignUser()` → PermissionDetailView | test_permissions | actief |
| DELETE | `/org/{slug}/permissions/groups/{group_id}/users/{user_id}` | `remove_user_from_group` | User uit groep verwijderen | `permissionsApi.removeUser()` → PermissionDetailView | test_permissions | actief |
| GET | `/org/{slug}/permissions/my-permissions` | `get_my_permissions` | Effectieve permissies huidige user in tenant | `permissionsApi.getMyPermissions()` → AppSidebar | test_permissions | actief |

### 2.7 Members

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/org/{slug}/members` | `list_members` | Org-leden met groep/zoek filtering + email privacy | `membersApi.list()` → PermissionDetailView, `fetchTeachers()` → tenant store | test_members | actief |

### 2.8 Collaborations

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/org/{slug}/collaborations/` | `list_collaborators` | Externe samenwerkingspartners ophalen | `collaborationsApi.list()` → CollaborationsView | test_collaboration | actief |
| POST | `/org/{slug}/collaborations/invite` | `invite_collaborator` | Externe partner uitnodigen | `collaborationsApi.invite()` → CollaborationsView | test_collaboration | actief |
| PUT | `/org/{slug}/collaborations/{membership_id}/toggle` | `toggle_collaborator` | Partner activeren/deactiveren | `collaborationsApi.toggle()` → CollaborationsView | test_collaboration | actief |

### 2.9 Features

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/org/{slug}/features` | `list_features` | Alle features met toegangsstatus voor tenant | `featuresApi.listFeatures()` → UpgradeView | test_feature_gating | actief |
| POST | `/org/{slug}/features/{feature_name}/trial` | `start_trial` | Feature trial starten voor tenant | `featuresApi.startTrial()` → UpgradeView | test_feature_gating | actief |

### 2.10 Platform Notification Preferences (Tenant-scoped)

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/org/{slug}/notification-preferences` | `get_preferences` | Platform notificatie-voorkeuren voor tenant (central DB) | `platformNotifPreferencesApi.list()` — **NIET AANGEROEPEN** | test_platform_notifications | **ongebruikt frontend** |
| PUT | `/org/{slug}/notification-preferences/{notification_type}` | `update_preference` | Platform notificatie-voorkeur bijwerken | `platformNotifPreferencesApi.update()` — **NIET AANGEROEPEN** | test_platform_notifications | **ongebruikt frontend** |

---

## 3. PLATFORM (`/api/v1/platform`)

### 3.1 Dashboard

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/platform/dashboard` | `get_platform_stats` | Platform statistieken (tenant/user/groep counts) | `admin.ts:getStats()` → AdminDashboardView | test_admin | actief |

### 3.2 Org Management

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS | OPMERKING |
|--------|-----|---------|-------------|----------|-------|--------|-----------|
| GET | `/platform/orgs/` | `list_tenants` | Organisaties ophalen (user-specifiek of alle voor admin) | `orgs.ts:list()` → WelcomeView | test_tenant | actief | |
| GET | `/platform/orgs/overview` | `list_tenants` | Organisaties met metrics (admin overzicht) | `admin.ts:getTenants()` → AdminTenantsView | test_admin | actief | **OVERLAP**: zelfde handler-naam als `/platform/orgs/`, verschillende implementatie |
| POST | `/platform/orgs/` | `create_tenant` | Nieuwe organisatie aanmaken (superadmin) | `orgs.ts:create()` → AdminTenantsView | test_tenant | actief | |
| GET | `/platform/orgs/check-slug` | `check_slug` | Slug beschikbaarheid controleren | `orgs.ts:checkSlug()` → CreateOrgWizardView | test_tenant | actief | |
| POST | `/platform/orgs/self-service` | `self_service_create` | Self-service org aanmaken met plan | `orgs.ts:selfServiceCreate()` → CreateOrgWizardView | test_tenant | actief | |
| GET | `/platform/orgs/{tenant_id}` | `get_tenant` | Organisatie details (membership check) | `orgs.ts:get()` → tenant store | test_tenant | actief | |
| POST | `/platform/orgs/{tenant_id}/provision` | `provision_tenant` | Tenant database provisioning | `orgs.ts:provision()` → AdminTenantsView | test_tenant | actief | |
| DELETE | `/platform/orgs/{tenant_id}` | `delete_tenant` | Organisatie verwijderen (superadmin + wachtwoord) | `orgs.ts:delete()` → AdminTenantsView | test_tenant | actief | |
| GET | `/platform/orgs/{tenant_id}/settings` | `get_settings` | Organisatie-instellingen ophalen | `orgs.ts:getSettings()` | test_tenant | actief | |
| PUT | `/platform/orgs/{tenant_id}/settings` | `update_settings` | Organisatie-instellingen bijwerken | `orgs.ts:updateSettings()` | test_tenant | actief | |
| GET | `/platform/orgs/{tenant_id}/detail` | `get_tenant_detail` | Uitgebreide tenant info met metrics | `admin.ts:getTenantDetail()` → Tenant360View | test_admin | actief | |

### 3.3 Org Memberships (Platform Admin)

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| POST | `/platform/orgs/{tenant_id}/memberships` | `add_membership` | User aan org toevoegen met optionele groep | `admin.ts:addMembership()` → Tenant360View | test_admin | actief |
| DELETE | `/platform/orgs/{tenant_id}/memberships/{user_id}` | `remove_membership` | User uit org verwijderen | `admin.ts:removeMembership()` → Tenant360View | test_admin | actief |
| PUT | `/platform/orgs/{tenant_id}/owner` | `transfer_ownership` | Org eigendom overdragen | `admin.ts:transferOwnership()` → Tenant360View | test_admin | actief |

### 3.4 Org Invitations (Platform Admin)

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| POST | `/platform/orgs/{tenant_id}/invitations` | `create_invitation` | Uitnodiging aanmaken voor email | `invitationsApi.create()` → InvitationsView | test_platform_invite | actief |
| GET | `/platform/orgs/{tenant_id}/invitations` | `list_invitations` | Uitnodigingen ophalen met status filter | `invitationsApi.list()` → InvitationsView | test_user_management | actief |
| POST | `/platform/orgs/{tenant_id}/invitations/bulk` | `create_bulk_invitations` | Meerdere uitnodigingen in één keer | `invitationsApi.createBulk()` → InvitationsView | test_user_management | actief |
| POST | `/platform/orgs/{tenant_id}/invitations/{invitation_id}/resend` | `resend_invitation` | Uitnodiging opnieuw versturen | `invitationsApi.resend()` → InvitationsView | test_user_management | actief |
| DELETE | `/platform/orgs/{tenant_id}/invitations/{invitation_id}` | `revoke_invitation` | Uitnodiging revoking | `invitationsApi.revoke()` → InvitationsView | test_user_management | actief |

### 3.5 Org Permission Groups (Platform Admin)

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS | OPMERKING |
|--------|-----|---------|-------------|----------|-------|--------|-----------|
| GET | `/platform/orgs/{tenant_id}/groups` | `admin_list_groups` | Permissiegroepen van org ophalen (admin scope) | `admin.ts:getTenantGroups()` → AdminTenantGroupsView | test_admin | actief | Spiegelt `/org/{slug}/permissions/groups` maar via UUID + platform permissie |
| POST | `/platform/orgs/{tenant_id}/groups` | `admin_create_group` | Groep aanmaken in org | `admin.ts:createTenantGroup()` → AdminTenantGroupsView | test_admin | actief | |
| GET | `/platform/orgs/{tenant_id}/groups/{group_id}` | `admin_get_group` | Groep details ophalen | geen frontend caller | test_admin | **ongebruikt frontend** | |
| PUT | `/platform/orgs/{tenant_id}/groups/{group_id}` | `admin_update_group` | Groep bijwerken | `admin.ts:updateTenantGroup()` → AdminTenantGroupDetailView | test_admin | actief | |
| DELETE | `/platform/orgs/{tenant_id}/groups/{group_id}` | `admin_delete_group` | Groep verwijderen (niet default) | `admin.ts:deleteTenantGroup()` → AdminTenantGroupsView | test_admin | actief | |
| GET | `/platform/orgs/{tenant_id}/groups/{group_id}/users` | `admin_list_group_users` | Users in groep ophalen | `admin.ts:getTenantGroupUsers()` → AdminTenantGroupDetailView | test_admin | actief | |
| POST | `/platform/orgs/{tenant_id}/groups/{group_id}/users` | `admin_assign_user_to_group` | User aan groep toewijzen | `admin.ts:assignUserToTenantGroup()` → AdminTenantGroupDetailView | test_admin | actief | |
| DELETE | `/platform/orgs/{tenant_id}/groups/{group_id}/users/{user_id}` | `admin_remove_user_from_group` | User uit groep verwijderen | `admin.ts:removeUserFromTenantGroup()` → AdminTenantGroupDetailView | test_admin | actief | |

### 3.6 Access: Users

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/platform/access/users` | `list_platform_users` | Platform users ophalen (superadmin + platform groepen) | `admin.ts:getPlatformUsers()` → PlatformUsersView | test_admin | actief |
| GET | `/platform/access/users/search` | `search_users` | Users zoeken op email/naam voor groep-toewijzing | `admin.ts:searchUsers()` → AdminPlatformGroupDetailView | test_admin | actief |
| POST | `/platform/access/users/invite` | `invite_platform_user` | Platform user uitnodigen (5/uur rate limit) | `admin.ts:invitePlatformUser()` → PlatformUsersView | test_platform_invite | actief |
| PUT | `/platform/access/users/{user_id}/superadmin` | `toggle_superadmin` | Superadmin status togglen | `admin.ts:toggleSuperAdmin()` → PlatformUsersView | test_admin | actief |
| POST | `/platform/access/users/{user_id}/reactivate` | `reactivate_user` | Gearchiveerd account reactiveren | geen frontend caller | test_account_archive | **ongebruikt frontend** |

### 3.7 Access: Platform Groups

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/platform/access/groups` | `list_platform_groups` | Platform-brede permissiegroepen ophalen | `admin.ts:getPlatformGroups()` → PlatformUsersView | test_admin | actief |
| POST | `/platform/access/groups` | `create_platform_group` | Platform permissiegroep aanmaken | `admin.ts:createPlatformGroup()` | test_admin | actief |
| GET | `/platform/access/groups/{group_id}` | `get_platform_group` | Platform groep details ophalen | geen frontend caller | test_admin | **ongebruikt frontend** |
| PUT | `/platform/access/groups/{group_id}` | `update_platform_group` | Platform groep bijwerken | `admin.ts:updatePlatformGroup()` → AdminPlatformGroupDetailView | test_admin | actief |
| DELETE | `/platform/access/groups/{group_id}` | `delete_platform_group` | Platform groep verwijderen | `admin.ts:deletePlatformGroup()` | test_admin | actief |
| GET | `/platform/access/groups/{group_id}/users` | `list_platform_group_users` | Users in platform groep | `admin.ts:getPlatformGroupUsers()` → AdminPlatformGroupDetailView | test_admin | actief |
| POST | `/platform/access/groups/{group_id}/users` | `assign_user_to_platform_group` | User aan platform groep toewijzen | `admin.ts:assignUserToPlatformGroup()` → AdminPlatformGroupDetailView | test_admin | actief |
| DELETE | `/platform/access/groups/{group_id}/users/{user_id}` | `remove_user_from_platform_group` | User uit platform groep verwijderen | `admin.ts:removeUserFromPlatformGroup()` → AdminPlatformGroupDetailView | test_admin | actief |

### 3.8 Access: Permissions Registry

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/platform/access/permissions/registry` | `get_registry` | Alle permissie-modules + codenames (code-driven singleton) | `permissionsApi.getRegistry()` → PermissionDetailView | test_permissions | actief |

### 3.9 Audit Logs

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS | OPMERKING |
|--------|-----|---------|-------------|----------|-------|--------|-----------|
| GET | `/platform/audit-logs` | `list_audit_logs` | Audit logs met paginatie + filters (user_id, action, date) | `admin.ts:getAuditLogs()` → AdminAuditLogsView | test_admin | actief | 70% operationeel, 30% security — past beter onder `/platform/operations/` |

### 3.10 Operations

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/platform/operations/dashboard` | `get_operations_dashboard` | Tenant health dashboard met metrics | `operations.ts:getOperationsDashboard()` → AdminDashboardView | test_operations | actief |
| GET | `/platform/operations/tenants/{tenant_id}` | `get_tenant_360` | 360° tenant view (leden, metrics, events) | `operations.ts:getTenant360()` → Tenant360View | test_operations | actief |
| GET | `/platform/operations/tenants/{tenant_id}/events` | `get_tenant_events` | Audit events voor tenant | `operations.ts:getTenantEvents()` → Tenant360View | test_operations | actief |
| GET | `/platform/operations/tenants/{tenant_id}/timeline` | `get_tenant_timeline` | Tenant activiteiten-tijdlijn met filters | `operations.ts:getTenantTimeline()` → Tenant360View | test_timeline | actief |
| GET | `/platform/operations/onboarding` | `get_onboarding_overview` | Onboarding voortgang alle tenants | `operations.ts:getOnboardingOverview()` → OnboardingView | test_operations | actief |
| GET | `/platform/operations/tenants/{tenant_id}/notes` | `get_tenant_notes` | Support notes voor tenant | `operations.ts:getTenantNotes()` → Tenant360View | test_support_notes | actief |
| POST | `/platform/operations/tenants/{tenant_id}/notes` | `create_tenant_note` | Support note aanmaken voor tenant | `operations.ts:createTenantNote()` → Tenant360View | test_support_notes | actief |
| GET | `/platform/operations/users/{user_id}/notes` | `get_user_notes` | Support notes voor user | `operations.ts:getUserNotes()` → Tenant360View | test_support_notes | actief |
| POST | `/platform/operations/users/{user_id}/notes` | `create_user_note` | Support note aanmaken voor user | `operations.ts:createUserNote()` → Tenant360View | test_support_notes | actief |
| PUT | `/platform/operations/notes/{note_id}` | `update_note` | Support note bijwerken | `operations.ts:updateNote()` → Tenant360View | test_support_notes | actief |
| DELETE | `/platform/operations/notes/{note_id}` | `delete_note` | Support note verwijderen | `operations.ts:deleteNote()` → Tenant360View | test_support_notes | actief |
| PATCH | `/platform/operations/notes/{note_id}/pin` | `toggle_pin_note` | Support note pinnen/lospinnen | `operations.ts:togglePinNote()` → Tenant360View | test_support_notes | actief |
| POST | `/platform/operations/users/{user_id}/force-password-reset` | `force_password_reset` | Geforceerde wachtwoord reset voor user | `operations.ts:forcePasswordReset()` → Tenant360View | test_quick_actions | actief |
| POST | `/platform/operations/users/{user_id}/toggle-active` | `toggle_user_active` | User activeren/deactiveren (vereist wachtwoord) | `operations.ts:toggleUserActive()` → Tenant360View | test_quick_actions | actief |
| POST | `/platform/operations/users/{user_id}/resend-verification` | `resend_verification` | Verificatie-email opnieuw versturen (admin) | `operations.ts:resendVerificationEmail()` → Tenant360View | test_quick_actions | actief |
| POST | `/platform/operations/users/{user_id}/revoke-sessions` | `revoke_user_sessions` | Alle sessies van user revoking | `operations.ts:revokeUserSessions()` → Tenant360View | test_quick_actions | actief |
| POST | `/platform/operations/users/{user_id}/disable-2fa` | `disable_user_2fa` | 2FA uitschakelen voor user (vereist wachtwoord) | `operations.ts:disableUser2FA()` → Tenant360View | test_quick_actions | actief |
| POST | `/platform/operations/impersonate` | `impersonate_user` | User impersonation voor debugging | `operations.ts:impersonateUser()` → Tenant360View | test_impersonate | actief |
| GET | `/platform/operations/jobs` | `get_job_monitor` | Job queue status (arq) | `operations.ts:getJobMonitor()` → JobMonitorView | test_job_monitor | actief |

### 3.11 Billing (Platform)

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/platform/billing/plans` | `list_plans` | Platform billing plannen ophalen | `billing.ts:listPlans()` → PlanManagerView | test_billing | actief |
| POST | `/platform/billing/plans` | `create_plan` | Nieuw platform plan aanmaken | `billing.ts:createPlan()` → PlanManagerView | test_billing | actief |
| PUT | `/platform/billing/plans/{plan_id}` | `update_plan` | Platform plan bijwerken | `billing.ts:updatePlan()` → PlanManagerView | test_billing | actief |
| GET | `/platform/billing/subscriptions/{tenant_id}` | `get_subscription` | Tenant abonnement ophalen | `billing.ts:getSubscription()` → Tenant360View | test_billing | actief |
| POST | `/platform/billing/subscriptions/{tenant_id}` | `create_subscription` | Abonnement aanmaken voor tenant | `billing.ts:createSubscription()` → Tenant360View | test_billing | actief |
| PUT | `/platform/billing/subscriptions/{tenant_id}` | `update_subscription` | Abonnement bijwerken (plan, status) | `billing.ts:updateSubscription()` → Tenant360View | test_billing | actief |
| POST | `/platform/billing/subscriptions/{tenant_id}/cancel` | `cancel_subscription` | Abonnement annuleren | `billing.ts:cancelSubscription()` → Tenant360View | test_billing | actief |
| GET | `/platform/billing/providers/{tenant_id}` | `get_providers` | Payment provider configs voor tenant | `billing.ts:getProviders()` → Tenant360View | test_billing | actief |
| POST | `/platform/billing/providers/{tenant_id}` | `configure_provider` | Payment provider toevoegen (Stripe/Mollie) | `billing.ts:configureProvider()` → Tenant360View | test_billing | actief |
| PUT | `/platform/billing/providers/{tenant_id}/{provider_id}` | `update_provider` | Provider config bijwerken | `billing.ts:updateProvider()` → Tenant360View | test_billing | actief |
| GET | `/platform/billing/invoices` | `list_invoices` | Platform facturen met filters | `billing.ts:listInvoices()` → BillingDashboardView | test_billing | actief |
| GET | `/platform/billing/invoices/{invoice_id}` | `get_invoice` | Factuur details | `billing.ts:getInvoice()` → BillingDashboardView | test_billing | actief |
| GET | `/platform/billing/payments` | `list_payments` | Betalingen met filters | `billing.ts:listPayments()` → BillingDashboardView | test_billing | actief |
| POST | `/platform/billing/payments/{payment_id}/refund` | `refund_payment` | Betaling terugbetalen | `billing.ts:refundPayment()` → BillingDashboardView | test_billing | actief |

### 3.12 Finance

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/platform/finance/overview` | `get_revenue_overview` | Revenue dashboard (MRR, ARR, top tenants) | `finance.ts:getRevenueOverview()` → RevenueView | test_finance | actief |
| GET | `/platform/finance/outstanding` | `get_outstanding_payments` | Openstaande facturen per aging bucket | `finance.ts:getOutstandingPayments()` → OutstandingPaymentsView | test_finance | actief |
| GET | `/platform/finance/tax-report` | `get_tax_report` | BTW rapport per jaar/kwartaal | `finance.ts:getTaxReport()` → TaxReportView | test_finance | actief |
| GET | `/platform/finance/tax-report/export` | `export_tax_report` | BTW rapport exporteren als CSV | `finance.ts:getTaxReportExportUrl()` → TaxReportView | test_finance | actief |
| GET | `/platform/finance/dunning/candidates` | `get_dunning_candidates` | Facturen in aanmerking voor aanmaning | `finance.ts:getDunningCandidates()` → OutstandingPaymentsView | test_finance | actief |
| POST | `/platform/finance/dunning/send` | `trigger_dunning` | Aanmaningen versturen (handmatige trigger) | `finance.ts:sendDunningReminders()` → OutstandingPaymentsView | test_finance | actief |

### 3.13 Notifications (Platform)

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/platform/notifications/types` | `list_notification_types` | Alle notificatietypen uit registry | `notifications.ts:listTypes()` → PlatformNotificationsAdminView | test_platform_notifications | actief |
| POST | `/platform/notifications` | `create_notification` | Platform notificatie aanmaken (unpublished) | `notifications.ts:create()` → PlatformNotificationsAdminView | test_platform_notifications | actief |
| GET | `/platform/notifications` | `list_notifications` | Alle notificaties ophalen (gepagineerd) | `notifications.ts:list()` → PlatformNotificationsAdminView | test_platform_notifications | actief |
| GET | `/platform/notifications/{notification_id}` | `get_notification` | Notificatie details ophalen | `notifications.ts:get()` → PlatformNotificationsAdminView | test_platform_notifications | actief |
| PUT | `/platform/notifications/{notification_id}` | `update_notification` | Notificatie bijwerken (vóór publicatie) | `notifications.ts:update()` → PlatformNotificationsAdminView | test_platform_notifications | actief |
| PUT | `/platform/notifications/{notification_id}/publish` | `publish_notification` | Notificatie publiceren naar ontvangers | `notifications.ts:publish()` → PlatformNotificationsAdminView | test_platform_notifications | actief |
| DELETE | `/platform/notifications/{notification_id}` | `delete_notification` | Notificatie verwijderen | `notifications.ts:remove()` → PlatformNotificationsAdminView | test_platform_notifications | actief |
| GET | `/platform/notifications/inbox` | `get_inbox` | Inbox huidige user (gepagineerd) | `notifications.ts:getInbox()` → NotificationBell (platform) | test_platform_notifications | actief |
| GET | `/platform/notifications/unread-count` | `get_unread_count` | Ongelezen telling | `notifications.ts:getUnreadCount()` → NotificationBell (platform) | test_platform_notifications | actief |
| PUT | `/platform/notifications/{recipient_id}/read` | `mark_read` | Notificatie als gelezen markeren | `notifications.ts:markRead()` → NotificationBell (platform) | test_platform_notifications | actief |
| PUT | `/platform/notifications/read-all` | `mark_all_read` | Alle notificaties als gelezen markeren | `notifications.ts:markAllRead()` → NotificationBell (platform) | test_platform_notifications | actief |

### 3.14 Products

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/platform/products/registry` | `get_product_registry` | Alle producten + navigatie items | `products.ts:getProductRegistry()` → useProductRegistry | test_product_registry | actief |

---

## 4. WEBHOOKS (`/api/v1/webhooks`)

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| POST | `/webhooks/mollie` | `mollie_webhook` | Mollie payment status callback | geen (extern) | test_webhooks | actief |
| POST | `/webhooks/stripe` | `stripe_webhook` | Stripe payment status callback | geen (extern) | test_webhook_verification | actief |

---

## 5. INFRA

| METHOD | PAD | HANDLER | WAT DOET HET | FRONTEND | TESTS | STATUS |
|--------|-----|---------|-------------|----------|-------|--------|
| GET | `/health/live` | `liveness` | Kubernetes liveness probe | geen | test_health | actief |
| GET | `/health/ready` | `readiness` | Kubernetes readiness probe (DB + Redis check) | geen | test_health | actief |
| GET | `/health/circuit-breakers` | `circuit_breakers` | Circuit breaker statussen | geen | test_circuit_breaker | actief |
| GET | `/metrics` | `prometheus_metrics` | Prometheus metrics endpoint | geen | — | actief |
| GET | `/branding` | `get_branding` | Platform branding (naam, logo, kleuren) | `branding.ts:getBranding()` → App.vue | — | actief |
| GET | `/docs` | `swagger_ui_html` | Swagger UI (alleen in development) | — | — | actief |
| GET | `/redoc` | `redoc_html` | ReDoc API docs | — | — | actief |

---

## 6. BEVINDINGEN

### 6.1 Overlaps / Dubbelingen

| # | Route A | Route B | Aard |
|---|---------|---------|------|
| 1 | `GET /platform/orgs/` (tenant_mgmt) | `GET /platform/orgs/overview` (admin) | Twee list-endpoints: user-specifiek vs admin-metrics. Zelfde handler-naam `list_tenants`, verschillende implementaties. |
| 2 | `GET /org/{slug}/notification-preferences` | `GET /org/{slug}/notifications/preferences/` | Twee aparte systemen (platform vs school), maar verwarrend dicht bij elkaar. Platform-variant heeft geen frontend UI. |
| 3 | `/org/{slug}/permissions/groups/*` (tenant) | `/platform/orgs/{tenant_id}/groups/*` (admin) | Zelfde CRUD op groepen, maar via slug (tenant-scoped) vs UUID (admin-scoped). Bewust: admin kan org beheren zonder lid te zijn. |
| 4 | `GET /org/{slug}/members` | `POST/DELETE /platform/orgs/{tenant_id}/memberships` | Members read via slug, membership write via UUID. Complementair, niet dubbel. |

### 6.2 Ongebruikte Frontend Routes

| # | Route | Backend status | Frontend status | Actie |
|---|-------|---------------|-----------------|-------|
| 1 | `GET /org/{slug}/notification-preferences` | Getest, werkend | API gedefinieerd maar nergens aangeroepen | Evalueer: verwijderen of UI bouwen |
| 2 | `PUT /org/{slug}/notification-preferences/{type}` | Getest, werkend | API gedefinieerd maar nergens aangeroepen | Zelfde als hierboven |
| 3 | `POST /platform/access/users/{user_id}/reactivate` | Getest, werkend | Geen frontend caller | Evalueer: UI toevoegen of bewust API-only |
| 4 | `GET /platform/access/groups/{group_id}` | Werkend | Niet direct aangeroepen (data via list context) | OK — detail endpoint voor toekomstig gebruik |
| 5 | `GET /platform/orgs/{tenant_id}/groups/{group_id}` | Werkend | Niet direct aangeroepen | OK — zelfde als hierboven |
| 6 | `GET /org/{slug}/notifications/logs/{log_id}` | Werkend | Geen frontend caller | OK — detail endpoint |

### 6.3 Structurele Observaties

| # | Observatie | Impact |
|---|-----------|--------|
| 1 | `/platform/audit-logs` staat plat op platform-root | 70% operationeel content → past beter onder `/platform/operations/audit-logs` |
| 2 | Trailing slash inconsistent: `students/` vs `members` vs `features` | Cosmetisch, geen functioneel probleem (FastAPI normaliseert) |
| 3 | Notes asymmetrie: aanmaken onder `tenants/{id}/notes`, wijzigen op `notes/{note_id}` | Logisch (note_id is globaal uniek), maar asymmetrisch |
| 4 | `{notification_id}` en `{recipient_id}` op zelfde path positie in notifications | Werkt door extra `/read` segment, maar parameter-naamgeving is misleidend |
