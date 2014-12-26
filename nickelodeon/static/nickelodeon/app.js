var JukeBox = function(swf_path){
  var PLAYING = 1,
      PAUSED = 0,
      HISTORY_MAX_LENGTH = 50,
      SEARCH_RESULTS_PER_PAGE = 50,
      NEXT_RANDOM = 0,
      NEXT_STOP = 1,
      NEXT_FINISH_QUEUE = 2;

  var Song = Backbone.Model.extend({
    idAttribute: "uuid",
    urlRoot : '/api/v1/song',
    defaults: {
      duration: -1
    },
    getDisplayText: function(){
      if(this.get('artist')){
        return [this.get('artist'), this.get('title')].join(' - ');
      }else if(this.get('title')){
        return this.get('title');
      }else{
        return "-";
      }
    }
  });

  var JukeBoxState = Backbone.Model.extend({
    defaults: {
      'playing_state': PAUSED,
      'behaviour': NEXT_RANDOM,
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
      data.play_history = _.map(data.play_history_ids, function(s){return new Song(s);});
      data.play_queue = _.map(data.play_queue_ids, function(s){return new Song(s);});
      delete data.play_history_ids;
      delete data.play_queue_ids;
      this.set(data);
    },
    save: function(){
      var data = _.clone(this.attributes);
      data.play_history_ids = _.map(data.play_history, function(s){return {uuid: s.id, title: s.getDisplayText()};});
      data.play_queue_ids = _.map(data.play_queue, function(s){return {uuid: s.id, title: s.getDisplayText()};});
      delete data.current_song;
      delete data.play_history;
      delete data.play_queue;
      delete data.search_results;
      $.jStorage.set("nickelodeon_options_v2", data);
    },
    toogle_play_pause: function(){
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
      add_to_history = (add_to_history===false)? false: true;
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
      if(avail.aac && (this.get('prefered_format') == 'aac' || !avail.mp3)){
          return 'aac';
      } else if(avail.mp3){
          return 'mp3';
      } else {
          return;
      }
    },
    load_song:function(replace_url){
      this.stop();
      replace_url = (replace_url===false)? false: true;
      router.navigate('/'+this.get('current_song').id, {trigger: false, replace: replace_url});
      var song, auto_play, format, mime;
      auto_play = (this.get('play_state')==PLAYING)? true: false;
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
            };
          })(this)
        });
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
          url: song.get('download_url')+'.'+format+'?;',
          volume: 100,
          autoPlay: auto_play,
          type: mime,
          multiShot: false,
          whileplaying: (function(_this){
            return function(){
              _this.while_playing(this);
            };
          })(this),
          whileloading: (function(_this){
            return function(){
              _this.while_loading(this);
            };
          })(this),
          onload: (function(_this){
            return function(){
              _this.while_loading(this);
            };
          })(this),
          onfinish: (function(_this){
            return function(){
              _this.on_song_finish();
            };
          })(this)
      });
      smsound.load();
    },
    jump_to_time: function(t){
      var  song = this.get('current_song'),
           sound = soundManager.getSoundById(song.id);
      this.set('position', t);
      sound.setPosition(t*1e3);
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
      if(this.get('behaviour') === NEXT_STOP || (this.get('behaviour') && this.get('play_queue').length === 0)){
        this.stop();
        this.set('play_state', PAUSED);
        this.set('behaviour', NEXT_RANDOM);
        this.load_song();
        return;
      }
      this.play_next();
    },
    soundManagerPlaying:function(){
        var sound_id = soundManager.soundIDs[0];
        var sound = soundManager.getSoundById(sound_id);
        if(sound){
          return !sound.paused && sound.playState!==0;
        }
        return false;
    },
    stop:function(){
      soundManager.stopAll();
      while(soundManager.soundIDs.length>0){
        soundManager.destroySound(soundManager.soundIDs[0]);
      }
      this.set('position', 0);
    },
    play_next: function(){
      var next_song = this.pull_queued();
      if(next_song){
        this.switch_song(next_song);
      }else{
        this.fetch_random_song(function(jb, song){
          jb.switch_song(song);
        });
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
            model.set('songs_count', response.count);
            if(response.count > 0){
                var song = new Song(response.results[0]);
                callback(model, song);
            }
          };
        })(this),
        error: function(xhr, tStatus, err){
          if(xhr.status === 404 && page !== 1){
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
        success: (function(_this, _cb){
          return _this.on_search_response(_this, _cb);
        })(this, callback),
        error: (function(_this){
          return _this.on_search_error;
        })(this)
      });
    },
    search_more: function(callback){
      var url = this.get('search_more_link');
      if(!url){
        return;
      }
      $.ajax({
        type: "GET",
        url: url,
        dataType: "JSON",
        success: (function(_this, _cb){
          return _this.on_search_response(_this, _cb);
        })(this, callback),
        error: (function(_this){
          return _this.on_search_error;
        })(this)
      });
    },
    on_search_response: function(_this, callback){
      return function(response){
        _this.set('searching', false);
        _this.set('search_more_link', response.next);
        if(response.results.length > 0){
          var results = _this.get('search_results');
          _this.set('search_results', results.concat(_.map(response.results, function(s){return new Song(s);})));
        }
        if(callback){
          callback();
        }
      };
    },
    on_search_error:function(xhr, tStatus, err){
      // TODO: Do something smart
      console.log('error searching songs for given keyword: '+err);
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
      var queue = _.clone(this.get('play_queue')),
          song = queue.shift();
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
      played = played.slice(0, HISTORY_MAX_LENGTH);
      this.set('play_history', played);
    },
    pull_played: function(){
      var played = _.clone(this.get('play_history')),
          song = played.shift();
      this.set('play_history', played);
      return song;
    },
    switch_behaviour: function(){
      var behav = this.get('behaviour');
      if(behav === NEXT_RANDOM){
        this.set('behaviour', NEXT_FINISH_QUEUE);
      }else if(behav === NEXT_FINISH_QUEUE){
        this.set('behaviour', NEXT_STOP);
      }else{
        this.set('behaviour', NEXT_RANDOM);
      }
    },
    delete_song: function(song){
      var uuid = song.id;
      $.ajax({
        url: '/api/v1/song/'+uuid,
        type: 'DELETE',
        dataType: 'JSON',
      })
    }
  });

  var SearchResultView = Backbone.View.extend({
    tagName: '<tr>',
    template: _.template($('#search_result_template').html()),
    events: {
      'click .song_link': 'press_song_link',
      'click .edit_song_button': 'press_edit_song',
      'click .queue_song_button': 'press_queue_song',
      'click .download_song_button': 'press_download_song',
      'click .delete_song_button': 'press_delete_song'
    },
    initialize: function(options){
      this.player = options.player;
      this.listenTo(this.model, 'change', this.render);
      this.render();
    },
    render: function(){
      this.$el.html(this.template({song: this.model}));
      return this;
    },
    press_song_link: function(e){
      e.preventDefault();
      if(e.ctrlKey){
        this.player.queue_song(this.model);
      } else {
        this.player.switch_song(this.model);
      }
    },
    press_edit_song: function(e){
      e.preventDefault();
      var song = this.model;
      $('#edit_song_modal').on('shown.bs.modal', function (e) {
        $('#edit_song_artist_input').focus();
      });
      // edit fields
      $('#edit_song_artist_input').val(song.get('artist'));
      $('#edit_song_title_input').val(song.get('title'));
      $('#edit_song_filename_input').val(song.get('filename'));
      $('#edit_song_uuid_input').val(song.id);
      // original values
      $('#edit_song_org_artist').val(song.get('artist'));
      $('#edit_song_org_title').val(song.get('title'));
      $('#edit_song_org_filename').val(song.get('filename'));

      $('#saving_song_change_i').hide();
      $("#edit_song_modal").modal('show');
    },
    press_download_song: function(e){
      e.preventDefault();
      window.open(this.model.get('download_url'));
    },
    press_queue_song: function(e){
      e.preventDefault();
      this.player.queue_song(this.model);
    },
    press_delete_song: function(e){
      e.preventDefault();
      var song = this.model;
      if(window.confirm('Are you sure?!')){
        this.player.delete_song(song)
      }
    }
  });

  var PlayedSongView = Backbone.View.extend({
    tagName: '<tr>',
    template: _.template($('#played_song_template').html()),
    events: {
      'click .song_link': 'press_song_link',
      'click .edit_song_button': 'press_edit_song',
      'click .download_song_button': 'press_download_song'
    },
    initialize: function(options){
      this.player = options.player;
      this.listenTo(this.model, 'change', this.render);
      this.render();
    },
    render: function(){
      this.$el.html(this.template({
        song: this.model
      }));
      return this;
    },
    press_song_link: function(e){
      e.preventDefault();
      if(e.ctrlKey){
        this.player.drop_queued(this.order_index);
      } else {
        this.player.switch_song(this.model);
      }
    },
    press_edit_song: function(e){
      e.preventDefault();
      var song = this.model;
      $('#edit_song_modal').on('shown.bs.modal', function (e) {
        $('#edit_song_artist_input').focus();
      });
      // edit fields
      $('#edit_song_artist_input').val(song.get('artist'));
      $('#edit_song_title_input').val(song.get('title'));
      $('#edit_song_filename_input').val(song.get('filename'));
      $('#edit_song_uuid_input').val(song.id);
      // original values
      $('#edit_song_org_artist').val(song.get('artist'));
      $('#edit_song_org_title').val(song.get('title'));
      $('#edit_song_org_filename').val(song.get('filename'));

      $('#saving_song_change_i').hide();
      $("#edit_song_modal").modal('show');
    },
    press_download_song: function(e){
      e.preventDefault();
      window.open(this.model.get('download_url'));
    }
  });

  var QueuedSongView = Backbone.View.extend({
    tagName: '<tr>',
    template: _.template($('#queued_song_template').html()),
    events: {
      'click .song_link': 'press_song_link',
      'click .edit_song_button': 'press_edit_song',
      'click .download_song_button': 'press_download_song',
      'click .move_up_button': 'press_move_up',
      'click .move_down_button': 'press_move_down',
      'click .drop_queued_song_button': 'press_drop_queued_song'
    },
    initialize: function(options){
      this.player = options.player;
      this.order_index = options.order_index;
      this.is_last = options.is_last;
      this.listenTo(this.model, 'change', this.render);
      this.render();
    },
    render: function(){
      this.$el.html(this.template({
        song: this.model,
        is_first: this.order_index===0,
        is_last:this.is_last
      }));
      return this;
    },
    press_song_link: function(e){
      e.preventDefault();
      if(e.ctrlKey){
        this.player.drop_queued(this.order_index);
      } else {
        this.player.switch_song(this.model);
      }
    },
    press_edit_song: function(e){
      e.preventDefault();
      var song = this.model;
      $('#edit_song_modal').on('shown.bs.modal', function (e) {
        $('#edit_song_artist_input').focus();
      });
      // edit fields
      $('#edit_song_artist_input').val(song.get('artist'));
      $('#edit_song_title_input').val(song.get('title'));
      $('#edit_song_filename_input').val(song.get('filename'));
      $('#edit_song_uuid_input').val(song.id);
      // original values
      $('#edit_song_org_artist').val(song.get('artist'));
      $('#edit_song_org_title').val(song.get('title'));
      $('#edit_song_org_filename').val(song.get('filename'));

      $('#saving_song_change_i').hide();
      $("#edit_song_modal").modal('show');
    },
    press_download_song: function(e){
      e.preventDefault();
      window.open(this.model.get('download_url'));
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
  });

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
      "click #open_zippy_modal_button": "on_press_open_zippy_modal",
      "click #download_zippy_button": "on_press_download_zippy",
      "keyup #zippy_url_input": "on_type_zippy_url",
      "click #use_aac_button": "on_press_use_aac",
      "click #use_mp3_button": "on_press_use_mp3",
      "click .search_more_button": "on_press_search_more",
      "click #edit_current_button": "on_press_edit_song",
      "click #download_current_button": "on_press_download_song",
      "click #save_song_change_button": "on_press_save_song_change",
      "click #behaviour_switch_button": "on_press_behaviour_switch"
    },
    initialize: function() {
      this.model.fetch();
      this.listenTo(this.model, "change", this.render);
      this.render({force:true});

      $('body').on(
        'keydown',
        (function(_this){
          return function(e){
            if(document.activeElement.tagName=='INPUT'){
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
              _this.on_press_play_pause(e);
            } else if(e.key=='b' || code==66){
              _this.on_press_prev(e);
            } else if(e.key=='n' || code==78){
              _this.on_press_next(e);
            } else if(e.keyCode=="S".charCodeAt(0)) {
              e.preventDefault();
              $('#search_input').focus();
            }
          };
        })(this)
      );

      $('#current_song_display').hover(function(){ //onmouseenter
        var width = $('#current_song_display').css('width', '100%').width();
        var target_width = $('#current_song_display').css('overflow', 'auto')[0].scrollWidth;
        if(width>target_width){
          return;
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
              };
            })(width)
          }
        );
      },
      function(){ //onmouseleave
      });
    },
    render: function(options) {
      var JB = this.model,
          force,
          results,
          div_template,
          target_div;
      JB.save();
      force = (options.force||false);
      // title
      if(force || JB.changed.current_song || JB.get('current_song').getDisplayText() != $('#current_song_display').html()){
        var title = JB.get('current_song').getDisplayText();
        $('#current_song_display').attr('title', title).html(title);
      }
      // play pause button
      if(JB.soundManagerPlaying()){
        $('#play_pause_button > i')
        .addClass('fa-pause')
        .removeClass('fa-play');
      }else{
        $('#play_pause_button > i')
        .addClass('fa-play')
        .removeClass('fa-pause');
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
          if(t==-1){
            return '?';
          }
          var mf = Math.floor,
              to2digits = function(x){return ('0'+mf(x)).slice(-2);},
              txt = t>3600?mf(t/3600)+':':'';
          txt += to2digits((t/60)%60)+':'+to2digits(t%60);
          return txt;
        };
        var progress_txt = [
          printTime(JB.get('position')),
          printTime(JB.get('current_song').get('duration'))
        ].join('/');
        $('#progress_bar_text').html(progress_txt);
        if(JB.get('current_song').get('duration') != -1){
          var perc = JB.get('position')/JB.get('current_song').get('duration')*100;
          $('#progress_bar').css('width', perc+'%').attr('aria-valuenow', perc);
        }else{
          $('#progress_bar').css('width', '100%').attr('aria-valuenow', '100');
        }
      }
      if(force || JB.changed.behaviour !== undefined){
        target_div = $("#behaviour_switch_button > i");
        target_div.removeClass();
        var behav = JB.get('behaviour');
        if(behav === NEXT_RANDOM){
          target_div.addClass('fa fa-random');
        }else if(behav === NEXT_FINISH_QUEUE){
          target_div.addClass('fa fa-sort-amount-asc');
        }else{
          target_div.addClass('fa fa-minus-circle');
        }
      }
      // history
      if(force || JB.changed.play_history){
        target_div = this.$el.find('#play_history_table');
        results = JB.get('play_history');
        target_div.html('');
        if(results.length > 0){
          _.each(results, function(song){
            var line = new PlayedSongView({
              model:song,
              player:JB
            });
            target_div.append(line.render().el);
          });
        } else {
          div_template = _.template($('#empty_queue_template').html());
          target_div.append($(div_template()));
        }
      }
      // queue
      if(force || JB.changed.play_queue){
        results = JB.get('play_queue');
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
          div_template = _.template($('#empty_queue_template').html());
          target_div.append($(div_template()));
        }
      }
      // Search
      if(force || JB.changed.search_results || JB.changed.search_query || (JB.changed.searching != undefined)){
        results = JB.get('search_results');
        target_div = this.$el.find('#search_results_table');
        target_div.html('');
        if(results.length > 0){
          _.each(results, function(song){
            var line = new SearchResultView({
              model:song,
              player:JB
            });
            target_div.append(line.render().el);
          });
          if(JB.get('search_more_link')){
            div_template = _.template($('#search_more_template').html());
            target_div.append($(div_template({link: JB.get('search_more_link')})));
          }
        } else {
          if(JB.get('searching')===true){
            div_template = _.template($('#search_loading_template').html());
            target_div.append($(div_template({query: JB.get('search_query')})));
          }else{
            div_template = _.template($('#search_no_results_template').html());
            target_div.append($(div_template({query: JB.get('search_query')})));
          }
        }
      }
    },
    on_press_next: function(e){
      e.preventDefault();
      this.model.play_next();
    },
    on_press_prev: function(e){
      e.preventDefault();
      this.model.play_prev();
    },
    on_press_play_pause: function(e){
      e.preventDefault();
      this.model.toogle_play_pause();
    },
    on_press_progress_bar: function(e){
      var perc = (e.pageX - $('#full_progress_bar').offset().left)/$('#full_progress_bar').width(),
          target_time = this.model.get('current_song').get('duration')*perc;
      this.model.jump_to_time(target_time);
    },
    on_type_search: function(e){
      if(e.keyCode == 13){
        this.submit_search();
      }
    },
    on_press_search: function(e){
      this.submit_search();
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
    on_press_edit_song: function(e){
      e.preventDefault();
      var song = this.model.get('current_song');
      $('#edit_song_modal').on('shown.bs.modal', function (e) {
        $('#edit_song_artist_input').focus();
      });
      // edit fields
      $('#edit_song_artist_input').val(song.get('artist'));
      $('#edit_song_title_input').val(song.get('title'));
      $('#edit_song_filename_input').val(song.get('filename'));
      $('#edit_song_uuid_input').val(song.id);
      // original values
      $('#edit_song_org_artist').val(song.get('artist'));
      $('#edit_song_org_title').val(song.get('title'));
      $('#edit_song_org_filename').val(song.get('filename'));

      $('#saving_song_change_i').hide();
      $("#edit_song_modal").modal('show');
    },
    on_press_save_song_change: function(){
      $('#saving_song_change_i').show();
      var artist = $('#edit_song_artist_input').val(),
          title = $('#edit_song_title_input').val(),
          filename = $('#edit_song_filename_input').val(),
          uuid = $('#edit_song_uuid_input').val(),
          update_data = {
            'artist': artist,
            'title': title,
            'filename': filename
 	  },
          data_changed = false;
      // Only send changes
      if(artist != $('#edit_song_org_artist').val() || title != $('#edit_song_org_title').val() || filename != $('#edit_song_org_filename').val()){
        data_changed = true;
      }
      if(data_changed){
        $.ajax({
          url: '/api/v1/song/'+uuid,
          type: 'PUT',
          dataType: 'JSON',
          data: update_data
        }).success(
          function(response){
            $('#edit_song_modal').modal('hide');
            // TODO: Update current, searched, queued, played
          }
        );
      }else{
        $('#edit_song_modal').modal('hide');
      }
    },
    on_press_download_song: function(e){
      e.preventDefault();
      window.open(this.model.get('current_song').get('download_url'));
    },
    on_press_open_yt_modal: function(e){
      e.preventDefault();
      $('#yt_modal').on('shown.bs.modal', function (e) {
        $('#yt_url_input').focus();
      });
      $('#yt_url_input').val('');
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
            {pos: 4, re: /^(https?:\/\/)?(www\.|m\.)?youtube\.com\/watch\?(.*&)?v=([a-zA-Z0-9_-]{11})(&.*)?$/},
            {pos: 2, re: /^(https?:\/\/)?youtu\.be\/([a-zA-Z0-9_-]{11})(\?.*)?$/}
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
        $.ajax(
          {
            url: '/api/v1/youtube_dl/',
            type: 'POST',
            dataType: 'JSON',
            data: {
              video_id: video_id
            }
          }
        ).success(
          function(response){
            $('#yt_modal').modal('hide');
            // TODO: track import process
          }
        );
      } else {
        // TODO: Warn not valid youtube url
      }
    },
    on_press_open_zippy_modal: function(e){
      e.preventDefault();
      $('#zippy_modal').on('shown.bs.modal', function (e) {
        $('#zippy_url_input').focus();
      });
      $('#zippy_url_input').val('');
      $('#download_zippy_submitting_i').hide();
      $("#zippy_modal").modal('show');
    },
    on_press_download_zippy: function(e){
      e.preventDefault();
      this.submit_zippy_download();
    },
    on_type_zippy_url: function(e){
      if(e.keyCode == 13){
        this.submit_zippy_download();
      }
    },
    submit_zippy_download: function(){
      var zippy_url_re = /^http:\/\/www\d{0,2}\.zippyshare\.com\/v\/\d+\/file\.html$/,
          user_val = $('#zippy_url_input').val();
      is_zippy_url = zippy_url_re.test(user_val);
      if(is_zippy_url){
        // TODO: Move away from view
        $('#download_zippy_submitting_i').show();
        $.ajax(
          {
            url: '/api/v1/zippy_dl/',
            type: 'POST',
            dataType: 'JSON',
            data: {
              url: user_val
            }
          }
        ).success(
          function(response){
            $('#zippy_modal').modal('hide');
            // TODO: track import process
          }
        );
      } else {
        // TODO: Warn not valid youtube url
        alert('Invalid URL');
      }
    },
    on_press_use_aac: function(e){
      e.preventDefault();
      this.model.switch_format('aac');
    },
    on_press_use_mp3: function(e){
      e.preventDefault();
      this.model.switch_format('mp3');
    },
    on_press_behaviour_switch: function(e){
      e.preventDefault();
      this.model.switch_behaviour();
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
      preferFlash: false,
      onready: function() {
        // Ready to use; soundManager.createSound() etc. can now be called.
        player = new JukeBoxView();
        if(!Backbone.history.start({
          hasChange: true,
          pushState: true,
          root: "/jukebox/"
        })){
          // No Song playing...
          player.model.play_next();
        }
      }
    });
  };

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
};
