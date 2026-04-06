# *****************************************************************************
#       Project: ZBVR - Zion Brock Vintage Radio
#  Project Repo: https://github.com/mloit/zbvr-firmware
#         About: Baseline firmware for the Zion Brock Vintage Radio 
#
#          File: led.py
#       Version: 26.0.1 Alpha
#   Description: Abstraction for RGB LED control. Current implementation is 
#                based on using NeoPixels
# 
#        Author: Mark Loit
#        Credit: Zion Brock
#
#       License: CC BY-NC-SA
# 
#  (c) Copyright 2026 Mark Loit. All Rights Reserved.
# ****************************************************************************

import neopixel
from machine import Pin

print("Loading Module: LED")

# ****************************************************************************
# LED Class
# ****************************************************************************
class LED:
    def __init__(self, pin = 16, count = 1):
        self._np = neopixel.NeoPixel(Pin(pin), n=count, bpp=3, timing=1)
        self._np.fill((0,0,0))
        self._np.write()
    
    # set the colour of the LED, no value will output white
    def color(self, RGBval = (63,63,63)):
        self._np[0] = RGBval
        self._np.write()
