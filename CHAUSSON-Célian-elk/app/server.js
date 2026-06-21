const express = require('express');
const crypto = require('crypto');

const app = express();
const port = process.env.PORT || 8080;

// Application state representing our custom business metric
let currentBacklog = 0;

// Logging utility to stdout
function log(level, message, extra = {}) {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    message,
    ...extra,
    queue_backlog: currentBacklog
  };
  console.log(JSON.stringify(logEntry));
}

// Request logging & correlation ID middleware
app.use((req, res, next) => {
  // Read request ID from header or generate a new UUID
  const requestId = req.headers['x-request-id'] || crypto.randomUUID();
  res.setHeader('X-Request-ID', requestId);

  const start = process.hrtime();

  res.on('finish', () => {
    const diff = process.hrtime(start);
    const durationMs = (diff[0] * 1e3 + diff[1] * 1e-6).toFixed(2);
    const statusCode = res.statusCode;

    // Determine log level based on response status code
    let level = 'info';
    if (statusCode >= 400 && statusCode < 500) {
      level = 'warn';
    } else if (statusCode >= 500) {
      level = 'error';
    }

    log(level, `HTTP ${req.method} ${req.path} -> ${statusCode} (${durationMs}ms)`, {
      method: req.method,
      path: req.path,
      status_code: statusCode,
      duration_ms: parseFloat(durationMs),
      request_id: requestId
    });
  });

  next();
});

// JSON body parser
app.use(express.json());

// 1. Nominal Traffic Endpoint (200 OK)
app.get('/', (req, res) => {
  setTimeout(() => {
    res.status(200).json({
      status: 'success',
      message: 'Welcome to the ELK Stack TP Demo Application!'
    });
  }, Math.random() * 50); // Simulate network latency up to 50ms
});

// 2. Data Retrieval Endpoint (200 OK)
app.get('/api/data', (req, res) => {
  setTimeout(() => {
    res.status(200).json({
      status: 'success',
      data: {
        id: Math.floor(Math.random() * 1000),
        items: ['elastic', 'kibana', 'logstash', 'filebeat'],
        timestamp: new Date().toISOString()
      }
    });
  }, Math.random() * 100); // Simulate network latency up to 100ms
});

// 3. Client Error Route (404 Not Found)
app.get('/api/not-found', (req, res) => {
  res.status(404).json({
    status: 'error',
    error: 'NotFound',
    message: 'The requested API route does not exist.'
  });
});

// 4. Server Error Route (500 Internal Server Error)
app.get('/api/error', (req, res) => {
  res.status(500).json({
    status: 'error',
    error: 'InternalServerError',
    message: 'A simulated system critical error has occurred.'
  });
});

// 5. Custom Business/Technical Behavior: Queue Add
app.post('/api/queue/add', (req, res) => {
  const amount = Math.floor(Math.random() * 10) + 5; // Add between 5 and 15 items
  currentBacklog += amount;
  
  log('info', `Business Event: Added ${amount} items to the backlog. New backlog is ${currentBacklog}`, {
    event_type: 'queue_addition',
    added_amount: amount
  });

  res.status(200).json({
    status: 'success',
    message: `Added ${amount} items to the backlog.`,
    current_backlog: currentBacklog
  });
});

// 6. Custom Business/Technical Behavior: Queue Process
app.post('/api/queue/process', (req, res) => {
  if (currentBacklog <= 0) {
    log('info', 'Business Event: Attempted to process backlog but queue is empty.', {
      event_type: 'queue_idle'
    });
    return res.status(200).json({
      status: 'success',
      message: 'Queue is already empty.',
      current_backlog: 0
    });
  }

  const amount = Math.min(currentBacklog, Math.floor(Math.random() * 10) + 5); // Process between 5 and 15 items
  currentBacklog -= amount;

  log('info', `Business Event: Processed ${amount} items from the backlog. New backlog is ${currentBacklog}`, {
    event_type: 'queue_processing',
    processed_amount: amount
  });

  res.status(200).json({
    status: 'success',
    message: `Processed ${amount} items from the backlog.`,
    current_backlog: currentBacklog
  });
});

// Start the server
app.listen(port, () => {
  log('info', `Application server successfully started on port ${port}`, {
    port: port,
    node_version: process.version
  });
});
