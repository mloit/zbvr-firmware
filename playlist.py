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
SHUFFLE   = 2

# max number of files before it's considered a large folder
FOLDER_THRESHOLD = 255

# private Deck class to manage shuffling of tracks or albums (like a card-deck)
# Notes on shuffling: Algorithm used is the Fisher-Yates Shuffle algorithm
class Deck:
    def __init__(self, shuffle=False, reshuffle=False):
        self._shuffle   = shuffle    # Flag to indicate if we should shuffle the deck before issuing a card
        self._reshuffle = reshuffle  # Flag to indicate if we should reshuffle the deck when we cycle back to the start (requires shuffle to be True)
        self._shuffled  = False      # Flag to indicate if the deck has been shuffled
        self._card      = -1         # Current index into the deck (-1 indicates nothing dealt)
        self._deck      = []         # The deck of cards

    # perform the Fisher-Yates Shuffle
    def do_shuffle(self, start = 0):
        self._shuffled = True # clear the flag, so we're not constantly called
        # nothing to do if shuffle not enabled
        if self._shuffle == False:
            return

        deck = self._deck
        end = len(deck) - 1
        if start >= end: # nothing to do if start is >= end
            return

        for idx in range(start, end): # loop from 0 to end - 1 (always need at least 2 cells)
            swap = random.randint(idx, end) # swap index is random from index to end
            deck[idx], deck[swap] = deck[swap], deck[idx] # swap index with the randomly selected cell
        self._deck = deck

    # shuffles the deck from the current positoon to the end. preserving the current card, and anything before
    def shuffle_end(self):
        self.do_shuffle(self._card + 1)

    # clears the deck
    def clear(self):
        self._shuffled = False
        self._card = -1
        self._deck = []

    # resets the deck
    def reset(self):
        self._shuffled = False
        self._card = -1

    # sets the current card to the first card in the deck
    def start(self):
        self._card = 0

    # sets the current card to last card in the deck
    def end(self):
        self._card = len(self._deck) - 1

    # adds one card to the deck, clears the shuffled flag
    def append(self, card):
        self._deck.append(card)
        self._shuffled  = False

    # adds several cards to the deck, clears the shuffled flag
    def extend(self, cards):
        self._deck.extend(cards)
        self._shuffled  = False

    # sets the deck to the passed deck
    def set_all(self, cards):
        self._deck = cards
        self._card = -1
        self._shuffled  = False

    # returns the full deck
    def get_all(self):
        return self._deck

    # returns true if the current card is the first one in the deck
    def is_first(self):
        return (self._card <= 0)

    # returns true if the current card is the last one in the deck
    def is_last(self):
        return (len(self._deck) == (self._card + 1))

    # returns true when there are no careds in the deck
    def is_empty(self):
        return (len(self._deck) == 0)

    # returns true when no cards have been dealt yet
    def is_undealt(self):
        return (self._card < 0)

    # returns the number of cards in the deck
    def count(self):
        return len(self._deck)

    # sets the shuffle enable for the deck
    def shuffle(self, shuffle):
        self._shuffle = shuffle
        self._shuffled = not shuffle # if shuffle is turned on, force a shuffle

    # deal the top card on the deck
    # will advance the state if current card is -1 (undealt)
    def get(self):
        if len(self._deck) == 0:
            raise OSError("Empty deck has no cards")

        idx = self._card

        # shuffle if necessary (shuffles from current+1 to end)
        if not self._shuffled:
            self.do_shuffle(idx + 1)

        # if no cards dealt, consume the first one
        if idx < 0:
            idx = 0
            self._card = 0

        return self._deck[idx]

    # consumes the current card, andvances to the next (call get() to get the card)
    # cycles back to the start at the end of the deck (reshuffles if set to do so)
    # this is the normal flow
    def next(self):
        cards = len(self._deck)
        if cards == 0:
            raise OSError("Empty deck has no cards")

        idx = self._card

        if (idx + 1) >= cards:
            last = self._deck[cards-1]
            if (self._reshuffle) and (cards > 1):
                self.do_shuffle() # do a full-deck shuffle
                # make sure the first card isn't the last one dealt, if so swap it with a random location
                if self._deck[0] == last:
                    swap = random.randint(1, cards) # swap index is random from index to end
                    self._deck[0], self._deck[swap] = self._deck[swap], self._deck[0] # swap index with the randomly selected cell

        # shuffle if necessary (shuffles from current+1 to end)
        if not self._shuffled:
            self.do_shuffle(idx + 1)

        idx += 1
        if idx >= cards:
            idx = 0

        self._card = idx
        #return self._deck[idx]

    # rewinds to the previous card from the deck (undeal a card, call get() to get the card)
    # cycles back to the start at the end of the deck (does not reshuffle)
    def previous(self):
        if len(self._deck) == 0:
            raise OSError("Empty deck has no cards")

        idx = self._card
        # shuffle if necessary (shuffles from current+1 to end)
        if not self._shuffled:
            self.do_shuffle(idx + 1)
        idx -= 1

        if idx < 0:
            idx = len(self._deck) - 1

        self._card = idx
        #return self._deck[idx]

    # End Deck Class

