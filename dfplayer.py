# *****************************************************************************
#       Project: ZBVR - Zion Brock Vintage Radio
#  Project Repo: https://github.com/mloit/zbvr-firmware
#         About: Baseline firmware for the Zion Brock Vintage Radio 
#
#          File: dfplayer.py
#       Version: 26.0.1
#   Description: Full implementation of the serial protocol used by the
#                DFPlayer from DFRobot. 
# 
#        Author: Mark Loit
#        Credit: Zion Brock (Original Vintage Radio code and inspiration)
#
#       License: CC BY-NC-SA
# 
#  (c) Copyright 2026 Mark Loit. All Rights Reserved.
# ****************************************************************************

# TODO:
#  - Create custom exceptions and get rid of the generic OSErrors

from machine import UART, Pin
import time, micropython, machine

print("Loading Module: DFPlayer")

# baudrate used by the DFPlayer protocol
_DF_BAUD = 9600

_DF_FRAME_TIME  = 10  # milliseconds - approximate time to send 1 frame of 10 bytes, 10 bits per byte, at 9600 baud
_DF_ACK_TIMEOUT = 25  # milliseconds - max time to wait for an ACK or Error (2.5 frame times)
_DF_QUERY_TIMEOUT = 100 # milliseconds - max time for a query
_DF_FILE_QUERY_TIMEOUT = 1000 # milliseconds - max time for a file/folder query (these can take longer than normal queries)

# ****************************************************************************
# Command Constants
# ****************************************************************************
class DFcmd:
    NONE     = 0x00
    RESET    = 0x0c     # 0c 0? 00 00 -- reset DFPlayer
    class device:
        NEXT     = 0x01 # 01 0? 00 00 -- play next track
        PREV     = 0x02 # 02 0? 00 00 -- play previous track
        PLAY     = 0x0d # 0d 0? 00 00 -- play current track
        PAUSE    = 0x0e # 0e 0? 00 00 -- pause current track
        STOP     = 0x16 # 16 0? 00 00 -- stop all playback (3.6.10)
        RANDOM   = 0x18 # 18 0? 00 00 -- random playback across entire disk (3.6.12)
    class play: 
        DISK     = 0x03 # 03 0? xx xx -- play track (0001 - 3000) device (3.6.1)
        FOLDER   = 0x0f # 0f 0? FF TT -- play track (TT: 001-255) in folder (FF: 00-99) (3.6.5)
        MP3      = 0x12 # 12 0? xx xx -- play track (0001 - 3000) in '/MP3' folder (3.6.7)
        BIG      = 0x14 # 14 0? FT TT -- play track (TTT: 0001 - 1999) in folder (F: 01-15) with 4 digit names (3.6.9)
    class advert: # inserts/preemptive
        PLAY     = 0x13 # 13 0? 00 xx -- pause normal playback and play ad track (0001 - 3000) from '/ADVERT' (3.6.8)
        STOP     = 0x15 # 15 0? 00 00 -- stop playing ad, resume current track (3.6.10)
    class volume:
        UP       = 0x04 # 04 0? 00 00 -- increase volume
        DN       = 0x05 # 05 0? 00 00 -- decrease volume
        SET      = 0x06 # 06 0? 00 xx -- volume 0-30 (3.6.2)
    class loop:
        DISK_ONE = 0x08 # 08 0? 00 xx -- repeatedly plays specified device track (0001-3000) (3.6.3)
        DISK_ALL = 0x11 # 11 0? 00 0x -- set repeat all of root folder 1=enable, 0=disable (3.6.6)
        FOLDER   = 0x17 # 17 0? 00 xx -- repeat folder (01 - 99) (3.6.11)
        CURRENT  = 0x19 # 19 0? 00 0x -- x=0 enable; x=1 disable; set repeat current track (3.6.13)
    class set:
        SOURCE   = 0x09 # 09 0? 00 0x -- param: storage (3.6.4)
        EQ       = 0x07 # 07 0? 00 0x -- param: eq_mode
        SLEEP    = 0x0a # 0a 0? 00 00 -- set sleep mode
        AMP      = 0x10 # 10 0? AA GG -- MSB=1: amp on (AA: 0-1); LSB: gain (GG: 0-31)
        DAC      = 0x1a # 1a 0? 00 0x -- x=0 enable; x=1 disable; set DAC (3.6.14)
    class query:
        STORAGE      = 0x3f # 3f 0? 00 00 -- get current storage device (3.7.1)
        STATUS       = 0x42 # 42 0? 00 00 -- get current status (3.7.2)
        GET_VOL      = 0x43 # 43 0? 00 00 -- get current volume
        GET_EQ       = 0x44 # 44 0? 00 00 -- get current eq mode
        USB_TOTAL    = 0x47 # 47 0? 00 00 -- number of tracks in usb drive
        SDC_TOTAL    = 0x48 # 48 0? 00 00 -- number of tracks in sd drive
        FLASH_TOTAL  = 0x49 # 4a 0? 00 00 -- number of tracks in onboard FLASH  (not documented, but in ref code)
        USB_CUR      = 0x4b # 4b 0? 00 00 -- current track being played on usb
        SDC_CUR      = 0x4c # 4c 0? 00 00 -- current track being played on sd
        FLASH_CUR    = 0x4d # 4d 0? 00 00 -- current track being played on FLASH (not documented, but in ref code)
        GET_TRACKS   = 0x4e # 4e 0? 00 xx -- number of tracks in folder (01 - 99) (3.7.3)
        GET_FOLDERS  = 0x4f # 4f 0? 00 00 -- number of folders on current storage (3.7.4)

