# *****************************************************************************
#       Project: ZBVR - Zion Brock Vintage Radio
#  Project Repo: https://github.com/mloit/zbvr-firmware
#         About: Baseline firmware for the Zion Brock Vintage Radio 
#
#          File: main.py
#       Version: 26.0.1 Alpha
#   Description: main application logic for the Vintage Radio Firmware
# 
#        Author: Mark Loit
#        Credit: Zion Brock (Original code and inspiration)
#
#       License: CC BY-NC-SA
# 
#  (c) Copyright 2026 Mark Loit. All Rights Reserved.
# ****************************************************************************
# Baseline 26.0.1 - Retro Radio 
#
#
# Notes:
# - Total refactor of Zion's original "5.9.1" code 
# - Modularized most things to make it more maintainable 
# - Centralized configuration settings into 'config.py'
# - Added bi-directional communications with the DFPlayer
# - Removed need for blind searching if another track or folder exists
# - Added generation of the playlist at boot to only have folders with valid tracks to prevent lockups
#   - Altered to be semi-background to speed up startup time. Playlist is slowly populated between 
#     track and folder changes, until folder count is met, or all files have been accounted for
# - Added colours to various states to give more visual feedback
# - made the button monitoring timer based, to simplify the main loop
# - converted the main loop into a state machine
# - added exception handling to main, to clean up nicely on a crash or when Thonny stops the program
# - added handling of live SD card removal and insertion
# - added ability to change the equalizer setting
# - WAV playback can now fade in and out for softer edge transitions
# - Album change can now fade out & back in with the WAV playback for a smoother transition
# - added support for large folders (4 digit filename). Folders with 256 tracks or more can only be
#   in the range of 01-15. The folder must have more than 255 tracks for the code to automatically
#   switch to using 4 digit names.
#   - folders outside the 1-15 range are artifically capped to 255 files during playlist generation
# - Added support for track and album randomization
# - added "all tracks" shuffle, when enabled long-press reshuffles and starts over instead of advancing album
# - added a quickstart mode to do background scanning for albums in order to get faster boot time

# Known issues:
# - if there is a gap in folder names, some folders after the gaps may be missed in the scan as we only scan
#   the number of reported folders
#   -- solution: folder names cannot be skipped, but folders can be left empty, to ensure all used folders
#      are scanned and used

# TODO:
# - use exception bubbling to handle common/repeated code conditions, when the normal flow needs to break
#   - handle "offline" to prompt the reset code from the main loop, instead of repeating in each state
#   - handle "not found" in normal playback to trigger a rescan of the media


import micropython
import time, machine
from machine import Pin, I2C

# enable optimizations for all our code
micropython.opt_level(3)
micropython.alloc_emergency_exception_buf(100)

from config import App, Config
from led import LED
from audioplayer import WAV
from dfplayer import DFPlayer, DFequalizer_strings, DFequalizer
from controls import Controls
from playlist import Playlist

_VERSION = "26.0.1 BETA"

lev = micropython.opt_level()
print(f"\nMicroPython Optimization Level: {lev}")
micropython.mem_info()

print("\nInitiailzing Modules")

if Config.LED.ENABLE:
    led = LED(Config.LED.PIN)
    led.color(Config.LED.DEFAULT)

# initialize the sense GPIO's
power_sense = Pin(Config.Sense.PIN, Pin.IN, Pin.PULL_DOWN)

# not used anymore, initialized anyway to prevent side-effects
pin_busy    = Pin(Config.Busy.PIN, Pin.IN, Pin.PULL_DOWN)  

# configure the DFPlayer module
dfp = DFPlayer(Config.DFPlayer.UART.UNIT, 
               tx = Config.DFPlayer.UART.Pins.TX, 
               rx = Config.DFPlayer.UART.Pins.RX)

