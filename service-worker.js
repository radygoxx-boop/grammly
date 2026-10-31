const CACHE_NAME = 'grammly-v3';

// インストール時にキャッシュするコアアセット
const CORE_ASSETS = [
  '/index.html',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

// ===== インストール =====
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

// ===== アクティベート：古いキャッシュ削除 =====
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ===== フェッチ戦略 =====
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // questions.json : Network First（毎日更新されるので最新を優先）
  if (url.pathname.startsWith('/questions.json')) {
    event.respondWith(networkFirstWithCache(event.request));
    return;
  }

  // 外部リソース（Googleフォント等）: Cache First
  if (url.origin !== location.origin) {
    event.respondWith(cacheFirst(event.request));
    return;
  }

  // その他（index.html等）: Cache First
  event.respondWith(cacheFirst(event.request));
});

// Network First: ネットワーク優先、失敗したらキャッシュ
async function networkFirstWithCache(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cacheKey = new Request(new URL(request.url).pathname);
      cache.put(cacheKey, response.clone());
    }
    return response;
  } catch {
    const cached = await cache.match('/questions.json');
    if (cached) return cached;
    return new Response(JSON.stringify({ questions: {}, generated_at: 'offline' }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

// Cache First: キャッシュ優先、なければNetwork
async function cacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch {
    return cache.match('/index.html');
  }
}
