var VERSION_NAME = 'humppakone_v2018022303'
self.addEventListener('install', function(e){
 var timeStamp = Date.now();
 e.waitUntil(
   caches.open(VERSION_NAME).then(function(cache){
     return cache.addAll([
       '/',
       'index.html?ts='+timeStamp,
       'index.js?ts='+timeStamp,
       'index.css?ts='+timeStamp,
       'background.mp4?ts='+timeStamp,
       'background.webm?ts='+timeStamp
     ]).then(function(){self.skipWaiting()});
   })
 );
});

self.addEventListener('activate', function(event){
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function(event){
  event.respondWith(
    caches.match(event.request, {ignoreSearch: true, cacheName: VERSION_NAME}).then(function(response){
      return response || fetch(event.request);
    })
  );
});
