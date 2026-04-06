# Baseline 5.8 – Retro Radio (synced AM + DF fade, stable resume, Option A album wrap)
# Option A: if next album (long-press) does not exist / does not confirm BUSY, wrap to Album 1 Track 1

from machine import Pin, PWM, Timer, UART
import neopixel, ustruct, time

# ===========================
#      CONFIGURATION
# ===========================

PIN_AUDIO       = 3
PIN_BUTTON      = 2
PIN_NEOPIX      = 16
PIN_UART_TX     = 0
PIN_UART_RX     = 1
PIN_SENSE       = 14      # power sense from Rail 2
PIN_BUSY        = 15      # DFPlayer BUSY (0 = playing, 1 = idle)

VOLUME          = 1.0
WAV_FILE        = "AMradioSound.wav"
PWM_CARRIER     = 125_000
DFPLAYER_VOL    = 28

FADE_IN_S       = 2.4            # time to ramp DF volume up while AM plays
DF_BOOT_MS      = 2000           # time after GP14 HIGH before DF reset/play

LONG_PRESS_MS   = 1000           # hold for NEXT ALBUM
TAP_WINDOW_MS   = 800            # time after last tap to decide 1/2/3 taps

ALBUM_FILE      = "album_state.txt"
MAX_ALBUM_NUM   = 99             # folders 01..99 available

# BUSY behavior
BUSY_CONFIRM_MS = 1800           # how long we wait for BUSY low to confirm a track started
POST_CMD_GUARD_MS = 120          # small pause between stop and play commands

# ===========================
#   NeoPixel + Pins
# ===========================

np = neopixel.NeoPixel(Pin(PIN_NEOPIX), 1)
np[0] = (4, 4, 4)
np.write()

button      = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_UP)
power_sense = Pin(PIN_SENSE, Pin.IN, Pin.PULL_DOWN)
pin_busy    = Pin(PIN_BUSY, Pin.IN)

uart = UART(0, baudrate=9600, tx=Pin(PIN_UART_TX), rx=Pin(PIN_UART_RX))

pwm = None
tim = None
MID = 32768

current_album = 1
current_track = 1

# album -> highest track index confirmed to play
KNOWN_TRACKS = {}

# ignore BUSY edges after manual skips so they don't look like "track finished"
ignore_busy_until = 0

# ===========================
#   DFPlayer helpers
# ===========================

def df_send(cmd, p1=0, p2=0):
    pkt = bytearray([0x7E, 0xFF, 0x06, cmd, 0x00, p1 & 0xFF, p2 & 0xFF])
    csum = -sum(pkt[1:7]) & 0xFFFF
    pkt.append((csum >> 8) & 0xFF)
    pkt.append(csum & 0xFF)
    pkt.append(0xEF)
    uart.write(pkt)
    time.sleep_ms(30)

def df_reset():
    print("DF: RESET")
    df_send(0x3F, 0x00, 0x00)
    time.sleep_ms(800)

def df_set_vol(v):
    v = max(0, min(30, v))
    print("DF: set volume", v)
    df_send(0x06, 0x00, v)

def df_play_folder_track(folder, track):
    print("DF: play folder", folder, "track", track)
    df_send(0x0F, folder, track)

def df_stop():
    print("DF: stop")
    df_send(0x16, 0, 0)

# ===========================
#   Album state save / load
# ===========================

def load_state():
    global current_album, current_track, KNOWN_TRACKS
    try:
        with open(ALBUM_FILE, "r") as f:
            raw = f.read().strip()
        print("Loaded raw album_state:", raw)

        parts = raw.split(";")
        a_str, t_str = parts[0].split(",")
        current_album = int(a_str)
        current_track = int(t_str)

        KNOWN_TRACKS = {}
        if len(parts) > 1 and parts[1].startswith("tracks="):
            track_part = parts[1][7:]
            if track_part:
                for pair in track_part.split(","):
                    if not pair:
                        continue
                    a, c = pair.split(":")
                    KNOWN_TRACKS[int(a)] = int(c)

        print("Loaded album", current_album, "track", current_track)
        print("Loaded KNOWN_TRACKS:", KNOWN_TRACKS)

    except Exception as e:
        print("No valid album_state.txt, starting fresh. Reason:", e)
        current_album = 1
        current_track = 1
        KNOWN_TRACKS = {}

