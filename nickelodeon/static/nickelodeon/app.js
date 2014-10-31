var JukeBox = function(swf_path){
  var PLAYING = 1,
      PAUSED = 0,
      HISTORY_MAX_LENGTH = 20,
      SEARCH_RESULTS_PER_PAGE = 20,
      ongoing_search_request = null
      state = null;

  var Song = Backbone.Model.extend({
    idAttribute: "uuid",
    urlRoot : '/api/v1/song',
    defaults: {
      duration: -1
    },
    getDisplayText: function(){
      if(this.get('artist')){
        return [this.get('artist'), this.get('title')].join(' - ')
      }else if(this.get('title')){
        return this.get('title')
      }else{
        return "Unknown"
      }
    }
  });

  var JukeBoxState = Backbone.Model.extend({
    defaults: {
      'playing_state': PAUSED,
      'stop_after_current': false,
      'stop_after_playlist': false,
      'songs_count': 0,
      'play_history': [],
      'play_queue': [],
      'search_results': [],
      'prefered_format': 'aac',
      'position': 0,
      'loaded': 0,
      'current_song': new Song()
    },
    fetch: function(){
      var data = $.jStorage.get("nickelodeon_options_v2", this.defaults);
      console.log(data)
    },
    save: function(){
      var data = _.clone(this.attributes);
      delete data['current_song']
      $.jStorage.set("nickelodeon_options_v2", data);
    },
    fetchCurrentSong: function(on_success, on_error){
      console.log('fetch current song')
      var song = new Song({
        'uuid':this.get('current_song_uuid')
      });
      song.fetch({
        success:(function(_this){
          return function(model, response, options){
            _this.set('current_song', model);
            if(on_success){
              on_success();
            }
          }
        })(this),
        error: function(){
          if(on_error){
            on_error();
          }
        }
      });
    },
    toogle_play_pause: function(){
      console.log('toogle play pause')
      var sound_id = soundManager.soundIDs[0];
      if(this.get('play_state') == PLAYING){
        soundManager.pause(sound_id);
        this.set('play_state', PAUSED);
      }else{
        this.set('play_state', PLAYING);
        soundManager.play(sound_id);
      }
    },
    switch_song: function(song){
      this.set('current_song', song);
      this.load_song();
    },
    load_song:function(replace_url){
      this.stop();
      console.log('loading song '+this.get('current_song').id)
      replace_url = replace_url===null?true:replace_url;
      router.navigate('/'+this.get('current_song').id, {trigger: false, replace:replace_url})
      var song, avail, auto_play, format, mime;
      auto_play = (this.get('play_state')==PLAYING)?true:false;
      song = this.get('current_song');
      avail = song.get('availability');
      if(!avail){
        console.log('nope')
        song.fetch({
          success: (function(_this){
            return function(model, response, options){
              _this.set('current_song', model);
              _this.load_song(false);
              console.log('ok' + model.getDisplayText());
            }
          })(this)
        })
        return
      }
      if(avail['aac'] && (this.get('prefered_format') == 'aac' || !avail['mp3'])){
          format = 'aac'
          mime = 'audio/aac'
      } else if(avail['mp3']){
          format = 'mp3'
          mime = 'audio/mpeg'
      } else {
          console.log('song not available')
          this.play_next();
          return;
      }
      console.log('autoplay '+auto_play)
      var smsound = soundManager.createSound({
          id: song.id,
          url: song.get('download_url')+'.'+format,
          volume: 100,
          autoPlay: auto_play,
          type: mime,
          multiShot: false,
          whileplaying: (function(_this){
            return function(){
              _this.while_playing(this);
            }
          })(this),
          whileloading: (function(_this){
            return function(){
              _this.while_loading(this);
            }
          })(this),
          onload: (function(_this){
            return function(){
              _this.while_loading(this);
            }
          })(this),
          onfinish: (function(_this){
            return function(){
              _this.on_song_finish();
            }
          })(this)
      });
      smsound.load()
    },

    jump_to_time: function(t){
      var  song = this.get('current_song'),
           sound = soundManager.getSoundById(song.id);
      this.set('position', t);
      sound.setPosition(t*1000);
      console.log('jump to time '+t)
    },

    while_playing: function(sound){
      var song = this.get('current_song');
      this.set('position', sound?sound.position/1e3:0);
      song.set('duration', sound?sound.durationEstimate/1e3:0);
    },

    while_loading: function(sound){
      var song = this.get('current_song');
      song.set('duration', sound.durationEstimate/1e3);
      this.set('loaded', +new Date());
    },

    on_song_finish: function(){
      console.log('song finished');
      if(this.get('stop_after_current')){
        this.stop();
        this.set('play_state', PAUSED);
        this.set('stop_after_current', false)
        this.load_song();
        return;
      }
      this.play_next();
    },

    soundManagerPlaying:function(){
        var sound_id = soundManager.soundIDs[0];
        var sound = soundManager.getSoundById(sound_id)
        if(sound){
          return !sound.paused && sound.playState!=0;
        }
        return false
    },

    stop:function(){
      console.log('stop');
      soundManager.stopAll();
      while(soundManager.soundIDs.length>0){
        soundManager.destroySound(soundManager.soundIDs[0]);
      }
      this.set('position', 0);
    },

    play_next: function(){
      console.log('play_next')
      var queue = this.get('play_queue');
      if(queue.length > 0){
        var next_song = queue.shift();
        this.switch_song(next_song);
        console.log(this.get('play_queue'));
      }else{
        this.fetchRandomSong(function(jb){jb.load_song()});
        this.stop();
      }
    },

    play_prev: function(){
      console.log('play_prev')
    },

    fetchRandomSong: function(callback, page){
      console.log('fetching random')
      var index = page || Math.floor(Math.random()*this.get('songs_count'))+1;
      $.ajax({
        type: "GET",
        url: "/api/v1/songs/",
        data: {
          'results_per_page': 1, 
          'page': Math.max(1, index)
        },
        dataType: "JSON",
        success: (function(model){
          return function(response){
            console.log('fetched random song')
            model.set('songs_count', response.count);
            if(response.count > 0){
                var song = new Song(response.results[0])
                model.set('current_song', song);
                callback(model, response);
            }
          }
        })(this),
        error: function(xhr, tStatus, err){
          console.log('error fetching random song: '+err)
          if(xhr.status === 404 && current_index !== 1){
            this.fetchRandomSong(callback, 1);
          } else if(xhr.status === 403) {
            window.reload();
          }
        }
      });
    },
    search_songs: function(keyword, callback){
      this.set('search_query', keyword);
      this.set('search_more_link', null);
      this.set('search_results', []);
      this.set('searching', true);
      $.ajax({
        type: "GET",
        url: "/api/v1/songs/",
        data: {
          'q': keyword,
          'results_per_page': SEARCH_RESULTS_PER_PAGE,
          'page': 1
        },
        dataType: "JSON",
        success: (function(_this, _cb){return _this.on_search_response(_this, _cb)})(this, callback),
        error: (function(_this){return _this.on_search_response;})(this)
      });
    },
    search_more: function(callback){
      this.set('searching', true);
      var url = this.get('search_more_link');
      if(!url){
        return
      }
      $.ajax({
        type: "GET",
        url: "/api/v1/songs/",
        dataType: "JSON",
        success: (function(_this){return _this.on_search_response(_this, _cb)})(this, callback),
        error: (function(_this){return _this.on_search_response;})(this)
      });
    },
    on_search_response: function(_this, callback){
      return function(response){
        _this.set('searching', false);
        _this.set('search_more_link', response.next);
        if(response.results.length>0){
          var results = _this.get('search_results');
          _this.set('search_results', results.concat(response.results));
          console.log(_this.get('search_results'))
        }
        if(callback){
          callback()
        }
      }
    },
    on_search_error:function(xhr, tStatus, err){
      console.log('error searching songs for given keyword: '+err)
    },
    queue_song: function(song){
      this.get('play_queue').push(song);
      console.log(this.get('play_queue'))
    }
  });
  var SearchResultView = Backbone.View.extend({
    tagName: '<tr>',
    template: _.template($('#search_result_template').html()),
    events: {
      'click .link_song': 'press_play_song',
      'click .edit_song': 'press_edit_song',
      'click .queue_song': 'press_queue_song'
    },
    initialize: function(options){
      this.player = options.player
      this.listenTo(this.model, 'change', this.render);
      this.render()
    },
    render: function(){
      this.$el.html(this.template({song: this.model}));
      return this
    },
    press_play_song: function(e){
      e.preventDefault()
      console.log('play song '+this.model.id)
      this.player.switch_song(this.model)
    },
    press_edit_song: function(e){
      e.preventDefault()
      console.log('edit song '+this.model.id)
    },
    press_queue_song: function(e){
      e.preventDefault();
      console.log('queue song '+this.model.id);
      this.player.queue_song(this.model);
    }
  })

  var JukeBoxView = Backbone.View.extend({
    el: $('#jukebox_div'),
    model: new JukeBoxState(),
    events: {
      "click #play_pause_button": "press_play_pause",
      "click #next_button": "press_next",
      "click #prev_button": "press_prev",
      "click #full_progress_bar": "press_progress_bar",
      "keyup #search_input": "type_search",
      "click #search_button": "press_search",
    },
    initialize: function() {
      this.model.fetch();
      this.listenTo(this.model, "change", this.render);
      this.render();
    },
    render: function() {
      //console.log('rendering')
      var JB = this.model;
      console.log(JB.changed)
      // title
      if(JB.changed.current_song || JB.get('current_song').getDisplayText() != $('#current_song_display').html()){
        $('#current_song_display').html(JB.get('current_song').getDisplayText());
      }
      // play pause button
      if(JB.soundManagerPlaying()){
        $('#play_pause_button > i').addClass('fa-pause').removeClass('fa-play')
      }else{
        $('#play_pause_button > i').addClass('fa-play').removeClass('fa-pause')
      }
      // progress bar
      if(JB.changed.position !== undefined || JB.get('current_song') && JB.get('current_song').changed.duration !== undefined){
        var printTime = function(t){
          if(t==-1){ return '?'}
          var mf = Math.floor,
              to2digits = function(x){return ('0'+mf(x)).slice(-2);},
              txt = t>3600?mf(t/3600)+':':'';
          txt += to2digits((t/60)%60)+':'+to2digits(t%60);
          return txt;
        }
        var progress_txt = [
          printTime(JB.get('position')),
          printTime(JB.get('current_song').get('duration'))
        ].join('/');
        $('#progress_bar_text').html(progress_txt);
        if(JB.get('current_song').get('duration') != -1){
          var perc = JB.get('position')/JB.get('current_song').get('duration')*100;
          $('#progress_bar').css('width', perc+'%').attr('aria-valuenow', perc);
        }else{
          $('#progress_bar').css('width', '100%').attr('aria-valuenow', perc);
        }
      }
      if(JB.changed.search_results || JB.changed.search_query || JB.changed.searching!==undefined){
        var result_template = _.template($('#search_result_template').html()),
            results = JB.get('search_results'),
            target_div = this.$el.find('#search_results_table');
        target_div.html('');
        if(results.length > 0){
            _.each(results, function(song_data){
              var line = new SearchResultView({
                model:new Song(song_data),
                player:JB
              });
              target_div.append(line.render().el);
            })
        } else {
          if(JB.get('searching')===true){
            var template = _.template($('#search_loading_template').html());
            target_div.append($(template({query: JB.get('search_query')})));
          }else{
            var template = _.template($('#search_no_results_template').html());
            target_div.append($(template({query: JB.get('search_query')})));
          }
        }
      }
    },
    press_next: function(e){
      e.preventDefault()
      this.model.play_next();
    } ,
    press_prev: function(e){
      e.preventDefault()
      this.model.play_prev();
    },
    press_play_pause: function(e){
      e.preventDefault()
      this.model.toogle_play_pause();
    },
    press_progress_bar: function(e){
      var perc = (e.pageX - $('#full_progress_bar').offset().left)/$('#full_progress_bar').width(),
          target_time = this.model.get('current_song').get('duration')*perc;
      this.model.jump_to_time(target_time);
    },
    type_search: function(e){
      if(e.keyCode == 13){
        this.submit_search()
      }
    },
    press_search: function(e){
      this.submit_search()
    },
    submit_search: function(){
      var keyword = this.$el.find('#search_input').val();
      this.model.search_songs(keyword);
      $('#search_tab').tab('show');
    }
  });
  var player = null;

  var init = function(){
    if(!this instanceof JukeBox){
      return new JukeBox(swf_path);
    }
    soundManager.setup({
      url: swf_path,
      flashVersion: 9, // optional: shiny features (default = 8)
      // optional: ignore Flash where possible, use 100% HTML5 mode
      // preferFlash: false,
      onready: function() {
        // Ready to use; soundManager.createSound() etc. can now be called.
        console.log('SM2 ready')
        player = new JukeBoxView();
        if(!Backbone.history.start({
          hasChange: true,
          pushState: true,
          root: "/jukebox/"
        })){
          // No Song playing...
          console.log('Player initialized pick random')
          player.press_next()
        };
      }
    });
  }
  var router = new (Backbone.Router.extend({
    initialize: function(options){
      // Matches /<uuid>/,
      this.route(/^([a-zA-Z0-9]{22})/, "playSong");
    },
    playSong: function(song_uuid){
      player.model.stop();
      player.model.switch_song(new Song({uuid: song_uuid}));
    }
  }))();
  init();
}

