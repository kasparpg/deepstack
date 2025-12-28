import itertools
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
from copy import deepcopy
from helper_functions import get_available_actions, combination_idx_to_card_pair, card_to_index
from resolver import take_action
from state_manager import GameState
from oracle import generate_utility_matrix, correct_format, create_deck, shuffle_deck
import numpy as np
import keras
import random

full_deck = False
num_cards = 24
if full_deck:
    num_cards = 52
pot_size_max = 200


def one_hot_encode_cards(cards_on_table, full_deck):
    num_cards_on_table = len(cards_on_table)
    deck_size = 52 if full_deck else 24
    one_hot_size = deck_size

    one_hot_encoded = np.zeros((num_cards_on_table, one_hot_size), dtype=int)

    for i, card in enumerate(cards_on_table):
        card_idx = card_to_index(card, full_deck)  # Convert card string to index

        # Skip the index if it's out of bounds for the one_hot_size.
        if card_idx < one_hot_size:
            one_hot_encoded[i, card_idx] = 1

    return one_hot_encoded

class Node:
    def __init__(self, player, actions, parent=None, terminal=False, cards_on_table=[], pot_size=0, lap=0, initial_lap=0, depth=0):
        self.pot_size = pot_size
        self.cards_on_table = cards_on_table
        if not parent:
            list_of_pairs = [combination_idx_to_card_pair(i, full_deck) for i in range(276)]
            p1_range = np.array([random.randint(0, 100) for i in range(276)])
            p2_range = np.array([random.randint(0, 100) for i in range(276)])

            # Set cards on table to 0 in range.
            for card in self.cards_on_table:
                c = card_to_index(card, full_deck)
                all_indices_with_card = [
                    i for i, pair in enumerate(list_of_pairs) if c in pair
                ]
                p1_range[all_indices_with_card] = 0
                p2_range[all_indices_with_card] = 0

            p1_range = np.array(p1_range)/np.sum(p1_range)
            p2_range = np.array(p2_range)/np.sum(p2_range)
        else:
            p1_range = np.ones(276)
            p2_range = np.ones(276)
            """
            list_of_pairs = [combination_idx_to_card_pair(i, full_deck) for i in range(276)]
            for card in cards_on_table:
                c = card_to_index(card, full_deck)
                all_indices_with_card = [
                    i for i, pair in enumerate(list_of_pairs) if c in pair
                ]
                p1_range[all_indices_with_card] = 0
                p2_range[all_indices_with_card] = 0
            """
            p1_range = np.array(p1_range) / np.sum(p1_range)
            p2_range = np.array(p2_range) / np.sum(p2_range)

        self.p1_range = p1_range
        self.p2_range = p2_range

        self.lap = lap
        self.initial_lap = initial_lap
        self.depth = depth
        self.player = player
        self.actions = actions

        self.strategy_array = None
        self.regret_matrix = None
        self.regret_matrix_positive = None
        self.v1_range = []
        self.v2_range = []

        self.parent = parent
        self.children = []
        self.terminal = terminal

    def initialize_strategy_array(self, actions_length):
        strategy_array = np.array([random.uniform(0, 1) for i in range(276 * actions_length)])\
            .reshape(276, actions_length)
        self.strategy_array = strategy_array / strategy_array.sum(axis=1)[:, None]

    def initialize_regret_matrix(self, actions_length):
        self.regret_matrix = np.zeros((276, actions_length))
        self.regret_matrix_positive = np.zeros((276, actions_length))

    def update_ranges(self, cards):
        list_of_pairs = [combination_idx_to_card_pair(i, full_deck) for i in range(276)]
        for card in cards:
            c = card_to_index(card, full_deck)
            all_indices_with_card = [
                i for i, pair in enumerate(list_of_pairs) if c in pair
            ]
            self.p1_range[all_indices_with_card] = 0
            self.p2_range[all_indices_with_card] = 0
        self.p1_range = np.array(self.p1_range) / np.sum(self.p1_range)
        self.p2_range = np.array(self.p2_range) / np.sum(self.p2_range)


