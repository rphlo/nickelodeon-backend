self.addEventListener('install', function(e){
 e.waitUntil(
   caches.open('humppakone').then(function(cache){
     return cache.addAll([
       '/',
       '/index.html',
       '/index.js',
       '/index.css',
       '/static/background.mp4',
       '/static/background.webm'
     ]);
   })
 );
});
