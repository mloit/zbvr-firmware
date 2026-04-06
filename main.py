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
#        Credit: Zion Brock
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
# - Modularized most things to make it more maintanable 
# - Centralized configuration settings into 'config.py'
# - Added bi-directional commmunications withteh DFPlayer
# - Removed blind searching if another track or folder exists
# - Added generation of the playlist at boot to only have folders with valid tracks to prevent lockups
# - Added colours to varous states to give more visual feedback
# - made the button monitoring timer based, to simplify the main loop
# - converted the main loop into a state machine
# - added exception handling to main, to clean up nicely on a crash or when Thonny stops the program

# Known issues with ALPHA
# - if there is a gap in folder names, some folders after the gaps may be mised
#   -- solution, either scan for all 99 possibilities, or make the caviat that foldernames cannot
#      be skipped, but folders can be left empty

_VERSION = "26.0.1 ALPHA-2"

import micropython
micropython.opt_level(3) # comment out this line when debugging
micropython.alloc_emergency_exception_buf(100)

from machine import Pin, I2C
import time, sys, machine

from config import App, Config
from led import LED
from audioplayer import WAV
from dfplayer import DFPlayer
from controls import Controls
from playlist import Playlist

lev = micropython.opt_level()
print(f"\nMicroPython Optimization Level: {lev}")
micropython.mem_info()

print("\nInitiailzing Modules")

if(Config.USE_LED):
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
if(Config.USE_I2C):
    i2c = I2C(Config.I2C.UNIT, 
              sda  = Config.I2C.Pins.SDA, 
              scl  = Config.I2C.Pins.SCL, 
              freq = Config.I2C.RATE)

# ****************************************************************************
# Playlist Handling
# ****************************************************************************
playlist = Playlist()

restore_playlist = False
playlist_restore_idx = -1
playlist_restore_trk = 0

# Dynamically determines the playlist from the contents of the SD 
def generate_playlist(folders = -1):
    if folders == -1:
        folders = dfp.get_folder_count()

    if folders == 0:
        print("SDCard has no folders")
        return

    print("Discovering playlist")
    print("Scanning: ", end="")
    
    for dir in range(folders):
        files = dfp.get_file_count(dir + 1)
        if files:
            print("+", end="")
            playlist.add(dir+1, files)
        else:
            print(".",end="")
    print("")

    albums = playlist.albums()
    print("playlist contains", albums, "albums")
    pl = playlist.all()
    for entry in pl:
        print(f"album: {entry[0]:02d} - {entry[1]} tracks")

# ****************************************************************************
# State Machine
# ****************************************************************************
#state machine constants
class State:
    IDLE        = 0 # Idle state, Potentiometer in off poosition (Next: POWER_UP)
    BOOT        = 2 # Potentiometer just turned on Wait for DFPlayer to boot (Next: START_UP)
    MEDIA_CHECK = 3 # Check and wait for SD Card
    START_UP    = 5 # Initialize playlist, start first track
    PLAY_TRACK  = 6 # Normal run state, plays to the end of the track
    PLAY_NEXT   = 7 # normal advance to next track
    NEXT_ALBUM  = 8 # special advance where effect is played at transition
    POWER_DN    = 9 # Potentiometer just turned off (Next: IDLE)

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
    if(last != State.IDLE):
        print("Waiting for Power On (potentiometer)")
        if(Config.USE_LED):
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
    if(last != State.BOOT):
        print("Waiting for DFPlayer to come online")
        if(Config.USE_LED):
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
    if(last != State.MEDIA_CHECK):
        no_card = not dfp.has_sdc()
        print("SDCard ", end="")
        if no_card:
            print("NOT ", end="")
        print("present")

        if no_card:
            print("Waiting for SDCard insertion")
            if(Config.USE_LED):
                led.color(App.Colors.WAITING)
            return State.MEDIA_CHECK
        return State.START_UP

    last_hint = time.ticks_ms()
    while not dfp.has_sdc():
        if time.ticks_diff(time.ticks_ms(), last_hint) > App.Timing.HINT:
            print(" - still waiting SDCard insertion")
            return State.MEDIA_CHECK
        app_wait(App.Timing.MAIN)

    print("SDCard inserted")
    if(Config.USE_LED):
        led.color(App.Colors.IDLE)

    return State.START_UP

states[State.MEDIA_CHECK] = app_media_check

