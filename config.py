# *****************************************************************************
#       Project: ZBVR - Zion Brock Vintage Radio
#  Project Repo: https://github.com/mloit/zbvr-firmware
#         About: Baseline firmware for the Zion Brock Vintage Radio 
#
#          File: config.py
#       Version: 26.0.1 Alpha
#   Description: Configuration settings for the main firmware application
# 
#        Author: Mark Loit
#        Credit: Zion Brock
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
        # to the point of invalidating the index values
        PRESEVE          = True

        # Once the last track of an album has played, the defult behaviour (False) is to restart the same album
        # setting this option to true will cause it to advance to the next album
        CYCLE_ALBUMS     = False 

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
        WARNING         = (15, 5, 0)    # yellow
        ERROR           = (10, 0, 0)    # red

# ****************************************************************************
# Hardware configuration
# ****************************************************************************
class Config:
    USE_LED         = True        # Enable/Disable use of NeoPixel LED
    USE_I2C         = False       # Enable/Disable I2C
# NeoPixel LED -- Onboard Status LED, or future effects
    class LED:
        PIN           = 16        # RP-Zero LED is GPIO16, PCB LED is GPIO6 (optional config)
        COUNT         = 1         # number of NeoPixels attached
        DEFAULT       = (4, 4, 4) # White(ish) -- default colour at startup/power-on

# I2C Settings (currently unused, build option)
    class I2C:
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
        SHORT_PRESS   = 150       # Minimum length to register as a press (milliseconds)
        LONG_PRESS    = 1000      # Long press threshold (milliseconds)

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
        FADE_IN       = 0         # Wav fade-in at start of playback (seconds)
        FADE_OUT      = 0.8       # WAV fade-out at end of playback (seconds)

# DFPlayer SPecific settings
    class DFPlayer:
        class UART:
            UNIT      = 0         # Uart unit DFPlayer is connected to
            class Pins:
                TX    = 0         # RP-Zero.TX -> DFPlayer.RX
                RX    = 1         # RP-Zero.RX <- DFPlayer.TX
        VOLUME        = 28        # play volume (0-30)
        FADE          = 2.4       # Volume fade-in duration (seconds)
        FADE_STEPS    = 20        # number of fade-in steps