# configure the button control module
button = Controls(Config.Button.PIN, 
                  pull        = Config.Button.PULL,
                  invert      = Config.Button.INVERT, 
                  rate        = Config.Button.RATE, 
                  debounce    = Config.Button.DEBOUNCE, 
                  tap_gap     = Config.Button.TAP_GAP,
                  short_press = Config.Button.SHORT_PRESS, 
                  long_press  = Config.Button.LONG_PRESS)

# configure I2C if used
if Config.I2C.ENABLE:
    i2c = I2C(Config.I2C.UNIT, 
              sda  = Config.I2C.Pins.SDA, 
              scl  = Config.I2C.Pins.SCL, 
              freq = Config.I2C.RATE)

# ****************************************************************************
# Playlist Handling
# ****************************************************************************
playlist = Playlist(advance_folder = App.Playlist.CYCLE_ALBUMS, 
                    shuffle_albums = App.Playlist.ALBUM_SHUFFLE, 
                    shuffle_tracks = App.Playlist.TRACK_SHUFFLE,
                    shuffle_all    = App.Playlist.FULL_SHUFFLE,
                    auto_reshuffle = App.Playlist.AUTO_RESHUFFLE)

# state vars for managing/restiring the playlist between sessions
restore_playlist = False
dfp_folders      = -1     # number of folders reported on disk
dfp_tracks       = -1     # number of tracks reported on disk
is_scanning      = False  # flag set if background folder scan is in progress
scan_index       = 0      # current folder index of scan
scan_remain      = 0      # number of remaining files to be found

# Dynamically determines the playlist from the contents of the SD 
def generate_playlist(folders = -1, files = -1):
    global is_scanning, scan_index, scan_remain

    # turn off background scan if we end up in here
    is_scanning = False
    scan_index  = 0
    scan_remain = 0

    if files == -1:
        files = dfp.get_total_files()

    if files == 0:
        print("SDCard has no files")
        return

    if folders == -1:
        folders = dfp.get_folder_count()

    if folders == 0:
        print("SDCard has no folders")
        return

    print("Discovering playlist")
    print("Scanning: ", end="")
    
    for dir in range(folders):
        tracks = dfp.get_file_count(dir + 1)

        if tracks:
            print("+", end="")

            # only folders 1-15 can have more than 255 tracks
            if (dir > 14) and (tracks > 255):
                tracks = 255

            playlist.add(dir+1, tracks, ((dir & 1) == 1) and App.Playlist.ALTERNATE_SHUFFLE)
            files -= tracks
        else:
            print(".",end="")
        if files == 0:
            print("!",end="")
            break
    print("")
    playlist.prepare()
    display_playlist()

# visually displays the playlist contents
def display_playlist():
    albums = playlist.get_albums()
    tracks = playlist.get_total_tracks()
    print(f"playlist contains {albums} albums and a total of {tracks} tracks")
    pl = playlist.all()
    for entry in pl:
        print(f"album: {entry[0]:02d} - {entry[1]} tracks [{entry[2]}]")


# functions for background playlist scanning
# initialize the background scanning
def scan_init(folders = -1, files = -1):
    global is_scanning, scan_index, scan_remain, dfp_tracks, dfp_folders
    if files == -1:
        files = dfp.get_total_files()

    if files == 0:
        print("SDCard has no files")
        return

    if folders == -1:
        folders = dfp.get_folder_count()

    if folders == 0:
        print("SDCard has no folders")
        return

    if is_scanning: # if flag set, we attempt to resume the scan
        print("Resuming Discovery")
        return

    print("Discovering playlist (background scan)")
    dfp_tracks  = files
    dfp_folders = folders
    scan_remain = files
    scan_index  = 0
    is_scanning = True


# keeps scanning until one album is found
def scan_find():
    global is_scanning, scan_index, scan_remain, dfp_tracks, dfp_folders

    print("Scanning: ", end="")
    for dir in range(scan_index, dfp_folders):
        tracks = dfp.get_file_count(dir + 1)
        scan_index = dir + 1
        if tracks:
            print("+", end="")
            # only folders 1-15 can have more than 255 tracks
            if (dir > 14) and (tracks > 255):
                tracks = 255

            playlist.add(dir+1, tracks, ((dir & 1) == 1) and App.Playlist.ALTERNATE_SHUFFLE)
            scan_remain -= tracks
            break
        else:
            print(".",end="")
    print("")
    if (scan_remain == 0) or (scan_index >= dfp_folders):
        print("Playlist Discovery complete")
        is_scanning = False

