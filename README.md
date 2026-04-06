# Zion Brock Vintage Radio Firmware

Baseline MicroPython firmware for the Zion Brock Vintage Radio. While we call it a "radio" that is by appearance and experience only. The device is really a basic MP3 player intended to mimic the feel of an old time AM Radio.

See [Zion's website](https://www.zionbrock.com/radio) for more details on the radio, and the story behind it.

This repository is intended to work in conjunction with the [PCB I designed](https://github.com/mloit/zbvr) for the radio, but the code will also work with the breadboard version featured on Zion's website. Provided that the most recent version of the wiring diagram has been used, which includes both UART connections, and not just the TX line.

---
## Customization

`config.py` contains a number of user options that can be changed to alter the features and behaviour of the code. please see the comments there for more info

## Installation

### The Easy Way

Starting with 26.0.1 The code is available in a `.UF2` file.
- Plug the RP2040 into your computer via USB
- Press and hold the `BOOT` button on the RP2040, tap the `RESET` button. (or hold the `BOOT` button while plugging in)
- A new drive called `RPI-RP2` should appear connected to your computer
- Unzip the firmware from the latest release binary, copy the decompressed `.UF2` file (not the `.ZIP` file) to the `RPI-RP2` drive

At that point the board will program itself, and reset when done. If all goes well, you should get a green LED on the RP2040.

### The Manual Way 

Using [Thonny](https://thonny.org/), or other tool that can connect to a device loaded with MicroPython, upload all the `.py` files and the `AMradioSoud.WAV` file onto your device. Reset your device and the LED on the RP2040 should turn green. (you may need to disconnect from MicroPython tool as it may prevent the code from running automatically) 

### Watch Zion's Tutorial

[![Watch the video](https://img.youtube.com/vi/b8Drmv0MxDI/default.jpg)]([https://youtu.be/nTQUwghvy5Q](https://youtu.be/b8Drmv0MxDI))

---

All code in the 5.x.x versions is Copyright Zion Brock<br>
All code starting at 26.0.0 and beyond is Copyright Mark Loit
