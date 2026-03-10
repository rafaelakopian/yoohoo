/**
 * Centralized API error handling with i18n-ready message mapping.
 *
 * Usage:
 *   import { extractError } from '@/utils/errors'
 *
 *   catch (e) {
 *     error.value = extractError(e, 'invite')
 *   }
 */

type Locale = 'nl' | 'en'

// Current locale — single place to switch language
let currentLocale: Locale = 'nl'

export function setErrorLocale(locale: Locale) {
  currentLocale = locale
}

// ---------------------------------------------------------------------------
// Known backend messages → user-friendly translations
// Keys are the exact `detail` strings returned by the backend.
// ---------------------------------------------------------------------------

const translations: Record<string, Record<Locale, string>> = {
  // --- Auth / Login ---
  'Invalid email or password': {
    nl: 'Ongeldig e-mailadres of wachtwoord',
    en: 'Invalid email or password',
  },
  'Account is deactivated': {
    nl: 'Account is gedeactiveerd',
    en: 'Account is deactivated',
  },
  'Missing authentication token': {
    nl: 'Authenticatietoken ontbreekt',
    en: 'Missing authentication token',
  },
  'Invalid or expired token': {
    nl: 'Ongeldige of verlopen token',
    en: 'Invalid or expired token',
  },
  'Token gebonden aan ander apparaat': {
    nl: 'Token gebonden aan ander apparaat',
    en: 'Token bound to different device',
  },
  'E-mailadres is nog niet geverifieerd. Controleer je inbox.': {
    nl: 'E-mailadres is nog niet geverifieerd. Controleer je inbox.',
    en: 'Email address not yet verified. Check your inbox.',
  },
  'Invalid refresh token': {
    nl: 'Ongeldige verversingstoken',
    en: 'Invalid refresh token',
  },
  'Refresh token not found or revoked': {
    nl: 'Verversingstoken niet gevonden of ingetrokken',
    en: 'Refresh token not found or revoked',
  },
  'Refresh token expired': {
    nl: 'Verversingstoken verlopen',
    en: 'Refresh token expired',
  },
  'Login failed': {
    nl: 'Inloggen mislukt',
    en: 'Login failed',
  },
  'Registration failed': {
    nl: 'Registratie mislukt',
    en: 'Registration failed',
  },

  // --- Password ---
  'Huidig wachtwoord is onjuist': {
    nl: 'Huidig wachtwoord is onjuist',
    en: 'Current password is incorrect',
  },
  'Onjuist wachtwoord': {
    nl: 'Onjuist wachtwoord',
    en: 'Incorrect password',
  },
  'Ongeldige of verlopen resetlink': {
    nl: 'Ongeldige of verlopen resetlink',
    en: 'Invalid or expired reset link',
  },
  'Resetlink is verlopen': {
    nl: 'Resetlink is verlopen',
    en: 'Reset link has expired',
  },
  'Incorrect password': {
    nl: 'Onjuist wachtwoord',
    en: 'Incorrect password',
  },

  // --- Email verification ---
  'Ongeldige of verlopen verificatielink': {
    nl: 'Ongeldige of verlopen verificatielink',
    en: 'Invalid or expired verification link',
  },
  'Verificatielink is verlopen. Vraag een nieuwe aan.': {
    nl: 'Verificatielink is verlopen. Vraag een nieuwe aan.',
    en: 'Verification link expired. Request a new one.',
  },

  // --- 2FA / TOTP ---
  'Ongeldige verificatiecode': {
    nl: 'Ongeldige verificatiecode',
    en: 'Invalid verification code',
  },
  'Ongeldige code': {
    nl: 'Ongeldige code',
    en: 'Invalid code',
  },
  '2FA is al actief. Schakel het eerst uit.': {
    nl: '2FA is al actief. Schakel het eerst uit.',
    en: '2FA is already active. Disable it first.',
  },
  'Start eerst de 2FA-setup': {
    nl: 'Start eerst de 2FA-setup',
    en: 'Start the 2FA setup first',
  },
  'Ongeldige of verlopen 2FA-token': {
    nl: 'Ongeldige of verlopen 2FA-token',
    en: 'Invalid or expired 2FA token',
  },
  'Te veel pogingen. Vraag een nieuwe code aan.': {
    nl: 'Te veel pogingen. Vraag een nieuwe code aan.',
    en: 'Too many attempts. Request a new code.',
  },
  'Deze code is al gebruikt': {
    nl: 'Deze code is al gebruikt',
    en: 'This code has already been used',
  },
  'Deze code is verlopen': {
    nl: 'Deze code is verlopen',
    en: 'This code has expired',
  },

  // --- Sessions ---
  'Sessie niet gevonden': {
    nl: 'Sessie niet gevonden',
    en: 'Session not found',
  },
  'Sessie niet geverifieerd': {
    nl: 'Sessie niet geverifieerd',
    en: 'Session not verified',
  },
  'Sessie is al ongeldig gemaakt': {
    nl: 'Sessie is al ongeldig gemaakt',
    en: 'Session already invalidated',
  },
  'Sessie is verlopen': {
    nl: 'Sessie is verlopen',
    en: 'Session has expired',
  },

  // --- Invitations ---
  'Ongeldige of verlopen uitnodiging': {
    nl: 'Ongeldige of verlopen uitnodiging',
    en: 'Invalid or expired invitation',
  },
  'Al een platformgebruiker': {
    nl: 'Deze gebruiker is al een platformmedewerker',
    en: 'This user is already a platform member',
  },
  'Er staat al een uitnodiging open voor dit emailadres': {
    nl: 'Er staat al een uitnodiging open voor dit e-mailadres',
    en: 'There is already a pending invitation for this email address',
  },
  'Je moet ingelogd zijn om deze uitnodiging te accepteren': {
    nl: 'Je moet ingelogd zijn om deze uitnodiging te accepteren',
    en: 'You must be logged in to accept this invitation',
  },
  'Je bent ingelogd met een ander account dan waarvoor de uitnodiging is': {
    nl: 'Je bent ingelogd met een ander account dan waarvoor de uitnodiging is',
    en: 'You are logged in with a different account than the invitation was sent to',
  },
  'Platformgebruikers kunnen niet worden uitgenodigd voor een organisatie': {
    nl: 'Platformgebruikers kunnen niet worden uitgenodigd voor een organisatie',
    en: 'Platform users cannot be invited to an organization',
  },
  'Wachtwoord en naam zijn verplicht voor nieuwe gebruikers': {
    nl: 'Wachtwoord en naam zijn verplicht voor nieuwe gebruikers',
    en: 'Password and name are required for new users',
  },

  // --- Superadmin ---
  'Je kunt je eigen superadmin-status niet ontnemen': {
    nl: 'Je kunt je eigen superadmin-status niet ontnemen',
    en: 'You cannot revoke your own superadmin status',
  },
  'De laatste superadmin kan niet worden verwijderd': {
    nl: 'De laatste superadmin kan niet worden verwijderd',
    en: 'The last superadmin cannot be removed',
  },

  // --- Permissions / Groups ---
  'Default groups cannot be deleted': {
    nl: 'Standaardgroepen kunnen niet worden verwijderd',
    en: 'Default groups cannot be deleted',
  },
  'User is already assigned to this group': {
    nl: 'Gebruiker is al toegewezen aan deze groep',
    en: 'User is already assigned to this group',
  },

  // --- Tenants / Orgs ---
  'User already has a membership for this tenant': {
    nl: 'Gebruiker is al lid van deze organisatie',
    en: 'User already has a membership for this organization',
  },
  'Not a member of this organization': {
    nl: 'Geen lid van deze organisatie',
    en: 'Not a member of this organization',
  },

  // --- Rate limiting ---
  'Too many requests': {
    nl: 'Te veel verzoeken. Probeer het later opnieuw.',
    en: 'Too many requests. Please try again later.',
  },

  // --- Account management ---
  'Dit account is geanonimiseerd en kan niet worden hersteld': {
    nl: 'Dit account is geanonimiseerd en kan niet worden hersteld',
    en: 'This account has been anonymized and cannot be restored',
  },
  'Accountreactivatie is uitgeschakeld in de configuratie': {
    nl: 'Accountreactivatie is uitgeschakeld in de configuratie',
    en: 'Account reactivation is disabled in the configuration',
  },

  // --- Impersonation ---
  'Je kunt jezelf niet impersonaten.': {
    nl: 'Je kunt jezelf niet impersoneren',
    en: 'You cannot impersonate yourself',
  },
  'Doelgebruiker is niet actief.': {
    nl: 'Doelgebruiker is niet actief',
    en: 'Target user is not active',
  },

  // --- Email change ---
  'Het nieuwe e-mailadres is hetzelfde als het huidige': {
    nl: 'Het nieuwe e-mailadres is hetzelfde als het huidige',
    en: 'The new email address is the same as the current one',
  },
  'Dit e-mailadres is inmiddels al in gebruik': {
    nl: 'Dit e-mailadres is inmiddels al in gebruik',
    en: 'This email address is already in use',
  },

  // --- Students ---
  'Leerling is al toegewezen aan een docent. Gebruik transfer.': {
    nl: 'Leerling is al toegewezen aan een docent. Gebruik transfer.',
    en: 'Student is already assigned to a teacher. Use transfer.',
  },

  // --- Billing ---
  'Tenant heeft al een actief abonnement': {
    nl: 'Organisatie heeft al een actief abonnement',
    en: 'Organization already has an active subscription',
  },
  'Alleen betaalde betalingen kunnen worden terugbetaald': {
    nl: 'Alleen betaalde betalingen kunnen worden terugbetaald',
    en: 'Only paid payments can be refunded',
  },
}

