const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());

// Health check endpoint (required for Render)
// Note: Does NOT query database to allow Neon auto-suspend
app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

// API endpoint for feed data (can be switched to DB-backed later)
app.get('/api/feed', (req, res) => {
  const feedPath = path.join(__dirname, 'public', 'data', 'feed.json');
  if (fs.existsSync(feedPath)) {
    try {
      const feed = JSON.parse(fs.readFileSync(feedPath, 'utf8'));
      res.set('Cache-Control', 'public, max-age=300'); // 5 min cache
      res.json(feed);
    } catch (err) {
      console.error('Error reading feed:', err.message);
      res.status(500).json({ error: 'Failed to read feed' });
    }
  } else {
    res.status(404).json({ error: 'Feed not found' });
  }
});

// API endpoint to update feed (POST with JSON body)
// Protected by a simple secret for now
app.post('/api/feed', (req, res) => {
  const secret = req.headers['x-feed-secret'];
  const expectedSecret = process.env.FEED_SECRET;

  if (!expectedSecret || secret !== expectedSecret) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const feedPath = path.join(__dirname, 'public', 'data', 'feed.json');
  try {
    // Ensure directory exists
    const dir = path.dirname(feedPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(feedPath, JSON.stringify(req.body, null, 2));
    res.json({ success: true, message: 'Feed updated' });
  } catch (err) {
    console.error('Error writing feed:', err.message);
    res.status(500).json({ error: 'Failed to write feed' });
  }
});

// Serve static files from public folder
app.use(express.static(path.join(__dirname, 'public')));

app.get('/', (req, res) => {
  const htmlPath = path.join(__dirname, 'public', 'index.html');

  if (fs.existsSync(htmlPath)) {
    res.sendFile(htmlPath);
  } else {
    res.json({ message: 'V85Modellen — Coming soon' });
  }
});

app.listen(port, () => {
  console.log(`V85Modellen running on port ${port}`);
});
