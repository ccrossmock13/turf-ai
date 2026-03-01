// Greenside AI - Service Worker
// Provides offline support, caching, and push notification foundation

const CACHE_NAME = 'greenside-v1';

// App shell: static assets and HTML pages to pre-cache on install
const STATIC_ASSETS = [
  '/static/css/shared.css',
  '/static/css/dashboard.css',
  '/static/css/calendar.css',
  '/static/css/scouting.css',
  '/static/css/equipment.css',
  '/static/css/budget.css',
  '/static/css/irrigation.css',
  '/static/css/crew.css',
  '/static/css/soil.css',
  '/static/css/course-map.css',
  '/static/css/cultivars.css',
  '/static/css/community.css',
  '/static/css/reports.css',
  '/static/css/calculator.css',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/manifest.json'
];

const HTML_PAGES = [
  '/dashboard',
  '/spray-tracker',
  '/calendar',
  '/scouting',
  '/equipment',
  '/budget',
  '/irrigation',
  '/crew'
];

const ALL_PRECACHE = [...STATIC_ASSETS, ...HTML_PAGES];

// ─── Install: pre-cache the app shell ───────────────────────────────────────

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Pre-caching app shell');
        return cache.addAll(ALL_PRECACHE);
      })
      .then(() => {
        // Activate immediately instead of waiting for existing tabs to close
        return self.skipWaiting();
      })
  );
});

// ─── Activate: clean up old caches ──────────────────────────────────────────

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name !== CACHE_NAME)
            .map((name) => {
              console.log('[SW] Removing old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => {
        // Take control of all open tabs immediately
        return self.clients.claim();
      })
  );
});

// ─── Fetch: network-first for API, cache-first for static assets ────────────

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests (POST/PUT/DELETE go straight to network)
  if (request.method !== 'GET') {
    return;
  }

  // API calls: network-first with cache fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Static assets (CSS, JS, images, icons): cache-first with network fallback
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // HTML pages: network-first so users get fresh content when online
  event.respondWith(networkFirst(request));
});

// ─── Caching strategies ─────────────────────────────────────────────────────

/**
 * Cache-first: try cache, fall back to network and update cache.
 * Best for static assets that change infrequently.
 */
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }

  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    return offlineFallback(request);
  }
}

/**
 * Network-first: try network, fall back to cache.
 * Best for API calls and HTML pages that should be fresh.
 */
async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    return offlineFallback(request);
  }
}

/**
 * Offline fallback: return a minimal offline page when nothing is cached.
 */
function offlineFallback(request) {
  const acceptHeader = request.headers.get('Accept') || '';

  // For HTML requests, return an offline page
  if (acceptHeader.includes('text/html')) {
    return new Response(
      `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Greenside AI - Offline</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; background: #f5f7f5; color: #1a4d2e;
      text-align: center; padding: 2rem;
    }
    .offline-container { max-width: 420px; }
    .offline-icon { font-size: 4rem; margin-bottom: 1rem; }
    h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
    p { color: #555; margin-bottom: 1.5rem; line-height: 1.5; }
    button {
      background: #1a4d2e; color: white; border: none;
      padding: 0.75rem 2rem; border-radius: 8px; font-size: 1rem;
      cursor: pointer; transition: background 0.2s;
    }
    button:hover { background: #2d6b45; }
  </style>
</head>
<body>
  <div class="offline-container">
    <div class="offline-icon">&#127967;</div>
    <h1>You're Offline</h1>
    <p>Greenside AI needs an internet connection to load this page. Check your connection and try again.</p>
    <button onclick="window.location.reload()">Retry</button>
  </div>
</body>
</html>`,
      {
        status: 503,
        headers: { 'Content-Type': 'text/html; charset=utf-8' }
      }
    );
  }

  // For other requests, return a simple error
  return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
}

// ─── Push notifications (basic structure) ───────────────────────────────────

self.addEventListener('push', (event) => {
  let data = {
    title: 'Greenside AI',
    body: 'You have a new notification.',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-192.png',
    tag: 'greenside-notification'
  };

  // Parse incoming push data if available
  if (event.data) {
    try {
      const payload = event.data.json();
      data = { ...data, ...payload };
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon || '/static/icons/icon-192.png',
    badge: data.badge || '/static/icons/icon-192.png',
    tag: data.tag || 'greenside-notification',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/dashboard'
    },
    actions: data.actions || []
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Handle notification click: open the relevant page
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const targetUrl = event.notification.data?.url || '/dashboard';

  // Handle action button clicks
  if (event.action) {
    // Future: route to specific pages based on action
    console.log('[SW] Notification action clicked:', event.action);
  }

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // If a tab is already open, focus it and navigate
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            client.focus();
            return client.navigate(targetUrl);
          }
        }
        // Otherwise open a new window
        return self.clients.openWindow(targetUrl);
      })
  );
});

// Handle notification close (for analytics)
self.addEventListener('notificationclose', (event) => {
  console.log('[SW] Notification dismissed:', event.notification.tag);
});

// ─── Background sync (future use) ──────────────────────────────────────────

self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-spray-logs') {
    event.waitUntil(syncSprayLogs());
  }
  if (event.tag === 'sync-scouting-reports') {
    event.waitUntil(syncScoutingReports());
  }
});

async function syncSprayLogs() {
  // Future: send queued spray logs when back online
  console.log('[SW] Syncing spray logs...');
}

async function syncScoutingReports() {
  // Future: send queued scouting reports when back online
  console.log('[SW] Syncing scouting reports...');
}
