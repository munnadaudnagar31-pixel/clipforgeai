# ClipForge AI — Production Deployment Guide

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Ubuntu | 22.04 LTS | Or any Debian-based OS |
| Docker | 24+ | `curl -fsSL https://get.docker.com | sh` |
| Docker Compose | 2.20+ | Included in Docker Desktop |
| Domain | `clipforge.ai` | Point A record → your server IP |
| RAM | 8 GB minimum | 16 GB recommended for GPU worker |

---

## Step 1 — Clone & Configure

```bash
git clone https://github.com/your-org/clipforge-ai.git
cd clipforge-ai

# Create your .env from the example
cp .env.example .env
nano .env
```

### Required `.env` values

```env
# ── App ─────────────────────────────────────────────
SECRET_KEY=<generate: openssl rand -hex 32>
APP_ENV=production
DEBUG=false

# ── Database ─────────────────────────────────────────
POSTGRES_PASSWORD=<strong-password>
DATABASE_URL=postgresql+asyncpg://clipforge:<password>@postgres:5432/clipforge_db

# ── Redis ─────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
CELERY_BROKER=redis://redis:6379/0
CELERY_BACKEND=redis://redis:6379/1

# ── AWS (for S3 clip storage) ────────────────────────
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-south-1
S3_BUCKET_RAW=clipforge-raw-videos
S3_BUCKET_RENDERED=clipforge-rendered-clips

# ── Stripe ───────────────────────────────────────────
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_CREATOR=price_...
STRIPE_PRICE_ID_AGENCY=price_...

# ── Google OAuth ─────────────────────────────────────
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# ── YouTube API (for Shorts publishing) ──────────────
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=

# ── TikTok API ───────────────────────────────────────
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=

# ── Sentry (optional but recommended) ────────────────
SENTRY_DSN=https://...@sentry.io/...
```

---

## Step 2 — Build & Start Services

```bash
# Start full production stack
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Verify all containers are running
docker-compose ps
```

Expected output:
```
NAME                    STATUS          PORTS
clipforge_postgres      Up (healthy)    5432/tcp
clipforge_redis         Up              6379/tcp
clipforge_api           Up (healthy)    8000/tcp
clipforge_worker        Up              —
clipforge_publish       Up              —
clipforge_nginx         Up (healthy)    0.0.0.0:80->80/tcp
```

---

## Step 3 — Run Database Migrations

```bash
# Run Alembic migrations inside the API container
docker-compose exec api alembic upgrade head

# Verify tables were created
docker-compose exec postgres psql -U clipforge -d clipforge_db -c "\dt"
```

---

## Step 4 — SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Stop nginx temporarily to get cert
docker-compose stop nginx

# Get certificate
sudo certbot certonly --standalone -d clipforge.ai -d www.clipforge.ai \
  --email admin@clipforge.ai --agree-tos --no-eff-email

# Restart nginx
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d nginx
```

Then uncomment the HTTPS server block in `nginx.conf` and reload:
```bash
docker-compose exec nginx nginx -s reload
```

### Auto-renewal cron
```bash
# Add to crontab (runs daily at 3am)
echo "0 3 * * * certbot renew --quiet && docker-compose exec nginx nginx -s reload" | crontab -
```

---

## Step 5 — Stripe Webhook

```bash
# In Stripe Dashboard → Webhooks → Add endpoint:
# URL: https://clipforge.ai/api/webhooks/stripe
# Events to listen for:
#   - checkout.session.completed
#   - customer.subscription.updated
#   - customer.subscription.deleted
#   - invoice.payment_failed

# Copy the webhook secret → paste into .env as STRIPE_WEBHOOK_SECRET
# Then restart the API container:
docker-compose restart api
```

---

## Step 6 — Verify Health

```bash
# API health check
curl https://clipforge.ai/api/health
# Expected: {"status": "ok", "version": "1.0.0"}

# Check Celery worker
docker-compose exec api celery -A app.workers.job_worker.celery_app inspect active

# Check logs
docker-compose logs api --tail=50
docker-compose logs worker --tail=50
```

---

## Step 7 — AI Model Setup

```bash
# The YOLO gaming models need to be placed in the /models volume
# Create the directory and copy your trained .pt file:
docker-compose exec worker bash -c "ls /models/"

# Copy your trained YOLO model:
docker cp gaming_yolo_v8.pt clipforge_worker:/models/gaming_yolo_v8.pt

# Update .env to point to the model:
echo "YOLO_MODEL_PATH=/models/gaming_yolo_v8.pt" >> .env
docker-compose restart worker
```

---

## Monitoring & Maintenance

### View real-time logs
```bash
docker-compose logs -f api worker publish
```

### Restart a single service
```bash
docker-compose restart api
docker-compose restart worker
```

### Update to latest code
```bash
git pull origin main
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api worker publish_worker
docker-compose exec api alembic upgrade head
```

### Backup database
```bash
docker-compose exec postgres pg_dump -U clipforge clipforge_db > backup_$(date +%Y%m%d).sql
```

### Scale workers (for high load)
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale worker=3
```

---

## Rollback

```bash
# Rollback code
git checkout <previous-tag>
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api worker

# Rollback database migration
docker-compose exec api alembic downgrade -1
```

---

## Environment Checklist Before Going Live

- [ ] All `.env` values filled in (no empty required fields)
- [ ] `SECRET_KEY` is cryptographically random (`openssl rand -hex 32`)
- [ ] `POSTGRES_PASSWORD` is strong and unique
- [ ] `APP_ENV=production` and `DEBUG=false`
- [ ] SSL certificate installed and auto-renewal configured
- [ ] Stripe webhook configured and `STRIPE_WEBHOOK_SECRET` set
- [ ] Google OAuth consent screen configured with `https://clipforge.ai` as origin
- [ ] S3 buckets created with appropriate IAM policies
- [ ] YOLO model file copied into `/models` volume
- [ ] All containers healthy (`docker-compose ps`)
- [ ] API health endpoint returns 200 (`curl https://clipforge.ai/api/health`)
- [ ] Test end-to-end: paste a YouTube URL → verify clip generates → download clip
- [ ] Test Stripe: complete a test checkout with Stripe test card
- [ ] Enable Sentry alerts for production errors