def save_state(reason=""):
    global current_album, current_track, KNOWN_TRACKS
    try:
        track_str = ",".join("%d:%d" % (a, c) for a, c in sorted(KNOWN_TRACKS.items()))
        payload = f"{current_album},{current_track};tracks={track_str}"
        with open(ALBUM_FILE, "w") as f:
            f.write(payload)
        print("Saved state", ("[" + reason + "]" if reason else ""), ":", payload)
    except Exception as e:
        print("State save error:", e)

# ===========================
#       WAV Loader
# ===========================

def load_wav_u8(path):
    with open(path, "rb") as f:
        if f.read(4) != b"RIFF":
            raise ValueError("Not RIFF")
        f.read(4)
        if f.read(4) != b"WAVE":
            raise ValueError("Not WAVE")
        samplerate = 8000
        while True:
            cid = f.read(4)
            if not cid:
                raise ValueError("No data chunk")
            clen = ustruct.unpack("<I", f.read(4))[0]
            if cid == b"fmt ":
                fmt = f.read(clen)
                samplerate = ustruct.unpack("<I", fmt[4:8])[0]
            elif cid == b"data":
                data = f.read(clen)
                break
            else:
                f.seek(clen, 1)
    return data, samplerate

print("Loading WAV:", WAV_FILE)
data, SR = load_wav_u8(WAV_FILE)

lut = [0] * 256
scale = int(256 * VOLUME)
for i in range(256):
    d = MID + (i - 128) * scale
    d = max(0, min(65535, d))
    lut[i] = d

# ===========================
#   BUSY helpers
# ===========================

def wait_for_busy_low(timeout_ms=BUSY_CONFIRM_MS):
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
        if pin_busy.value() == 0:
            return True
        time.sleep_ms(25)
    return False

def note_track_learned(album, track):
    global KNOWN_TRACKS
    prev = KNOWN_TRACKS.get(album, 0)
    if track > prev:
        KNOWN_TRACKS[album] = track
        print("Learned track", track, "for album", album, "-> KNOWN_TRACKS =", KNOWN_TRACKS)
        save_state("learned track")

# ===========================
#   Synced AM playback + DF fade + confirm
# ===========================

