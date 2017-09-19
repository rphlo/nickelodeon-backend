self.addEventListener('install', function(e){
 e.waitUntil(
   caches.open('lomalaskuri').then(function(cache){
     return cache.addAll([
       '/',
       '/index.html',
       '/background.gif'
     ]);
   })
 );
});