# checks a single album candidate
def scan_one():
    global is_scanning, scan_index, scan_remain, dfp_tracks, dfp_folders

    print("Probing: ", end="")
    dir = scan_index
    scan_index += 1
    tracks = dfp.get_file_count(dir + 1)
    
    if tracks:
        print("+")
        # only folders 1-15 can have more than 255 tracks
        if (dir > 14) and (tracks > 255):
            tracks = 255

        playlist.add(dir+1, tracks, ((dir & 1) == 1) and App.Playlist.ALTERNATE_SHUFFLE)
        scan_remain -= tracks
    else:
        print(".")

    if (scan_remain == 0) or (scan_index >= dfp_folders):
        print("Playlist Discovery complete")
        is_scanning = False

# ****************************************************************************
# State Machine
# ****************************************************************************
#state machine constants
class State:
    IDLE        = 0  # Idle state, Potentiometer in off poosition (Next: POWER_UP)
    WARM_BOOT   = 1  # power was on, send a reset to the DFPlayer
    BOOT        = 2  # Potentiometer just turned on Wait for DFPlayer to boot (Next: START_UP)
    MEDIA_CHECK = 3  # Check and wait for SD Card
    START_UP    = 5  # Initialize playlist, start first track
    PLAY_TRACK  = 6  # Normal run state, plays to the end of the track
    PLAY_NEXT   = 7  # normal advance to next track
    NEXT_ALBUM  = 8  # special advance where effect is played at transition
    MEDIA_WAIT  = 9  # SD Card was reoved, waiting for insertion
    MEDIA_LOAD  = 10 # SD Card was inserted, reload and resume playback
    POWER_DN    = 11 # Potentiometer just turned off (Next: IDLE)

app_state = State.IDLE
states = {}

# break longer waits into smaller parts to allow background tasks to run
def app_wait(duration):
    if duration  > App.Timing.STEP:
        time.sleep_ms(App.Timing.STEP)
        duration -= App.Timing.STEP
    time.sleep_ms(duration)

# ****************************************************************************
# states should accept one parameter assumed to be "next"
# Idle state loop body
# power is off
def app_idle(last):
    if last != State.IDLE:
        print("Waiting for Power On (potentiometer)")
        if Config.LED.ENABLE:
            led.color(App.Colors.IDLE)

    if power_sense.value() == 1:
        print("Power On Detected")
        return State.BOOT

    last_hint = time.ticks_ms()
    while power_sense.value() == 0:
        if time.ticks_diff(time.ticks_ms(), last_hint) > App.Timing.HINT:
            print(" - waiting for power on")
            return State.IDLE
        app_wait(App.Timing.MAIN)
    return State.IDLE

states[State.IDLE] = app_idle

# ****************************************************************************
# power was turned on, wait for DFPlayer to boot. 
def app_boot(last):
    if last != State.BOOT:
        print("Waiting for DFPlayer to come online")
        if Config.LED.ENABLE:
            led.color(App.Colors.WAITING)
    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN
    if dfp.is_online():
        print("DFPlayer online, ready to proceed")
        return State.MEDIA_CHECK
    
    return State.BOOT

states[State.BOOT] = app_boot

