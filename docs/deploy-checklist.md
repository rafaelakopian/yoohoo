# Yoohoo — Deploy Checklist

Stap-voor-stap go-live handleiding voor de Hetzner VPS.

## Pre-deploy

- [ ] Hetzner Cloud account aangemaakt
- [ ] Hetzner API token gegenereerd
- [ ] SSH keypair aangemaakt voor deploy user
- [ ] Domeinnaam geregistreerd
- [ ] DNS A-records wijzen naar VPS IP:
  - `yoohoo.nl` → VPS IP (marketing website)
  - `www.yoohoo.nl` → VPS IP (redirect naar yoohoo.nl)
  - `app.yoohoo.nl` → VPS IP (SaaS portaal)
- [ ] Sentry project aangemaakt (gratis tier: 5K events/mo)
- [ ] GitHub repository secrets geconfigureerd:
  - `VPS_HOST` — VPS IP-adres
  - `VPS_SSH_KEY` — Private SSH key voor deploy
  - `SLACK_WEBHOOK_URL` — Slack webhook voor deploy notificaties

## 1. VPS Provisioning

```bash
cd infra/
cp terraform.tfvars.example terraform.tfvars
# Vul in: hcloud_token, ssh_public_key
terraform init
terraform plan
terraform apply
```

Na `apply`: noteer het server IP uit de output.

## 2. Server Configuratie

SSH naar de server (cloud-init draait automatisch bij eerste boot):

```bash
ssh deploy@<SERVER_IP>

# Controleer of cloud-init klaar is
cloud-init status --wait

# Verifieer installatie
docker --version
docker compose version
ufw status
fail2ban-client status
```

## 3. Applicatie Deployen

```bash
# Op de server
cd /opt/yoohoo
git clone https://github.com/<org>/yoohoo.git .

# .env instellen
cp .env.example .env
nano .env
# Wijzig ALLE secrets:
#   SECRET_KEY, POSTGRES_PASSWORD, JWT_SECRET_KEY
#   SENTRY_DSN, GRAFANA_ADMIN_PASSWORD
#   SMTP_* (productie SMTP provider)
#   APP_ENV=production, DEBUG=false
#   FRONTEND_URL=https://app.yoohoo.nl
#   CORS_ORIGINS=https://app.yoohoo.nl

# PgBouncer credentials
nano pgbouncer/userlist.txt
# Wijzig naar productie wachtwoord (matching POSTGRES_PASSWORD)
```

## 4. Containers Starten

```bash
# Docker netwerken aanmaken
docker network create yoohoo_default
docker network create yoohoo_monitoring

# Applicatie starten
docker compose up -d

# Monitoring platform starten (Prometheus, Grafana, Loki, Uptime Kuma)
docker compose -f monitoring/docker-compose.monitoring.yml up -d

# Log collector starten (Promtail — altijd op app-server)
docker compose -f monitoring/docker-compose.collector.yml up -d

# Logs bekijken
docker compose logs -f
```

## 5. Database Migraties

```bash
# Central database
docker compose exec api alembic -x mode=central upgrade head

# Tenant database (voor elke school)
docker compose exec api alembic -x mode=tenant -x tenant_slug=pianoschool-apeldoorn upgrade head
```

## 6. Superadmin Aanmaken

```bash
docker compose exec api python -c "
from app.modules.platform.auth.core.service import AuthService
# Maak superadmin via API of direct database
"
```

Of registreer via de API en stel `is_superadmin=True` in de database:

```bash
docker compose exec postgres psql -U yoohoo -d ps_core_db -c \
  "UPDATE users SET is_superadmin = true WHERE email = 'admin@yoohoo.nl';"
```

## 7. SSL Certificaat

```bash
# Certbot installeren (als niet via cloud-init)
apt-get install certbot

# Eerste certificaat aanvragen (alle 3 domeinen)
bash scripts/ssl/init-ssl.sh yoohoo.nl www.yoohoo.nl app.yoohoo.nl

# docker-compose.yml: activeer SSL volume + port 443
# Herstart met SSL config
docker compose up -d

# Auto-renewal instellen
crontab -e
# Voeg toe:
# 0 */12 * * * /opt/yoohoo/scripts/ssl/renew-ssl.sh >> /var/log/yoohoo-ssl-renew.log 2>&1
```

## 8. Backup Cron

```bash
crontab -e
# Voeg toe:
# 0 2 * * * /opt/yoohoo/scripts/backup/backup.sh >> /var/log/yoohoo-backup.log 2>&1
```

Test de backup:

```bash
bash scripts/backup/backup.sh
ls -la /backups/daily/
```

## Post-deploy Verificatie

- [ ] `curl -s https://yoohoo.nl/health/live` retourneert `{"status": "ok"}`
- [ ] `curl -s https://yoohoo.nl/health/ready` retourneert `{"status": "ok"}`
- [ ] Frontend laadt correct op https://yoohoo.nl
- [ ] Login werkt
- [ ] Student CRUD werkt
- [ ] E-mail verzending werkt (test via uitnodiging)
- [ ] Sentry test event ontvangen
- [ ] Grafana dashboards laden op http://localhost:3000 (via SSH tunnel)
- [ ] Uptime Kuma actief op http://localhost:3001 (via SSH tunnel)
- [ ] Backup cron draait (`ls /backups/daily/`)
- [ ] SSL auto-renewal getest (`certbot renew --dry-run`)
- [ ] Smoke test: registreer, login, CRUD, notificatie

## Monitoring Toegang (via SSH Tunnel)

Grafana en Uptime Kuma zijn alleen lokaal beschikbaar. Gebruik SSH tunneling:

```bash
# Grafana
ssh -L 3000:127.0.0.1:3000 deploy@<SERVER_IP>
# Open: http://localhost:3000 (admin / $GRAFANA_ADMIN_PASSWORD)

# Uptime Kuma
ssh -L 3001:127.0.0.1:3001 deploy@<SERVER_IP>
# Open: http://localhost:3001
```

## Uptime Kuma Monitors Instellen

Na eerste login op Uptime Kuma:

1. Health check: `https://yoohoo.nl/health/ready` (interval: 60s)
2. Frontend: `https://yoohoo.nl` (interval: 60s)
3. SSL expiry: `https://yoohoo.nl` (type: certificate, threshold: 14 dagen)

## Rollback

Bij problemen na een deploy:

```bash
# Terug naar vorige image
docker compose pull   # Als je specifieke tags gebruikt
docker compose up -d

# Of terug naar vorige git commit
git log --oneline -5
git checkout <previous-commit>
docker compose up -d --build

# Database restore (alleen als nodig)
bash scripts/backup/restore.sh /backups/daily/yoohoo_YYYYMMDD_HHMMSS.sql.gz
```
