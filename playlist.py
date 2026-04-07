# *****************************************************************************
#       Project: ZBVR - Zion Brock Vintage Radio
#  Project Repo: https://github.com/mloit/zbvr-firmware
#         About: Baseline firmware for the Zion Brock Vintage Radio 
#
#          File: playlist.py
#       Version: 26.0.1
#   Description: Simple playlist implemetation to manage valid folders
#                maximum number of tracks, and navigating forwards and 
#                backwareds through the list. Designed to be used with 
#                the DFPlayer
# 
#        Author: Mark Loit
#        Credit: Zion Brock (Original code and inspiration)
#
#       License: CC BY-NC-SA
# 
#  (c) Copyright 2026 Mark Loit. All Rights Reserved.
# ****************************************************************************
import random

print("Loading Module: Playlist")

# positional values for the data in playlist[]
ALBUM_ID  = 0
TRACKS    = 1

# max number of files before it's considered a large folder
FOLDER_THRESHOLD = 255

# ****************************************************************************
# Playlist class
# ****************************************************************************

# Notes on shuffling: Algorithm used is the Fisher-Yates Shuffle algorithm
# When shuffling is enabled, the internal album and track state numbers become 
# index values. (Album was always an index, but now becomes double indexed)
# the index kept is into the xxx_order lists in the state object, which in turn 
# holds the index vor the actual album in the playlist[], while track is the actual track number 1 <= playlist[album][tracks]
# internally tracks and albums are both 0 based. 
# album_id that is returned is the arbitrary value that was passed in during add() 
# track_id is always the internal track index + 1


