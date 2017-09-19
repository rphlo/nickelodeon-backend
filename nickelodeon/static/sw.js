self.addEventListener('install', function(e){
 e.waitUntil(
   caches.open('humppakone').then(function(cache){
     return cache.addAll([
       '/',
       '/index.html',
       '/static/background.gif'
     ]);
   })
 );
});