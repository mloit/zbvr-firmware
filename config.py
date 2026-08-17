# *****************************************************************************
#       Project: ZBVR - Zion Brock Vintage Radio
#  Project Repo: https://github.com/mloit/zbvr-firmware
#         About: Baseline firmware for the Zion Brock Vintage Radio 
#
#          File: config.py
#       Version: 26.0.1
#   Description: Configuration settings for the main firmware application
# 
#        Author: Mark Loit
#        Credit: Zion Brock (Original code and inspiration)
#
#       License: CC BY-NC-SA
# 
#  (c) Copyright 2026 Mark Loit. All Rights Reserved.
# ****************************************************************************

print("Loading Config")

# ****************************************************************************
# Application Configuration
# ****************************************************************************
class App:
    class Playlist:
        # Attempt to presserve album and track index in the playlist between (pot) power-cycles
        # only works as long as the RP remains powered, and the contents of the SD don't change
        # to the point of invalidating the index values. (USB power must remain present between power events)
        # Default Setting: True
        PRESEVE          = True

        # Once the last track of an album has played, the defult behaviour (False) is to restart the same album
        # setting this option to true will cause it to advance to the next album. Once the last album is reached
        # it will cycle back to the first
        # Default Setting: False
        CYCLE_ALBUMS     = False

        # Shuffle playback of tracks within an album
        # Default Setting: False
        TRACK_SHUFFLE    = False

        # Shuffle order in which albums are played
        # Default Setting: False
        ALBUM_SHUFFLE    = False

        # Shuffle alternate albums
        # odd numbered albums (01,03,05...) will be played sequentially
        # even numbered albums (02, 04, 06...) will be shuffled
        # Note: this setting has no effect if TRACK_SHUFFLE is True 
        # Default Setting: False
        ALTERNATE_SHUFFLE = False

        # Shuffle all music
        # treats the entire music library on the SD card as a single large album.
        # This feature also changes the function of the long button press from advancing albums (as there is 
        # effectioively only one) to reshuffling and restarting the playlist at the start
        # NOTE: this feature overrides the CYCLE_ALBUMS and the TRACK_SHUFFLE, ALBUM_SHUFFLE, and ALTERNATE_SHUFFLE options 
        #       as they no longer apply.
        # Default Setting: False
        FULL_SHUFFLE     = False

        # reshuffle playlist on restarts
        # When set to true, this option causes albums to be reshuffled when the playlist (disk or album)
        # loops back to the start.
        # Default Setting: False
        AUTO_RESHUFFLE   = False

        # Faster startup.
        # This feature when set true causes music to start playing before the disk has been fully scanned
        # for valid folders and tracks. This has some side effects in that the first track played on initial
        # power-up will always come from the first folder found, regardless of shuffle mode used. It may also 
        # result in extended delay when advancing folders if the scan has not completed and the user attempts 
        # to advance to a folder not scanned in yet. 
        # When set to false, startup is a bit slower as a full scan of the SD card contents is performed before 
        # playback begins. This can feel unreasonably long with large collections on the disk
        # Default Setting: True
        QUCKSTART        = True

    class Effects:
        # enables the use of the PWM Audio module,
        # if disabled, all other Effects options have no effect
        ENABLE           = True
        # Play radio effect on startup
        ON_START         = True
        # Play radio effect on album change
        ON_ALBUM         = True

    # Timing Values -- General timing settings for application operation
    class Timing:
        TIMEOUT          = 1000   # Command timeout in milliseconds
        GUARD            = 120    # small pause between tracks
        MAIN             = 10     # Main loop pacing in milliseconds
        BOOT             = 1500   # Time for DFPlayer reset
        STEP             = 5      # timing interval
        HINT             = 5000   # Rate at repeated wait messages

    # Colour defaults for various states -- only used with NeoPixel
    # values are (R,G,B)
    class Colors: 
        WAITING         = (10, 0, 8)    # purple
        IDLE            = (0, 10, 0)    # green
        PLAYING_WAV     = (0, 10, 8)    # cyan
        PLAYING_SONG    = (0, 0, 10)    # blue
        ACTIVE          = (10, 10, 10)  # White
        WARNING         = (15, 2, 0)    # orange
        ERROR           = (10, 0, 0)    # red
        CONNECTED       = (15, 5, 0)    # yellow

