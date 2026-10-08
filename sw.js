/* Service worker d'Agenda : garde les fichiers de l'appli sur le téléphone pour qu'elle s'ouvre sans internet.
   Il ne touche jamais aux données (elles sont dans IndexedDB). Il ne remplace JAMAIS une version tout seul :
   la nouvelle version attend (« waiting ») jusqu'à ce que Pascal touche « Mettre à jour ».
   Règles qui évitent de mélanger deux versions :
   - la réserve porte le numéro de version (« agenda-<version> ») ;
   - l'installation est « tout ou rien » : tous les fichiers sont d'abord téléchargés EN MÉMOIRE, vérifiés, puis écrits d'un coup ; au moindre
     fichier manquant l'installation échoue et l'ancienne version reste entière ;
   - une fois actif, ce service worker ne sert QUE sa propre réserve (jamais celle d'une autre version) ;
   - l'ancienne réserve n'est effacée qu'APRÈS la prise de contrôle des pages. */
importScripts('version.js');

var CACHE = 'agenda-' + self.APP_VERSION;
var FILES = ['./', 'index.html', 'garde.js', 'db.js', 'rides.js', 'fuel.js', 'mots.js', 'sauvegarde.js', 'app.js', 'style.css', 'version.js', 'manifest.json', 'icon-192.png', 'icon-512.png'];
function abs(u) { return new URL(u, self.registration.scope).href; }

self.addEventListener('install', function (e) {
  /* cache:'reload' = on prend les fichiers frais sur le site, pas ceux que le navigateur aurait gardés */
  e.waitUntil(Promise.all(FILES.map(function (u) {
    return fetch(new Request(abs(u), { cache: 'reload' })).then(function (r) {
      if (!r.ok) throw new Error(u + ' : ' + r.status);
      return r.blob().then(function (b) { return { u: u, blob: b, init: { status: r.status, statusText: r.statusText, headers: r.headers } }; });
    });
  })).then(function (items) {                                       /* tout est arrivé : on écrit d'un coup */
    return caches.open(CACHE).then(function (c) {
      return Promise.all(items.map(function (it) { return c.put(abs(it.u), new Response(it.blob, it.init)); }));
    }).catch(function (er) { return caches.delete(CACHE).then(function () { throw er; }); });
  }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(self.clients.claim().then(function () {
    return caches.keys();
  }).then(function (keys) {                                          /* seulement maintenant : les pages sont à nous, on efface les anciennes réserves */
    return Promise.all(keys.filter(function (k) { return k.indexOf('agenda-') === 0 && k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }));
});

/* la réserve contient-elle TOUS les fichiers de cette version ? */
function complete() {
  return caches.open(CACHE).then(function (c) {
    return c.keys().then(function (ks) {
      var have = {}; ks.forEach(function (k) { have[k.url] = 1; });
      var missing = FILES.filter(function (u) { return !have[abs(u)]; });
      return { ok: missing.length === 0, version: self.APP_VERSION, missing: missing };
    });
  });
}

self.addEventListener('message', function (e) {
  var d = e.data || {};
  if (d.type === 'SKIP_WAITING') self.skipWaiting();                 /* seulement quand Pascal l'a demandé */
  else if (d.type === 'VERIFY' && e.ports && e.ports[0]) {          /* la page demande si la réserve est complète avant de se recharger */
    var port = e.ports[0];
    complete().then(function (r) { port.postMessage(r); }, function () { port.postMessage({ ok: false, version: self.APP_VERSION, missing: ['?'] }); });
  }
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;                    /* rien ne sort : aucune autre adresse n'est utilisée */
  if (url.search.indexOf('ag_net=') >= 0) return;                      /* test de connexion de la page (« ag_net ») : directement vers le site, jamais la réserve */
  e.respondWith(caches.open(CACHE).then(function (c) {                /* SA réserve seulement, jamais celle d'une autre version */
    return c.match(req, { ignoreSearch: true }).then(function (hit) {
      if (hit) return hit;
      return fetch(req).catch(function () {
        return req.mode === 'navigate' ? c.match('./') : Response.error();
      });
    });
  }));
});
