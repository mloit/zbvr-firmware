# *****************************************************************************
#       Project: ZBVR - Zion Brock Vintage Radio
#  Project Repo: https://github.com/mloit/zbvr-firmware
#         About: Baseline firmware for the Zion Brock Vintage Radio 
#
#          File: audioplayer.py
#       Version: 26.0.1 Alpha
#   Description: PWM Based WAV Audio Playback
# 
#        Author: Mark Loit
#        Credit: Zion Brock
#
#       License: CC BY-NC-SA
# 
#  (c) Copyright 2026 Mark Loit. All Rights Reserved.
# ****************************************************************************

# TODO: 
# - Add Fade-In Capability

from machine import Pin, PWM, Timer
import ustruct

print("Loading Module: Audio Player (PWM)")

# The output audio signal is biased at 50% duty cycle. (2.5V)
BIAS = 32768

# ****************************************************************************
# WAV Audio Player Class
# ****************************************************************************
class WAV:
    def __init__(self, pin, wav_file, volume=1.0, carrier=125_000):

        self._pin = pin
        self._carrier = carrier
        self._pwm = None
        self._tmr = None
        self._volume = max(0.0, min(1.0, volume)) # clamp volume to the 0.0-1.0 range
        self._data, self._rate = self._load_wav(wav_file)
        self._lut = self._build_table(self._volume)

        # Playback state (shared with ISR)
        self._state = {
            "idx": 0,
            "n": len(self._data),
            "done": False,
            "fade_out": 0
        }

    def get_rate(self):
        return self._rate
    
    def get_size(self):
        return len(self._data)


# load in the given WAV file, return its sample rate and data
    def _load_wav(self, path):
        with open(path, "rb") as f:

            # validate that we have a proper WAV file
            if f.read(4) != b"RIFF":
                raise ValueError("Not RIFF")
            f.read(4)
            if f.read(4) != b"WAVE":
                raise ValueError("Not WAVE")
            
            # default samplerate, overwritten if specified in the file
            samplerate = 8000

            # parse through the chunks processing the ones we recognize
            while True:
                cid = f.read(4)
                if not cid: 
                    raise ValueError("Unexpected EOF")
                
                clen = ustruct.unpack("<I", f.read(4))[0]

                if cid == b"fmt ": # format chunk (samplerate)
                    fmt = f.read(clen)
                    samplerate = ustruct.unpack("<I", fmt[4:8])[0]
                elif cid == b"data": # data chunk
                    data = f.read(clen)
                    break
                else:
                    f.seek(clen, 1)
        return data, samplerate

# generate a look-up of duty cycles for a given sample value
# preadjusted for a preset volume level
    def _build_table(self, volume = 1.0):
        lut = [0] * 256 # create an empty table of 256 entries

        # convert volume to scaling factor
        scale = int(256 * volume)

        #populate the table
        for i in range(256):
            d = BIAS + (i - 128) * scale
            d = max(0, min(65535, d)) # clamp duty to 16 bit PWM range
            lut[i] = d
        return lut

    # timer ISR
    def _timer_isr(self, _t):
        pwm = self._pwm
        if pwm is None:
            self._state["done"] = True
            return

        idx = self._state["idx"]
        n = self._state["n"]
        if idx >= n:
            pwm.duty_u16(BIAS)
            self._state["done"] = True
            return

        raw_duty = self._data[idx]

        fo = self._state["fade_out"]
        if fo > 0 and idx >= n - fo:
            into = idx - (n - fo)
            remaining = fo - into
            if remaining < 0:
                remaining = 0
            scale_val = (remaining * 256)
            duty = BIAS + ((raw_duty - BIAS) * scale_val)
        else:
            duty = raw_duty

        pwm.duty_u16(self._lut[duty])


        self._state["idx"] = idx + 1

    # play the loaded wav file
    def play(self, fade_out=0):
        if fade_out > 0:
            fade_samples = int(self._rate * fade_out)
            if fade_samples > self._state["n"]:
                fade_samples = self._state["n"]
            self._state["fade_out_samples"] = fade_samples
        else:
            self._state["fade_out_samples"] = 0

        self._state["idx"] = 0
        self._state["done"] = False

        self._pwm = PWM(Pin(self._pin))
        self._pwm.freq(self._carrier)
        self._pwm.duty_u16(BIAS)

        self._tmr = Timer()
        self._tmr.init(freq=self._rate, mode=Timer.PERIODIC, callback=self._timer_isr, hard=True)

    # stop playing and cleanup
    def stop(self):
        if self._tmr:
            try:
                self._tmr.deinit()
            except:
                pass
            self._tmr = None

        if self._pwm:
            try:
                self._pwm.duty_u16(BIAS)
            except:
                pass
            self._pwm = None

        self._state["done"] = True

    # returns if the player is currently running
    def is_playing(self):
        return not self._state["done"]