def play_am_and_fade_df_confirming(folder, track):
    """
    Start DF play immediately, then play AM WAV while fading DF volume up.
    During the fade, we watch BUSY for a confirmation that DF actually started.
    Returns True if we confirm BUSY LOW at any point during the AM window.
    """
    global pwm, tim

    # Start DF track immediately (synced start)
    df_stop()
    time.sleep_ms(POST_CMD_GUARD_MS)
    df_play_folder_track(folder, track)

    np[0] = (0, 10, 0)
    np.write()

    print("RP: starting AM WAV (synced)")

    p = Pin(PIN_AUDIO)
    pwm = PWM(p)
    pwm.freq(PWM_CARRIER)
    pwm.duty_u16(MID)

    state = {"idx": 0, "n": len(data), "done": False}

    # fade AM out at the very end
    fade_out_s = 0.8
    fo = int(SR * fade_out_s)
    if fo > state["n"]:
        fo = state["n"]
    state["fade_out_samples"] = fo

    tim = Timer()

    def isr_cb(_t):
        idx = state["idx"]
        n = state["n"]
        if idx >= n:
            pwm.duty_u16(MID)
            state["done"] = True
            return

        raw_duty = lut[data[idx]]
        fo2 = state["fade_out_samples"]
        if fo2 > 0 and idx >= n - fo2:
            into = idx - (n - fo2)
            remaining = fo2 - into
            if remaining < 0:
                remaining = 0
            scale_val = (remaining * 256) // fo2
            duty = MID + ((raw_duty - MID) * scale_val) // 256
        else:
            duty = raw_duty

        pwm.duty_u16(duty)
        state["idx"] = idx + 1

    tim.init(freq=SR, mode=Timer.PERIODIC, callback=isr_cb)

    # DF fade steps spread across FADE_IN_S (or the AM length, whichever is shorter)
    fade_steps = 20
    fade_delay = int((FADE_IN_S * 1000) / fade_steps)
    if fade_delay < 40:
        fade_delay = 40

    confirmed = False
    confirm_deadline = time.ticks_add(time.ticks_ms(), BUSY_CONFIRM_MS)

    try:
        for step in range(fade_steps + 1):
            df_set_vol(int((step / fade_steps) * DFPLAYER_VOL))

            # while we wait between volume steps, keep checking BUSY
            t_start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t_start) < fade_delay:
                if (not confirmed) and (time.ticks_diff(time.ticks_ms(), confirm_deadline) <= 0):
                    if pin_busy.value() == 0:
                        confirmed = True
                        print("BUSY went LOW -> playback started (confirmed during AM)")
                if state["done"]:
                    break
                time.sleep_ms(10)

            if state["done"]:
                break

        # wait until AM finishes if it hasn't yet
        while not state["done"]:
            if (not confirmed) and (time.ticks_diff(time.ticks_ms(), confirm_deadline) <= 0):
                if pin_busy.value() == 0:
                    confirmed = True
                    print("BUSY went LOW -> playback started (confirmed during AM)")
            time.sleep_ms(20)

    finally:
        try:
            tim.deinit()
        except:
            pass
        try:
            pwm.duty_u16(MID)
        except:
            pass
        np[0] = (0, 0, 0)
        np.write()
        print("RP: AM WAV done")

    return confirmed

# ===========================
#       Start Sequence
# ===========================

def start_sequence_synced():
    """
    On power up or pot ON:
    - Reset DF
    - Start DF play immediately (synced with AM)
    - Fade DF volume up while AM plays
    - If not confirmed, do a quick second-chance re-trigger
    """
    global current_album, current_track

    df_reset()
    df_set_vol(0)

    print("Start sequence (synced): album", current_album, "track", current_track)

    confirmed = play_am_and_fade_df_confirming(current_album, current_track)

    if confirmed:
        note_track_learned(current_album, current_track)
        save_state("boot start")
        return

    print("No BUSY LOW in confirm window (will second-chance after AM ends).")
    print("Second-chance: re-trigger DF after AM")
    df_reset()
    df_set_vol(DFPLAYER_VOL)
    df_stop()
    time.sleep_ms(POST_CMD_GUARD_MS)
    df_play_folder_track(current_album, current_track)

    if wait_for_busy_low(1500):
        print("Second-chance confirmed (BUSY LOW).")
        note_track_learned(current_album, current_track)
        save_state("boot start (2nd chance)")
        return

    print("Second-chance still not confirmed. (Possible BUSY wiring issue or DF not playing.)")

# ===========================
#   Play current + learn
# ===========================

def play_current(label=""):
    global ignore_busy_until, current_album, current_track
    print("Play request", ("[" + label + "]" if label else ""), "album", current_album, "track", current_track)

    df_stop()
    time.sleep_ms(POST_CMD_GUARD_MS)
    df_play_folder_track(current_album, current_track)

    if wait_for_busy_low():
        print("BUSY went LOW -> playback started")
        note_track_learned(current_album, current_track)
        ignore_busy_until = time.ticks_add(time.ticks_ms(), 2000)
        return True

    print("No BUSY LOW -> not confirmed")
    return False

# ===========================
#     MAIN BOOT LOGIC
# ===========================

print("Booting Retro Radio Baseline 5.8")

print("Waiting for GP14 HIGH (power sense)...")
last_hint = time.ticks_ms()
while power_sense.value() == 0:
    if time.ticks_diff(time.ticks_ms(), last_hint) > 1500:
        print("...still waiting for GP14 HIGH")
        last_hint = time.ticks_ms()
    time.sleep_ms(20)

print("GP14 HIGH detected.")
load_state()