# ****************************************************************************
# Parameter Constants
# ****************************************************************************
class DFstorage:
    AUTO       = -1   # use currently selected storage (internal value only)
    NONE       = 0
    USB        = 0x01 # USB Storage
    SDC        = 0x02 # SDCard
    PC         = 0x04 # USB Target Mode? -- only shows in message after reset/boot/storage query
    FLASH      = 0x08 # Flag set in storage query response? (onboard flash)
    SYSTEM     = 0x10 # flag used in status query

class DFequalizer:
    NORM       = 0    # normal EQ setting
    POP        = 1    # Pop music optimized Eq
    ROCK       = 2    # Rock music optimized Eq
    JAZZ       = 3    # Jazz music optimized Eq
    CLASSICAL  = 4    # Classical music optimized Eq
    BASS       = 5    # Bass optimized Eq

# Note: These values are inverse of what is intuitive
class DFenable_neg: # used for the DAC and loop.current enables
    YES        = 0    # Enable DAC or loop.current mode 
    NO         = 1    # disable DAC or loop.current mode

class DFenable: # used for other enables
    NO         = 0    # disable DAC or loop.current mode
    YES        = 1    # Enable DAC or loop.current mode 

class DFresponse: # we only worry about non-command responses here (or where response code is not the same as command code)
    DEV_ADDED    = 0x3a # 3a 00 00 xx -- ASYNC storage plugged in, data follows storage values (3.5.5)
    DEV_REMOVED  = 0x3b # 3b 00 00 xx -- ASYNC storage removed, data follows storage values (3.5.5)
    USB_PLAY     = 0x3c # 3c 00 xx xx -- ASYNC track on usb drive finished playing (3.5.2)
    SDC_PLAY     = 0x3d # 3d 00 xx xx -- ASYNC track on SD card finished playing (3.5.2)
    STORAGE      = 0x3f # 3f 00 00 0x -- ASYNC/SYNC Reset/Boot and Storage Query response/message. (3.5.1 / 3.7.1)
    ERROR        = 0x40 # 40 00 00 xx -- ASYNC/SYNC module returns error data param xx is error code (3.5.4)
    FEEDBACK     = 0x41 # 41 00 00 00 -- SYNC Acknowledge response of "feedback flag" is sent (3.5.3)

class DFerrors:
    NONE         = 0x00 # "No error",
    BUSY         = 0x01 # "Module is Busy Initializing",
    SLEEPING     = 0x02 # "Currently in Sleep Mode",
    BAD_FRAME    = 0x03 # "Serial RX Error",
    BAD_SUM      = 0x04 # "Bad Checksum",
    SCOPE        = 0x05 # "Track out of scope",
    NOT_FOUND    = 0x06 # "Track not found", # also returned if get_tracks called on empty folder (3.7.3)
    INSERT       = 0x07 # "Insertion error", # error playing a preemptive 'ADVERT' track
    READ_ERROR   = 0x08 # "SD Card read failed",
    GOODNIGHT    = 0x0a # "Entered into sleep"

    MAX_ERROR    = 0x0b # for range-checking, set to one more than the highest known error code

class DFstatus:
    STOPPED     = 0 # no track playing
    PLAYING     = 1 # track playing
    PAUSED      = 2 # track is paused
    INSERTING   = 3 # internal/local state, ADVERT track playing (normal track paused)
    INSERTPAUSE = 4 # internal/local state, ADVERT track paused (normal track paused)

# ****************************************************************************
# Strings for terminal messages
# ****************************************************************************
DFerror_strings = {
    0x00: "No error",
    0x01: "Module is Busy Initializing",
    0x02: "Currently in Sleep Mode",
    0x03: "Serial RX Error",
    0x04: "Bad Checksum",
    0x05: "Track out of scope",
    0x06: "Track not found", # also returned if get_tracks called on empty folder (3.7.3)
    0x07: "Insertion error", # error playing a preemptive 'ADVERT' track
    0x08: "SD Card read failed",
    0x09: "Undocumented errorr (0x09)", # this code value isn't mentioned in code or documentation
    0x0a: "Entered into sleep"
}

DFstorage_strings = { # these are actually bitmask values, so combined strings are here for convenient lookups
      -1: "AUTO",    # auto select/current
    0x00: "None",
    0x01: "USB",     # USB Storage
    0x02: "SDC",     # SDCard
    0x03: "USB+SDC", 
    0x04: "PC",      # USB Target Mode? -- only shows in message after reset/boot/storage query
    0x05: "PC+USB",
    0x06: "PC+SDC",
    0x07: "PC+USB+SDC",
    0x08: "FLASH",   # always sset in storage query, never set in boot response
    0x09: "USB+FLASH",
    0x0a: "SDC+FLASH",
    0x0b: "USB+SDC+FLASH", 
    0x0c: "PC+FLASH",
    0x0d: "PC+USB+FLASH",
    0x0e: "PC+SDC+FLASH",
    0x0f: "PC+USB+SDC+FLASH",
    0x10: "System"   # flag used in status query
}

_STORAGE_MASK = 0x03  # used to mask to only the 2 main storage devices SDC, USB

DFstatus_strings = {
    0: "Stopped",
    1: "Playing",
    2: "Paused"
}

DFequalizer_strings = {
    0: "Normal",    # normal EQ setting
    1: "Pop",       # Pop music optimized Eq
    2: "Rock",      # Rock music optimized Eq
    3: "Jazz",      # Jazz music optimized Eq
    4: "Classical", # Classical music optimized Eq
    5: "Bass"       # Bass optimized Eq
}

# class DFProtocolErrorException(Exception):
#     """Raised when an error is received back"""

#     def __init__(self, error, message):
#         self.errno = error
#         self.message = f"DFPlayer: "
#         super().__init__(self.message)



