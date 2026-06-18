# Zion Brock Vintage Radio Firmware

MicroPython Firmware for the Zion Brock Vintage Radio. While we call it a "radio" that is by appearance and experience only. The device is really a basic MP3 player intended to mimic the feel of an old time AM Radio.

See [Zion's website](https://www.zionbrock.com/radio) for more details on the radio, and the story behind it.

This repository is intended to work in conjunction with the [PCB I designed](https://github.com/mloit/zbvr) for the radio, but the code will also work with the breadboard version featured on Zion's website. Provided that the most recent version of the wiring diagram has been used, which includes both UART connections, and not just the TX line. May work with others as well, provided that they are based on the same.

---
## About the Firmware

This firmware is a complete refactor of Zion's original `5.9.1` "Baseline" firmware. A number of changes to the original firmware have been made to improve stability, and the overall user experience. In addition a number of configurable options are available for customizing the user experience on your radio. (See [Customization](#customization) below for details) See the release notes for the [latest release](https://github.com/mloit/zbvr-firmware/releases/latest) for full details.

### Summary of features

- Centralized configuration settings into 'config.py'
- Added bi-directional communications with the DFPlayer for more reliable operation
- Generation of the playlist at boot to only have folders with valid tracks to prevent lockups
- Quickstart discovery mode (enabled by default) for faster booting
- Enabled watchdog timer to reboot in the event the Python interpreter crashes
- Added colours to various states to give more visual feedback via the LED on the RP2040
- Support for large folder (4 digit track name) playback capability (Folders 01-15 only)
- Capable of handling of live SD card removal and insertion
- Option to change the equalizer setting on the DFPlayer
- Option to auto advance through albums
- Options for track and album shuffle
- Option for full disk shuffle mode
- Option to auto-reshuffle reshuffle albums and tracks when cycling back to the start
- Option for per directory shuffle capability (even number directories are shuffled, odd numbered directories are played sequentially)

---
## Operation

Under normal operation the radio will begin by playing the first track of the first album (folder) on the SD card. (on first power-up) Tracks will be played in sequential order. Once the last track of an album is played, the radio will cycle back and restart from the first track of the same album. This behaviour can be modified through configuration options. (See [Customization](#customization) below for details)

The radio has 2 control inputs. The volume knob on the front and the button on the top. The radio is turned on and off via the knob on the front. Fully counter-clockwise (past the click) turns the radio off. Turning clockwise past the click will turn it on. After that point the knob works as a traditional volume control. Clockwise louder, counter-clockwise quieter. When the radio is on, the LED on the front panel should be on as well.

The top button affects playback. 
- 1 short press: Play next track
- 2 short presses: Play previous track
- 3 short presses: Restart current album
- Long hold: Play next album

When the radio is "Off" it remains internally powered and will remember what album and track were last played, and will continue from that point when it is turned back on (at the beginning of the track. If the radio is unplugged or power is lost, the radio will start back at the first album and track when it is turned "On" again.

---
## Firmware Installation

You can find the latest stable released version from the [Releases page](https://github.com/mloit/zbvr-firmware/releases/latest) page. (Currently 26.0.2)

**NOTE:**
- If there are newer Alpha or Beta releases, you can try those for testing but not recommended for production.
- For production I recommend always using the most recent official release.

### The Easy Way

Starting with 26.0.1 The firmware is available as a `UF2` file for easy installation. No additional tools are required for basic/default installation.

- Download the [latest](https://github.com/mloit/zbvr-firmware/releases/latest) `.uf2.zip` release binary
- Plug the RP2040 into your computer via USB
- Press and hold the `RESET` button on the RP2040
- Press and hold the `BOOT` button (or hold the `BOOT` button while plugging in)
- Release the `RESET` button
- Release the `BOOT` button
- A new removable drive called `RPI-RP2` should appear connected to your computer
- Unzip the firmware from the latest release binary, copy the decompressed `.UF2` file (not the `.ZIP` file) to the `RPI-RP2` drive

At that point the board will program itself, and reset when done. If all goes well, you should get a green LED on the RP2040.

### The Manual Way 

This process requires a debug/development (`REPL`) tool like [Thonny](https://thonny.org/) to install the firmware.

- Follow the instructions for your chosen tool for installing the `MicroPython` interpreter onto the `RP2040` (Note the latest version of `MicroPython` can be installed by [downloading](https://micropython.org/download/RPI_PICO/) and installing the `UF2` image manually)
- Download the latest Source `ZIP` archive of the radio firmware
- Plug the `RP2040` into your computer via USB and connect to it with your `REPL` tool
- Unzip the firmware source code `.ZIP` file, and copy all the files to the `RP2040` (not the `.ZIP`) using your `REPL` tool
    - All `.py` files, the `LICENSE.txt` file and `AMradioSound.wav` file
    - the `README.md` file does not need to be copied
- Disconnect the your `REPL` tool from the `RP2040`
- Reset the `RP2040` by momentarily pressing the `RESET` button

At this point you should get a green LED on the RP2040.

**NOTE:**
If your `REPL` tool remains connected, the firmware may not auto start after reset. You can manually launch it by selecting and opening `main.py` and pressing `run` in your tool.

---
## Customization

By default the firmware runs in a mode equivalent to the original `5.9.1` release. (see [Operation](#operation) above) However, `config.py` contains a number of user options that can be changed to alter the behaviour of the radio. To change the options you will need a `REPL` debug/development environment as described in the [Manual Installation](#the-manual-way) section. Using the `REPL` tool, you can connect to the RP2040. Download the `config.py` file, edit it's contents. Then upload it back to the `RP2040` to save your changes. Next time the firmware is run, it will use the newly saved configuration.

### Configuration Options

Only the most common user-facing options will be outlined here. Unless otherwise noted, the options can be used in conjunction with each other to create more complex behaviour.

#### *App/Playlist/*`PRESERVE`

The `PRESERVE` option is set to `True` by default. This option causes the radio to try and resume playback from the point (start of the current track) where it was last turned off via the knob. Note that if external power is lost, the state will be lost and the radio will start back at the beginning. Setting this option to `False` will cause the radio to always start from the beginning.

#### *App/Playlist/*`CYCLE_ALBUMS`

This option, when set to `True` causes the radio to automatically advance to the next album when it has finished playing the last track of the current album. The default setting is `False` which results in the radio returning to the start of the current album, after the last track is played.

#### *App/Playlist/*`TRACK_SHUFFLE`

This option, when set to `True` will cause the playback order of tracks in an album to be randomized. The order will be reshuffled each time the album is entered for the first time. The default setting is `False` which results in the tracks being played back in sequential order.

#### *App/Playlist/*`ALBUM_SHUFFLE`

This option controls the playback order of albums on the SD card. When set to `True` the order will be randomized on startup. Default setting is `False` which causes albums to be played back in sequential order.

#### *App/Playlist/*`ALTERNATE_SHUFFLE`

This option is causes alternating albums to be played sequentially or shuffled. When set to `True` tracks in odd numbered albums (`01`, `03`, `05`...) will be played back in random order. While tracks in even numbered albums (`02`, `04`, `06`...) will be played back in sequential order. This can be handy if you have some episodic content that you want sequential playback, while also wanting other content to be randomized. This setting has no effect if `TRACK_SHUFFLE` is set to `True`. Default setting is `False`

#### *App/Playlist/*`FULL_SHUFFLE`

This setting causes the entire contents to be treated as a single large album, with playback in random order when set to `True`. Default is `False`, for normal playback. When set to `True` the `CYCLE_ALBUMS`, `TRACK_SHUFFLE`, `ALBUM_SHUFFLE`, and `ALTERNATE_SHUFFLE` options have no effect. This options also changes the button behaviour slightly. 

- 1 short press: Play next track
- 2 short presses: Play previous track
- 3 short presses: Restart from the beginning (don't reshuffle)
- Long hold: Reshuffle and restart from the beginning

#### *App/Playlist/*`AUTO_RESHUFFLE`

When set to `True` This option causes the shuffle order for any of the shuffle options to be re-randomized after the last track is played. This option has no effect if none of the other shuffle options are enabled. Default is setting `False` meaning that cycling back to the start does not result in a reshuffle.

#### *App/Playlist/*`QUICKSTART`

The `QUICKSTART` option, when set to `True` causes album and track discovery to occur in the background, resulting in a faster startup time. The result of this is that on first power-on the first track played will always be from the first album regardless of shuffle mode used. New albums and tracks will be shuffled in as they are discovered (if `ALBUM_SHUFFLE` or `FULL_SHUFFLE` are enabled). When set to `False` the full contents of the SD  card are discovered before playback of the first track begins. This can cause a long delay if there are a lot of albums and or tracks on the disk. However once complete the full contents are known and if `SHUFFLE_ALBUMS` or `FULL_SHUFFLE` are enabled, the first track played is not necessarily from the first album on the SD card. Default setting is `True`.

#### *App/Effects/*`ENABLE`

This option controls the playback of the radio effect that is played at power-on and on album changes. Default is `True`, by setting this to `False` the radio effect will not be played.

#### *App/Effects/*`ON_START`

This option controls if the radio effect sound is played at power-on of the radio. Default is `True`, by setting this to `False` the radio effect will not be played at power-on.

#### *App/Effects/*`ON_ALBUM`

This option controls if the radio effect sound is played on album changes (by button press). Default is `True`, by setting this to `False` the radio effect will not be played on album changes.

#### *Config/Audio/*`VOLUME`

This option sets the playback volume for the Radio effect sound. The range is fractional number between `0.0` and `1.0`. Default is `1.0`. This setting has no effect if 'Effects/`ENABLE`' is set to `False`

#### *Config/DFPlayer/*`VOLUME`

This option sets the playback volume for the `MP3` tracks on the SD card. Range is an integer number between `0` and `30`. Default is `28`.

#### *Config/DFPlayer/*`EQUALIZER`

This option configures a number of built in equalizer presets for `MP3` playback. The range for this is an integer value from `0` to `5`, with the default being `0`.

The `EQUALIZER` values have the following meanings:
- 0: Normal (Default setting)
- 1: Pop
- 2: Rock
- 3: Jazz
- 4: Classical
- 5: Bass

### Additional Options

There are additional configuration options that define hardware settings and timings. These options should normally not need to be changed, and require knowledge of how the code operates to be set appropriately. As such these options will are considered advanced and will not be outlined here. See comments in the code and in `config.py` for further info.

---
## Loading MP3 Content

MP3 content playback is performed by the DFPlayer module used on the PCB. Unfortunately this module does not give direct access to the SD card's contents to the microcontroller. As such MP3 content cannot be loaded over the USB connection, but instead much be loaded onto the SD card directly. 

The DFPlayer is picky about the structure and naming of files, as well as the format of the SD card itself. The DFPlayer is also sensitive to how the MP3 data itself is encoded. The MP3 files should not contain any meta-data (ID3 tags) and should be `CBR` (Constant Bit Rate) encoded and not `VBR` (Variable Bit Rate) Encoded. As the DFPlayer does not properly support `VBR` encoding.

### There's an App for That

Due to the complexity of managing the naming and encoding of the data I recommend using the [Vintage Radio app](https://github.com/alexnoctis76/Vintage_radio) by [alexnoctis76](https://github.com/alexnoctis76). This app automates the process of managing, renaming, and re-encoding any content you want to put on the SD card. While it is capable of installing his firmware, the app is fully compatible with this firmware for the SD card management side of things.

### Manual SD Card Management

#### SD Card Partition and Format

The DFPlayer module is limited in the partition style and filesystem format used on the SD card. The capacity should also be 64GB or less. The partition style must be `MBR` (Master Boot Record) and not `GPT` (GUID Partition Table). The filesystem must be `FAT16` or `FAT32` (recommended), and cannot be `ExFAT` or any other `FAT` variant. For formatting I recommend the [SD Association Format Utility](https://www.sdcard.org/downloads/formatter/) Most new out-of-box cards should already have the correct format and partition style.

**Note:** `SDXC` cards are formatted `ExFAT` from the factory by specification. Even the SD Association tool linked above will default to `ExFAT` if it determines the card is `SDXC` As such I recommend using `SD` or `SDHC` cards if you can. `SDXC` cards may require you to use low-level disk tools to force the format to be `FAT32`

#### Folder Naming

The DFPlayer only supports folders off of the main/root directory of the SD Card. Each folder is considered an "album" by the firmware. Folders must be named numerically with 2 digits ranging from `01` to `99`. Because the firmware cannot directly query for a list of available folders, it must probe for them. The result of this is that folders must be be sequential starting at `01` without any skips, to guarantee that they will get recognized. Folders may be left empty, if a particular arrangement is required, like when `ALTERNATE_SHUFFLE` is enabled.

#### Track Naming

Like folders, tracks are numerically named and must be sequential (with no breaks) and must have a `.mp3` extension. (`.wav` files are also supported) File names are three digits long starting at `001.mp3` and go to `255.mp3` for all folders. Folders `01` to `15` support more than the 255 file maximum of other folders, up to a maximum of 3000 files per directory. If you put more than 255 files in these folders, the filenames must be four digits (`0001.mp3` to `3000.mp3`). If you have 255 or less you must use the 3 digit naming.

Unlike folders which must be numeric only, tracks may contain additional characters after the digits, if you wish to retain the song name. (ie `001 - Song One.mp3`) It is recommended that these extra characters be standard ASCII printable characters, and not special or unicode characters.

### Note for Mac Users

MacOS can create a bunch of additional directories and files on the SD Card, that can sometimes cause a problem. If you plug your SD Card into a Mac computer running MacOS you want to run the `dot_clean` utility just before you eject the disk. 

To clean your disk run `dot_clean /Volumes/<Volume Name>` in a `Terminal` command prompt window where `<Volume Name>` is the name of the SD Card that shows up in `Finder`. Running the command may print some errors, as it is unable to remove everything, but it should get rid of the more critical problems. Namely the shadow `.mp3` files which the DFPlayer thinks are valid MP3 files and may hang if it tries to play one of them.


---
All code in the 5.x.x versions is Copyright Zion Brock<br>
All code starting at 26.0.0 and beyond is Copyright Mark Loit
