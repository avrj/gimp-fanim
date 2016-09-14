#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
  Copyright (C) 2016, Douglas Knowman
  douglasknowman@gmail.com

  Distributed under the terms of GNU GPL v3 (or lesser GPL) license.

FAnim
Timeline

"""
from gimpfu import gimp,pdb
import pygtk
pygtk.require('2.0')
import gtk, numpy, threading, time
gtk.threads_init()

WINDOW_TITLE = "GIMP FAnim Timeline [%s]"
# playback macros
NEXT = 1
PREV = 2
END = 3
START = 4
NOWHERE = 5

class Utils:
    @staticmethod
    def button_stock(stock,size):
        """
        Return a button with a image from stock items 
        """
        b = gtk.Button()
        img = gtk.Image()
        img.set_from_stock(stock,size)
        b.set_image(img)
        return b

    @staticmethod
    def toggle_button_stock(stock,size):
        """
        Return a button with a image from stock items 
        """
        b = gtk.ToggleButton()
        img = gtk.Image()
        img.set_from_stock(stock,size)
        b.set_image(img)
        return b

class PlayThread(threading.Thread):
    def __init__(self,timeline,play_button):
        threading.Thread.__init__(self)
        self.timeline = timeline
        self.play_button = play_button
        self.cnt = 0

    def run(self):
        while  self.timeline.is_playing:
            time.sleep((1.0/self.timeline.frames_per_second) + self.timeline.frames_time)

            if not self.timeline.is_replay and self.timeline.active >= len(self.timeline.frames)-1:
                self.timeline.on_toggle_play(self.play_button)

            self.timeline.on_goto(None,NEXT)


class AnimFrame(gtk.EventBox):
    def __init__(self,layer,width=100,height=120):
        gtk.EventBox.__init__(self)
        self.set_size_request(width,height)
        #variables
        self.thumbnail = None
        self.label = None
        self.layer = layer

        self._setup()

    def highlight(self,state):
        if state:
            self.set_state(gtk.STATE_SELECTED)
        else :
            self.set_state(gtk.STATE_NORMAL)

    def _setup(self):
        self.thumbnail = gtk.Image()
        self.label = gtk.Label(self.layer.name)

        frame = gtk.Frame()
        layout = gtk.VBox()
        # add frame to this widget
        self.add(frame)

        # add layout manager to the frame
        frame.add(layout)

        layout.pack_start(self.label)
        layout.pack_start(self.thumbnail)
        self._get_thumb_image()

    def _get_thumb_image(self):
        """
        convert the pixel info returned by python into a gtk image to be
        showed.
        """
        width = 100
        height = 100
        image_data = pdb.gimp_drawable_thumbnail(self.layer,width,height)
        w,h,c = image_data[0],image_data[1],image_data[2]
        # create a 2d array to store the organized data.
        p2d = [[[0 for z in range(c)] for x in range(w)] for y in range(h)]

        # looping through all pixels of the thumbnail and organize it.
        x = y = z = 0  # x and y coordenate and the color z
        for i in range(image_data[3]):
            p2d[y][x][z] = image_data[4][i]
            z += 1
            if z >= c: #if color reach the max 3 or 4 channesl (rgb and a)
                z = 0
                x += 1
                if x >= w:
                    x = 0
                    y += 1
        ##
        image_array = numpy.array(p2d,dtype=numpy.uint8)
        pixbuf = gtk.gdk.pixbuf_new_from_array(image_array,gtk.gdk.COLORSPACE_RGB,8)
        self.thumbnail.set_from_pixbuf(pixbuf)

    def update_layer_info(self):
        self._get_thumb_image()


class Timeline(gtk.Window):
    def __init__(self,title,image):
        gtk.Window.__init__(self,gtk.WINDOW_TOPLEVEL)

        self.set_title(title)
        self.image = image
        self.frame_bar = None
        # variables
        self.is_playing = False
        self.is_replay = False
        # modifiable widgets
        self.play_button_images = []
        self.widgets_to_disable = [] # widgets to disable when playing
        
        # frames
        self.frames = []
        self.selected = []
        self.active = None

        self.frames_per_second = 30
        self.frames_time = 0.01

        # onionskin variables
        self.onionskin_enabled = False
        self.onionskin_depth = 2
        self.onionskin_backward = True
        self.onionskin_forward = False
        self.onionskin_opacity = 50.0
        self.onionskin_opacity_decay = 20.0
        self.onionskin_disable_on_play= True

        self.play_thread = None

        # create all widgets
        self._setup_widgets()

    def destroy(self,widget):
        gtk.main_quit()

    def start(self):
        gtk.main()

    def _setup_widgets(self):
        """
        create all the window staticaly placed widgets.
        """
        # basic window definitions
        self.connect("destroy",self.destroy)
        self.set_default_size(400,140)
        self.set_keep_above(True)

        # start creating basic layout
        base = gtk.VBox()

        # commands bar widgets
        cbar = gtk.HBox()
        cbar.pack_start(self._setup_playbackbar(),False,False,10)
        cbar.pack_start(self._setup_editbar(),False,False,10)
        cbar.pack_start(self._setup_timebar(),False,False,10)
        cbar.pack_start(self._setup_onionskin(),False,False,10)
        cbar.pack_start(self._setup_generalbar(),False,False,10)

        # frames bar widgets
        self.frame_bar = gtk.HBox()
        scroll_window = gtk.ScrolledWindow()
        scroll_window.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        scroll_window.add_with_viewport(self.frame_bar)
        scroll_window.set_size_request(-1,140)

        # mount the widgets together
        base.pack_start(cbar,False,False,0)
        base.pack_start(scroll_window,True,True,0)
        self.add(base)
        
        # catch all layers
        self._scan_image_layers()

        # finalize showing all widgets
        self.show_all()

    def _scan_image_layers(self):
        layers = self.image.layers
        #layers.reverse()
        for layer in layers:
            f = AnimFrame(layer)
            self.frame_bar.pack_start(f,False,True,2)
            self.frames.append(f)

        if len(self.frames) > 0:
            self.active = 0
            self.on_goto(None,START)

    def _setup_playbackbar(self):
        playback_bar = gtk.HBox()
        button_size = 30
        stock_size = gtk.ICON_SIZE_BUTTON

        # play button
        ## image
        image_play = gtk.Image()
        image_play.set_from_stock(gtk.STOCK_MEDIA_PLAY,stock_size)
        image_pause = gtk.Image()
        image_pause.set_from_stock(gtk.STOCK_MEDIA_PAUSE,stock_size)
        ## append the images to a list to be used later on
        self.play_button_images.append(image_play)
        self.play_button_images.append(image_pause)
        ## button
        b_play = gtk.Button()
        b_play.set_image(image_play)
        b_play.set_size_request(button_size,button_size)

        b_tostart = Utils.button_stock(gtk.STOCK_MEDIA_PREVIOUS,stock_size)
        b_toend = Utils.button_stock(gtk.STOCK_MEDIA_NEXT,stock_size)
        b_prev = Utils.button_stock(gtk.STOCK_MEDIA_REWIND,stock_size)
        b_next = Utils.button_stock(gtk.STOCK_MEDIA_FORWARD,stock_size)

        b_repeat = Utils.toggle_button_stock(gtk.STOCK_REFRESH,stock_size)

        # connecting the button with callback
        b_play.connect('clicked',self.on_toggle_play)
        b_repeat.connect('toggled',self.on_replay)

        b_next.connect('clicked',self.on_goto,NEXT,True)
        b_prev.connect('clicked',self.on_goto,PREV,True)
        b_toend.connect('clicked',self.on_goto,END,True)
        b_tostart.connect('clicked',self.on_goto,START,True)


        # add to the disable on play list
        w = [b_repeat,b_prev,b_next,b_tostart,b_toend]
        map(lambda x: self.widgets_to_disable.append(x),w)

        # set the tooltips
        b_play.set_tooltip_text("Animation play/pause")
        b_repeat.set_tooltip_text("Animation replay active/deactive")
        b_prev.set_tooltip_text("To the previous frame")
        b_next.set_tooltip_text("To the next frame")
        b_tostart.set_tooltip_text("To the start frame")
        b_toend.set_tooltip_text("To the end frame")
        
        # packing everything in gbar
        playback_bar.pack_start(b_tostart,False,False,0)
        playback_bar.pack_start(b_prev,False,False,0)
        playback_bar.pack_start(b_play,False,False,0)
        playback_bar.pack_start(b_next,False,False,0)
        playback_bar.pack_start(b_toend,False,False,0)
        playback_bar.pack_start(b_repeat,False,False,0)

        return playback_bar

    def _setup_editbar(self):
        stock_size = gtk.ICON_SIZE_BUTTON
        edit_bar = gtk.HBox()
        
        b_back = Utils.button_stock(gtk.STOCK_GO_BACK,stock_size)
        b_forward = Utils.button_stock(gtk.STOCK_GO_FORWARD,stock_size)
        b_rem = Utils.button_stock(gtk.STOCK_REMOVE,stock_size)
        b_add = Utils.button_stock(gtk.STOCK_ADD,stock_size)

        # add to the disable on play list
        w = [b_back,b_forward,b_rem,b_add]
        map(lambda x: self.widgets_to_disable.append(x),w)

        # packing everything in gbar
        map(lambda x: edit_bar.pack_start(x,False,False,0),w)

        return edit_bar

    def _setup_timebar(self):
        stock_size = gtk.ICON_SIZE_BUTTON
        time_bar = gtk.HBox()

        b_time = Utils.button_stock(gtk.STOCK_PROPERTIES,stock_size)

        self.widgets_to_disable.append(b_time)

        time_bar.pack_start(b_time,False,False,0)
        return time_bar

    def _setup_onionskin(self):
        stock_size = gtk.ICON_SIZE_BUTTON
        button_size = 30
        onionskin_bar = gtk.HBox()

        # active onionskin
        b_active = Utils.toggle_button_stock(gtk.STOCK_DND_MULTIPLE,stock_size)

        # connect widgets
        b_active.connect("clicked",self.on_onionskin)

        # add to the disable on play list
        w = [b_active]
        map(lambda x: self.widgets_to_disable.append(x),w)

        # packing everything in gbar
        map(lambda x: onionskin_bar.pack_start(x,False,False,0),w)

        return onionskin_bar

    def _setup_generalbar(self):
        stock_size = gtk.ICON_SIZE_BUTTON
        general_bar = gtk.HBox()

        b_about = Utils.button_stock(gtk.STOCK_ABOUT,stock_size)
        b_export = Utils.button_stock(gtk.STOCK_CONVERT,stock_size)
        b_quit = Utils.button_stock(gtk.STOCK_QUIT,stock_size)

        # callbacks
        b_quit.connect('clicked',self.destroy)

        # add to the disable on play list
        w = [b_about, b_export, b_quit]
        map(lambda x: self.widgets_to_disable.append(x),w)

        # packing everything in gbar
        map(lambda x: general_bar.pack_start(x,False,False,0),w)

        return general_bar

#----------------------Callback Functions----------------#

    def on_toggle_play(self,widget):
        """
        This method change the animation play state,
        change the button image and will disable/enable the other buttons
        interation.
        for that they need 2 image which is stored in self.play_button_images
        variable.
        """
        # if onionskin on play is disable then disable remaining frames
        if self.onionskin_disable_on_play:
            self.layers_show(False)

        self.is_playing = not self.is_playing

        if self.is_playing:
            widget.set_image(self.play_button_images[1]) # set pause image to the button

            # start the thread to make the changes on the frames in background
            self.play_thread = PlayThread(self,widget)
            self.play_thread.start()
        else :
            widget.set_image(self.play_button_images[0])

        # loop through all playback bar children to disable interation
        for w in self.widgets_to_disable:
            w.set_sensitive(not self.is_playing)

    def on_replay(self,widget):
        self.is_replay = widget.get_active()

    def on_onionskin(self,widget):
        self.layers_show(False) # clear remaining onionskin frames
        self.onionskin_enabled = widget.get_active()
        self.on_goto(None,NOWHERE,True)

    def on_goto(self,widget,to,update=False):
        """
        This method change the atual active frame to when the variable
        (to) indicate, the macros are (START, END, NEXT, PREV)
        - called once per frame when is_playing is enabled.
        """
        self.layers_show(False)

        if update:
            self.frames[self.active].update_layer_info()

        if to == START:
            self.active = 0

        elif to == END:
            self.active = len(self.frames)-1

        elif to == NEXT:
            i = self.active + 1
            if i > len(self.frames)-1:
                i = 0
            self.active = i

        elif to == PREV:
            i = self.active - 1
            if i < 0:
                i= len(self.frames)-1
            self.active = i

        self.layers_show(True)
        self.image.active_layer = self.frames[self.active].layer
        gimp.displays_flush() # update the gipms displays to show de changes.

    def layers_show(self,state):
        """
        Util function to hide the old frames and show the next.
        """
        opacity = 0

        self.frames[self.active].layer.opacity = 100.0

        if not state:
            opacity = 100.0
        else :
            opacity = self.onionskin_opacity

        self.frames[self.active].layer.visible = state # show or hide the frame
        self.frames[self.active].highlight(state) # highlight or not the frame


        if self.onionskin_enabled and not(self.is_playing and self.onionskin_disable_on_play):
            # calculating the onionskin backward and forward
            for i in range(1,self.onionskin_depth +1):

                if self.onionskin_backward:
                    pos = self.active - i
                    if pos >= 0:
                        # calculate onionskin depth opacity decay.
                        o = opacity - i * self.onionskin_opacity_decay
                        self.frames[pos].layer.visible = state
                        self.frames[pos].layer.opacity = o

                if self.onionskin_forward:
                    pos = self.active +i
                    self.frames[self.active].layer.opacity = opacity

                    if pos <= len(self.frames)-1:
                        # calculate onionskin depth opacity decay.
                        o = opacity - i * self.onionskin_opacity_decay
                        self.frames[pos].layer.visible = state
                        self.frames[pos].layer.opacity = o

def timeline_main(image,drawable):
    global WINDOW_TITLE
    WINDOW_TITLE = WINDOW_TITLE % (image.name)
    win = Timeline(WINDOW_TITLE,image)
    win.start()
