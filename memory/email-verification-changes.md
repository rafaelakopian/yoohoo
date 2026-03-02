# Email Verificatie - Alle wijzigingen

Geïmplementeerd: feb 2026. Alles getest en werkend (28/28 tests groen).

## Flow
```
Registratie → Email met link → Klik op link → Account actief → Inloggen
Na 7 dagen niet geverifieerd → Account automatisch verwijderd
```

## Gewijzigde bestanden

### Backend - Bestaand gewijzigd
| Bestand | Wat gewijzigd |
|---------|--------------|
| `backend/requirements.txt` | Alle packages geüpdatet naar laatste versies; passlib vervangen door pwdlib; aiosmtplib toegevoegd |
| `backend/app/config.py` | `smtp_use_tls`, `frontend_url`, `email_verification_expire_hours`, `unverified_cleanup_days` toegevoegd; smtp_host default → "mailpit" |
| `backend/app/core/security.py` | passlib vervangen door pwdlib (Argon2Hasher + BcryptHasher); `verify_and_update_password()` toegevoegd |
| `backend/app/modules/auth/models.py` | 3 kolommen op User: `email_verified`, `verification_token_hash`, `verification_token_expires_at` |
| `backend/app/modules/auth/schemas.py` | `VerifyEmailRequest`, `ResendVerificationRequest`, `MessageResponse`, `RegisterResponse` toegevoegd; `email_verified` op `UserResponse` |
| `backend/app/modules/auth/service.py` | `register()` retourneert nu (user, token); `send_verification_email()`, `verify_email()`, `resend_verification()`, `cleanup_unverified_users()` toegevoegd; login checkt email_verified; transparante rehash bcrypt→Argon2 |
| `backend/app/modules/auth/router.py` | `POST /verify-email`, `POST /resend-verification` endpoints; register gebruikt BackgroundTasks voor email |
| `backend/app/main.py` | Periodieke cleanup task (elk uur, verwijdert >7 dagen onverifieerde accounts) via asyncio.create_task in lifespan |
| `backend/app/modules/student/service.py` | `await self.db.refresh(student)` na flush in update_student/delete_student (fix MissingGreenlet bug) |
| `backend/pytest.ini` | `asyncio_default_fixture_loop_scope = session` en `asyncio_default_test_loop_scope = session` voor pytest-asyncio 1.x |
| `backend/tests/conftest.py` | `verified_user`, `auth_headers`, `tenant_auth_headers` fixtures; `from app.main import app as fastapi_app` (fix module shadowing) |
| `backend/tests/test_auth.py` | Tests updaten voor verificatie + 5 nieuwe tests (unverified login, verify, invalid token, resend, expired) |
| `backend/tests/test_student.py` | `_get_auth_headers` vervangen door `tenant_auth_headers` fixture |
| `backend/tests/test_tenant.py` | Inline register+login vervangen door `auth_headers` fixture |
| `.env` | SMTP_HOST, SMTP_USE_TLS, FRONTEND_URL, EMAIL_VERIFICATION_EXPIRE_HOURS, UNVERIFIED_CLEANUP_DAYS |
| `.env.example` | Zelfde nieuwe vars als .env |

### Backend - Nieuw aangemaakt
| Bestand | Wat |
|---------|-----|
| `backend/app/core/email.py` | `send_email()` via aiosmtplib + `build_verification_email()` met Yoohoo brand kleuren |
| `backend/alembic/versions/central/002_add_email_verification.py` | Migratie: 3 kolommen + bestaande users op verified=true |

### Frontend - Gewijzigd
| Bestand | Wat gewijzigd |
|---------|--------------|
| `frontend/package.json` | Alle packages geüpdatet (pinia 3, vue-router 5, vite 7, tailwind 4, vue-tsc 3) |
| `frontend/vite.config.ts` | `@tailwindcss/vite` plugin toegevoegd |
| `frontend/src/style.css` | Tailwind v4 CSS-first config met `@import "tailwindcss"` en `@theme` |
| `frontend/src/types/models.ts` | `email_verified` op User interface |
| `frontend/src/api/auth.ts` | `verifyEmail()`, `resendVerification()` functies |
| `frontend/src/stores/auth.ts` | Register redirect naar `/register-success`; `registeredEmail` state |
| `frontend/src/router/index.ts` | Routes: `/register-success`, `/verify-email` |

### Frontend - Nieuw aangemaakt
| Bestand | Wat |
|---------|-----|
| `frontend/src/views/RegisterSuccessView.vue` | "Controleer je email" pagina met resend knop |
| `frontend/src/views/VerifyEmailView.vue` | Verwerkt verificatie-link (loading → success/error) |

### Frontend - Verwijderd
| Bestand | Reden |
|---------|-------|
| `frontend/postcss.config.js` | Niet nodig met @tailwindcss/vite (Tailwind v4) |
| `frontend/tailwind.config.js` | Vervangen door @theme in CSS (Tailwind v4) |

### Infra
| Bestand | Wat gewijzigd |
|---------|--------------|
| `docker-compose.dev.yml` | Mailpit service (axllent/mailpit:latest) + SMTP/email env vars op API service |

## Bugs gefixt tijdens implementatie
1. **passlib → pwdlib**: passlib is dood, vervangen door pwdlib met Argon2Hasher + BcryptHasher
2. **Mailhog → Mailpit**: Mailhog is unmaintained, vervangen door Mailpit
3. **aiosmtplib start_tls**: v5 default is True, breekt Mailpit. Fix: `start_tls=settings.smtp_use_tls` (False in dev)
4. **pwdlib API**: geen `is_deprecated()`, gebruikt `verify_and_update()` voor transparante rehash
5. **Module shadowing**: `import app.modules.student.models` shadowed `app` FastAPI instance. Fix: `from app.main import app as fastapi_app`
6. **pytest-asyncio 1.x**: session-scoped loop nodig voor zowel fixtures als tests
7. **MissingGreenlet**: `onupdate=func.now()` op `updated_at` triggerde lazy loading na flush. Fix: `await self.db.refresh(student)` na flush in update/delete
8. **Tailwind v4**: oude node_modules volume cached v3 packages. Fix: `docker compose build --no-cache` + `--renew-anon-volumes`

## Technische details
- **Token**: `secrets.token_urlsafe(32)` → SHA256 hash in DB (zelfde patroon als refresh tokens)
- **Email**: aiosmtplib via FastAPI BackgroundTasks (non-blocking)
- **Anti-enumeratie**: `/resend-verification` geeft altijd hetzelfde antwoord
- **Cleanup**: asyncio.create_task in lifespan, elk uur, verwijdert email_verified=False AND created_at < 7 dagen
- **Bestaande users**: migratie zet alle huidige users op email_verified=True
