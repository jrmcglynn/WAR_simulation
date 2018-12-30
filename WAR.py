from random import seed
from random import shuffle
from random import sample
import numpy as np
import pandas as pd


class War(object):
    '''
    Class built to simulate the card game War:
        https://en.wikipedia.org/wiki/War_(card_game)

    Includes settings to control the way discards are handled.

    Parameters:
    ---------
    max_hands: int
        Maximum number of gameplay turns to be simulated. Prevents
        never-ending games from running infinitely.

    discard_recylce_mode: string, ['fifo', 'filo', 'shuffled']
        Controls how discards are recycled back into the players' hands. Can
        either by fifo (first in first out), filo (first in last out), or
        shuffled (discard is shuffled before returning to hand).

    discard_randomness: boolean
        Determines whether the order of cards should be randomized as won
        cards are added to the back of the discard pile.

    starting_hands: None or nested list of integers
        If None, random hands are dealt for both players. Can optionally pass
        a length-2 list of integers to be used as the starting deal.
    '''

    def __init__(self, max_hands,
                discard_recycle_mode = 'fifo',
                discard_randomness = False,
                starting_hands = None):

        # Store game settings
        self.max_hands = max_hands
        self.discard_recycle_mode = discard_recycle_mode
        self.discard_recycle_func = self._set_discard_func()
        self.discard_randomness = discard_randomness

        if starting_hands is None:
            # Deal random starting hands and store
            self._player_1_dealt, self._player_2_dealt = self._random_hands()
        else:
            # Unpack the list of lists
            self._player_1_dealt, self._player_2_dealt = \
                                        starting_hands[0], starting_hands[1]

        # Create dictionaries with active hands and discard piles
        self.player_1 = {'hand': self._player_1_dealt.copy(), 'discard': []}
        self.player_2 = {'hand': self._player_2_dealt.copy(), 'discard': []}

        # Initialize empty winnings list
        self._winnings = []

        # Initialize gameflow tracking dataframe
        self._tracks = [26]

        # Initalize dictionary to summarize game status / results
        self.summary = {'hands_played': 0,
                        'finished': None,
                        'tracks': self._tracks,
                        'p1_dealt': self._player_1_dealt,
                        'p2_dealt': self._player_2_dealt,
                        'discard_recycle_mode': self.discard_recycle_mode,
                        'discard_randomness': self.discard_randomness}


    def play_game(self, max_hands = None):
        '''
        Play a full game.
        '''
        hand = self.summary['hands_played']

        if max_hands is None:
            max_hands = self.max_hands

        # Continue doing battle until the game is over;
        ## Track the results each time
        while not self.__game_over(hand, max_hands):
            self._do_battle()
            self._tracks.append(len(self.player_1['hand']) + len(self.player_1['discard']))
            hand += 1

        # Update summary once the game is over
        self.summary['hands_played'] = hand
        self.summary['tracks'] = pd.Series(self._tracks, name = 'player_1_cards')

        # Return the game summary
        return self.summary


    def seek(self, turn):
        '''
        Go to a particular turn number.
        '''

        # Reset the game if the game is already past that turn
        if self.summary['hands_played'] > turn:
            self.__reset_game()

        # Play the game up to the desired turn
        self.play_game(turn)

        # Return the game hands as a dataframe (only works for non-random
        # discard recycle modes)
        return self.to_dataframe()


    def skip(self, turns = 1):
        '''
        Skip ahead a certain number of turns.
        '''
        self.play_game(self.summary['hands_played'] + turns)

        return self.to_dataframe()


    def to_dataframe(self):
        '''
        Turn game hands into a dataframe. Does not work if the discard mode is
        shuffled, because there is no way to return the discard into the hand
        to create a combined dataframe.
        '''

        # Cannot turn shuffled into df
        if self.discard_recycle_mode == 'shuffled':
            raise NameError('Cannot turn shuffled game into df')

        else:
            # Move discards back into active handhand
            self.__recycle_discard(self.player_1)
            self.__recycle_discard(self.player_2)

            # Create a tuple of the hands and sort declining by length
            hands = [('P1', self.player_1['hand'].copy()),
                    ('P2', self.player_2['hand'].copy())]
            hands = sorted(hands, key = lambda x: len(x[1]), reverse = True)

            # Figure out and add the correct number of NaNs so hands are even
            add = len(hands[0][1]) - len(hands[1][1])
            hands[1][1].extend([np.NaN]*add)

            # Turn tuple into a dictionary
            hands_dict = {hands[0][0]: hands[0][1],
                            hands[1][0]: hands[1][1]}

            # Return dataframe
            return pd.DataFrame(hands_dict)


    def _random_hands(self):
        '''
        Generate a random 2-player game.
        '''

        # Create deck of cards and shuffle
        cards = list(range(2,15))*4
        shuffle(cards)

        # Assign half of the deck to each player and return
        player_1 = cards[:26]
        player_2 = cards[26:]
        return player_1, player_2


    def _set_discard_func(self):
        '''
        Method to generate the discard function. Doing this once with
        initialization rather than evaluating the if statement with every usage.
        '''

        #'First in first out' recycle mode
        if self.discard_recycle_mode == 'fifo':
            return lambda player: player['discard']

        # 'First in last out'; just keep the original discard
        ## Need to reverse the discard because it is ordered first in first out
        if self.discard_recycle_mode == 'filo':
            return lambda player: list(reversed(player['discard']))

        # Shuffled; shuffles the discard pile before returning to hand
        if self.discard_recycle_mode == 'shuffled':
            return lambda player: sample(player['discard'],
                                                len(player['discard']))


    def _do_battle(self):
        '''
        Run a single turn.
        '''

        # Get the top card from each player
        play_1, play_2 = (self.__get_top_card(self.player_1),
                                            self.__get_top_card(self.player_2))

        # Add new cards to potential winnings
        self.__add_to_winnings([[play_1], [play_2]])

        # Evaluate who wins and allocate winnings accordingly
        if play_1 > play_2:
            self.player_1['discard'].extend(self._winnings)
            self._winnings.clear()
        elif play_1 < play_2:
            self.player_2['discard'].extend(self._winnings)
            self._winnings.clear()

        # Deal with ties (WARS!!!)
        ## This just adds the wagers to winnings;
        ## winnings are allocated to the winner of the next turn
        else:
            # Figure out how many cards to wager
            if play_1 == 14:
                i1, i2 = 4, 4
            elif play_1 == 13:
                i1, i2 = 3, 3
            elif play_1 == 12:
                i1, i2 = 2, 2
            else:
                i1, i2 = 1,1

            # Add wager cards to winnings;
            ## make sure each player keeps at least 1 card
            wagers = [[], []]
            while i1 > 0 and len(self.player_1['hand']) + len(self.player_1['discard']) > 1:
                wagers[0] = wagers[0] + [self.__get_top_card(self.player_1)]
                i1 -= 1
            while i2 > 0 and len(self.player_2['hand']) + len(self.player_2['discard']) > 1:
                wagers[1] = wagers[1] + [self.__get_top_card(self.player_2)]
                i2 -= 1
            self.__add_to_winnings(wagers)


    def __game_over(self, hand, max_hands):
        '''
        Evaluate whether the game is over. Game is over when one player runs out
        of cards or the game goes past the max_hands limit.
        '''

        # If either player runs out of cards...
        if (self.player_1['hand'] == [] and self.player_1['discard'] == []) \
                or (self.player_2['hand'] == [] and
                                        self.player_2['discard'] == []):
            self.summary['finished'] = True
            return True

        # Or if the game exceeds the turn limit...
        elif hand >= max_hands:
            self.summary['finished'] = False
            return True

        # Otherwise, game not over
        else:
            return False


    def __get_top_card(self, player):
        '''
        Get a player's top card. Player should be either 'player_1' or
        'player_2'.
        '''

        # Pop the top card... will throw an error if the player's hand is empty
        try:
            return player['hand'].pop(0)

        # Handle the error by recycling discard pile and then popping
        except:
            self.__recycle_discard(player)
            return player['hand'].pop(0)


    def __recycle_discard(self, player):
        '''
        Recycle a player's discard pile back into their hand.
        '''
        # Apply recycle function to discard and move to the player's hand
        player['hand'] += self.discard_recycle_func(player)

        # Empty the discard pile
        player['discard'] = []



    def __add_to_winnings(self, card_list):
        '''
        Add cards to the winnings pile.
        '''

        # Shuffle the order in which we add player 1 / player 2 to discard
        ## if we are adding randomness there
        if self.discard_randomness:
            shuffle(card_list)

        # Add cards to winnings
        self._winnings = self._winnings + card_list[0] + card_list[1]


    def __reset_game(self):
        '''
        Reset a game to the dealt hands. This is useful when using the seek
        method to go to a turn previous to the turn that was played to.
        '''

        # Reset players' hands
        self.player_1['hand'] = self._player_1_dealt
        self.player_2['hand'] = self._player_2_dealt

        # Wipe discard
        self.player_1['discard'], self.player_2['discard'] = [], []

        # Wipe summary
        self.summary = {'hands_played': 0,
                        'finished': None,
                        'tracks': [26],
                        'p1_dealt': self._player_1_dealt,
                        'p2_dealt': self._player_2_dealt}



    def __str__(self):
        hands_df = self.to_dataframe()

        return(hands_df.to_string(na_rep = ' ', index = False,
                                float_format = lambda x: '{:.0f}'.format(x)))