# ****************************************************************************
# Hardware configuration
# ****************************************************************************
class Config:

# NeoPixel LED -- Onboard Status LED, or future effects
    class LED:
        ENABLE        = True      # Enable/Disable use of NeoPixel LED
        PIN           = 16        # RP-Zero LED is GPIO16, PCB LED is GPIO6 (optional config)
        COUNT         = 1         # number of NeoPixels attached
        DEFAULT       = (4, 4, 4) # White(ish) -- default colour at startup/power-on

# I2C Settings (currently unused, build option)
    class I2C:
        ENABLE        = False     # Enable/Disable I2C
        UNIT          = 0         # I2C0 on RP2040
        class Pins:
            SDA       = 4         # SDA0 on RP2040
            SCL       = 5         # SCL0 on RP2040
        RATE          = 100_000   # Default I2C rate 100KHz

# Button Behavior
    class Button:
        PIN           = 2         # UI Button Pin
        PULL          = 1         # 0 = none, 1 = pull-up, -1 = pull-down
        INVERT        = False     # False is active low, True is active high
        RATE          = 100       # poll rate in Hz
        DEBOUNCE      = 50        # Debounce duration (milliseconds)
        TAP_GAP       = 800       # Max time between taps for multi-tap detection (milliseconds)
        SHORT_PRESS   = 50        # Minimum length to register as a press (milliseconds)
        LONG_PRESS    = 1000      # Long press threshold (milliseconds)
        RESTART_PRESS = 5000      # Restart threshold (milliseconds)
        HALT_PRESS    = 10000     # Soft shutdown threshold (milliseconds)

# Power Sense -- used for dertermining when the radio is "on" (RP2040 is assumed to be always on)
    class Sense:
        PIN           = 14        # Power sense input (HIGH = equipment on)

# Busy Signal -- not used but connected, so we initialize it
    class Busy:
        PIN           = 15        # DFPlayer Busy Input (Not Used)

# WAV Playback
    class Audio:
        PIN           = 3         # GPIO pin for PWM audio output
        VOLUME        = 1.0       # WAV playback volume (0.0-1.0)
        CARRIER       = 125_000   # PWM carrier frequency in Hz
        FILE          = "AMradioSound.wav"  # WAV file to play (relative to project root)
        FADE_IN       = 0.8       # Wav fade-in at start of playback (seconds)
        FADE_OUT      = 0.8       # WAV fade-out at end of playback (seconds)

# DFPlayer SPecific settings
    class DFPlayer:
        class UART:
            UNIT      = 0         # Uart unit DFPlayer is connected to
            class Pins:
                TX    = 0         # RP-Zero.TX -> DFPlayer.RX
                RX    = 1         # RP-Zero.RX <- DFPlayer.TX
        VOLUME        = 28        # play volume (0-30)

        EQUALIZER     = 0         #     0: Normal
                                  #     1: Pop
                                  #     2: Rock
                                  #     3: Jazz
                                  #     4: Classical
                                  #     5: Bass

        # the total time for fade-in and fade_out should be at least 0.5s 
        # less than the playtime of the WAV file. (default WAV is 4.7s)
        # steps seems to be best around 20, but may need to be adjusted lower
        # if the time gets shorter than  about 1.5s
        FADE_IN       = 2.0       # Volume fade-in duration (seconds)
        STEPS_IN      = 20        # number of fade-in steps
        FADE_OUT      = 2.0       # Volume fade-out duration (seconds)
        STEPS_OUT     = 20        # number of fade-out steps
