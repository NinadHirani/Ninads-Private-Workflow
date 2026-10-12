// Shorts Factory Mobile Service Worker
const CACHE_NAME = 'shorts-factory-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Do network-first for API and deliverables to ensure fresh data
  if (event.request.url.includes('/api/') || event.request.url.includes('/deliverables/')) {
    event.respondWith(fetch(event.request));
    return;
  }
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