def build_subtree(game_state, depth=0, max_depth=10, parent=None, initial_lap=-1):
    game_state = GameState(
        players=deepcopy(game_state.players),
        my_index=game_state.my_index,
        cards_on_table=deepcopy(game_state.cards_on_table),
        highest_bid=game_state.highest_bid,
        deck=deepcopy(game_state.deck),
        lap=game_state.lap,
        fake_state=True)
    if initial_lap == -1:
        initial_lap = game_state.lap

    if depth >= max_depth or is_terminal(game_state):
        terminal_node = Node(game_state.players[game_state.my_index], [], parent=parent, terminal=True, cards_on_table=game_state.cards_on_table, pot_size=game_state.chips_on_table, lap=game_state.lap, initial_lap=initial_lap, depth=depth)
        terminal_node.children = []
        return terminal_node

    node = Node(game_state.players[game_state.my_index], [], parent=parent, cards_on_table=game_state.cards_on_table, pot_size=game_state.chips_on_table, lap=game_state.lap, initial_lap=initial_lap, depth=depth)
    actions = get_available_actions(game_state)
    node.initialize_strategy_array(len(actions))
    node.initialize_regret_matrix(len(actions))

    for action in actions:

        next_game_state = take_action(game_state, action)

        # Determine when to cut off depth off tree (to use NNs)
        if cut_off_tree(initial_lap, node, next_game_state, depth, action):
            child = build_subtree(next_game_state, depth + 1, max_depth, parent=node, initial_lap=initial_lap)
            node.actions.append(action)
            node.children.append(child)
    return node


def update_tree(node, M=None):
    # Update range for root node.
    if not node.parent:
        list_of_pairs = [combination_idx_to_card_pair(i, full_deck) for i in range(276)]
        p1_range = np.array([random.randint(0, 100) for i in range(276)])
        p2_range = np.array([random.randint(0, 100) for i in range(276)])

        # Set cards on table to 0 in range.
        for card in node.cards_on_table:
            c = card_to_index(card, full_deck)
            all_indices_with_card = [
                i for i, pair in enumerate(list_of_pairs) if c in pair
            ]
            p1_range[all_indices_with_card] = 0
            p2_range[all_indices_with_card] = 0

        node.p1_range = np.array(p1_range) / np.sum(p1_range)
        node.p2_range = np.array(p2_range) / np.sum(p2_range)

    for i, (action, child) in enumerate(zip(node.actions, node.children)):
        if cut_off_tree(node.initial_lap, node, child, node.depth, action):
            deploy_nn(node, M)
            update_ranges_and_values(node, action, i)

    # Update every node in the tree.
    for child in node.children:
        update_tree(child, M)

    # Update parent value ranges with children value ranges.
    if len(node.v1_range) == 0:
        node.v1_range = np.zeros(276)
        node.v2_range = np.zeros(276)
        for i, child in enumerate(node.children):
            node.v1_range += node.strategy_array[:, i] * child.v1_range
            node.v2_range += node.strategy_array[:, i] * child.v2_range

    # Update regrets.
    update_regrets(node)

    # Update strategies.
    update_strategies(node)
    return node


def cut_off_tree(initial_lap, node, child, depth, action):
    # Determine when to cut off depth off tree (to use NNs)
    if child.lap > initial_lap:
        continue_loop = False
        # Terminal node. (See above)
        if action == 'FOLD' and depth < 3 and (
                node.lap != child.lap or (node.player.role == 'Small Blind' and depth == 2)):
            continue_loop = True
        # Raise and chance node.
        elif ((child.lap - 1 == initial_lap) and (node.lap == initial_lap)) or (
                action == 'CALL' and node.lap - 1 == initial_lap and node.lap - 1 == initial_lap and depth == 2 and node.player.role == "Small Blind" and len(
                node.parent.actions) != 1):
            # Raise node
            if 'RAISE' in action and node.player.role == "Big Blind":
                continue_loop = True
            # Chance node
            elif action == 'CALL':
                continue_loop = True
        return continue_loop
    return True