# ****************************************************************************
# Generate the playlist
# Get first track playing with AMRadio effect
# button handler set-up on exit
# non looping, one pass, and it advances
def app_start_up(last):
    global restore_playlist, playlist_restore_idx, playlist_restore_trk

    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN
    if(last == State.START_UP):
        return State.PLAY_TRACK

    folders = dfp.get_folder_count()
    total = dfp.get_total_files()

    print("Filesystem has", total, "files in", folders, "folders")
    #time.sleep_ms(Timing.Guard)

    generate_playlist(folders)

    # no point in continuing if there are no music files
    if playlist.albums() == 0:
        print("No albums or tracks found... Exiting")
        raise OSError("No Music Found")
    
    # If this is a warm power-up, we can optionally continue where we left-off
    if App.Playlist.PRESEVE and restore_playlist:
        playlist.set_index(playlist_restore_idx)
        playlist.set_track(playlist_restore_trk)
    
    print("\n" + "*" * 40 + "\n")
 
    # start by playing the first album & track, with AM radio effect
    album, track = playlist.current()

    print(f"Now Playing: Album {album:02d} Track {track:03d}")

    if App.Effects.ENABLE and App.Effects.ON_START:
        fade_and_play_effect(album, track)
    else:
        dfp.play_folder_track(album, track)

    button.start() # start the button monitor 

    return State.PLAY_TRACK

states[State.START_UP] = app_start_up

# ****************************************************************************
# normal loop body
# Assumes a track is already playing on entry
def app_play(last):
    if(last != State.PLAY_TRACK):
        print(" - Waiting for playback to complete")
        if(Config.USE_LED):
            led.color(App.Colors.PLAYING_SONG)
    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN

    # any button press event will result in a change of tracks
    if button.has_event():
        dfp.stop()

    if (not dfp.is_playing()) or button.has_event():
        album, track = playlist.current()
        if button.has_event():
            dfp.stop()
            print(f"Album {album:02d} Track {track:03d} playback stopped")
        else:
            print(f"Album {album:02d} Track {track:03d} playback complete")
        if(Config.USE_LED):
            led.color(App.Colors.IDLE)
        app_wait(App.Timing.GUARD)
        return State.PLAY_NEXT
    return State.PLAY_TRACK

states[State.PLAY_TRACK] = app_play

# ****************************************************************************
# normal loop body
# sets up next track to play
def app_next(last):
    if(last == State.PLAY_NEXT):
        return State.PLAY_TRACK
    
    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN
    
    evt = Controls.Event.NONE
    if button.has_event():
        evt = button.get_event()

    if evt == Controls.Event.LONG: # next album
        print(" -- Long button press detected: Next Album")
        album, track = playlist.next_album()
        print(f"Changing to: Album {album:02d} Track {track:03d}")
        return State.NEXT_ALBUM
    elif evt == Controls.Event.TRIPLE: # restart album
        print(" -- Triple button press detected: Restarting Album")
        playlist.restart_album()
        album, track = playlist.current()
    elif evt == Controls.Event.DOUBLE: # previous track
        print(" -- Double button press detected: Previous Track")
        album, track = playlist.previous_track(App.Playlist.CYCLE_ALBUMS)
    else: # normal advance, or single press for next track
        if evt == Controls.Event.SINGLE:
            print(" -- Single button press detected: Next Track")
        album, track = playlist.next_track(App.Playlist.CYCLE_ALBUMS)

    print(f"Now Playing: Album {album:02d} Track {track:03d}")
    dfp.play_folder_track(album,track)

    return State.PLAY_TRACK

states[State.PLAY_NEXT] = app_next

# ****************************************************************************
# normal loop body
# sets up next album to play, and begins play with AM Radio effect
def app_next_album(last):
    if(last == State.NEXT_ALBUM):
        return State.PLAY_TRACK
    
    if power_sense.value() == 0:
        print("Power Off Detected")
        return State.POWER_DN

    # start by playing the first album & track, with AM radio effect
    album, track = playlist.current()

    print(f"Now Playing: Album {album:02d} Track {track:03d}")

    if App.Effects.ENABLE and App.Effects.ON_ALBUM:
        fade_and_play_effect(album, track)
    else:
        dfp.play_folder_track(album, track)
    
    return State.PLAY_TRACK
states[State.NEXT_ALBUM] = app_next_album


