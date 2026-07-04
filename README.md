# ⚡ ClipForge AI

> **AI-powered gaming highlight clip generator** — Turn hours of Twitch/YouTube streams into viral 9:16 Shorts automatically using Computer Vision + Audio AI.

---

## 🏗️ Project Structure

```
clipforge/
├── index.html              ← Landing page
├── auth.html               ← Sign in / OAuth
├── dashboard.html          ← Main dashboard
├── new-clip.html           ← Generate clips
├── my-clips.html           ← Clip library
├── my-videos.html          ← Video management
├── export.html             ← Publish to platforms
├── pricing.html            ← Pricing plans
├── settings.html           ← Account settings
│
├── styles/
│   ├── main.css            ← Design system
│   └── dashboard.css       ← Dashboard components
│
├── scripts/
│   ├── main.js             ← UI interactions
│   └── app.js              ← Data layer (localStorage)
│
├── backend/                ← Python FastAPI backend
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py         ← FastAPI app
│       ├── config.py       ← Settings (reads .env)
│       ├── database.py     ← Async SQLAlchemy
│       ├── models/
│       │   └── models.py   ← ORM models
│       ├── api/
│       │   ├── auth.py     ← JWT + OAuth routes
│       │   ├── videos.py   ← Video ingest routes
│       │   ├── clips.py    ← Clip management
│       │   └── webhooks.py ← Stripe webhooks
│       ├── ai/
│       │   ├── detector.py ← CV + Audio AI pipeline
│       │   └── reframer.py ← FFmpeg rendering
│       └── workers/
│           └── job_worker.py ← Celery background tasks
│
├── prisma/
│   └── schema.prisma       ← Database schema (Prisma)
│
├── docker-compose.yml      ← Full stack deployment
├── .env.example            ← Environment template
└── README.md
```

---

## 🚀 Quick Start (Frontend Only)

No installation needed! Just open in your browser:

```
Double-click: index.html
```

All data is persisted in `localStorage` — clips, videos, settings, and activity are saved across page refreshes.

---

## 🐍 Backend Setup (Python + Docker)

### Prerequisites
- Docker + Docker Compose
- (Optional) NVIDIA GPU for faster AI processing

### 1. Clone & configure
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start all services
```bash
docker-compose up -d
```

This starts:
| Service | URL | Description |
|---|---|---|
| **FastAPI** | http://localhost:8000 | REST API |
| **API Docs** | http://localhost:8000/api/docs | Swagger UI |
| **Flower** | http://localhost:5555 | Celery task monitor |
| **PostgreSQL** | localhost:5432 | Database |
| **Redis** | localhost:6379 | Message broker |

### 3. Run database migrations
```bash
docker-compose exec api alembic upgrade head
```

### 4. Start Celery worker (for AI processing)
```bash
docker-compose up worker -d
```

---

## 🧠 AI Pipeline

```
Stream URL / Upload
        ↓
   yt-dlp download
        ↓
  ┌─────────────────────────────────┐
  │  Audio Analysis (librosa)       │ → RMS peaks
  │  CV Detection (YOLO v8)         │ → Kill/victory events
  │  Chat Sentiment (optional)      │ → Emoji clusters
  └─────────────────────────────────┘
        ↓
  Fusion Score (weighted per-second)
        ↓
  Top-N Highlight Selection
        ↓
  FFmpeg Render (9:16 smart crop)
        ↓
  S3 Upload → CloudFront CDN
        ↓
  Database update + UI notification
```

---

## 💰 Plans

| Plan | Price | Clips/month | Quality |
|---|---|---|---|
| Free | $0 | 3 | 720p |
| **Pro** | $19/mo | 30 | 1080p 60fps |
| Creator | $49/mo | Unlimited | 4K |
| Agency | $149/mo | Unlimited | 4K + API |

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Email signup |
| POST | `/api/auth/token` | Login → JWT |
| POST | `/api/auth/google` | Google OAuth |
| GET | `/api/auth/me` | Current user |
| POST | `/api/videos/ingest-url` | Process stream URL |
| POST | `/api/videos/upload` | Upload video file |
| GET | `/api/videos/{id}/status` | Job status polling |
| GET | `/api/clips/` | List user's clips |
| GET | `/api/clips/{id}` | Download clip URL |
| DELETE | `/api/clips/{id}` | Delete clip |
| POST | `/api/export/publish` | Publish to platforms |
| GET | `/api/export/history` | Export history |
| POST | `/api/webhooks/stripe` | Stripe webhooks |

Full interactive docs: **http://localhost:8000/api/docs**

---

## 🔑 Required API Keys

| Service | Get it at | Used for |
|---|---|---|
| **Google OAuth** | console.cloud.google.com | Login with Google |
| **Twitch OAuth** | dev.twitch.tv/console | Login with Twitch |
| **Stripe** | dashboard.stripe.com | Subscriptions |
| **YouTube Data v3** | console.cloud.google.com | Shorts publishing |
| **TikTok for Dev** | developers.tiktok.com | TikTok publishing |
| **AWS S3** | aws.amazon.com/s3 | Video storage |
| **AWS CloudFront** | aws.amazon.com/cloudfront | CDN |

---

## 🚢 Production Deployment

### Option A — VPS (DigitalOcean / Hetzner)
```bash
# On your server
git clone <repo>
cp .env.example .env && nano .env
docker-compose up -d
```

### Option B — Cloud GPU (Modal.com)
```bash
pip install modal
modal run backend/app/workers/job_worker.py
```

### Option C — Frontend only (Netlify/Vercel)
```bash
# Drag-and-drop the clipforge/ folder to netlify.com
# Or:
npx netlify-cli deploy --dir=. --prod
```

---

## 📄 License

MIT © 2026 ClipForge AI