# ****************************************************************************
# Playlist class
# ****************************************************************************

# Album and track lists are double-indexed to make handling transparent between shuffled
# and unshuffled lists. Internally tracks and album numbers are 0 based

class Playlist:
    def __init__(self, advance_folder=False, shuffle_tracks=False, shuffle_albums=False, shuffle_all=False, auto_reshuffle=False):
        self._reshuffle = auto_reshuffle
        self._shuffle_all = shuffle_all

        if shuffle_all == True:
            self._advance_folder = False # library treated as one giant folder, so nowhere to advance
            self._shuffle_albums = False # library treated as one giant folder, so nothing to shuffle here
            self._shuffle_tracks = True  # library treated as one giant folder, force shuffling as all tracks + albums will be here
        else:
            self._advance_folder = advance_folder
            self._shuffle_albums = shuffle_albums
            self._shuffle_tracks = shuffle_tracks

        self.album_count = 0     # total number of albums - informational only
        self.track_count = 0     # total number of files - informational only
        self.library     = []    # list of entries stored as a tuple (album_id, tracks, shuffle_flag)
        self._dirty      = False # flag to indicate the library and lists are out of sync

        # playlist state
        self.albums = Deck(shuffle=self._shuffle_albums, reshuffle=self._reshuffle) # maintains album playback order
        self.tracks = Deck(shuffle=self._shuffle_tracks, reshuffle=self._reshuffle) # maintains track playback order for current album

    # adds an album to the library, tracks must be non-zero
    def add(self, album, tracks:int, shuffle=False):
        if tracks == 0:
            raise ValueError("Playlist Cannot add albums with zero tracks")
        self.album_count += 1
        self.track_count  += tracks
        self.library.append((album, tracks, shuffle or self._shuffle_tracks))
        self._dirty = True

    # returns true if the playlist is empty
    def is_empty(self):
        return (len(self.library) == 0)

    # internal function to synchronize current library list with the playlist album deck
    # only used when shuffle_all is false (normal operation), as albums may be added over time
    def _sync_albums(self):
        start = self.albums.count()
        stop = self.album_count
        if (stop - start) > 0:
            self.albums.extend(list(range(start, stop)))

    # internal function to synchronize current album track list with the playlist track deck
    # only used when shuffle_all is true, as then we have a potentially growing list of tracks
    def _sync_tracks(self):
        start = self.tracks.count()
        stop = self.track_count
        if (stop - start) > 0:
            self.tracks.extend(list(range(start, stop)))

    # prepares the decks for use (synchronizes with library, and shuffles if necessary)
    # if shuffling is enabled, shuffles are performed now
    def prepare(self):
        self._dirty = False # clear the flag so we don't constantly get called
        if self.is_empty():
            return

        if self._shuffle_all:
            self._sync_tracks()
            self.tracks.shuffle_end()
        else:
            self._sync_albums()
            self.albums.shuffle_end()

    # returns the number of albums in the playlist
    def get_albums(self):
        return self.album_count

    # returns the number of tracks in the playlist
    def get_total_tracks(self):
        return self.track_count

    # returns a copy of the internal playlist list
    def all(self):
        return self.library.copy()

    # reset the state like new -- used to invalidate the playlist
    def clear(self):
        self.album_count = 0     # total number of albums - informational only
        self.track_count = 0     # total number of files - informational only
        self.library     = []    # list of entries stored as a tuple (album_id, tracks, shuffle_flag)
        self._dirty      = False # flag to indicate the library and lists are out of sync
        self.albums.clear()
        self.tracks.clear()

    # converts the combined aalbum/track value to individual album/track values
    # used when shuffle_all is set to work with one big list of tracks
    def _decompose(self, track):
        album = 0
        # walk the library subtracint number of tracks in albums
        # until track is less than the current count. Then track must be
        # within that album
        while track >= self.library[album][TRACKS]:
            track -= self.library[album][TRACKS]
            album += 1
            # range check to make sure we don't go out of bounds
            if album >= self.album_count:
                raise ValueError("decomposed index exceeds album_count")
        return album, track

    # load the tracks for the current album
    def load_tracks(self, album = -1):
        if album < 0:
            album = self.albums.get()
        self.tracks.shuffle(self.library[album][SHUFFLE])
        self.tracks.set_all(list(range(0, self.library[album][TRACKS])))


    # returns true if the current album has more tracks than the threshold
    def is_large_album(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

        if self._dirty:
            self.prepare()

        if self._shuffle_all:
            combined_idx = self.tracks.get()
            album_idx, track_idx = self._decompose(combined_idx)
        else:
            album_idx = self.albums.get()

        return (FOLDER_THRESHOLD < self.library[album_idx][TRACKS])

    # returns a tuple with the current (album id, track id) -- does not advance the state
    def current(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

        if self._dirty:
            self.prepare()

        if self._shuffle_all:
            combined_idx = self.tracks.get()
            album_idx, track_idx = self._decompose(combined_idx)
        else:
            album_idx = self.albums.get()
            # initilialize track list if not already loaded
            if self.tracks.is_empty():
                self.load_tracks(album_idx)
            track_idx = self.tracks.get()

        return self.library[album_idx][ALBUM_ID], track_idx + 1

    # this is the main expected interface call
    # returns a tuple with the new (album id, track id) -- advances track and resets to 0 when the end is reached
    # if advance = False, only track is advanced - ie loops through current album only
    # if advance = True, it also advances album, resetting to 0 when the end is reached - ie loops through all albums
    def next_track(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

        if self._dirty:
            self.prepare()

        if self._advance_folder and self.tracks.is_last():
            self.albums.next()
            self.tracks.clear()
        else:
            self.tracks.next()

        return self.current()

    # same as next_track, but goes in reverse direction
    def previous_track(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

        if self._dirty:
            self.prepare()

        if self._advance_folder and self.tracks.is_first():
            self.albums.previous()
            self.tracks.clear()
            self.load_tracks()
            self.tracks.end()
        else:
            self.tracks.previous()

        return self.current()

    # restart the current album
    def restart_album(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

        if self._dirty:
            self.prepare()

        self.tracks.start()

    # returns a tuple with the next (album id, track id) 
    # -- advances album, and resets to 0 when the end is reached, track is always 0
    def next_album(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

        if self._shuffle_all:
            raise OSError("Cannot advance albums when FULL_SHUFFLE is enabled")

        if self._dirty:
            self.prepare()

        self.albums.next()
        self.tracks.clear()

        return self.current()

    # returns a tuple with the previous (album id, track id) 
    # -- advances album, and resets to MAX when the end is reached, track is always 0
    def previous_album(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

        if self._shuffle_all:
            raise OSError("Cannot advance albums when FULL_SHUFFLE is enabled")

        if self._dirty:
            self.prepare()

        self.albums.previous()
        self.tracks.clear()
        self.load_tracks()
        self.tracks.end()

        return self.current()

    # forces a reshuffle of the albums and tracks
    def reshuffle(self):
        if self.is_empty():
            raise OSError("Playlist: List is empty")

        if self._dirty:
            self.prepare()

        if not self.albums.is_empty():
            self.albums.reset()
            self.albums.do_shuffle()
        if not self.tracks.is_empty():
            self.tracks.reset()
            self.tracks.do_shuffle

    # returns true if the current track is the last track in the album
    def is_last_track(self):
        return self.tracks.is_last()

    # returns true if the current album is the last one in the playlist
    def is_last_album(self):
        return self.albums.is_last()

    # retuns true if this is the last track of the last album
    def is_last(self):
        return (self.albums.is_last() and self.tracks.is_last())

