var JukeBox = function(swf_path){
  var PLAYING = 1,
      PAUSED = 0,
      HISTORY_MAX_LENGTH = 50,
      SEARCH_RESULTS_PER_PAGE = 50,
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
      'prefered_format': 'mp3',
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
    switch_song: function(song, add_to_history){
      add_to_history = add_to_history===false?false:true;
        console.log("----------", song, add_to_history, this.get('current_song'))
      if(add_to_history && this.get('current_song')){
        this.set_played(this.get('current_song'));
      }
      this.set('current_song', song);
      this.load_song();
    },
    get_current_format: function(){
      var song = this.get('current_song'),
          avail = null;
      if(!song){
        return;
      }
      avail = song.get('availability');
      if(!avail){
        return;
      }
      if(avail['aac'] && (this.get('prefered_format') == 'aac' || !avail['mp3'])){
          return 'aac';
      } else if(avail['mp3']){
          return 'mp3';
      } else {
          return;
      }
    },
    load_song:function(replace_url){
      this.stop();
      console.log('loading song '+this.get('current_song').id)
      replace_url = replace_url===null?true:replace_url;
      router.navigate('/'+this.get('current_song').id, {trigger: false, replace:replace_url})
      var song, auto_play, format, mime;
      auto_play = (this.get('play_state')==PLAYING)?true:false;
      song = this.get('current_song');
      if(!song){
        this.play_next();
        return;
      }
      if(!song.get('download_url')){
        song.fetch({
          success: (function(_this){
            return function(model, response, options){
              _this.set('current_song', model);
              _this.load_song(false);
            }
          })(this)
        })
        return;
      }
      format = this.get_current_format();
      if(!format){
        this.play_next();
        return;
      }
      mime = {mp3: 'audio/mpeg', aac: 'audio/aac'}[format];
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
      smsound.load();
    },

    jump_to_time: function(t){
      var  song = this.get('current_song'),
           sound = soundManager.getSoundById(song.id);
      this.set('position', t);
      sound.setPosition(t*1e3);
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
      var next_song = this.pull_queued();
      if(next_song){
        this.switch_song(next_song);
      }else{
        this.fetch_random_song(function(jb, song){jb.switch_song(song)});
        this.stop();
      }
    },
    play_prev: function(){
      var prev_song = this.pull_played();
      if(prev_song){
        this.queue_next(this.get('current_song'));    
        this.switch_song(prev_song, false);
      }
    },
    fetch_random_song: function(callback, page){
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
                callback(model, song);
            }
          }
        })(this),
        error: function(xhr, tStatus, err){
          console.log('error fetching random song: '+err)
          if(xhr.status === 404 && current_index !== 1){
            this.fetch_random_song(callback, 1);
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
      var url = this.get('search_more_link');
      if(!url){
        return
      }
      $.ajax({
        type: "GET",
        url: url,
        dataType: "JSON",
        success: (function(_this, _cb){return _this.on_search_response(_this, _cb)})(this, callback),
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
    queue_next: function(song){
      var queue = _.clone(this.get('play_queue'));
      queue.unshift(song);
      this.set('play_queue', queue);
    },
    queue_song: function(song){
      var queue = _.clone(this.get('play_queue'));
      queue.push(song);
      this.set('play_queue', queue);
    },
    pull_queued: function(){
      var queue = _.clone(this.get('play_queue'));
      song = queue.pop();
      this.set('play_queue', queue);
      return song;
    },
    drop_queued: function(order_index){
      var queue = _.clone(this.get('play_queue'));
      queue.splice(order_index, 1);
      this.set('play_queue', queue);
    },
    swap_queued: function(index_a, index_b) {
      var queue = _.clone(this.get('play_queue')),
          temp = queue[index_a];
      if(index_a < 0 || index_a >= queue.length || index_b < 0 || index_b >= queue.length){
        return;
      }
      queue[index_a] = queue[index_b];
      queue[index_b] = temp;
      this.set('play_queue', queue);
    },
    move_queued_up: function(index){
      this.swap_queued(index-1, index);
    },
    move_queued_down: function(index){
      this.swap_queued(index+1, index);
    },
    switch_format: function(fmt){
      this.set('prefered_format', fmt);
      if(this.get_current_format != fmt){
          var pos = this.get('position');
          this.load_song();
          this.jump_to_time(pos);
      }
    },
    set_played: function(song){
      var played = _.clone(this.get('play_history'));
      played.unshift(song);
      played.slice(0, HISTORY_MAX_LENGTH);
      this.set('play_history', played);
    },
    pull_played: function(){
      var played = _.clone(this.get('play_history'));
      var song = played.shift();
      this.set('play_history', played);
      return song
    }
  });
  var SearchResultView = Backbone.View.extend({
    tagName: '<tr>',
    template: _.template($('#search_result_template').html()),
    events: {
      'click .song_link': 'press_song_link',
      'click .edit_song_button': 'press_edit_song',
      'click .queue_song_button': 'press_queue_song'
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
    press_song_link: function(e){
      e.preventDefault();
      if(e.ctrlKey){
        this.player.queue_song(this.model);
      } else {
        this.player.switch_song(this.model);
      }
    },
    press_edit_song: function(e){
      e.preventDefault();
    },
    press_queue_song: function(e){
      e.preventDefault();
      this.player.queue_song(this.model);
    }
  });
  var PlayedSongView = Backbone.View.extend({
    tagName: '<tr>',
    template: _.template($('#played_song_template').html()),
    initialize: function(options){
      this.player = options.player
      this.listenTo(this.model, 'change', this.render);
      this.render()
    },
    render: function(){
      this.$el.html(this.template({
        song: this.model
      }));
      return this
    }
  });
  var QueuedSongView = Backbone.View.extend({
    tagName: '<tr>',
    template: _.template($('#queued_song_template').html()),
    events: {
      'click .song_link': 'press_song_link',
      'click .edit_song_button': 'press_edit_song',
      'click .move_up_button': 'press_move_up',
      'click .move_down_button': 'press_move_down',
      'click .drop_queued_song_button': 'press_drop_queued_song'
    },
    initialize: function(options){
      this.player = options.player
      this.order_index = options.order_index;
      this.is_last = options.is_last;
      this.listenTo(this.model, 'change', this.render);
      this.render()
    },
    render: function(){
      this.$el.html(this.template({
        song: this.model,
        is_first: this.order_index===0,
        is_last:this.is_last
      }));
      return this
    },
    press_song_link: function(e){
      e.preventDefault()
      if(e.ctrlKey){
        this.player.drop_queued(this.order_index);
      } else {
        this.player.switch_song(this.model)
      }
    },
    press_edit_song: function(e){
      e.preventDefault();
      console.log('edit song '+this.model.id);
    },
    press_move_up: function(e){
      e.preventDefault();
      this.player.move_queued_up(this.order_index);
    },
    press_move_down: function(e){
      e.preventDefault();
      this.player.move_queued_down(this.order_index);
    },
    press_drop_queued_song: function(e){
      e.preventDefault();
      this.player.drop_queued(this.order_index);
    }
  })
  var JukeBoxView = Backbone.View.extend({
    el: $('#jukebox_div'),
    model: new JukeBoxState(),
    events: {
      "click #play_pause_button": "on_press_play_pause",
      "click #next_button": "on_press_next",
      "click #prev_button": "on_press_prev",
      "click #full_progress_bar": "on_press_progress_bar",
      "keyup #search_input": "on_type_search",
      "click #search_button": "on_press_search",
      "click #open_yt_modal_button": "on_press_open_yt_modal",
      "click #download_yt_button": "on_press_download_yt",
      "keyup #yt_url_input": "on_type_yt_url",
      "click #use_aac_button": "on_press_use_aac",
      "click #use_mp3_button": "on_press_use_mp3",
      "click .search_more_button": "on_press_search_more"
    },
    initialize: function() {
      this.model.fetch();
      this.listenTo(this.model, "change", this.render);
      this.render({force:true});
      $('#current_song_display').hover(function(){
        var width = $('#current_song_display').css('width', '100%').width();
        var target_width = $('#current_song_display').css('overflow', 'auto')[0].scrollWidth;
        if(width>target_width){
          return
        }
        $('#current_song_display').css('overflow', 'hidden');
        $('#current_song_display').css('text-overflow', 'ellipsis');
        $('#current_song_display').stop().animate(
          {
            'width': (target_width+5)+'px',
            'margin-left': (width-target_width)+'px'
          },
          {
            duration: (target_width-width)/50*1000,
            complete: (function(){
              return function(_w){
                setTimeout(
                  function(){
                    $('#current_song_display').stop().animate({
                      'width': _w,
                      'margin-left': '0px',
                      overflow: 'hidden',
                      'text-overflow': 'ellipsis'
                    },
                    {
                      complete: function(){
                        $('#current_song_display').attr('style', 'white-space:nowrap; display: block; overflow: hidden; text-overflow:ellipsis');
                      }
                    });
                  },
                  1000
                );
              }
            })(width)
          }
        )
      },
      function(){
      });
    },
    render: function(options) {
      //console.log('rendering')
      var JB = this.model;
          force = options.force||false;
      console.log(JB.changed)
      // title
      if(force || JB.changed.current_song || JB.get('current_song').getDisplayText() != $('#current_song_display').html()){
        var title = JB.get('current_song').getDisplayText();
        $('#current_song_display').attr('title', title).html(title);
      }
      // play pause button
      if(JB.soundManagerPlaying()){
        $('#play_pause_button > i').addClass('fa-pause').removeClass('fa-play')
      }else{
        $('#play_pause_button > i').addClass('fa-play').removeClass('fa-pause')
      }
      // format selector
      if(JB.get_current_format()){
        if(JB.get_current_format() == 'mp3' && !$('#use_mp3_button').hasClass('active')){
          $('#use_mp3_button').addClass('active');
          $('#use_aac_button').removeClass('active');
        } else if(JB.get_current_format() == 'aac' && !$('#use_aac_button').hasClass('active')){
          $('#use_aac_button').addClass('active');
          $('#use_mp3_button').removeClass('active');
        }
      }
      if(force || JB.get('current_song') && JB.get('current_song').get('availability')){
        var avail = JB.get('current_song').get('availability') || {};
        _.each(['mp3', 'aac'], function(fmt){
          if(avail[fmt]===true){
            if($('#use_'+fmt+'_button').hasClass('disabled')){
              $('#use_'+fmt+'_button').removeClass('disabled');
            }
          } else if(!$('#use_'+fmt+'_button').hasClass('disabled')){
            $('#use_'+fmt+'_button').addClass('disabled');
          }
        });
      }
      // progress bar
      if(force || JB.changed.position !== undefined || JB.get('current_song') && JB.get('current_song').changed.duration !== undefined){
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
      if(force || JB.changed.play_history){
        var results = JB.get('play_history'),
            target_div = this.$el.find('#play_history_table');
        console.log(results)
        target_div.html('');
        if(results.length > 0){
          _.each(results, function(song, order_index){
            var line = new PlayedSongView({
              model:song,
              player:JB
            });
            target_div.append(line.render().el);
          });
        } else {
          var template = _.template($('#empty_queue_template').html());
          target_div.append($(template()));
        }
      }
      if(force || JB.changed.play_queue){
        var results = JB.get('play_queue'),
            target_div = this.$el.find('#play_queue_table');
        target_div.html('');
        if(results.length > 0){
          _.each(results, function(song, order_index){
            var line = new QueuedSongView({
              model:song,
              player:JB,
              order_index: order_index,
              is_last: (results.length-1==order_index)
            });
            target_div.append(line.render().el);
          });
        } else {
          var template = _.template($('#empty_queue_template').html());
          target_div.append($(template()));
        }
      }
      if(force || JB.changed.search_results || JB.changed.search_query || JB.changed.searching){
        var results = JB.get('search_results'),
            target_div = this.$el.find('#search_results_table');
        target_div.html('')
        if(results.length > 0){
          _.each(results, function(song_data){
            var line = new SearchResultView({
              model:new Song(song_data),
              player:JB
            });
            target_div.append(line.render().el);
          });
          if(JB.get('search_more_link')){
            var template = _.template($('#search_more_template').html());
            target_div.append($(template({link: JB.get('search_more_link')})));
          }
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
    on_press_next: function(e){
      e.preventDefault()
      this.model.play_next();
    } ,
    on_press_prev: function(e){
      e.preventDefault()
      this.model.play_prev();
    },
    on_press_play_pause: function(e){
      e.preventDefault()
      this.model.toogle_play_pause();
    },
    on_press_progress_bar: function(e){
      var perc = (e.pageX - $('#full_progress_bar').offset().left)/$('#full_progress_bar').width(),
          target_time = this.model.get('current_song').get('duration')*perc;
      this.model.jump_to_time(target_time);
    },
    on_type_search: function(e){
      if(e.keyCode == 13){
        this.submit_search()
      }
    },
    on_press_search: function(e){
      this.submit_search()
    },
    submit_search: function(){
      var keyword = this.$el.find('#search_input').val();
      this.model.search_songs(keyword);
      $('#search_tab').removeClass('hidden').tab('show');
    },
    on_press_search_more: function(e){
      e.preventDefault();
      this.model.search_more();
    },
    on_press_open_yt_modal: function(e){
      e.preventDefault();
      $('#yt_modal').on('shown.bs.modal', function (e) {
        $('#yt_url_input').val('').focus();
      });
      $('#download_yt_submitting_i').hide();
      $("#yt_modal").modal('show');
    },
    on_press_download_yt: function(e){
      e.preventDefault();
      this.submit_yt_download();
    },
    on_type_yt_url: function(e){
      if(e.keyCode == 13){
        this.submit_yt_download();
      }
    },
    submit_yt_download: function(){
      var yt_video_id_re = [
            {pos: 1, re: /^([a-zA-Z0-9_-]{11})$/},
            {pos: 3, re: /^(https?:\/\/)?www\.youtube\.com\/watch\?(.*&)?v=([a-zA-Z0-9_-]{11})(&.*)?$/},
            {pos: 2, re: /^(https?:\/\/)?youtu\.be\/([a-zA-Z0-9_-]{11})(\?.*)?$/},
          ],
          video_id = null,
          user_val = $('#yt_url_input').val();
      video_id = _.filter(_.map(yt_video_id_re, function(re){
        if(re.re.test(user_val)){
          return user_val.match(re.re)[re.pos];
        }
      }))[0];
      if(video_id){
        // TODO: Move away from view
        $('#download_yt_submitting_i').show();
        $.ajax({
          url: '/api/v1/youtube_dl/',
          type: 'POST',
          dataType: 'JSON',
          data: {video_id: video_id}
        }).success(
          function(response){
            $('#yt_modal').modal('hide');
          }
        );
      } else {
        // TODO: Warn not valid youtube url
      }
    },
    on_press_use_aac: function(e){
      e.preventDefault();
      this.model.switch_format('aac');
    },
    on_press_use_mp3: function(e){
      e.preventDefault();
      this.model.switch_format('mp3');
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
          player.model.play_next();
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
      player.model.switch_song(new Song({uuid: song_uuid}), false);
    }
  }))();
  init();
}