# ****************************************************************************
# Protocol Constants
# ****************************************************************************
# DFPlayer Packet:
# 0: 7E - Start Byte
# 1: FF - Version (Always 0xFF)
# 2: 06 - Payload Length (Always 6)
# 3: ?? - Command
# 4: 0? - Feedback Request (0 = no, 1 = yes)
# 5: ?? - Parameter High
# 6: ?? - Parameter Low
# 7: ?? - Checksum High
# 8: ?? - Checksum Low
# 9: EF - End Byte
# constants for raw packes
class DFframe:
    class val: # fixed byte values
        STX      = 0x7E # Start Byte
        ETX      = 0xEF # End Byte
        VER      = 0xFF # Version (Always 0xFF)
        LEN      = 6    # Payload length (Always 6)
    # byte positions within the frame
    STX         = 0 # start sentinal position
    VER         = 1 # version position
    LEN         = 2 # length position
    CMD         = 3 # Command Pos
    REQ         = 4 # Feedback Request Pos
    PARAMETERHI = 5 # High byte of payload/parameter data
    PARAMETERLO = 6 # Low byte of payload/parameter data
    CHECKSUMHI  = 7 # High byte of checksum
    CHECKSUMLO  = 8 # Low byte of checksum
    ETX         = 9 # end sentinal position

    LENGTH = 10   # length of a DFPlayer protocol frame

# ****************************************************************************
# DFPlayer Hardware Implementation
# ****************************************************************************
class DFPlayer:
    LOWLEVEL = False # include  packet level debgging messages

    # constructor
    # uart: the UART unit ID (0 or 1)
    # tx and rx: pin numbers for the tx and rx pins used
    # ack: sets if the class should used ack confirmation for commands without responses (default enabled) [recommended]
    # debug: enables debug message printing to the console (default disabled)
    def __init__(self, uart, tx, rx, ack=True, debug = False):
        # create and initialize out buffers
        self._sending  = bytearray(DFframe.LENGTH)
        self._received = bytearray(DFframe.LENGTH)
        self._rxd = CircularBuffer(32)
        self._sending[DFframe.STX] = DFframe.val.STX
        self._sending[DFframe.ETX] = DFframe.val.ETX
        self._sending[DFframe.VER] = DFframe.val.VER
        self._sending[DFframe.LEN] = DFframe.val.LEN
        self._use_ack = ack
        self.debug = debug

        self._last_error = DFerrors.NONE # last received error code (valid when has_error is True)
        self._has_error = False # set to true when an error code is received, reading code must clear this
        self._query_lo = 0 # query result low byte
        self._query_hi = 0 # query result high byte

        # initialize other state variables
        self._online = False
        self._no_media = True
        self._storage = DFstorage.NONE
        self._status = DFstatus.STOPPED

        self._wait_ack = False     # flag for when a command is waiting for an acknowledge
        self._waiting = False      # indicates a query call is waiting for a response
        self._query = DFcmd.NONE   # command that made the query call

        # initialize the UART
        self._uart = UART(uart, tx=Pin(tx), rx=Pin(rx), baudrate=_DF_BAUD)

        # clear anything that might already be in the RX buffer
        nbytes = self._uart.any()
        if nbytes:
            self._uart.read(nbytes)
        # register the receive handler
        self._uart.irq(handler=self._uart_isr, trigger=UART.IRQ_RXIDLE) # type: ignore - This is fine

    # debug message printer
    def _print(self, *msg):
        if self.debug:
            print(" ".join(str(val) for val in msg))

# ****************************************************************************
# UART Interrupt handler for received data
# ****************************************************************************
    def _uart_isr(self, uart):
        while uart.any():
            if self._rxd.is_full():
                break
            try:
                val = uart.read(1)
            except:
                val = None
            
            if not (val is None):
                self._rxd.put(val[0])

        micropython.schedule(self._packet_processor, None)

# ****************************************************************************
# Packet RX message handlers
# ****************************************************************************
    def _handle_boot(self, sto):
        self._print("Boot message received")
        self._print("Detected Storage:", DFstorage_strings[sto & _STORAGE_MASK])
        self._online = True
        if((sto & DFstorage.SDC) != 0):
            self._no_media = False
        self._storage = sto

    def _handle_error(self, errno):
        # if we are waiting for a query response, or an ack, we can expect an error at this time
        # otherwise this is an unexpected message
        if not (self._waiting or self._wait_ack):
            if errno < DFerrors.MAX_ERROR:
                print("Unexpected Error Response: " + DFerror_strings[errno])
                raise OSError(DFerror_strings[errno])
            else:
                print(f"Unknown Error Response: Error{errno:02x}")
                raise OSError("Error code out of range")

        # special case while booting (maybe)
        if (not self._online) and errno == DFerrors.BUSY:
            return #nothing more to do

        # special case for get folder tracks queries
        # we want to fake a valid response of 0 if we get a not found error
        if self._waiting and errno == DFerrors.NOT_FOUND and self._query == DFcmd.query.GET_TRACKS:
            self._query_hi = 0
            self._query_lo = 0
        else: # otherwise set the error states
            self._last_error = errno
            self._has_error = True

        # unblock any code waiting
        self._waiting = False
        self._wait_ack = False
        self._query = DFcmd.NONE

    def _handle_mount(self, sto):
        self._print("Mount message received")
        self._print("Detected Storage:", DFstorage_strings[sto & _STORAGE_MASK])
        self._storage |= sto
        if((sto & DFstorage.SDC) != 0):
            self._no_media = False

    def _handle_unmount(self, sto):
        self._print("Unnount message received")
        self._print("Removed Storage:", DFstorage_strings[sto & _STORAGE_MASK])
        self._storage &= ~sto
        if((sto & DFstorage.SDC) != 0):
            self._no_media = True
            self._status = DFstatus.STOPPED
    
    def _handle_play_stop(self, cmd, par_hi, par_lo):
        par16 = (par_hi << 8) + par_lo
        cmd -= 0x3b # convert the command to a storage value
        self._print(f"play state change message received - track: {par16:04d} stopped on", DFstorage_strings[cmd])
        self._status = DFstatus.STOPPED