// ---------------------------------------------------------------------------
// Fallback messages per context category
// ---------------------------------------------------------------------------

const fallbacks: Record<string, Record<Locale, string>> = {
  generic:   { nl: 'Er is een fout opgetreden',      en: 'An error occurred' },
  login:     { nl: 'Inloggen mislukt',                en: 'Login failed' },
  register:  { nl: 'Registratie mislukt',             en: 'Registration failed' },
  invite:    { nl: 'Fout bij uitnodigen',             en: 'Failed to send invitation' },
  accept:    { nl: 'Fout bij accepteren',             en: 'Failed to accept invitation' },
  save:      { nl: 'Fout bij opslaan',                en: 'Failed to save' },
  delete:    { nl: 'Fout bij verwijderen',            en: 'Failed to delete' },
  load:      { nl: 'Fout bij laden',                  en: 'Failed to load' },
  password:  { nl: 'Fout bij wachtwoord wijzigen',    en: 'Failed to change password' },
  verify:    { nl: 'Verificatie mislukt',             en: 'Verification failed' },
  '2fa':     { nl: 'Ongeldige code',                  en: 'Invalid code' },
  email:     { nl: 'Vul een geldig e-mailadres in',   en: 'Enter a valid email address' },
}

// ---------------------------------------------------------------------------
// Validation error messages (422)
// Maps field paths like "body.email" to friendly messages.
// ---------------------------------------------------------------------------

