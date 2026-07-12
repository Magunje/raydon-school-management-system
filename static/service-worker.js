const CACHE_NAME = "raydon-school-system-v4-static-only";
const APP_SHELL = [
    "/static/css/styles.css",
    "/static/js/app.js",
    "/static/img/raydon-system-logo.svg",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()),
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))),
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") {
        return;
    }

    const url = new URL(request.url);
    // Only cache same-origin requests
    if (url.origin !== self.location.origin) {
        return;
    }

    const acceptsHtml = request.headers.get("accept")?.includes("text/html");

    // Never cache HTML pages. They can contain user/session-specific CSRF tokens.
    if (request.mode === "navigate" || acceptsHtml || !url.pathname.startsWith("/static/")) {
        return;
    }

    event.respondWith(
        fetch(request)
            .then((response) => {
                if (response.status === 200) {
                    const copy = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
                }
                return response;
            })
            .catch(() => {
                return caches.match(request).then((cached) => {
                    if (cached) {
                        return cached;
                    }
                    return null;
                });
            }),
    );
});