# ****************************************************************************
# DFPlayer is booted, check for media, wait if necessary
def app_media_check(last):

    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN

    if last != State.MEDIA_CHECK:
        no_card = not dfp.has_sdc()
        print("SDCard ", end="")
        if no_card:
            print("NOT ", end="")
        print("present")

        if no_card:
            print("Waiting for SDCard insertion")
            if Config.LED.ENABLE:
                led.color(App.Colors.WAITING)
            return State.MEDIA_CHECK
        return State.START_UP

    last_hint = time.ticks_ms()
    while not dfp.has_sdc():

        if power_sense.value() == 0:
            print("Power Off Detected")
            return State.POWER_DN

        if time.ticks_diff(time.ticks_ms(), last_hint) > App.Timing.HINT:
            print(" - still waiting SDCard insertion")
            return State.MEDIA_CHECK
        app_wait(App.Timing.MAIN)

    print("SDCard inserted")
    if Config.LED.ENABLE:
        led.color(App.Colors.IDLE)

    return State.START_UP

states[State.MEDIA_CHECK] = app_media_check

# ****************************************************************************
# Generate the playlist
# Get first track playing with AMRadio effect
# button handler set-up on exit
# non looping, one pass, and it advances
def app_start_up(last):
    global dfp_folders, dfp_tracks, is_scanning

    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN
    if last == State.START_UP:
        return State.PLAY_TRACK

    folders = dfp.get_folder_count()
    total = dfp.get_total_files()

    print("Filesystem has", total, "files in", folders, "folders")
    #time.sleep_ms(Timing.Guard)

    rebuild = False
    if (not App.Playlist.PRESEVE) or (folders != dfp_folders) or (total != dfp_tracks):
        rebuild = True
        if not playlist.is_empty():
            playlist.clear()

    if rebuild:
        if App.Playlist.QUCKSTART:
            scan_init(folders, total)
            scan_find()
            playlist.prepare()
            if not is_scanning:
                display_playlist()
        else:
            generate_playlist(folders, total)
            dfp_folders = folders
            dfp_tracks = total

    # no point in continuing if there are no music files
    if playlist.is_empty():
        print("No albums or tracks found... Exiting")
        raise OSError("No Music Found")
    
    # If this is a warm power-up, we can optionally continue where we left-off
    
    print("\n" + "*" * 40 + "\n")

    dfp.equalizer(Config.DFPlayer.EQUALIZER)
    print("Equalizer Setting:", DFequalizer_strings[dfp.get_equalizer()])
 
    # start by playing the first album & track, with AM radio effect
    album, track = playlist.current()
    large = playlist.is_large_album()

    print(f"Now Playing: Album {album:02d} Track {track:03d}")

    if App.Effects.ENABLE and App.Effects.ON_START:
        fade_and_play_effect(album, track, large=large)
    else:
        dfp.play_folder_track(album, track, large=large)

    button.start() # start the button monitor 

    return State.PLAY_TRACK

states[State.START_UP] = app_start_up

# ****************************************************************************
# normal loop body
# Assumes a track is already playing on entry
def app_play(last):
    if last != State.PLAY_TRACK:
        print(" - Waiting for playback to complete")
        if Config.LED.ENABLE:
            led.color(App.Colors.PLAYING_SONG)
    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN

    # check if playback stopped naturally
    if (not dfp.is_playing()) or button.has_event():
        album, track = playlist.current()
        if button.has_event():
            print(f"Album {album:02d} Track {track:03d} playback stopped") # technically not yet, but soon
            return State.PLAY_NEXT
        else:
            print(f"Album {album:02d} Track {track:03d} playback complete")

        if Config.LED.ENABLE:
            led.color(App.Colors.IDLE)
        app_wait(App.Timing.GUARD)
        return State.PLAY_NEXT
    return State.PLAY_TRACK

states[State.PLAY_TRACK] = app_play

