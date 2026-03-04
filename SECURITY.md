# Security Policy

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability, please report it responsibly.

### Preferred: GitHub Private Vulnerability Reporting

1. Go to the **Security** tab of this repository
2. Click **"Report a vulnerability"**
3. Fill in the details and submit

This ensures your report stays private until a fix is available.

### Alternative: Email

If GitHub reporting is unavailable, email **security@yoohoo.nl** with:

- Description of the vulnerability
- Steps to reproduce
- Impact assessment (if known)

**Do NOT open a public issue for security vulnerabilities.**

## Scope

### In scope

- Authentication and authorization bypasses
- SQL injection, XSS, CSRF
- Sensitive data exposure
- Server-side request forgery (SSRF)
- Privilege escalation between tenants
- Cryptographic weaknesses

### Out of scope

- Denial of service (DoS/DDoS)
- Social engineering
- Physical attacks
- Issues in third-party dependencies (report upstream)
- Issues requiring physical access to infrastructure

## Response Timeline

| Step | Timeframe |
|------|-----------|
| Acknowledgment | 48 hours |
| Triage & severity assessment | 7 days |
| Fix development | Depends on severity |
| Coordinated disclosure | 90 days |

## Disclosure Policy

- Security updates may be released without prior public notice
- We follow a **90-day coordinated disclosure** timeline
- Credit will be given to reporters (unless anonymity is requested)

## Supported Versions

Only the latest version on the `main` branch receives security updates.
