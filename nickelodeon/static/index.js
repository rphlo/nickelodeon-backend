var currentSong = null;
var queue = [];
var prefered_format = 'mp3';
var hardcore = false;
var auth_token = null;
var xhr_search = null;
var search_results = [];

$(document).ready(function(){
    auth_token = localStorage.getItem("auth_token");
    if(auth_token){
        startJukebox();
    } else {
        askLogin();
    }
    $('#seekBar').on('click', onClickSeekSong);

    $('body').on(
        'keydown',
        (function(_this){
          return function(e){
            if(document.activeElement.tagName=='INPUT' || !auth_token){
              return;
            }
            if(!e){
              e = window.event;
            }
            var code = e.keyCode;
            if(e.charCode && code === 0){
              code = e.charCode;
            }
            if(e.key=='Spacebar' || code==32){
              e.preventDefault();
              togglePause();
            } else if(e.key=='n' || code==78){
              playNextSong();
            } else if(e.keyCode=="S".charCodeAt(0)) {
              e.preventDefault();
              $('#searchInput').focus().select();
            }
          };
        })(this)
    );

    $('#currentTitle').on('click', function(e){
        e.preventDefault();
        if(e.ctrlKey){
            editSong(currentSong);
        }
    });
});

var Song = function(id, path, filename){
    this.set_filename = function(filename){
        this.filename = filename;
        var title_matches = filename.match(/[^\/]+$/);
        this.title = title_matches[0];
    };

    this.id = id;
    this.path = path;
    this.set_filename(filename);


    this.load = function(autoPlay){
        autoPlay = (typeof autoPlay !== 'undefined') ?  autoPlay : true;
        if(!hardcore && this.filename.startsWith('rphl/Happy Hardcore/')){
            playNextSong();
            return;
        }
        console.log('Playing '+this.filename);
        currentSong = this;
        displayCurrentSong();
        var mySound = soundManager.createSound({
            url: this.path + '.' + prefered_format+'?auth_token='+auth_token
        });
        mySound.play({onfinish: playNextSong, whileplaying: scrollProgressBar});
        if(!autoPlay){
          mySound.pause();
        }
    };
};

var askLogin = function(){
    $('#login').show();
    $('#jukebox').hide();
};

var displayCurrentSong = function(){
    $('#currentTitle').text(currentSong.title).attr('title', currentSong.filename);
};

var displayQueue = function() {
    var $div = $('#queuedSongs');
    if(queue.length === 0){
        $div.text('-');
    }else{
        $div.html('');
        var handleUnqueueSong = function(index){
          return function(ev){
            ev.preventDefault();
            unqueueSong(index);
          };
        };
        var handleEditSong = function(song){
          return function(ev){
            ev.preventDefault();
            if(ev.ctrlKey){
              editSong(song);
              return;
            }
            stopSounds();
            song.load();
          };
        };
        for(var i=0; i < queue.length; i++){
            var ndiv = $('<div>');
            ndiv.append($('<a>').attr('href', '#')
                                .text('[x]')
                                .on('click', handleUnqueueSong(i)))
                .append(' ')
                .append($('<a>').attr('href', '#')
                               .text(queue[i].title)
                               .attr('title', queue[i].path)
                               .on('click', handleEditSong(queue[i])));
            $div.append(ndiv);
        }
    }
};

var displaySearchResults = function(){
    var results = search_results;
    var $resdiv = $('#searchResults');
    $resdiv.html('');
    var handleQueueSong = function(song){
      return function(ev){
        ev.preventDefault();
        queueSong(song);
      };
    };
    var handleEditSong = function(song){
      return function(ev){
        ev.preventDefault();
        if(ev.ctrlKey){
          editSong(song);
          return;
        }
        stopSounds();
        song.load();
      };
    };
    for(var i=0; i < results.length; i++){
        var ndiv = $('<div>');

        ndiv.append($('<a>').attr('href', '#')
                               .text('[q]')
                               .on('click', handleQueueSong(results[i])))
            .append(' ')
            .append($('<a>').attr('href', '#')
                            .text(results[i].title)
                            .attr('title', results[i].filename)
                            .on('click', handleEditSong(results[i])));
            $resdiv.append(ndiv);
    }
};

var editSong = function(song){
    var new_path = window.prompt('new file path', song.filename);
    if(new_path && new_path != song.filename){
        $.ajax({
            url: '/api/songs/'+song.id,
            method: 'PATCH',
            data: {filename: new_path},
            dataType: 'JSON',
            headers: {
              Authorization: 'Token ' + auth_token
            }
        }).done(function(e){
            console.log('filename changed to ' + new_path);
            song.set_filename(new_path);
            displayCurrentSong();
            displayQueue();
            displaySearchResults();
        });
    }
};

var loadRandomSong = function(autoPlay){
    autoPlay = (typeof autoPlay !== 'undefined') ?  autoPlay : true;
    $.ajax({
        url: 'api/songs/random',
        method: 'GET',
        dataType: 'json',
        headers: {
          Authorization: 'Token ' + auth_token
        }
    }).done(function(song_info){
        var song = new Song(song_info.id, song_info.download_url, song_info.filename);
        console.log('Loaded random song');
        song.load(autoPlay);
    }).fail(function(e){
        if(e.status == 401){
            askLogin();
        }
    });
};