print("Giving DFPlayer time to boot:", DF_BOOT_MS, "ms")
time.sleep_ms(DF_BOOT_MS)

start_sequence_synced()

# ===========================
#     BUTTON + BUSY LOOP
# ===========================

print("Button active. tap=next, double=prev, triple=restart album, long=next album")

tap_count = 0
press_start = 0
last_button = 1
last_release_time = 0
prev_busy = pin_busy.value()
last_sense = power_sense.value()
rail2_on = (last_sense == 1)

while True:
    curr = button.value()
    now = time.ticks_ms()

    # 1) Button press edge
    if last_button == 1 and curr == 0:
        press_start = now

    # 2) Button release edge
    elif last_button == 0 and curr == 1:
        press_dur = time.ticks_diff(now, press_start)

        if press_dur >= LONG_PRESS_MS:
            # Long press -> next album (Option A wrap if missing)
            print("Long press: request next album")
            candidate = current_album + 1
            if candidate > MAX_ALBUM_NUM:
                candidate = 1

            current_album = candidate
            current_track = 1
            save_state("long press album change")

            if not play_current("next album"):
                # OPTION A: wrap to album 1 track 1
                print("Album", candidate, "did not confirm. Wrapping to album 1 track 1.")
                current_album = 1
                current_track = 1
                save_state("wrap to album 1 after missing album")
                play_current("wrapped album 1")

            tap_count = 0
            last_release_time = 0

        else:
            tap_count += 1
            last_release_time = now
            print("Short tap detected, tap_count =", tap_count)

        time.sleep_ms(40)

    # 3) Decide 1 / 2 / 3 taps after quiet period
    if tap_count > 0 and time.ticks_diff(now, last_release_time) >= TAP_WINDOW_MS:
        max_known = KNOWN_TRACKS.get(current_album, max(current_track, 1))

        if tap_count >= 3:
            current_track = 1
            save_state("triple tap restart")
            play_current("restart album")

        elif tap_count == 2:
            if max_known < 1:
                max_known = 1
            current_track -= 1
            if current_track < 1:
                current_track = max_known
            save_state("double tap prev")
            play_current("previous track")

        else:
            candidate = current_track + 1
            if candidate <= max_known:
                current_track = candidate
                save_state("single tap next inside known")
                play_current("next track known")
            else:
                current_track = candidate
                if not play_current("probe new track"):
                    current_track = 1
                    save_state("wrap to 1 after silent new track")
                    play_current("wrap to track 1")
                else:
                    save_state("extended known range")

        tap_count = 0
        last_release_time = 0

    # 4) Detect track finished via BUSY edge (0 -> 1)
    if rail2_on:
        b = pin_busy.value()
        now_ts = time.ticks_ms()
        if time.ticks_diff(now_ts, ignore_busy_until) >= 0:
            if prev_busy == 0 and b == 1:
                max_known = KNOWN_TRACKS.get(current_album, max(current_track, 1))
                candidate = current_track + 1
                print("BUSY edge: track finished. Auto advance from", current_track, "->", candidate)

                if candidate <= max_known:
                    current_track = candidate
                    save_state("auto next inside known")
                    play_current("auto next known")
                else:
                    current_track = candidate
                    if not play_current("auto probe new track"):
                        current_track = 1
                        save_state("auto wrap to 1")
                        play_current("auto wrap to track 1")
                    else:
                        save_state("auto extended known range")

        prev_busy = b

    # 5) Watch power sense line for pot OFF / ON
    sense = power_sense.value()
    if sense != last_sense:
        if sense == 0:
            print("GP14 LOW - Rail 2 power OFF (pot turned OFF)")
            rail2_on = False
            save_state("pot turned off")
            df_stop()
        else:
            print("GP14 HIGH - Rail 2 power ON (pot turned ON)")
            rail2_on = True
            save_state("pot turned back on")
            print("Giving DFPlayer time to boot:", DF_BOOT_MS, "ms")
            time.sleep_ms(DF_BOOT_MS)
            start_sequence_synced()
        last_sense = sense

    last_button = curr
    time.sleep_ms(10)


