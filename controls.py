# *****************************************************************************
#       Project: ZBVR - Zion Brock Vintage Radio
#  Project Repo: https://github.com/mloit/zbvr-firmware
#         About: Baseline firmware for the Zion Brock Vintage Radio 
#
#          File: controls.py
#       Version: 26.0.1
#   Description: Timer based input polling and abstraction
# 
#        Author: Mark Loit
#        Credit: Zion Brock (Original code and inspiration)
#
#       License: CC BY-NC-SA
# 
#  (c) Copyright 2026 Mark Loit. All Rights Reserved.
# ****************************************************************************

from machine import Pin, Timer
import time, micropython, machine

print("Loading Module: Controls")

# ****************************************************************************
# Controls class
# ****************************************************************************

# class to provied abstraction for the physical controls
# currently only a single button is implemented
# Button modes
#   1 press → Next track
#   2 presses → Previous track
#   3 presses → Restart album
#   Long hold → Next album
# timing is determined by 4 parameters: debounce, short_press, long_press, tap_window
# For a press to register as short: short_press <= press <= long_press
# For a press to register as long: long_press <= press
# To register multipe presses: short_press -> release -> short_press, where debounce <= release <= tap_window
class Controls:
    class Event:
        NONE   = 0
        SINGLE = 1
        DOUBLE = 2
        TRIPLE = 3
        LONG   = 4
    # create an instance of the controls monitor
    # pin: pin number for the button input
    # rate: speed in Hz at which the input should be sampled
    # debounce: debounce interval in ms
    # short_press: minimum length for a short press in ms (for filtering out accidental presses)
    # long_press: length of a long press in ms
    # tap_window: max gap between presses to register for multiple presses in ms
    def __init__(self, pin, pull=1, invert=False, rate=100, debounce=50, short_press=200, long_press=1000, tap_gap=800):
        # init the gpio here
        if pull < 0:
            self._pin = Pin(pin, Pin.IN, Pin.PULL_DOWN)
        elif pull > 0:
            self._pin = Pin(pin, Pin.IN, Pin.PULL_UP)
        else:
            self._pin = Pin(pin, Pin.IN)
        self._invert = invert            # inverts the state from active low to active high

        # initialize the timer values
        period = int((1 / rate) * 1000)       # convert frequency into a period
        if debounce < period:
            raise OSError("Debounce period is shorter than polling period (1/rate)")
        intervals = int(debounce / period)    # convert debounce time into number of timer intervals
        self._period = period
        self._intervals = intervals

        # save our trigger thresholds
        self._min_press = short_press    # minimum press time to filter out accidental presses
        self._max_press = long_press     # anything longer than this is registered as a long press
        self._max_gap = tap_gap          # max amount of time between presses to register as multi-tap action
        
        # timer related
        self._running = False            # true when the timer is initialized and running
        self._tmr = Timer()

        # debouncing
        self._isr_count = 0
        self._button = False             # debounced value
        
        # event processor internal
        self._in_event = False
        self._event_start = 0
        self._event_state = False        # last state within the current event
        self._event_count = 0            # button press count
        self._wait_timeout = False       # flag indicating timeout in progress
        self._timeout = 0                # timeout time remaining

        # event related
        self._has_event = False
        self._event = Controls.Event.NONE

    # resets the internal state variables, but leaves teh init parameters alone
    def _reset(self):
        # timer related
        self._running = False            # true when the timer is initialized and running

        # debouncing
        self._isr_count = 0
        self._button = False             # debounced value
        
        # event processor internal
        self._in_event = False
        self._event_start = 0
        self._event_state = False        # last state within the current event
        self._event_count = 0            # button press count
        self._wait_timeout = False       # flag indicating timeout in progress
        self._timeout = 0                # timeout time remaining

        # event related
        self._has_event = False
        self._event = Controls.Event.NONE


    # timer callback
    # perfoms the basic debouncing and passes the debounced events onto the event_processor
    def timer_isr(self, _):
        cur = (self._pin.value() == 0) ^ self._invert # read the pin as active low, and invert if necessary
        trigger = False

        if self._wait_timeout:
            self._timeout -= self._period
            if self._timeout <= 0:
                self._wait_timeout = False # stop the timeout timer
                trigger = True             # force an event

        # test for a state, change. if so count it
        if cur != self._button:
            self._isr_count += 1
            if self._isr_count >= self._intervals:
                # we met the threshold, so update the state
                self._button = cur
                self._isr_count = 0
                trigger = True # schedule the event processor
            else: # preserve the state value for the event processor
                cur = self._button 
        else: # start over
            self._isr_count = 0
        
        if trigger:
            micropython.schedule(self._event_processor, cur)

    # event processor
    # triggered by the polling isr on a state change
    # determins the button event from the state changes
    # posts the event on final release
    def _event_processor(self, state):
        now = time.ticks_ms()
        last = self._event_state
        count = self._event_count

        if state and self._wait_timeout: # we only run timeouts on release cycles
            irq_state = machine.disable_irq() # begin critical section
            self._wait_timeout = False
            self._timeout = 0
            machine.enable_irq(irq_state) # End of critical section

        # basic code for single/long type events only
        if self._in_event:
            if (not state) and state == last: # timeout
                count = max(0, min(3, count)) # clamp count to 3
                self._event = count
                self._has_event = True
                self._in_event = False # event is done
                count = 0
            elif not state: # it was a release
                then = self._event_start
                duration = time.ticks_diff(now, then)
                if duration >= self._max_press:  # test for long press first
                    self._event = Controls.Event.LONG
                    self._has_event = True
                    self._in_event = False # event is done
                    count = 0
                elif duration >= self._min_press: # short press / tap
                    count += 1
                    irq_state = machine.disable_irq() # begin critical section
                    self._timeout = self._max_gap
                    self._wait_timeout = True
                    machine.enable_irq(irq_state) # End of critical section
        else:
            count = 0

        if state: # press event
            self._event_start = now
            self._in_event = True

        self._event_count = count
        self._event_state = state

    def get_event(self):
        evt = Controls.Event.NONE
        if self._has_event:
            irq_state = machine.disable_irq() # begin critical section
            evt = self._event
            self._event = Controls.Event.NONE
            self._has_event = False
            machine.enable_irq(irq_state) # End of critical section
        return evt

    def has_event(self):
        return self._has_event

    # starts up the timer and monitoring, resets state
    def start(self):
        if self._running: # already running, nothing more to do
            return
        self._tmr.init(period = self._period, mode=Timer.PERIODIC, callback=self.timer_isr)
        self._running = True

    # shuts down the monitioring, clears state
    def stop(self):
        if self._running:
            self._tmr.deinit()
        self._running = False
        self._reset()

    def is_runnning(self):
        return self._running