# ****************************************************************************
# power was turned off
# notify DFPlayer opbject of power state change
# reset playlist
# disable button handler
# non looping, one pass, and it advances
def app_power_down(last):
    global restore_playlist, playlist_restore_idx, playlist_restore_trk

    if(last == State.POWER_DN):
        return State.IDLE

    if(Config.USE_LED):
        led.color(App.Colors.IDLE)

    button.stop() # stop the button monitor 

    # inform the DFPlayer object that power is off
    dfp.set_offline()

    # invalidate the playlist, preserving state for possible restoration
    restore_playlist = True
    playlist_restore_idx = playlist.get_index()
    playlist_restore_trk = playlist.get_track()
    playlist.clear()

    print("Power-Down")
    return State.IDLE

states[State.POWER_DN] = app_power_down

# ****************************************************************************
# AM Radio Effect Playback
# ****************************************************************************
def fade_and_play_effect(folder, track):
    if not dfp.is_stopped():
        dfp.stop()

    # start playing the new track
    dfp.volume(0)
    try:
        dfp.play_folder_track(folder, track)
    except:
        print(f"unable to start Album {folder:02d} Track {track:03d}")
        dfp.volume(Config.DFPlayer.VOLUME) # exit with volume set to expected state
        raise

    if(Config.USE_LED):
        led.color(App.Colors.PLAYING_WAV)

    # the PWM player uses a lot of python resources, and causes problems
    # with out uart code in the DFPlayer. To reduce risk of issue here
    # we temporarily disable command acknowledgements to reduce traffic
    ack_mode = dfp.disable_reliability()

    print(f"PWM Audio: starting  '{Config.Audio.FILE}'")
    wav.play(fade_out=Config.Audio.FADE_OUT)

    fade_steps = Config.DFPlayer.FADE_STEPS
    fade_delay = int((Config.DFPlayer.FADE * 1000) / fade_steps)
    if fade_delay < 40:
        fade_delay = 40

    try:
        vol = 0
        print(f"Fade-In Volume [{vol} ", end="")
        for step in range(fade_steps + 1):
            vol = int((step / fade_steps) * Config.DFPlayer.VOLUME)
            print(">", end="")
            dfp.volume(vol)

            t_start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t_start) < fade_delay:
                if not wav.is_playing():
                    break
                app_wait(10)
        
            if not wav.is_playing():
                break
        print(f" {vol}]")

        while wav.is_playing():
            app_wait(20)

    finally:
        wav.stop()

    # restore the DFPlayer command acknowledgement mode
    dfp.enable_reliability(ack_mode)

    if(Config.USE_LED):
        led.color(App.Colors.PLAYING_SONG)
    print(f"PWM Audio: '{Config.Audio.FILE}' playback complete")

    # just in case make sure we leave with volume set to where we expect
    dfp.volume(Config.DFPlayer.VOLUME)
    return

# ****************************************************************************
# Load Resources
# ****************************************************************************
if App.Effects.ENABLE:
    # micropython.mem_info()
    print(f"Loading Audio Data: '{Config.Audio.FILE}'")
    wav = WAV(Config.Audio.PIN, Config.Audio.FILE, Config.Audio.VOLUME, Config.Audio.CARRIER)
    samps = wav.get_size()
    rate = wav.get_rate()
    duration = (1.0 * samps) / (1.0 * rate)
    rate = rate / 1000
    print(f"Audio Data: {rate}KHz {samps} samples / {duration:.2f}s" )
    # micropython.mem_info()

# ****************************************************************************
# Main Loop
# ****************************************************************************
#TODO: Add SDCard removal handling
def main():
    global app_state

    print("")
    print("*" * 40)
    print("*" * 40)
    print("*" * 40)

    print(f"\nBooting Retro Radio Baseline {_VERSION}\n")

    if power_sense.value() == 1:
        app_state = State.BOOT
        print("Power Detected")
        dfp.reset()

    last = None
    while True:
        # basic loop logic
        current = app_state
        app_state = states[app_state](last)
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
    if wav.is_playing():
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
        if(Config.USE_LED):
            led.color(Config.LED.DEFAULT)
        app_cleanup()
        sys.exit()

    except Exception as e:
        print("\nError: %s" % e)
        if(Config.USE_LED):
            led.color(App.Colors.ERROR)
        app_cleanup()
        print("Waiting for power off to reset")
        while power_sense.value() == 1:
            time.sleep_ms(20)
        print("resetting in 1 second")
        time.sleep_ms(1000)
        if(Config.USE_LED):
            led.color(App.Colors.WARNING)
        machine.soft_reset() # software only reset
        # machine.reset()    # hard reset
        # raise
