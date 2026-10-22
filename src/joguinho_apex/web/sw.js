"use strict";

// Service worker do console: guarda só os arquivos estáticos.
// Troque CACHE_VERSION ao publicar mudanças no console para invalidar o cache antigo.
const CACHE_VERSION = "apex-nexus-console-v21.1.0";
const ASSETS = ["./", "index.html", "style.css", "app.js", "manifest.json", "icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_VERSION).then((cache) => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((name) => name !== CACHE_VERSION).map((name) => caches.delete(name)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // A API nunca é servida do cache: o jogo depende do estado do servidor.
  if (event.request.method !== "GET" || !url.pathname.startsWith("/console")) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
