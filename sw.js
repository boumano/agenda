/* Service worker d'Agenda : garde les fichiers de l'appli sur le téléphone pour qu'elle s'ouvre sans internet.
   Il ne touche jamais aux données (elles sont dans IndexedDB). Il ne remplace JAMAIS une version tout seul :
   la nouvelle version attend (« waiting ») jusqu'à ce que Pascal touche « Mettre à jour ». */
importScripts('version.js');

var CACHE = 'agenda-' + self.APP_VERSION;
var FILES = ['./', 'index.html', 'db.js', 'rides.js', 'fuel.js', 'app.js', 'style.css', 'version.js', 'manifest.json', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', function (e) {
  /* cache:'reload' = on prend les fichiers frais sur le site, pas ceux que le navigateur aurait gardés */
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return Promise.all(FILES.map(function (u) { return c.add(new Request(u, { cache: 'reload' })); }));
  }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf('agenda-') === 0 && k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('message', function (e) {
  if (e.data && e.data.type === 'SKIP_WAITING') self.skipWaiting();   /* seulement quand Pascal l'a demandé */
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;                    /* rien ne sort : aucune autre adresse n'est utilisée */
  e.respondWith(caches.match(req, { ignoreSearch: true }).then(function (hit) {
    if (hit) return hit;
    return fetch(req).catch(function () {
      return req.mode === 'navigate' ? caches.match('./') : Response.error();
    });
  }));
});