# ****************************************************************************
# normal loop body
# sets up next track to play
def app_next(last):
    global is_scanning

    if last == State.PLAY_NEXT:
        return State.PLAY_TRACK
    
    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN
    
    evt = Controls.Event.NONE
    if button.has_event():
        evt = button.get_event()

    # check for Long Press first, we don't want the stop and pause effect
    # of a normal transition, so we can fade out and in with the AM Radio sound
    if evt == Controls.Event.LONG: # next album, or reshuffle
        if App.Playlist.FULL_SHUFFLE:
            print(" -- Long button press detected: Reshuffling")
            playlist.reshuffle()
            album, track = playlist.current()
        else:
            print(" -- Long button press detected: Next Album")
            # special case for when advancing albums, and next album not available yet
            if playlist.is_last_album():
                dfp.stop()
                if Config.LED.ENABLE:
                    led.color(App.Colors.IDLE)
                app_wait(App.Timing.GUARD)
                scan_find()
                playlist.prepare()
                if not is_scanning:
                    display_playlist()
            album, track = playlist.next_album()
        print(f"Changing to: Album {album:02d} Track {track:03d}")
        return State.NEXT_ALBUM
    
    # check that we got here by a button press, if so emulate 
    # a normal transition
    if evt != Controls.Event.NONE:
        dfp.stop()
        if Config.LED.ENABLE:
            led.color(App.Colors.IDLE)
        app_wait(App.Timing.GUARD)

    # at this point the track should be stopped, so we can scan if necessary
    was_scanning = is_scanning
    if is_scanning:
        scan_one()

    if evt == Controls.Event.TRIPLE: # restart album
        print(" -- Triple button press detected: Restarting Album")
        playlist.restart_album()
        album, track = playlist.current()
    elif evt == Controls.Event.DOUBLE: # previous track
        print(" -- Double button press detected: Previous Track")
        album, track = playlist.previous_track()
    else: # normal advance, or single press for next track
        if evt == Controls.Event.SINGLE:
            print(" -- Single button press detected: Next Track")
        album, track = playlist.next_track()

    print(f"Now Playing: Album {album:02d} Track {track:03d}")
    dfp.play_folder_track(album,track, large=playlist.is_large_album())

    if was_scanning and (not is_scanning):
        display_playlist()

    return State.PLAY_TRACK

states[State.PLAY_NEXT] = app_next

# ****************************************************************************
# normal loop body
# sets up next album to play, and begins play with AM Radio effect
def app_next_album(last):
    if last == State.NEXT_ALBUM:
        return State.PLAY_TRACK
    
    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN

    # start by playing the first album & track, with AM radio effect
    album, track = playlist.current()
    large = playlist.is_large_album()

    print(f"Now Playing: Album {album:02d} Track {track:03d}")

    if App.Effects.ENABLE and App.Effects.ON_ALBUM:
        button.stop() # stop the button monitor during WAV playback
        fade_and_play_effect(album, track, large=large)
        button.start() # restart teh button monitor
    else:
        # no transition effect, emulate a normal transition
        dfp.stop()
        if Config.LED.ENABLE:
            led.color(App.Colors.IDLE)
        app_wait(App.Timing.GUARD)

        # TODO scan for more folders here

        dfp.play_folder_track(album, track, large=large)
    
    return State.PLAY_TRACK
states[State.NEXT_ALBUM] = app_next_album


# ****************************************************************************
# power was turned off
# notify DFPlayer opbject of power state change
# reset playlist
# disable button handler
# non looping, one pass, and it advances
def app_power_down(last):
    global restore_playlist, playlist_state

    if last == State.POWER_DN:
        return State.IDLE

    if Config.LED.ENABLE:
        led.color(App.Colors.IDLE)

    button.stop() # stop the button monitor 

    # inform the DFPlayer object that power is off
    dfp.set_offline()

    # invalidate the playlist, if not set to preserve it
    if not App.Playlist.PRESEVE:
        playlist.clear()

    print("Power-Down")
    return State.IDLE

states[State.POWER_DN] = app_power_down

