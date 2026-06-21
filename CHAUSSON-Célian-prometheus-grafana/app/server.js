const express = require('express');
const client = require('prom-client');

const app = express();
const port = process.env.PORT || 8080;

// Enable default metrics collection (CPU, Memory, event loop, etc.)
client.collectDefaultMetrics({ register: client.register });

// Custom Counter for HTTP requests
const httpRequestsTotal = new client.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests processed',
  labelNames: ['method', 'code']
});

// Custom Histogram for request durations
const httpRequestDurationSeconds = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'code'],
  buckets: [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
});

// Custom Gauge for Queue Backlog Size (Specific business/technical metric)
const queueBacklogSize = new client.Gauge({
  name: 'demo_app_queue_backlog_size',
  help: 'Current backlog size of the demo application queue'
});

// Internal state variable to keep track of backlog accurately
let currentBacklog = 0;
queueBacklogSize.set(currentBacklog);

// Middleware to track HTTP requests total and duration
app.use((req, res, next) => {
  if (req.path === '/metrics') {
    return next();
  }
  const end = httpRequestDurationSeconds.startTimer({ method: req.method });
  res.on('finish', () => {
    const labels = { method: req.method, code: res.statusCode.toString() };
    httpRequestsTotal.inc(labels);
    end(labels);
  });
  next();
});

// Prometheus metrics endpoint
app.get('/metrics', async (req, res) => {
  try {
    res.set('Content-Type', client.register.contentType);
    res.end(await client.register.metrics());
  } catch (err) {
    res.status(500).end(err);
  }
});

// Main endpoint (200 OK)
app.get('/', (req, res) => {
  setTimeout(() => {
    res.send({ status: 'OK', message: 'Welcome to the Prometheus & Grafana TP Demo Application' });
  }, Math.random() * 50); // Simulate network latency up to 50ms
});

// Standard API data endpoint (200 OK)
app.get('/api/data', (req, res) => {
  setTimeout(() => {
    res.send({
      status: 'success',
      data: {
        id: Math.floor(Math.random() * 1000),
        timestamp: new Date().toISOString(),
        items: ['apple', 'banana', 'orange']
      }
    });
  }, Math.random() * 100); // Simulate network latency up to 100ms
});

// Simulated client error (404 Not Found)
app.get('/api/not-found', (req, res) => {
  res.status(404).send({ error: 'Not Found', message: 'The requested resource does not exist' });
});

// Simulated server error (500 Internal Server Error)
app.get('/api/error', (req, res) => {
  res.status(500).send({ error: 'Internal Server Error', message: 'A simulated system error occurred' });
});

// Route to increase the queue backlog size
app.post('/api/queue/add', (req, res) => {
  const amount = Math.floor(Math.random() * 10) + 5; // Add between 5 and 15 items
  currentBacklog += amount;
  queueBacklogSize.set(currentBacklog);
  res.send({ status: 'updated', message: `Added ${amount} items to the backlog`, current_backlog: currentBacklog });
});

// Route to decrease the queue backlog size
app.post('/api/queue/process', (req, res) => {
  if (currentBacklog <= 0) {
    return res.send({ status: 'idle', message: 'Queue backlog is already empty', current_backlog: 0 });
  }
  const amount = Math.min(currentBacklog, Math.floor(Math.random() * 10) + 5); // Process between 5 and 15 items
  currentBacklog -= amount;
  queueBacklogSize.set(currentBacklog);
  res.send({ status: 'updated', message: `Processed ${amount} items from the backlog`, current_backlog: currentBacklog });
});

app.listen(port, () => {
  console.log(`Demo app running on port ${port}`);
});
