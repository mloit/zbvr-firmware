# *****************************************************************************
#       Project: ZBVR - Zion Brock Vintage Radio
#  Project Repo: https://github.com/mloit/zbvr-firmware
#         About: Baseline firmware for the Zion Brock Vintage Radio 
#
#          File: playlist.py
#       Version: 26.0.1 Alpha
#   Description: Simple playlist implemetation to manage valid folders
#                maximum number of tracks, and navigating forwards and 
#                backwareds through the list. Designed to be used with 
#                the DFPlayer
# 
#        Author: Mark Loit
#        Credit: Zion Brock
#
#       License: CC BY-NC-SA
# 
#  (c) Copyright 2026 Mark Loit. All Rights Reserved.
# ****************************************************************************

print("Loading Module: Playlist")

# ****************************************************************************
# Playlist class
# ****************************************************************************
class Playlist:
    def __init__(self):
        self.album    = 0    # current album index (albums must have at least one track)
        self.track    = 1    # current track in album (track ID's are 1 based)
        self.is_empty = True # quick flag for when the playlist is empty
        self.playlist = []   # list of entries stored as a tuple (album_id, tracks)

    # adds an album to the playlist tracks must be non-zero
    def add(self, album, tracks):
        if tracks == 0:
            raise OSError("Playlist Cannot add albums with zero tracks")

        self.is_empty = False
        self.playlist.append((album, tracks))

    # this is the main expected interface call
    # returns a tuple with the new (album id, track id) -- advances track and resets to 1 when the end is reached
    # if advance = False, only track is advanced - ie loops through current album only
    # if advance = True, it also advances album, resetting to 0 when the end is reached - ie loops through all albums
    def next_track(self, advance=False):
        if self.is_empty:
            raise OSError("Playlist: List is empty")
        
        track = self.track + 1 # start by advancing the track index
        album = self.album     # get the current album
        if track > self.playlist[self.album][1]:
            if advance:
                album += 1
                if album >= self.albums():
                    album = 0
                self.album = album
            track = 1           
        self.track = track
        return self.playlist[album][0], track

    # same as next_track, but goes in reverse direction
    def previous_track(self, advance=False):
        if self.is_empty:
            raise OSError("Playlist: List is empty")
        
        track = self.track - 1 # start by backing the index up
        album = self.album     # get the current album
        if track < 1:
            track = self.playlist[self.album][1]
            if advance:
                album -= 1
                if album < 0:
                    album += self.albums()
                self.album = album
                track = 1    
        self.track = track
        return self.playlist[album][0], track

    # returns a tuple with the previous (album id, track id) -- advances album, and resets to MAX when the end is reached, track is always 1
    def previous_album(self):
        if self.is_empty:
            raise OSError("Playlist: List is empty")

        track = 1              # reset track index
        album = self.album - 1 # advance the current album to previous
        if album < 0:
            album += self.albums()
        self.album = album
        self.track = track
        return self.playlist[album][0], track


    # returns a tuple with the next (album id, track id) -- advances album, and resets to 0 when the end is reached, track is always 1
    def next_album(self):
        if self.is_empty:
            raise OSError("Playlist: List is empty")

        track = 1              # reset track index
        album = self.album + 1 # advance the current album to next
        if album >= self.albums():
            album = 0
        self.album = album
        self.track = track
        return self.playlist[album][0], track

    # returns a tuple with the current (album id, track id) -- does not advance the state
    def current(self):
        if self.is_empty:
            raise OSError("Playlist: List is empty")
        return self.playlist[self.album][0], self.track

    # returns the number of tracks for the current album
    def tracks(self):
        if self.is_empty:
            return 0
        return self.playlist[self.album][1]

    # returns the number of albums in the playlist
    def albums(self):
        return len(self.playlist)

    # restart the current album
    def restart_album(self):
        self.track = 1

    # reset the state like new -- used to invalidate the playlist
    def clear(self):
        self.album = 0
        self.track = 1
        self.is_empty = True
        self.playlist = []

    # gets the current album index -- for restoring position
    def get_index(self):
        if self.is_empty:
            raise OSError("Playlist: List is empty")
        return self.album

    # sets the current album index -- for restoring position
    # if out of range, resets to 0
    def set_index(self, idx):
        max(0, idx)
        if idx > self.albums():
            idx = 0
        self.album = idx
        self.set_track(self.track) # this will make sure track is still in range

    # sets the current track -- for restoring position
    # if out of rannge, resets to 1
    def set_track(self, track):
        if self.is_empty:
            raise OSError("Playlist: List is empty")
        max(1,track)
        if track > self.playlist[self.album][1]:
            self.track = 1
        self.track = track

    # returns the current album id
    def get_album(self):
        if self.is_empty:
            raise OSError("Playlist: List is empty")
        return self.playlist[self.album][0]
    
    # returns the current track id
    def get_track(self):
        if self.is_empty:
            raise OSError("Playlist: List is empty")
        return self.track
    
    # returns a copy of the internal playlist list
    def all(self):
        return self.playlist.copy()