def deploy_nn(node, M):
    initial_lap = node.initial_lap
    model_location = 'NONE'
    # Flop
    if initial_lap == 0 and len(node.cards_on_table) == 3:
        model_location = 'models/model24_3cards_10000rollouts_1000epochs'
    # Turn
    elif initial_lap == 1 and len(node.cards_on_table) == 4:
        model_location = 'models/model24_4cards_10000rollouts_1000epochs'
    # River
    elif initial_lap == 2 and len(node.cards_on_table) == 5:
        model_location = 'models/model24_5cards_10000rollouts_1000epochs'
    # Showdown
    elif initial_lap == 3 and len(node.cards_on_table) == 5:
        node.update_ranges(node.cards_on_table)
        node.v1_range = node.p2_range.dot(M)
        node.v2_range = node.p1_range.dot(M)

    if model_location != 'NONE':
        x1 = np.zeros((1, int((num_cards * (num_cards - 1)) / 2)))
        x2 = np.zeros((1, int((num_cards * (num_cards - 1)) / 2)))
        x3 = np.zeros((1, len(node.cards_on_table), num_cards))
        x4 = np.zeros((1, 1))

        node.update_ranges(node.cards_on_table)
        one_hot_cards = one_hot_encode_cards(node.cards_on_table, full_deck)

        x1[0] = np.array(node.p1_range)
        x2[0] = np.array(node.p2_range)
        x3[0] = np.array(one_hot_cards)
        x4[0] = np.array(node.pot_size / pot_size_max)

        model = keras.models.load_model(model_location)
        y_hat = model.predict([x1, x2, x3, x4], batch_size=1, verbose=0)

        node.v1_range = y_hat[0][:len(y_hat[0]) // 2]
        node.v2_range = y_hat[0][len(y_hat[0]) // 2:]


def update_ranges_and_values(node, action, i):
    a_i = i  # action index
    p_a = np.sum(node.strategy_array[a_i], axis=0) / np.sum(np.sum(node.strategy_array[a_i], axis=0),
                                                            axis=0)  # prob(action)
    for i, child in enumerate(node.children):
        if node.player.human:
            for j, hole in enumerate(child.p1_range):
                child.p1_range[j] *= (node.strategy_array[j][a_i] * node.p1_range[j]) / p_a
            child.p2_range = node.p2_range
            if child.terminal:
                if action == 'FOLD':
                    child.v1_range = np.zeros(276)
                    child.v2_range = np.zeros(276)
                    for j, hole in enumerate(child.p1_range):
                        if hole > 0:
                            child.v1_range[j] = child.pot_size / pot_size_max
                            child.v2_range[j] = - (child.pot_size / pot_size_max)
        else:
            for j, hole in enumerate(child.p2_range):
                child.p2_range[j] *= (node.strategy_array[j][a_i] * node.p2_range[j]) / p_a
            child.p1_range = node.p1_range
            if child.terminal:
                if action == 'FOLD':
                    child.v1_range = np.zeros(276)
                    child.v2_range = np.zeros(276)
                    for j, hole in enumerate(child.p2_range):
                        if hole > 0:
                            child.v1_range[j] = - (child.pot_size / pot_size_max)
                            child.v2_range[j] = child.pot_size / pot_size_max


def update_regrets(node):
    if len(node.children) > 0:
        for i, child in enumerate(node.children):
            if node.player.human:
                node.regret_matrix[:, i] += (node.v1_range - child.v1_range)
                node.regret_matrix_positive[:, i] = node.regret_matrix[:, i].clip(min=0)
            else:
                node.regret_matrix[:, i] += (node.v2_range - child.v2_range)
                node.regret_matrix_positive[:, i] = node.regret_matrix[:, i].clip(min=0)


def update_strategies(node):
    if len(node.children) > 0:
        for i, child in enumerate(node.children):
            node.strategy_array[:, i] = node.regret_matrix_positive[:, i]/np.sum(node.regret_matrix_positive, axis=1)


def is_terminal(game_state):
    if game_state.lap == 4:
        return True
    if game_state.folded_players[0] or game_state.folded_players[1]:
        return True
    return False