# ****************************************************************************
# Packet RX message handling dispatcher
# ****************************************************************************
    def _packet_processor(self, _):
        # we have more time here to do stuff
        if self.LOWLEVEL:
            self._print("Received", self._rxd.size(), "bytes")
        if self._rxd.is_empty():
            return         # nothing more to do

        # scan past and discard any unexpected values before STX
        start = False
        while not start:
            val = self._rxd.peek()
            if val == DFframe.val.STX:
                start = True
                break
            # if we get here it wasn't a STX, consume the byte and try again
            self._rxd.get()
            if self._rxd.is_empty():
                return         # nothing more to do
            
        # at this point we have a start
        if self._rxd.size() < DFframe.LENGTH:
            return # need to wait for more data

        # we have a full frames worth of data, copy it into the _received packet buffer for processing
        for idx in range(DFframe.LENGTH):
            self._received[idx] = self._rxd.get()

        valid = self._is_valid()

        # if there's more data, schediule again
        if self._rxd.size() >= DFframe.LENGTH:
             micropython.schedule(self._packet_processor, None)

        if self.LOWLEVEL:
            self._print("packet received:", self._received.hex(' '), "Valid: ", valid)

        if not valid:
            if self.LOWLEVEL:
                self._print("Bad Packet, skipping")
            return

        # big ugly 'if' tree because micropython does not currently support match/case
        # note each case is expected to be non-returning
        cmd = self._received[DFframe.CMD]
        parlo = self._received[DFframe.PARAMETERLO]
        parhi = self._received[DFframe.PARAMETERHI]

        # early exit for query responses, they are not handled here
        if cmd == self._query: ## matches query command, no need to process, the command function will handle that
            self._waiting = False
            self._query = DFcmd.NONE
            self._query_hi = parhi
            self._query_lo = parlo
            return

        if cmd == DFresponse.FEEDBACK: # ACK requested (used for all non-query commands)
            if self.LOWLEVEL:
                self._print("Acknowldege Received")
            self._wait_ack = False
            return

        if cmd == DFresponse.ERROR:
            return self._handle_error(parlo)
        
        if cmd == DFresponse.USB_PLAY: # USB playback stopped
            return self._handle_play_stop(cmd, parhi, parlo)

        if cmd == DFresponse.SDC_PLAY: # SDC playback stopped
            return self._handle_play_stop(cmd, parhi, parlo)


        if cmd == DFresponse.STORAGE: # boot/storage messages (normal STORAGE responses are handled through the query mechanism)
            return self._handle_boot(parlo)
        
        if cmd == DFresponse.DEV_ADDED: 
            return self._handle_mount(parlo)
        
        if cmd == DFresponse.DEV_REMOVED: 
            return self._handle_unmount(parlo)

        # catch-all condition
        # if we got here, we got something unexpected
        self._received[DFframe.CMD] = cmd
        self._print("packet received:", self._received.hex(' '), "Valid: ", valid)
        self._print("Unrecognized Message Code: " + hex(cmd))
        raise OSError("Unhandled Message")

# ****************************************************************************
# Packet validation
# ****************************************************************************
    # calculates and returns the 16bit checksum for the provided frame 
    def _calculate_checksum(self, frame):
        sum = 0
        for idx in range(DFframe.VER, DFframe.CHECKSUMHI):
            sum -= frame[idx]
        sum = sum & 0x0ffff
        return sum

    # validates the structure checksum of the received frame
    def _is_valid(self):
        if self._received[DFframe.STX] != DFframe.val.STX:
            return False
        if self._received[DFframe.ETX] != DFframe.val.ETX:
            return False
        if self._received[DFframe.VER] != DFframe.val.VER:
            return False
        if self._received[DFframe.LEN] != DFframe.val.LEN:
            return False
        
        csum = self._calculate_checksum(self._received)
        psum = (self._received[DFframe.CHECKSUMHI] << 8) + self._received[DFframe.CHECKSUMLO]

        return (csum == psum)