const validationFieldMessages: Record<string, Record<Locale, string>> = {
  email:          { nl: 'Vul een geldig e-mailadres in',            en: 'Enter a valid email address' },
  password:       { nl: 'Wachtwoord voldoet niet aan de eisen',     en: 'Password does not meet requirements' },
  full_name:      { nl: 'Naam is verplicht',                        en: 'Name is required' },
  token:          { nl: 'Ongeldige token',                          en: 'Invalid token' },
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

interface ApiErrorDetail {
  type: string
  loc: string[]
  msg: string
}

/**
 * Get a client-side validation message by context key.
 * Use this for pre-submit validation (no API error to parse).
 *
 * @param context Key from fallbacks or validationFieldMessages (e.g. 'email', 'password')
 */
export function validationMessage(context: string): string {
  const fieldMsg = validationFieldMessages[context]
  if (fieldMsg) return fieldMsg[currentLocale]
  return _getFallback(context)
}

/**
 * Extract a user-friendly error message from an API error.
 *
 * @param e       The caught error (typically AxiosError)
 * @param context Optional category for the fallback message (e.g. 'invite', 'login')
 * @returns       Translated user-friendly error string
 */
export function extractError(e: unknown, context: string = 'generic'): string {
  const err = e as { response?: { status?: number; data?: { detail?: unknown } } }
  const detail = err.response?.data?.detail
  const status = err.response?.status

  // 422: Pydantic validation errors (array of objects)
  if (status === 422 && Array.isArray(detail)) {
    return _parseValidationErrors(detail as ApiErrorDetail[])
  }

  // String detail — look up in translations
  if (typeof detail === 'string') {
    return _translate(detail)
  }

  // 429: Rate limiting
  if (status === 429) {
    return _translate('Too many requests')
  }

  // Fallback
  return _getFallback(context)
}

/**
 * Translate a backend error message. Returns the original if no translation found.
 */
function _translate(message: string): string {
  // Exact match
  const entry = translations[message]
  if (entry) return entry[currentLocale]

  // Partial match: check if a known key is contained in the message
  // (handles messages like "Er staat al een uitnodiging open voor 'user@email.com'")
  for (const [key, value] of Object.entries(translations)) {
    if (message.includes(key)) return value[currentLocale]
  }

  // Backend already returns Dutch messages in most cases — pass through
  return message
}

/**
 * Parse 422 validation errors into a single user-friendly message.
 */
function _parseValidationErrors(errors: ApiErrorDetail[]): string {
  if (errors.length === 0) return _getFallback('generic')

  // Try to match the field name to a known friendly message
  const first = errors[0]
  const fieldName = first.loc[first.loc.length - 1]
  const fieldMsg = validationFieldMessages[fieldName]
  if (fieldMsg) return fieldMsg[currentLocale]

  // Fallback: generic validation message
  return currentLocale === 'nl'
    ? 'Controleer de ingevoerde gegevens'
    : 'Please check the entered data'
}

function _getFallback(context: string): string {
  const fb = fallbacks[context] ?? fallbacks.generic
  return fb[currentLocale]
}