var logout = function(){
    stopSounds();
    $.ajax({
        url: '/api/auth/logout/',
        method: 'POST',
        headers: {
          Authorization: 'Token ' + auth_token
        }
    }).done(function(e){
        console.log('logged out, token removed');
    });
    askLogin();
    localStorage.setItem("auth_token", null);
    $('#password').val('');
    displaySearchResults([]);
    queue = [];
    displayQueue();
    $('#searchInput').val('');
    auth_token = null;
};

var onClickSeekSong = function(e){
    console.log('Seek song');
    var perc = e.pageX/$('#seekBar').width();
    var sound_id = soundManager.soundIDs[0];
    var sound = soundManager.getSoundById(sound_id);
    if(sound){
        var target_time = sound.durationEstimate*perc;
        seekSong(target_time);
    }
};

var onLogin = function(){
    var username = $('#username').val();
    var password = $('#password').val();
    $.ajax({
        url: '/api/auth/login/',
        data: {
            username: username,
            password: password
        },
        dataType: 'json',
        method: 'POST',
    }).done(function(e){
        auth_token = e.token;
        localStorage.setItem("auth_token", auth_token);
        startJukebox();
    }).fail(function(){
        $('#password').val('');
    });
};

var onSearchInputChange = function(){
    var query = $('#searchInput').val();
    searchSongs(query);
};

var playNextSong = function(){
    stopSounds();
    if(queue.length > 0){
        queue[0].load();
        unqueueSong(0);
    }else{
        loadRandomSong();
    }
};

var promptYoutubeURL = function(){
    var url = window.prompt('Enter a Youtube URL');
    if(url===null){
        return;
    }
    var yt_video_id_re = [
        {pos: 1, re: /^([a-zA-Z0-9_\-]{11})$/},
        {pos: 4, re: /^(https?:\/\/)?(www\.|m\.)?youtube\.com\/watch\?(.*&)?v=([a-zA-Z0-9_\-]{11})(&.*)?$/},
        {pos: 2, re: /^(https?:\/\/)?youtu\.be\/([a-zA-Z0-9_\-]{11})(\?.*)?$/}
    ];
    var video_id = null;
    video_id = yt_video_id_re.map(function(re){
        if(re.re.test(url)){
            return url.match(re.re)[re.pos];
        }
    }).filter(function(el){return !!el;})[0];
    if(video_id){
        $.ajax(
            {
                url: '/api/youtube-dl/'+video_id,
                type: 'POST',
                headers: {
                  Authorization: 'Token ' + auth_token
                }
            }
        ).done(
            function(response){
                // TODO: track import process
                console.log('Sent intent to download video '+video_id);
            }
        );
    } else {
        alert('Invalid Youtube URL');
    }
};

var queueSong = function(song){
    queue.push(song);
    displayQueue();
};

var scrollProgressBar = function(){
    var sound_id = soundManager.soundIDs[0];
    var sound = soundManager.getSoundById(sound_id);
    var perc = sound.position/sound.durationEstimate*100;
    $('#seekBar > .progressbarbar').css('width', perc+'%');
};

var searchSongs = function(query){
    if(xhr_search){
        xhr_search.abort();
    }
    $('#searchResults').html('<i class="fa fa-circle-o-notch fa-spin fa-fw"></i><span class="sr-only">Loading...</span>');
    xhr_search = $.ajax({
        url: 'api/songs/',
        data: {'q': query},
        method: 'GET',
        dataType: 'json',
        headers: {
          Authorization: 'Token ' + auth_token
        }
    }).done(function(songs){
        xhr_search = null;
        console.log('Found '+songs.length+' match');
        search_results = [];
        for(var i=0; i<songs.length; i++){
            search_results.push(new Song(songs[i].id, songs[i].download_url, songs[i].filename));
        }
        displaySearchResults();
    }).fail(function(e){
        if(e.status == 401){
            askLogin();
        }
        $('#searchResults').html('');
    });
};

var seekSong = function(time){
    var sound_id = soundManager.soundIDs[0];
    soundManager.setPosition(sound_id, time);
};

var startJukebox = function(){
    $('#login').hide();
    $('#jukebox').show();
    soundManager.setup({
      url: 'https://cdnjs.cloudflare.com/ajax/libs/soundmanager2/2.97a.20150601/swf/',
      flashVersion: 9,
      preferFlash: false,
      onready: function() {
        if(auth_token){
          loadRandomSong(false);
        }
      }
    });
};

var stopSounds = function(){
    soundManager.stopAll();
    while(soundManager.soundIDs.length>0){
        soundManager.destroySound(soundManager.soundIDs[0]);
    }
};

var toggleHardcore = function(){
    if(hardcore){
        $('#hardcoreSwitch').html('<i class="fa fa-heart-o"></i>');
    }else{
        $('#hardcoreSwitch').html('<i class="fa fa-heartbeat"></i>');
    }
    hardcore = !hardcore;
};

var togglePause = function(){
    var sound_id = soundManager.soundIDs[0];
    soundManager.togglePause(sound_id);
};

var unqueueSong = function(index){
    queue.splice(index, 1);
    displayQueue();
};