# ****************************************************************************
# Packet TX 
# ****************************************************************************
    # send_frame
    # ack = enables a response packet
    # wait = wait for transmission to complete. 
    def _send_frame(self, cmd, arg = 0, ack = False, wait = False):
        self._sending[DFframe.CMD] = cmd
        self._sending[DFframe.PARAMETERLO] = arg & 0x00ff
        self._sending[DFframe.PARAMETERHI] = (arg >> 8) & 0x00ff

        self._sending[DFframe.REQ] = DFenable.NO
        if ack:
            self._sending[DFframe.REQ] = DFenable.YES
            self._wait_ack = True
            wait = True

        sum = self._calculate_checksum(self._sending)
        self._sending[DFframe.CHECKSUMLO] = sum & 0x00ff
        self._sending[DFframe.CHECKSUMHI] = (sum >> 8) & 0x00ff

        if not self._uart.txdone(): # make sure any previous packet is fully sent
            self._uart.flush()
            self._df_sleep_wait(10)

        self._uart.write(self._sending)
        if wait:
            self._uart.flush()

    # sends a command without generating or waiting for an acknowledge
    def _send_command(self, cmd, arg = 0, wait = False):
        if (not self._online) or (self._no_media):
            raise OSError("DFPlayer not online")
        
        self._send_frame(cmd, arg=arg, wait=wait)

    # sends a command, waits for the acknowledgement
    def _send_command_confirmed(self, cmd, arg = 0, timeout=_DF_ACK_TIMEOUT):
        if (not self._online) or (self._no_media):
            raise OSError("DFPlayer not online")
        
        # note only confirms if _use_ack is True
        self._send_frame(cmd, arg=arg, ack=self._use_ack, wait=True)

        deadline = time.ticks_add(time.ticks_ms(), timeout) # calculate the timeout
        if self._use_ack:
            while self._wait_ack and (time.ticks_diff(deadline, time.ticks_ms()) > 0):
                self._df_sleep_wait(_DF_FRAME_TIME // 2) # test for acknoledge twice every frame-time
        else:
            self._df_sleep_wait(timeout) # wait the timeout period for an error response
            self._wait_ack = False

        if self._wait_ack: # we timed out!
            self._wait_ack = False
            print(f"Command 0x{cmd:02x} timed out")
            raise OSError("DFPlayer: Operation timed out")

        if self._has_error:
            errno = self._get_last_error()
            print(f"Command 0x{cmd:02x} failed with error:",DFerror_strings[errno])
            raise OSError(DFerror_strings[errno])

    # sends a query, and waits for a response
    def _send_query(self, cmd, arg = 0, timeout=_DF_QUERY_TIMEOUT):
        if (not self._online) or (self._no_media):
            raise OSError("DFPlayer not online")
        
        self._waiting = True
        self._query = cmd
        self._send_frame(cmd, arg=arg, wait=True)

        deadline = time.ticks_add(time.ticks_ms(), timeout) # calculate the timeout
        while self._waiting and (time.ticks_diff(deadline, time.ticks_ms()) > 0):
            self._df_sleep_wait(_DF_FRAME_TIME // 2)

        if self._waiting: # we timed out!
            self._waiting = False
            print(f"Query 0x{cmd:02x} timed out")
            raise OSError("DFPlayer: Operation timed out")

        if self._has_error:
            errno = self._get_last_error()
            print(f"Query 0x{cmd:02x} failed with error:",DFerror_strings[errno])
            raise OSError(DFerror_strings[errno])

    # returns and clears the last error received
    def _get_last_error(self):
        self._has_error = False
        errno = self._last_error
        self._last_error = DFerrors.NONE
        return errno
    
    def _get_query_result(self):
        rval = (self._query_hi << 8) + self._query_lo
        self._query_hi = 0
        self._query_lo = 0
        return rval

    # break longer waits into shorter segments
    # to allow othe rbackground things to happen
    def _df_sleep_wait(self, duration):
        while duration > 5:
            time.sleep_ms(5)
            duration -= 5
        time.sleep_ms(duration)


# ****************************************************************************
# ****************************************************************************
#
# DFPlayer Higher Level API
#
# ****************************************************************************
# ****************************************************************************


# ****************************************************************************
# DFPlayer system commands
# ****************************************************************************
    # Reset DFPlayer
    #     RESET        0c 0? 00 00 -- reset DFPlayer
    def reset(self):
        self._print("DF: reset()")

        self._send_frame(DFcmd.RESET, wait=True)
        self._df_sleep_wait(10)
        self.set_offline()

    # Sleep the DFPlayer 
    #     SLEEP    = 0x0a # 0a 0? 00 00 -- set sleep mode
    def sleep(self):
        self._print("DF: sleep()")
        self._send_command_confirmed(DFcmd.set.SLEEP)
        #TODO: manage object state for sleeping

# ****************************************************************************
# DFPlayer general queries
# ****************************************************************************
#ISSUES/LIMITATIONS: 
# While the DFPlayer supports having files in ROOT, as well as a folder called 
# MP3, and another called ADVERT. There is no documented way to query the 
# existence of these directories or how many tracks they contain.
# The GET_TRACKS command only accepts numbered folders
# The *_ROOT (renamed to *_TOTAL) commands return the total number of files on
# the disk, not the number of files in the root directory as the name suggested
# The GET_FOLDERS function appears to return the total number of directory 
# entries, as such it includes ROOT and the MP3 and ADVERT directories

    # get current device status
    #     STATUS       42 0? 00 00 -- get current status (3.7.2)
    def get_status(self):
        self._print("DF: get_status()")

        self._send_query(DFcmd.query.STATUS)
        return self._get_query_result()

    # get root file count for device (code seems to suggest this is total disk files)
    #     USB_TOTAL     47 0? 00 00 -- number of tracks in usb drive
    #     SDC_TOTAL     48 0? 00 00 -- number of tracks in sd drive
    #     FLASH_TOTAL   49 0? 00 00 -- number of tracks in onboard FLASH  (not documented, but in ref code)
    def get_total_files(self, storage = DFstorage.AUTO, timeout=_DF_FILE_QUERY_TIMEOUT):
        self._print(f"DF: get_total_files({DFstorage_strings[storage]})")

        if storage == DFstorage.AUTO:
            storage = self._storage
            if storage & DFstorage.SDC:
                storage = DFstorage.SDC
            elif storage & DFstorage.USB:
                storage = DFstorage.USB
            elif storage & DFstorage.FLASH:
                storage = DFstorage.FLASH
            else:
                storage = 0 # no valid source
            self._print("Using:", DFstorage_strings[storage])

        storage = storage & 0x000f

        count = bin(storage).count('1')
        if (count > 1) or (count == 0):
            raise OSError("Invalid storage selection value")

        if storage & DFstorage.SDC:
            cmd = DFcmd.query.SDC_TOTAL
        elif storage & DFstorage.USB:
            cmd = DFcmd.query.USB_TOTAL
        elif storage & DFstorage.FLASH:
            cmd = DFcmd.query.FLASH_TOTAL
        else:
            raise OSError("Invalid Storage Selector")
        
        self._send_query(cmd)
        return self._get_query_result()

    # get current playing track number 
    # Note: this may be a disk relative number, and not the folder relative one
    #     USB_CUR      4b 0? 00 00 -- current track being played on usb
    #     SDC_CUR      4c 0? 00 00 -- current track being played on sd
    #     FLASH_CUR    4d 0? 00 00 -- current track being played on FLASH (not documented, but in ref code)
    def get_current_track(self, storage = DFstorage.AUTO):
        self._print(f"DF: get_current_track({DFstorage_strings[storage]})")

        if storage == DFstorage.AUTO:
            storage = self._storage
            if storage & DFstorage.SDC:
                storage = DFstorage.SDC
            elif storage & DFstorage.USB:
                storage = DFstorage.USB
            elif storage & DFstorage.FLASH:
                storage = DFstorage.FLASH
            else:
                storage = 0 # no valid source
            self._print("Using:", DFstorage_strings[storage])

        storage = storage & 0x000f

        count = bin(storage).count('1')
        if (count > 1) or (count == 0):
            raise OSError("Invalid storage selection value")

        if storage & DFstorage.SDC:
            cmd = DFcmd.query.SDC_CUR
        elif storage & DFstorage.USB:
            cmd = DFcmd.query.USB_CUR
        elif storage & DFstorage.FLASH:
            cmd = DFcmd.query.FLASH_CUR
        else:
            raise OSError("Invalid Storage Selector")
        
        self._send_query(cmd)
        return self._get_query_result()

    # get file count for the specified folder on the current drive
    #     GET_TRACKS   4e 0? 00 xx -- number of tracks in folder (01 - 99) (3.7.3)
    def get_file_count(self, folder):
        self._print(f"DF: get_file_count({folder:02d}) [{DFstorage_strings[self._storage & _STORAGE_MASK]}]")

        self._send_query(DFcmd.query.GET_TRACKS, arg=folder, timeout=_DF_FILE_QUERY_TIMEOUT)
        return self._get_query_result()

    # get folder count for the current drive
    # The command appears to return the total number of folders on the disk, including ROOT
    # the function subtracts one to account for ROOT
    #     GET_FOLDERS  4f 0? 00 00 -- number of folders on current storage (3.7.4)
    def get_folder_count(self):
        self._print(f"DF: get_folder_count() [{DFstorage_strings[self._storage & _STORAGE_MASK]}]")

        self._send_query(DFcmd.query.GET_FOLDERS, timeout=_DF_FILE_QUERY_TIMEOUT)
        return self._get_query_result() - 1

# ****************************************************************************
# Playbck Controls
# ****************************************************************************

# device playback controls
    # play/resume current track
    def play(self):
        self._print("DF: play()")

        self._send_command_confirmed(DFcmd.device.PLAY)

        if self._status <= DFstatus.PAUSED:
            self._status = DFstatus.PLAYING
        else: # must be in advert mode
            self._status = DFstatus.INSERTING

    # pause playback
    def pause(self):
        self._print("DF: pause()")

        self._send_command_confirmed(DFcmd.device.PAUSE)

        if self._status <= DFstatus.PAUSED:
            self._status = DFstatus.PAUSED
        else: # must be in advert mode
            self._status = DFstatus.INSERTPAUSE

    # stop all playback
    def stop(self):
        self._print("DF: stop()")

        self._send_command_confirmed(DFcmd.device.STOP)

        self._status = DFstatus.STOPPED

    # play previous track
    def previous(self):
        self._print("DF: previous()")

        self._send_command_confirmed(DFcmd.device.PREV)

        self._status = DFstatus.PLAYING

    # play next track
    def next(self):
        self._print("DF: next()")

        self._send_command_confirmed(DFcmd.device.NEXT)

        self._status = DFstatus.PLAYING

    # random playback across all folders (3.6.12)
    def play_disk_random(self):
        self._print("DF: play_disk_random()")

        self._send_command_confirmed(DFcmd.device.RANDOM)

        self._status = DFstatus.PLAYING

# general playback controls
    # play disk track (0001 - 3000) (3.6.1)
    def play_disk_track(self, track):
        self._print(f"DF: play_disk_track({track:04d})")

        self._send_command_confirmed(DFcmd.play.DISK, arg = track)

        self._status = DFstatus.PLAYING

    # play track (0001 - 3000) in '/MP3' folder (3.6.7)
    def play_mp3_track(self, track):
        self._print(f"DF: play_mp3_track({track:04d})")

        self._send_command_confirmed(DFcmd.play.MP3, arg = track)

        self._status = DFstatus.PLAYING

    # play track (001-255) in folder (00-99) (3.6.5)
    # note setting Large=True is the same as calling play_large_folder_track()
    def play_folder_track(self, folder, track, large=False):
        if large:
            return self.play_large_folder_track(folder, track)

        self._print(f"DF: play_folder_track({folder:02d}, {track:03d})")

        combined = ((folder & 0x00ff) << 8) + (track & 0x00ff)
        self._send_command_confirmed(DFcmd.play.FOLDER, arg = combined)

        self._status = DFstatus.PLAYING

    # play track (0001 - 3000) in folder (01-15) with 4 digit names (3.6.9)
    def play_large_folder_track(self, folder, track):
        self._print(f"DF: play_large_folder_track({folder:02d}, {track:04d})")

        combined = ((folder & 0x000f) << 12) + (track & 0x0fff)
        self._send_command_confirmed(DFcmd.play.BIG, arg = combined)

        self._status = DFstatus.PLAYING

# advert (insert) playback controls
    #  pause normal playback and play advert track (0001 - 3000) from '/ADVERT' (3.6.8)
    def play_advert(self, track):
        self._print(f"DF: play_advert({track:04d})")

        if self._status != DFstatus.PLAYING:
            raise OSError("DFPlayer not currently playing")
        self._send_command_confirmed(DFcmd.advert.PLAY, arg = track)

        self._status = DFstatus.INSERTING

    # stop playing advert track, resume current track (3.6.10)
    def stop_advert(self):
        self._print("DF: stop_advert()")

        if self._status < DFstatus.INSERTING:
            raise OSError("DFPlayer not currently playing advert")
        self._send_command_confirmed(DFcmd.advert.STOP)

        self._status = DFstatus.PLAYING

# ****************************************************************************
# Loop/Repeat Commands
# ****************************************************************************
    # plays teh specific track on DISK repeatedly
    #     DISK_ONE 08 0? 00 xx -- repeatedly plays specified device track (0001-3000) (3.6.3)
    def loop_one(self, track):
        self._print(f"DF: loop_one({track:04d})")

        self._send_command_confirmed(DFcmd.loop.DISK_ONE, arg = track)
        self._status = DFstatus.PLAYING

    # starts continuous play of all tracks on the disk
    #     DISK_ALL 11 0? 00 0x -- set repeat all of root folder 1=enable, 0=disable (3.6.6)
    def loop_all_start(self):
        self._print("DF: loop_all_start()")

        self._send_command_confirmed(DFcmd.loop.DISK_ALL, arg = DFenable.YES)
        self._status = DFstatus.PLAYING

    # stops continuous play of all tracks on the disk
    #     DISK_ALL 11 0? 00 0x -- set repeat all of root folder 1=enable, 0=disable (3.6.6)
    def loop_all_stop(self):
        self._print("DF: loop_all_stop()")

        self._send_command_confirmed(DFcmd.loop.DISK_ALL, arg = DFenable.NO)
        self._status = DFstatus.STOPPED

    # continuously play the tracks in the specified folder
    #     FOLDER   17 0? 00 xx -- repeat folder (01 - 99) (3.6.11)
    def loop_folder(self, folder):
        self._print(f"DF: loop_folder({folder:02d})")

        self._send_command_confirmed(DFcmd.loop.FOLDER, arg = folder)
        self._status = DFstatus.PLAYING

    # start continuous of the current track
    #     CURRENT  19 0? 00 0x -- x=0 enable; x=1 disable; set repeat current track (3.6.13)
    def loop_current_enable(self):
        self._print("DF: loop_current_enable()")

        self._send_command_confirmed(DFcmd.loop.CURRENT, arg = DFenable.YES)

    # stop continuous of the current track
    #     CURRENT  19 0? 00 0x -- x=0 enable; x=1 disable; set repeat current track (3.6.13)
    def loop_current_disable(self):
        self._print("DF: loop_current_disable()")

        self._send_command_confirmed(DFcmd.loop.CURRENT, arg = DFenable.NO)

# ****************************************************************************
# Volume and Amplifier
# ****************************************************************************
    # get current volume setting (query)
    #     GET_VOL  43 0? 00 00 -- get current volume
    def get_volume(self):
        self._print("DF: get_volume()")

        self._send_query(DFcmd.query.GET_VOL)
        return self._get_query_result()

    # incerase the current volume
    #     UP       04 0? 00 00 -- increase volume
    def volume_up(self):
        self._print("DF: volume_up()")

        self._send_command_confirmed(DFcmd.volume.UP)

    # decrease the current volume
    #     DN       05 0? 00 00 -- decrease volume
    def volume_down(self):
        self._print("DF: vol_down()")

        self._send_command_confirmed(DFcmd.volume.DN)

    # set the current volume
    #     SET      06 0? 00 xx -- volume 0-30 (3.6.2)
    def volume(self, vol):
        vol = max(0, min(30, vol)) # clamp the value to the valid range
        self._print(f"DF: volume({vol})")

        self._send_command_confirmed(DFcmd.volume.SET, arg = vol)

    # enable the amplifier
    #     AMP      10 0? AA GG -- MSB=1: amp on (AA: 0-1); LSB: gain (GG: 0-31)
    def enable_amp(self, gain):
        gain = max(0, min(31, gain)) # clamp the value to the valid range
        self._print(f"DF: enable_amp({gain})")
        gain = gain | 0x0100 # set the amp enable bit
        self._send_command_confirmed(DFcmd.set.AMP, arg = gain)

    # disable the amplifier
    #     AMP      10 0? AA GG -- MSB=1: amp on (AA: 0-1); LSB: gain (GG: 0-31)
    def disable_amp(self, gain):
        self._print("DF: disable_amp()")
        self._send_command_confirmed(DFcmd.volume.SET)

    # enable the DAC
    #     DAC      1a 0? 00 0x -- x=0 enable; x=1 disable; set DAC (3.6.14)
    def enable_dac(self):
        self._print("DF: enable_dac()")
        self._send_command_confirmed(DFcmd.set.DAC, arg = DFenable_neg.YES)

    # disable the DAC
    #     DAC      1a 0? 00 0x -- x=0 enable; x=1 disable; set DAC (3.6.14)
    def disable_dac(self):
        self._print("DF: disable_dac()")
        self._send_command_confirmed(DFcmd.set.DAC, arg = DFenable_neg.NO)

# ****************************************************************************
# Equalizer
# ****************************************************************************
    # get current EQ settings (query)
    #     GET_EQ   44 0? 00 00 -- get current eq mode
    def get_equalizer(self):
        self._print("DF: get_equalizer()")

        self._send_query(DFcmd.query.GET_EQ)
        return self._get_query_result()

    # set the equalizer mode
    #     EQ       07 0? 00 0x -- param: eq_mode
    def equalizer(self, eq):
        if (eq > 5) or (eq < 0): # set any invalid value to 0
            eq = 0
        self._print(f"DF: equalizer({DFequalizer_strings[eq]})")

        self._send_command_confirmed(DFcmd.set.EQ, arg = eq)

# ****************************************************************************
# Storage Device
# ****************************************************************************
    # get storage device info
    #     STORAGE  3f 0? 00 00 -- get current storage device (3.7.1)
    def get_storage(self):
        self._print("DF: get_storage()")

        self._send_query(DFcmd.query.STORAGE)
        return self._get_query_result()

    # set the storage device: (note only a single big can be set in the parameter)
    # this can be used to select unknow/undocumented storage settings
    # suggest to sue the select_XXX routines instead
    #     SOURCE   09 0? 00 0x -- param: storage (3.6.4)
    def set_storage(self, sto):
        sto = sto & 0x00ff
        self._print(f"DF: set_storage({sto:02x})")

        count = bin(sto).count('1')
        if (count > 1) or (count == 0):
            raise OSError("Invalid storage selection value")
        self._send_command_confirmed(DFcmd.set.SOURCE, arg = sto)

    # sets the current drive to be the USB storage
    #     SOURCE   09 0? 00 0x -- param: storage (3.6.4)
    def select_usb(self):
        self._print("DF: select_usb()")

        self._send_command_confirmed(DFcmd.set.SOURCE, arg = DFstorage.USB)

    # sets the current drive to be the SDC storage
    #     SOURCE   09 0? 00 0x -- param: storage (3.6.4)
    def select_sdc(self):
        self._print("DF: select_sdc()")

        self._send_command_confirmed(DFcmd.set.SOURCE, arg = DFstorage.SDC)

# ****************************************************************************
# Status and State
# ****************************************************************************
    def has_sdc(self):
        return (self._storage & DFstorage.SDC)

    def has_usb(self):
        return (self._storage & DFstorage.USB)

    def is_online(self):
        return self._online

    # clears and resets any state
    def set_offline(self):
        self._online = False
        self._no_media = True
        self._storage = DFstorage.NONE
        self._status = DFstatus.STOPPED
        self._waiting = False
        self._wait_ack = False
        self._query = DFcmd.NONE
        self._rxd.clear()

    # returns true for stopped conditions
    def is_stopped(self):
        return self._status == DFstatus.STOPPED

    # returns true for playing condition
    def is_playing(self):
        return (self._status == DFstatus.PLAYING) or (self._status == DFstatus.INSERTING)

    #returns true if paused condition
    def is_paused(self):
        return (self._status == DFstatus.PAUSED) or (self._status == DFstatus.INSERTPAUSE)
    
    # emulate typical disable/enable interrupt behavior for ack processing
    # so we can turn it off to ease the load on the scheduler during
    # critical sections
    def disable_reliability(self):
        ack = self._use_ack
        self._use_ack = False
        return ack

    def enable_reliability(self, enable=True):
        self._use_ack = enable

    # releases any callbacks - object is expected to be destroyed after
    # and a new object will need to be created
    def release(self):
        self._uart.deinit()


# ****************************************************************************
# Circular Buffer
# ****************************************************************************
# simple circular buffer implementation
# should be IRQ safe, as long as there is only one reader and one writer to the buffer
class CircularBuffer:
    def __init__(self, size):

        self._data = bytearray(size)
        self._capacity = size
        self._head = 0 # points to location of where first byte of valid data in buffer is 
        self._tail = 0 # points to location where to load next byte
        self._size = 0 # indicates how many valid bytes in buffer

    # returns true if buffer has no data
    def is_empty(self):
        return self._size == 0

    # retuns true if buffer is full
    def is_full(self):
        return self._size == self._capacity

    # resets the state of the buffer, discarding any data
    def clear(self):
        irq_state = machine.disable_irq() # begin critical section
        self._head = 0
        self._tail = 0
        self._size = 0
        machine.enable_irq(irq_state) # End of critical section

    # returns number of bytes currently stored in the buffer 
    def size(self):
        return self._size

    # reads a single byte from the buffer
    def get(self):
        if self.is_empty():
            raise OSError("No Data")
        pos = self._head
        val = self._data[pos]
        pos += 1
        if pos == self._capacity:
            pos = 0
        irq_state = machine.disable_irq() # begin critical section
        self._head = pos
        self._size -= 1
        machine.enable_irq(irq_state) # End of critical section

        return val

    # reads a single byte from the buffer, does not remove it
    def peek(self):
        if self.is_empty():
            raise OSError("No Data")
        return self._data[self._head]

    # adds a single byte to the buffer
    # val is assumed to be an integer in the range of 0-255
    def put(self, val):
        if self.is_full():
            raise OSError("Buffer Overflow")

        pos = self._tail
        self._data[pos] = val
        pos = pos + 1
        if pos >= self._capacity:
            pos = 0
        irq_state = machine.disable_irq() # begin critical section
        self._tail = pos 
        self._size += 1
        machine.enable_irq(irq_state) # End of critical section

    # returns up to the specified number of bytes from the buffer as a bytearray, and removes them
    def read(self, len = -1):
        if self.is_empty():
            raise OSError("No Data")

        # clamp the length value to the number of bytes we have
        if len <= 0 or len > self._size:
            len = self._size

        start = self._head
        end = start + len - 1
        wrap = False

        if end > self._capacity:
            end -= self._capacity
            wrap = True

        if not wrap:
            rval = self._data[start:end]
        else:
            rval = self._data[start:]+self._data[:end]
        if end == self._capacity:
            end = 0
        irq_state = machine.disable_irq() # begin critical section
        self._head = end
        self._size -= len
        machine.enable_irq(irq_state) # End of critical section

        return rval

    # writes multiple bytes to the buffer 
    # arr is assumed to be a list or array type holding 8bit integer values
    def write(self, arr):
        bytes = len(arr)
        if self.is_full() or self._size + bytes > self._capacity:
            raise OSError("Buffer Overflow")
        pos = self._tail
        idx = 0
        while idx < bytes:
            self._data[pos] = arr[idx]
            pos += 1
            idx += 1
            if pos >= self._capacity:
                pos = 0

        irq_state = machine.disable_irq() # begin critical section
        self._tail = pos
        self._size -= bytes
        machine.enable_irq(irq_state) # End of critical section
