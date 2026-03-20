# V85Modellen — Standalone Deploy Guide

This is the complete codebase for **V85Modellen**, a Swedish harness racing analytics site. It runs independently outside Polsia on any Node.js host.

---

## What This Is

- **Backend:** Express.js (Node 18+)
- **Frontend:** Static HTML/CSS/JS served from `/public`
- **Data:** Feed JSON file at `/public/data/feed.json` (updated via optional POST API)

---

## Requirements

| Tool | Version |
|------|---------|
| Node.js | 18 or higher |
| npm | 8+ |

---

## Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```env
PORT=3000

# Optional — protects the POST /api/feed endpoint
FEED_SECRET=some-random-secret-string
```

---

## Local Development

```bash
# 1. Install dependencies
npm install

# 2. Create .env file
cp .env.example .env
# Edit .env with your DATABASE_URL

# 3. Start the development server
npm run dev
```

Server will be live at `http://localhost:3000`

---

## Production Build & Start

```bash
npm install
npm run build
npm start       # starts server on $PORT (default 3000)
```

---

## Updating the Feed Data

The homepage pulls data from `/public/data/feed.json`. To update it:

```bash
# Via curl (requires FEED_SECRET to be set)
curl -X POST https://your-domain.com/api/feed \
  -H "Content-Type: application/json" \
  -H "X-Feed-Secret: your-secret-here" \
  -d @public/data/feed.json
```

Or just edit `public/data/feed.json` directly and redeploy.

### Feed JSON Structure

```json
{
  "brand": { "name": "V85Modellen", "tagline": "..." },
  "links": { "patreon": "...", "telegram": "...", "x": "..." },
  "stats": { "updated_at": "2026-01-01T12:00:00Z", "alpha_price_sek_per_month": 49 },
  "recent_results": [
    {
      "date": "2026-01-01",
      "mode": "union",
      "game_id": "V85-2026-01-01",
      "game_type": "V86",
      "track": "Solvalla",
      "hits": 6,
      "total_legs": 8,
      "leg_results": ["✓", "✓", "✓", "✗", "✓", "✓", "✗", "✓"],
      "payout_sek": null,
      "status": "6 rätt"
    }
  ],
  "today_card": { ... }
}
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Landing page |
| `GET` | `/health` | Health check — returns `{ status: "healthy" }` |
| `GET` | `/api/feed` | Returns current feed JSON (cached 5 min) |
| `POST` | `/api/feed` | Updates feed JSON (requires `X-Feed-Secret` header) |

---

## Deployment Options

### Option 1: Render (Recommended — matches current setup)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service → connect your repo
3. Settings:
   - **Build command:** `npm install`
   - **Start command:** `npm start`
   - **Health check path:** `/health`
4. Add environment variables in Render dashboard as needed:
   - `FEED_SECRET` — optional secret for feed updates
   - `NODE_ENV=production`
5. Deploy — takes ~2 minutes

**Free tier:** Render's free tier spins down after 15 min inactivity (cold starts ~30s). Upgrade to Starter ($7/mo) for always-on.

---

### Option 2: Railway

1. Push repo to GitHub
2. [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
3. Set `FEED_SECRET` if you want to keep the POST feed update endpoint
4. Railway auto-detects Node.js and deploys

---

### Option 3: Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login and launch
fly auth login
fly launch --name v85modellen

# Set secrets
fly secrets set FEED_SECRET="your-secret"

# Deploy
fly deploy
```

---

### Option 4: Any VPS (Ubuntu/Debian)

```bash
# On your server
git clone https://github.com/YOUR_USER/YOUR_REPO.git
cd YOUR_REPO

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install PM2 for process management
npm install -g pm2

# Install dependencies and build
npm install
npm run build

# Create .env
echo 'FEED_SECRET=your-secret' > .env
echo 'PORT=3000' >> .env

# Start with PM2
pm2 start server.js --name v85modellen
pm2 save
pm2 startup  # auto-start on reboot

# Nginx reverse proxy (optional, for port 80/443)
sudo apt install nginx
# Configure /etc/nginx/sites-available/v85modellen
# Add: proxy_pass http://localhost:3000;
```

---

### Option 5: Vercel (Serverless — minimal changes needed)

Not recommended — this is an Express app designed for persistent processes. Use Render or Railway instead.

---

## Custom Domain

On any platform:
1. Add your domain (e.g., `v85modellen.se`) in the hosting dashboard
2. Point your DNS:
   - `A` record: `@` → the platform's IP
   - `CNAME`: `www` → your app's subdomain
3. SSL auto-provisions

---

## Database Migrations

Migrations run automatically during `npm run build`. To run manually:

```bash
npm run migrate        # apply all pending migrations
```

Migration files are in `/migrate.js` (single-file runner). Add new migrations there.

---

## Image Assets

Static images referenced in the HTML currently point to Polsia's R2 CDN. To self-host:

1. Download the images from the URLs in `public/index.html`
2. Put them in `public/images/`
3. Update the `<img src>` and `<meta property="og:image">` tags in `public/index.html`

---

## `.env.example`

```env
# Required
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require

# Server port (Render/Railway set this automatically)
PORT=3000

# Protects POST /api/feed from unauthorized updates
FEED_SECRET=change-this-to-a-random-string

# Optional: Node environment
NODE_ENV=production
```

---

## Support

This codebase is owned by you and is fully portable. No Polsia dependencies at runtime.

For questions about the codebase, contact the developer who built it.