# ****************************************************************************
# SD Card was removed (Main loop auto-injects this state when SD Card is removed)
# reset playlist
# stop button
# wait for re-insertion
def app_media_wait(last):
    global restore_playlist, playlist_state

    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN

    if last != State.MEDIA_WAIT:
        button.stop()

        # invalidate the playlist, if not set to preserve it
        if not App.Playlist.PRESEVE:
            playlist.clear()
        
        print("SDCard was removed, waiting for SDCard")
        if Config.LED.ENABLE:
            led.color(App.Colors.WAITING)
        return State.MEDIA_WAIT

    last_hint = time.ticks_ms()
    while not dfp.has_sdc():

        if power_sense.value() == 0:
            print("Power Off Detected")
            return State.POWER_DN
        
        if time.ticks_diff(time.ticks_ms(), last_hint) > App.Timing.HINT:
            print(" - still waiting SDCard insertion")
            return State.MEDIA_WAIT
        app_wait(App.Timing.MAIN)

    print("SDCard inserted")
    if Config.LED.ENABLE:
        led.color(App.Colors.IDLE)

    return State.MEDIA_LOAD

states[State.MEDIA_WAIT] = app_media_wait


# ****************************************************************************
# SD Card was re-inserted
# rebuild playlist - can safely do a full scan here
# restart button
# resume playing
def app_media_load(last):
    global dfp_folders, dfp_tracks

    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN
    if last == State.MEDIA_LOAD:
        return State.PLAY_TRACK

    folders = dfp.get_folder_count()
    total = dfp.get_total_files()

    print("Filesystem has", total, "files in", folders, "folders")

    rebuild = False
    if (not App.Playlist.PRESEVE) or (folders != dfp_folders) or (total != dfp_tracks):
        rebuild = True
        if not playlist.is_empty():
            playlist.clear()

    if rebuild:
        generate_playlist(folders)
        dfp_folders = folders
        dfp_tracks = total

    # no point in continuing if there are no music files
    if playlist.get_albums() == 0:
        print("No albums or tracks found... Exiting")
        raise OSError("No Music Found")

    # start by playing the first album & track, with AM radio effect
    album, track = playlist.current()

    print(f"Now Playing: Album {album:02d} Track {track:03d}")

    dfp.volume(Config.DFPlayer.VOLUME)

    dfp.play_folder_track(album, track, large=playlist.is_large_album())

    button.start() # start the button monitor 

    return State.PLAY_TRACK

states[State.MEDIA_LOAD] = app_media_load

# ****************************************************************************
# AM Radio Effect Playback
# ****************************************************************************
def fade_and_play_effect(folder, track, large=False):

    if Config.LED.ENABLE:
        led.color(App.Colors.PLAYING_WAV)

    print(f"PWM Audio: starting  '{Config.Audio.FILE}'")
    wav.play(fade_in=Config.Audio.FADE_IN, fade_out=Config.Audio.FADE_OUT)

    # doesn't make sense to have more steps than actual adjustment resolution
    fade_in_steps  = min(30, min(Config.DFPlayer.STEPS_IN, Config.DFPlayer.VOLUME)) # max of 30 steps
    fade_out_steps = min(30, min(Config.DFPlayer.STEPS_OUT, Config.DFPlayer.VOLUME))
    fade_in_delay  = max(int((Config.DFPlayer.FADE_IN * 1000) / (fade_in_steps - 1)), 40) # min of 40ms
    fade_out_delay = max(int((Config.DFPlayer.FADE_OUT * 1000) / (fade_out_steps - 1)), 40)
    play_vol = min(30, Config.DFPlayer.VOLUME)

    if not dfp.is_stopped(): # track is currently playing, fade it out, then stop
        # fade out the old track
        try:
            vol = play_vol

            t_start = time.ticks_ms()
            for step in range(fade_out_steps):
                vol = play_vol - int((play_vol / fade_out_steps) * step)
                dfp.volume(vol)

                t_next = fade_out_delay * step
                while time.ticks_diff(time.ticks_ms(), t_start) < t_next:
                    app_wait(App.Timing.MAIN)

        except DFPlayer.Error:
            print(" DFPlayer stopped unexpectedly")
            wav.stop()
            if dfp.is_online():
                dfp.set_offline()
            return
        except: # bubble up any other exceptions
            raise
        dfp.volume(0)
        if not dfp.is_stopped():
            dfp.stop()

    # start playing the new track
    try:
        dfp.play_folder_track(folder, track, large=large)
    except:
        print(f"unable to start Album {folder:02d} Track {track:03d}")
        dfp.volume(play_vol) # exit with volume set to expected state
        raise

    # fade in the new track
    try:
        vol = 0
        t_start = time.ticks_ms()
        for step in range(fade_in_steps):
            vol = int((play_vol / fade_in_steps) * step)
            dfp.volume(vol)

            t_next = fade_in_delay * step
            while time.ticks_diff(time.ticks_ms(), t_start) < t_next:
                app_wait(App.Timing.MAIN)

        while wav.is_playing():
            app_wait(App.Timing.MAIN)

    except DFPlayer.Error:
        print(" DFPlayer stopped unexpectedly")
        wav.stop()
        if dfp.is_online():
            dfp.set_offline()
        return
    except: # bubble up any other exceptions
        raise

    dfp.volume(play_vol)
    wav.stop()

    if Config.LED.ENABLE:
        led.color(App.Colors.PLAYING_SONG)
    print(f"PWM Audio: '{Config.Audio.FILE}' playback complete")


