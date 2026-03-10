export function isValidEmail(email: string): boolean {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return re.test(email)
}

export function isValidSlug(slug: string): boolean {
  return /^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(slug)
}

export function isValidPassword(password: string): boolean {
  return password.length >= 8
}

export function isValidPhone(phone: string): boolean {
  // International format: +, digits, spaces, dashes, parens. Min 7 digits.
  const digits = phone.replace(/\D/g, '')
  return /^[+\d\s\-()]+$/.test(phone) && digits.length >= 7
}

// ---------------------------------------------------------------------------
// Input sanitizers — strip characters that should never appear in a field.
// Use these to clean a value before assigning to v-model, or in directives.
// ---------------------------------------------------------------------------

/** Phone: only +, digits, spaces, dashes, parentheses */
export function sanitizePhone(value: string): string {
  return value.replace(/[^+\d\s\-()]/g, '')
}

/** Name: strip control characters and obvious code injection chars */
export function sanitizeName(value: string): string {
  return value.replace(/[<>{}[\]\\]/g, '')
}

/** Numeric only (for integer fields like duration, amount) */
export function sanitizeNumeric(value: string): string {
  return value.replace(/[^\d]/g, '')
}

/** Slug: lowercase, digits, dashes only */
export function sanitizeSlug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9-]/g, '')
}
