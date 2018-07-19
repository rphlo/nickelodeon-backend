//2018-02-23
var currentSong = null;
var queue = [];
var prefered_format = 'mp3';
var hardcore = false;
var auth_token = null;
var xhr_search = null;
var search_results = [];
var searchTimeout = null;

// IE fixup --
if (!String.prototype.startsWith) {
  String.prototype.startsWith = function(searchString, position) {
    position = position || 0;
    return this.indexOf(searchString, position) === position;
  };
}
$.ajaxSetup({ cache: false });
// --

$(document).ready(function(){
    $('#loading').hide();
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
            playNextSong(autoPlay);
            return;
        }
        console.log('Playing '+this.filename);
        currentSong = this;
        displayCurrentSong();
        stopSounds();
        var mySound = soundManager.createSound({
            url: this.path + '.' + prefered_format+'?auth_token='+auth_token,
            type: 'audio/mpeg',
            onerror: playNextSong
        });
        mySound.play({onfinish: playNextSong, whileplaying: scrollProgressBar});
        if(!autoPlay){
          mySound.pause();
        } else {
          $('#playPauseButton > i').removeClass('fa-play').addClass('fa-pause');
        }
    };
};

var askLogin = function(){
    localStorage.removeItem('auth_token');
    auth_token = null;
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
                               .attr('title', queue[i].filename)
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
        }).fail(function(e){
            if(e.status == 401){
                askLogin();
            }
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
    $('#password').val('');
    displaySearchResults([]);
    displayQueue();
    $('#searchInput').val('');
    $('#seekBar > .progressbarbar').css('width', '100%');
    currentSong = null;
    queue = [];
    prefered_format = 'mp3';
    hardcore = false;
    auth_token = null;
    xhr_search = null;
    search_results = [];
    searchTimeout = null;
    askLogin();
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
        method: 'POST'
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
    if(searchTimeout) {
        clearTimeout(searchTimeout);
    }
    searchTimeout = setTimeout(function(){searchSongs(query)}, 500);
};

var playNextSong = function(autoPlay){
    autoPlay = (typeof autoPlay !== 'undefined') ?  autoPlay : true;
    stopSounds();
    if(queue.length > 0){
        var song = unqueueSong(0);
        song.load(autoPlay);
    }else{
        loadRandomSong(autoPlay);
    }
};

var promptYoutubeURL = function(){
    var url = window.prompt('Enter a Youtube URL');
    if(url===null){
        return;
    }
    var yt_video_id_re = [
        {pos: 1, re: /^([a-zA-Z0-9_\-]{11})$/},
        {pos: 4, re: /^(https?:\/\/)?(www\.|m\.)?youtube\.com\/watch\?(.*&)?v=([a-zA-Z0-9_\-]{11})(&.*)?#?$/},
        {pos: 2, re: /^(https?:\/\/)?youtu\.be\/([a-zA-Z0-9_\-]{11})(\?.*)?#?$/}
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
                url: '/api/youtube-dl/' + video_id,
                type: 'POST',
                headers: {
                  Authorization: 'Token ' + auth_token
                }
            }
        ).done(
            function(response){
                // TODO: track import process
                console.log('Sent intent to download video ' + video_id);
            }
        ).fail(function(e){
            if(e.status == 401){
                askLogin();
            } else {
                alert('Youtube download ' + video_id + ' did not go through...');
            }
        });
    } else {
        alert('Invalid Youtube URL');
    }
};

var queueSong = function(song){
    queue.push(song);
    displayQueue();
};

var printTime = function(t) {
    t = Math.round(t / 1000);
    var h = Math.round(t / 3600);
    var m = Math.round((t % 3600) / 60);
    var s = t % 60;
    return [
        ('0' + h).slice(-2),
        ('0' + m).slice(-2),
        ('0' + s).slice(-2)
    ].join(':');
};

var printTimeProgress = function() {
    var sound_id = soundManager.soundIDs[0];
    var sound = soundManager.getSoundById(sound_id);
    return printTime(sound.position) + '/' + printTime(sound.durationEstimate);
};

var scrollProgressBar = function(){
    var sound_id = soundManager.soundIDs[0];
    var sound = soundManager.getSoundById(sound_id);
    var perc = sound.position/sound.durationEstimate*100;
    $('#seekBar > .progressbarbar').css('width', perc+'%').attr('title', printTimeProgress());
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
    $('#playPauseButton > i').removeClass('fa-pause').addClass('fa-play');
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
    var $playButton = $('#playPauseButton > i');
    if($playButton.hasClass('fa-play')) {
        $playButton.removeClass('fa-play').addClass('fa-pause');
    } else {
        $playButton.removeClass('fa-pause').addClass('fa-play');
    }
    soundManager.togglePause(sound_id);
};

var unqueueSong = function(index){
    var songs = queue.splice(index, 1);
    displayQueue();
    return songs[0];
};