# ****************************************************************************
# Load Resources
# ****************************************************************************
if App.Effects.ENABLE:
    print(f"Loading Audio Data: '{Config.Audio.FILE}'")
    try:
        wav = WAV(Config.Audio.PIN, Config.Audio.FILE, Config.Audio.VOLUME, Config.Audio.CARRIER)
    except:
        print("Error Loading Audio Data. Disabling feature")
        App.Effects.ENABLE = False # type: ignore - Goes against convention, but this is deliberate
    else:
        samps = wav.get_size()
        rate = wav.get_rate()
        duration = (1.0 * samps) / (1.0 * rate)
        rate = rate / 1000
        print(f"Audio Data: {rate}KHz {samps} samples / {duration:.2f}s" )

# ****************************************************************************
# Main Loop
# ****************************************************************************
def main():
    global app_state

    print("")
    print("*" * 40)
    print("*" * 40)
    print("*" * 40)

    print(f"\nBooting Retro Radio Baseline {_VERSION}\n")

    if App.Playlist.FULL_SHUFFLE:
        print("Full Disk Shuffle Mode Enabled")

    if power_sense.value() == 1:
        app_state = State.BOOT
        dfp.reset()
        print("Power Detected")

    last = None
    while True:
        # basic loop logic

        # check power state, force power_down if power was lost
        if (app_state > State.IDLE) and (power_sense.value() == 0):
            app_state = State.POWER_DN

        # check if SDCard is present, force lost and wait to recover state
        if (app_state > State.START_UP) and (app_state < State.MEDIA_WAIT) and (not dfp.has_sdc()):
            app_state = State.MEDIA_WAIT

        current = app_state
        # TODO: Wrap this in try/except
        app_state = states[current](last)
        last = current
        time.sleep_ms(App.Timing.MAIN)
# main never exits

# ****************************************************************************
# Cleanup Code
# ****************************************************************************
# function called on exit from an exception of from Thonny to shut things down cleanly
def app_cleanup():
    if button.is_runnning:
        button.stop()
    if App.Effects.ENABLE and wav.is_playing():
        wav.stop()
    if dfp.is_online():
        dfp.disable_reliability()
        dfp.stop()
        time.sleep_ms(20)
        dfp.release()
 

# ****************************************************************************
# Entry Point
# ****************************************************************************
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt: # this is when Thonny stops the code
        print("\nStopped by user")
        if Config.LED.ENABLE:
            led.color(Config.LED.DEFAULT)
        app_cleanup()

    except Exception as e:
        print("\nError: %s" % e)
        if Config.LED.ENABLE:
            led.color(App.Colors.ERROR)
        app_cleanup()
        print("Waiting for power off to reset")
        while power_sense.value() == 1:
            time.sleep_ms(20)
        print("resetting in 1 second")
        time.sleep_ms(1000)
        if Config.LED.ENABLE:
            led.color(App.Colors.WARNING)
        machine.soft_reset() # software only reset