class Playlist:
    # container class for the state
    class State:
        album          = 0     # current album index (albums must have at least one track)
        track          = 0     # current track in album
        album_count    = 0     # total number of albums - informational only, used for validation on restore
        file_count     = 0     # total number of files - informational only, used for validation on restore
        album_order    = []    # play order (when shuffling) for albums
        track_order    = []    # play order (when shuffling) for tracks in the current album

    def __init__(self, advance_folder=False, shuffle_tracks=False, shuffle_albums=False):
        self._state = Playlist.State()
        self._advance_folder = advance_folder
        self._shuffle_albums = shuffle_albums
        self._shuffle_tracks = shuffle_tracks
        self.playlist = []   # list of entries stored as a tuple (album_id, tracks)
        self._frozen = False

    # perform the Fisher-Yates Shuffle
    def _do_shuffle(self, deck):
        end = len(deck) - 1
        # print(f"Shuffle({end+1}) ", end="")
        for idx in range(0, end): # loop from 0 to end - 1 (always need at least 2 cells)
            # print(".", end="")
            swap = random.randint(idx, end) # swap index is random from index to end
            deck[idx], deck[swap] = deck[swap], deck[idx] # swap index with the randomly selected cell
        # print("", deck)
        return deck

    # creates the shufle list for albumes. Previous state will be overwritten
    def _do_shuffle_albums(self):
        if self.is_empty():
            return # can't shuffle an empty list
        albums = self._state.album_count
        deck = list(range(0, albums))
        self._state.album_order = self._do_shuffle(deck)

    # creates the shufle list for albumes. Previous state will be overwritten
    def _do_shuffle_tracks(self):
        if self.is_empty():
            return # can't shuffle an empty list
        
        album_idx = self._state.album
        if self._shuffle_albums:
            album_idx = self._state.album_order[album_idx]

        tracks = self.playlist[album_idx][TRACKS]
        deck = list(range(0, tracks))
        self._state.track_order = self._do_shuffle(deck)

    # adds an album to the playlist tracks must be non-zero
    def add(self, album, tracks:int):
        if tracks == 0:
            raise ValueError("Playlist Cannot add albums with zero tracks")
        if self._frozen:
            raise OSError("cannot add to frozen playlist")
        # self._state.is_empty = False
        self._state.album_count += 1
        self._state.file_count += tracks
        self.playlist.append((album, tracks))

    # freezes the playlist, preventing furhter additions
    # if shuffling is enabled, shuffles are performed now
    def freeze(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")
        self._frozen = True
        # shuffle if necessary
        if self._shuffle_albums:
            self._do_shuffle_albums()
        if self._shuffle_tracks:
            self._do_shuffle_tracks()

    # returns a tuple with the current (album id, track id) -- does not advance the state
    def current(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

        album_idx = self._state.album
        if self._shuffle_albums:
            album_idx = self._state.album_order[album_idx]

        track_idx = self._state.track
        if self._shuffle_tracks:
            track_idx = self._state.track_order[track_idx]

        return self.playlist[album_idx][ALBUM_ID], track_idx + 1

    # this is the main expected interface call
    # returns a tuple with the new (album id, track id) -- advances track and resets to 0 when the end is reached
    # if advance = False, only track is advanced - ie loops through current album only
    # if advance = True, it also advances album, resetting to 0 when the end is reached - ie loops through all albums
    def next_track(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")
        
        track = self._state.track + 1 # start by advancing the track index
        album = self._state.album     # get the current album
        album_idx = album
        if self._shuffle_albums:
            album_idx = self._state.album_order[album_idx]
        if track >= self.playlist[album_idx][TRACKS]:
            if self._advance_folder:
                album += 1
                if album >= self._state.album_count:
                    album = 0
                self._state.album = album
                if self._shuffle_tracks:
                    self._do_shuffle_tracks()
            track = 0
        self._state.track = track
        return self.current()

    # same as next_track, but goes in reverse direction
    def previous_track(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")
        
        track = self._state.track - 1 # start by backing the index up
        album = self._state.album     # get the current album
        album_idx = album
        if self._shuffle_albums:
            album_idx = self._state.album_order[album_idx]
        if track < 0:
            track += self.playlist[album_idx][TRACKS]
            if self._advance_folder:
                album -= 1
                if album < 0:
                    album += self._state.album_count
                self._state.album = album
                if self._shuffle_tracks:
                    self._do_shuffle_tracks()
                track = 0
        self._state.track = track
        return self.current()

    # returns a tuple with the previous (album id, track id) 
    # -- advances album, and resets to MAX when the end is reached, track is always 0
    def previous_album(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

        album = self._state.album - 1 # advance the current album to previous
        if album < 0:
            album += self._state.album_count
        self._state.album = album
        if self._shuffle_tracks:
            self._do_shuffle_tracks()
        self._state.track = 0         # reset track index
        return self.current()

    # returns a tuple with the next (album id, track id) 
    # -- advances album, and resets to 0 when the end is reached, track is always 0
    def next_album(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

        album = self._state.album + 1 # advance the current album to next
        if album >= self._state.album_count:
            album = 0
        self._state.album = album
        if self._shuffle_tracks:
            self._do_shuffle_tracks()
        self._state.track = 0         # reset track index
        return self.current()

    # restart the current album
    def restart_album(self):
        self._state.track = 0

    # reset the state like new -- used to invalidate the playlist
    def clear(self):
        self._state = Playlist.State()
        self.playlist = []
        self._frozen = False

    # gets the current internal state
    def get_state(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")
        return self._state

    # restore the state of the playlist, only if passed state is compatible with current list
    def set_state(self, state: Playlist.State):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

    # basic check for compatibility, make sure album and total file count match
        if (state.album_count != self._state.album_count) or (state.file_count != self._state.file_count):
            raise OSError("State incompatible with current playlist")
        
    # next make sure the current track is valed for the curent album (album shuld be valid if we passed the previous test) 
        if (state.track > self.playlist[state.album][TRACKS]):
            raise OSError("State incompatible with current playlist")

        self._state = state

    # returns the number of albums in the playlist
    def get_albums(self):
        return self._state.album_count

    # returns the current album
    def get_album(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")
        
        idx = self._state.album
        if self._shuffle_albums:
            idx = self._state.album_order[idx]
        return self.playlist[idx][ALBUM_ID]

    # returns the number of tracks for the current album
    def get_tracks(self):
        if self.is_empty():
            return 0
        return self.playlist[self._state.album][TRACKS]

    # returns the current track id
    def get_track(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")
        
        idx = self._state.track
        if self._shuffle_tracks:
            idx = self._state.track_order[idx]
        return idx + 1 # track id is index + 1

    # returns a copy of the internal playlist list
    def all(self):
        return self.playlist.copy()
    
    # set the cycle state for albums
    def cycle_albums(self, enable):
        self._advance_folder = enable

    # set the shuffle state for albums
    def shuffle_albums(self, enable):
        if self._shuffle_albums:
            return
        self._shuffle_albums = enable
        self._do_shuffle_albums()

    # set the shuffle state for tracks
    def shuffle_tracks(self, enable):
        if self._shuffle_tracks:
            return
        self._shuffle_tracks = enable
        self._do_shuffle_tracks()

    # forces a reshuffle of the albums and tracks
    def reshuffle(self):
        self._do_shuffle_albums()
        self._do_shuffle_tracks()

    # returns true if the playlist is empty
    def is_empty(self):
        return (len(self.playlist) == 0)

    # returns true if the current album has more tracks than the threshold
    def is_large_album(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")
        return (FOLDER_THRESHOLD < self.playlist[self._state.album][TRACKS])
