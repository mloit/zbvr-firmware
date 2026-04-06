# *****************************************************************************
#       Project: ZBVR - Zion Brock Vintage Radio
#  Project Repo: https://github.com/mloit/zbvr-firmware
#         About: Baseline firmware for the Zion Brock Vintage Radio 
#
#          File: audioplayer.py
#       Version: 26.0.1
#   Description: PWM Based WAV Audio Playback
# 
#        Author: Mark Loit
#        Credit: Zion Brock (Original code and inspiration)
#
#       License: CC BY-NC-SA
# 
#  (c) Copyright 2026 Mark Loit. All Rights Reserved.
# ****************************************************************************

# TODO: 
#  - Optimize away the division in the ISR?
#  - Fix up exception handling and raising, create custom exception class

from machine import Pin, PWM, Timer
import ustruct

print("Loading Module: Audio Player (PWM)")

# The output audio signal is biased at 50% duty cycle. (2.5V)
PWM_BIAS = 32768
PCM_BIAS = 128

# ****************************************************************************
# WAV Audio Player Class
# ****************************************************************************
class WAV:

    def __init__(self, pin, wav_file, volume=1.0, carrier=125_000):

        # audio data
        self._data, self._rate = self._load_wav(wav_file)  # load the WAV data

        # hardware config
        self._pin = pin          # pwm pin to use
        self._carrier = carrier  # PWM carrier frequency
        self._pwm = None         # pwm timer module (initialized on play)
        self._tmr = None         # sample timer (initilaized on play)

        self._data_len = len(self._data)                   # store number of samples for quick access
        self._volume   = max(0.0, min(1.0, volume))        # clamp volume to the 0.0 - 1.0 range
        self._lut      = self._build_table(self._volume)   # quick LUT for PWM duty during playback
        self._fade_in  = 0      # number of fade in samples
        self._fade_out = 0      # number of fade_out samples
        self.isr_done = False
        self._isr_index = 0

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
                # read in the chunk identifier
                chunk_id = f.read(4)
                if not chunk_id: 
                    raise ValueError("Unexpected EOF")

                # read in the lengh of the chunk
                chunk_len = ustruct.unpack("<I", f.read(4))[0]

                if chunk_id == b"fmt ":   # format chunk (samplerate)
                    format = f.read(chunk_len)
                    samplerate = ustruct.unpack("<I", format[4:8])[0]
                elif chunk_id == b"data": # data chunk
                    data = f.read(chunk_len)
                    break
                else:                     # skip past chunks we're not inteerested in
                    f.seek(chunk_len, 1)
        return data, samplerate

    # generate a look-up of duty cycles for a given sample value
    # preadjusted for a preset volume level
    def _build_table(self, volume = 1.0):
        lut = [0] * 256 # create an empty table of 256 entries

        # convert volume to scaling factor
        scale = int(256 * volume)

        #populate the table
        for i in range(256):
            d = PWM_BIAS + (i - PCM_BIAS) * scale
            d = max(0, min(65535, d)) # clamp duty to 16 bit PWM range
            lut[i] = d
        return lut

    # playback sample timer runs at sample rate to update the PWM duty
    # playback timer ISR
    def _timer_isr(self, _t):
        pwm = self._pwm
        if pwm is None:
            self._isr_done = True
            return

        idx = self._isr_index
        samples = self._data_len
        if idx >= samples:
            pwm.duty_u16(PWM_BIAS)
            self._isr_done = True
            return

        raw_duty = self._lut[self._data[idx]]
        fade_in = self._fade_in
        fade_out = self._fade_out

        # run the fade-in, if index is less than fade_in samples
        if fade_in > 0 and idx <= fade_in: 
            scale_val = (idx * 256) // fade_in
            duty = PWM_BIAS + ((raw_duty - PWM_BIAS) * scale_val) // 256

        # run the fade-out if index is within fade_out samplles of the end
        elif fade_out > 0 and idx >= samples - fade_out: 
            into = idx - (samples - fade_out)
            remaining = fade_out - into
            if remaining < 0:
                remaining = 0
            scale_val = (remaining * 256) // fade_out
            duty = PWM_BIAS + ((raw_duty - PWM_BIAS) * scale_val) // 256

        # normal playback (not fading in or out)
        else:
            duty = raw_duty

        if duty < 0:
            duty = 0
        
        if duty > 65535:
            duty = 65535

        pwm.duty_u16(duty)

        self._isr_index = idx + 1

    # play the loaded wav file
    def play(self, fade_in=0, fade_out=0):

        # reset the state
        self._isr_done = False
        self._isr_index = 0

        # if fade time exceeds play_time, proportionatly adjust the fades
        if (fade_in > 0) and (fade_out > 0):
            duration = self._data_len / self._rate  # calculate runtime of audio
            fade_time = fade_in + fade_out          # calculate total requested fade time
            if fade_time > duration: # if fade time exceeds play_time
                # proportionatly adjust the fades
                fi_ratio = fade_in / fade_time      
                fo_ratio = fade_out / fade_time
                fade_in = duration * fi_ratio
                fade_out = duration * fo_ratio

        fade_in_samples = 0
        fade_out_samples = 0

        # convert fades to samples, and range check the fade durations
        if fade_in > 0:
            fade_in_samples = int(self._rate * fade_in)
            fade_in_samples = min(self._data_len, fade_in_samples)

        if fade_out > 0:
            fade_out_samples = int(self._rate * fade_out)
            fade_out_samples = min(self._data_len, fade_out_samples)

        self._fade_in  = fade_in_samples
        self._fade_out = fade_out_samples

        # start playback
        self._pwm = PWM(Pin(self._pin))
        self._pwm.freq(self._carrier)
        self._pwm.duty_u16(PWM_BIAS)

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
                self._pwm.duty_u16(PWM_BIAS)
            except:
                pass
            self._pwm = None

        self._isr_done = True

    # returns if the player is currently running
    def is_playing(self):
        return not self._isr_done
