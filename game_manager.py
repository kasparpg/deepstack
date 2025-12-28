import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import time
import random
from oracle import create_deck, shuffle_deck, Player, get_ai_names, check_winner, generate_utility_matrix, correct_format
from helper_functions import input_number, get_proper_array_index, check_legal_action, leaderboard, check_if_all_players_taken_action, check_highest_bid, display_tree, get_available_actions, card_to_index, combination_idx_to_card_pair
from state_manager import GameState
from art import tprint
from resolver_subtree import build_subtree, update_tree
from resolver import take_action
import numpy as np


def create_game(player_count: int, human_count: int, full_deck: bool, cards_per_hand: int):
    tprint("TEXAS HOLD'EM")
    print("Welcome to Texas Hold'em with AI!")
    time.sleep(1)
    
    # Ask for player count
    player_count = input_number("\nHow many players? (2-6): ")
    
    # Make sure that we have 2-6 players.
    if player_count > 6:
        print("ERROR: The maximum number of players is 6.")
        return
    if player_count < 2:
        print("ERROR: The minimum number of players is 2.")
        return
    
    # Ask for human count
    human_count = input_number("\nHow many human players? (0-" + str(player_count) + "): ")
    
    # Make sure that we do not have more human players than the specified number of players, and no less than 1.
    if human_count > player_count:
        print("ERROR: The maximum number of human players is:", player_count)
        return
    if human_count < 0:
        print("ERROR: The minimum number of human players is 0.")
        return
    
    print("\nAttempting to create a game with", player_count, "players, where", int(player_count-human_count),
          "are bot(s), and", human_count, "are human(s).")
    time.sleep(1)

    # Ask for how many chips per player.
    chips_per_player = input_number("\nHow many chips would you like per player? Enter here: ")
    print("-> Each player will start with", chips_per_player, "chips.")
    time.sleep(1)
    
    if chips_per_player < 0:
        print("ERROR: Starting chips have to be greater than 0.")
        return

    bet_limit = input_number("\nWhat should the bet limit be? Enter here: ")
    print("-> The bet limit is set to", bet_limit, "chips.")
    time.sleep(1)

    # Create players.
    players = []
    ai_names = shuffle_deck(get_ai_names(), 10)  # Get random bot names.
    for i in range(player_count):
        # Assign humans.
        if i < human_count:
            name = input("\nPlayer "+str(i+1)+", please enter your name: ")
            players.append(Player(name, True, [], False, "", chips_per_player, 0, False))
            print("->", name, "has joined the lobby.")
            time.sleep(0.5)
        # Assign bots.
        else:
            if i == human_count:
                print("\nCreating bots...")
                time.sleep(1)
            name = ai_names.pop()
            players.append(Player(name, False, [], False, "", chips_per_player, 0, False))
            print("->", name, "has joined the lobby.")
            time.sleep(0.5)

    # Create big blind index & table chip count.
    dealer_index = random.randint(0, len(players) - 1)

    # GAME ROUNDS:
    print("\nThe game is about to begin...")
    time.sleep(2)
    rounds = 0
    while len(players) > 1:

        # Ask the players if they want to play another round.
        if rounds > 0:
            start_another_game = input("\nPlay another round? (yes/no): ")
            if start_another_game.lower() == "no":
                are_you_sure = input("Are you sure you want to end the game? (yes/no): ")
                if are_you_sure.lower() == "yes":
                    break

        print("\n--- Round", int(rounds + 1), "started. ---")
        leaderboard(players)

        # Create deck.
        deck = create_deck(full_deck)

        # Ask for number of shuffles, and then shuffle deck.
        shuffle_count = input_number("\nDeck created with " + str(len(deck)) +
                                     " cards. How many shuffles would you like? Enter here: ")
        deck = shuffle_deck(deck, shuffle_count)
        print("-> Deck shuffled", shuffle_count, "times.")
        time.sleep(1)

        # Reset player cards, role (dealer, big blind, small blind), etc.
        for player in players:
            player.cards = []
            player.role = ""
            player.chips_added_to_table = 0
            player.folded = False
            player.action_taken = False

        # Deal cards.
        print("\nDealing out", cards_per_hand, "cards to each player...")
        time.sleep(1)
        while len(players[-1].cards) < cards_per_hand:
            for player in players:
                print("->", player.name, "was dealt a card.")
                player.cards.append(deck.pop())
                time.sleep(0.3)

        # Assign dealer, small blind and big blind. Set up so that if there are only 2 players left,
        # the "Dealer" becomes the big blind.
        players[dealer_index].role = "Dealer"
        players[get_proper_array_index(dealer_index, players, 1)].role = "Small Blind"
        players[get_proper_array_index(dealer_index, players, 2)].role = "Big Blind"

        # Highest current bid for the lap, and the chips on the table.
        highest_bid = 0
        table_chips = 0

        # Take chips from small blind and big blind.
        for player in players:
            # if the player has the role small blind.
            if player.role == "Small Blind":
                chips_to_give = round(bet_limit/2)
                # if the player has fewer chips than the bet limit divided by 2, set the player chips to 0
                # and take the remaining chips to the table.
                if player.chips < chips_to_give:
                    chips_to_give = player.chips
                    player.chips = 0
                # if the player has more chips than the bet limit divided by 2, reduce that amount from the
                # player and take the chips to the table.
                else:
                    player.chips -= chips_to_give
                table_chips += chips_to_give

                print("\n"+str(player.name), "is the small blind and", chips_to_give, "was taken and added to the table.")

                highest_bid = check_highest_bid(chips_to_give, highest_bid, False)  # keep track of the highest bid
                player.chips_added_to_table += chips_to_give
                time.sleep(1)

            elif player.role == "Big Blind":
                chips_to_give = bet_limit
                # if the player has fewer chips than the bet limit, set the player chips to 0
                # and take the remaining chips to the table.
                if player.chips < chips_to_give:
                    chips_to_give = player.chips
                    player.chips = 0
                # if the player has more chips than the bet limit, reduce that amount from the
                # player and take the chips to the table.
                else:
                    player.chips -= chips_to_give
                table_chips += chips_to_give

                print("\n"+player.name, "is the big blind and", bet_limit, "was taken and added to the table.")
                highest_bid = check_highest_bid(chips_to_give, highest_bid, False)  # keep track of the highest bid
                player.chips_added_to_table += chips_to_give
                time.sleep(1)

        # The player left to big blind starts betting. (3 spots from the dealer.)
        action_index_start = get_proper_array_index(dealer_index, players, 3)
        action_index = action_index_start
        lap = 0  # how many times each player has taken an action each. (When to deal cards etc.)

        # Create an empty array for the cards on the table, and the burned cards.
        cards_on_table = []
        burned_cards = []

        # Create while loop to allow players to do actions.
        while True:
            # Update the game state.
            game_state = GameState(players, action_index, cards_on_table, highest_bid, deck, lap, False)

            # Check if all players except 1 have folded.
            players_folded = 0
            for player in players:
                if player.folded:
                    players_folded += 1
            if players_folded == len(players)-1:
                # Find the player who hasn't folded, and give the chips on the table to the player.
                for player in players:
                    if not player.folded:
                        player.chips += table_chips
                        print(player.name, "has won the round and", table_chips, "were given to the player.")
                        break
                break

            print("\nThere are", table_chips, "chips on the table.")
            print("The highest bid is", str(highest_bid), "chips.")

            # Make sure the current player taking an action has not folded.
            current_player = players[action_index]
            if not current_player.folded:
                # The current player taking an action is a human.
                if current_player.human:
                    while True:
                        action = input_number("\nIt is " + str(current_player.name) + "'s turn. You have " +
                                              str(current_player.chips) + " chips, and " +
                                              str(current_player.chips_added_to_table) +
                                              " chips on the table. What will you do? " +
                                              "\n1 - Add chips to table" +
                                              "\n2 - Fold" +
                                              "\n3 - Show your cards" +
                                              "\n4 - Show cards on table" +
                                              "\n5 - Show player chips" +
                                              "\nEnter number here: ")
                        action, highest_bid, chips_to_give = check_legal_action(action, game_state, 0)
                        table_chips += chips_to_give
                        if action >= 0:
                            action_index = get_proper_array_index(action, players, 1)
                            break
                        # If action is -1 (informational action), loop back and ask again

                # The current player taking an action is a bot.
                else:
                    print("\nIt is", str(current_player.name) + "'s turn.")

                    # Use resolver if there are 2 players, where 1 is a bot.
                    if len(game_state.players) == 2:
                        print("There are 2 players in this game, and 1 is a bot. Resolver activated.\n")
                        print("Building subtree...")
                        root = build_subtree(game_state)
                        display_tree(root)
                        M = None
                        if root.initial_lap == 3 and len(root.cards_on_table) == 5:
                            M = generate_utility_matrix(correct_format(root.cards_on_table), full_deck)
                        print("-> Subtree built.")
                        T = 100
                        root_strategy_array = root.strategy_array
                        print("\nStarting tree update rollouts, T = "+ str(T) + "...")
                        for t in range(T):
                            update_tree(root, M)
                            root_strategy_array += root.strategy_array
                            print("-> Rollout " + str(t) + " of " + str(T) + " complete.")
                        print("--> Tree rollouts completed. \n")
                        action_values = root_strategy_array/root_strategy_array.sum(axis=1)[:,None]
                        action_values = np.nanmean(action_values, axis=0)
                        action_values = np.round(action_values, decimals=5)
                        print(action_values)
                        display_tree(root)
                        uniform = random.uniform(0, 1)
                        total_value = 0
                        action = 0
                        for i, value in enumerate(action_values):
                            total_value += value
                            if total_value >= uniform:
                                action = i
                                break

                        game_state.fake_state = False

                        a = get_available_actions(game_state)
                        game_state = take_action(game_state, a[action])
                        highest_bid = game_state.highest_bid
                        table_chips = game_state.chips_on_table
                        action_index = get_proper_array_index(1, game_state.players, 1)

                    # If there are more than 2 players, do a random action.
                    else:
                        game_state.fake_state = False
                        a = get_available_actions(game_state)
                        game_state = take_action(game_state, a[random.randint(0, len(a) - 1)])
                        highest_bid = game_state.highest_bid
                        table_chips = game_state.chips_on_table
                        action_index = get_proper_array_index(1, game_state.players, 1)

            # The current player taking an action has folded, skip to the next player.
            else:
                action_index = get_proper_array_index(action_index, players, 1)
                continue

            # check if every player has taken an action this turn, and they match the highest bet.
            if check_if_all_players_taken_action(players, highest_bid):
                # set action_taken to False for each player.
                for player in players:
                    player.action_taken = False

                action_index = action_index_start
                lap += 1
                # The first betting round is over. Add 3 cards to the table.
                if lap == 1:
                    print("\n")
                    while len(cards_on_table) < 3:
                        card = deck.pop()
                        burned_card = deck.pop()

                        cards_on_table.append(card)
                        print("-> " + str(card.value) + str(card.color), "was added to the table.")
                        time.sleep(0.3)
                        burned_cards.append(burned_card)
                        print("-> A card was burned.")
                        time.sleep(0.3)
                # The second betting round is over. Add another card to the table.
                elif lap == 2 or lap == 3:
                    print("\n")
                    card = deck.pop()
                    burned_card = deck.pop()

                    cards_on_table.append(card)
                    print("-> " + str(card.value) + str(card.color), "was added to the table.")
                    time.sleep(0.3)
                    burned_cards.append(burned_card)
                    print("-> A card was burned.")
                    time.sleep(0.3)
                else:
                    # check winner
                    winner = check_winner(players, cards_on_table)
                    print("\n" + winner.name, "has won the round!")
                    """
                    if winner.sidepotted:
                        winner.chips += winner.chips_added_to_table
                        table_chips -= winner.chips_added_to_table
                        for player in players:
                            if player.chips_added_to_table > 0:
                                player.chips += player.chips_added_to_table
                                table_chips -= player.chips_added_to_table
                    else:
                        winner.chips += table_chips
                    """
                    winner.chips += table_chips
                    print("->", table_chips, "was added to their inventory.")
                    table_chips = 0
                    break

        # Check if any players have 0 chips. If so, remove them from the game.
        for player in players:
            if player.chips == 0:
                print(player.name, "has run out of chips and has been removed from the game.")
                players.remove(player)

        # Increment number of rounds, increase dealer index, and end round.
        print("\n--- Round", int(rounds + 1), "ended. ---")
        rounds += 1
        dealer_index = get_proper_array_index(dealer_index, players, 1)

    return 0


# Game configuration
full_deck = False
cards_per_hand = 2
# player_count and human_count are now requested within create_game()
game = create_game(0, 0, full_deck, cards_per_hand)
