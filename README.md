# V85Modellen

A cleaned standalone Express app for the V85Modellen landing page.

## Requirements

- Node.js 18+

## Environment Variables

- `PORT` - Server port (default: 3000)
- `FEED_SECRET` - optional secret for `POST /api/feed`

## Endpoints

- `GET /` - Landing page
- `GET /health` - Health check
- `GET /api/feed` - Feed JSON
- `POST /api/feed` - Optional protected feed update endpoint

## Local Development

```bash
npm install
npm run dev
```

## Deployment

This app is configured for Render deployment via `render.yaml`.
