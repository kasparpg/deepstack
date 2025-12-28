import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import uuid
from copy import deepcopy
from oracle import create_deck, shuffle_deck, Player, check_winner, generate_utility_matrix, correct_format
from helper_functions import get_proper_array_index, check_if_all_players_taken_action, check_highest_bid, get_available_actions, card_to_index, combination_idx_to_card_pair
from state_manager import GameState
from resolver_subtree import build_subtree, update_tree
from resolver import take_action
import numpy as np

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active games
games = {}

class WebGame:
    def __init__(self, game_id, player_count, human_count, chips_per_player, bet_limit, full_deck=False):
        self.game_id = game_id
        self.player_count = player_count
        self.human_count = human_count
        self.chips_per_player = chips_per_player
        self.bet_limit = bet_limit
        self.full_deck = full_deck
        self.cards_per_hand = 2
        self.rounds = 0
        self.dealer_index = 0
        self.action_index = 0
        self.table_chips = 0
        self.highest_bid = 0
        self.cards_on_table = []
        self.burned_cards = []
        self.deck = []
        self.lap = 0
        self.players = []
        self.connected_humans = {}
        self.current_player_sid = None
        self.game_started = False
        self.waiting_for_action = False
        
    def add_human_player(self, sid, name):
        if len(self.connected_humans) < self.human_count:
            self.connected_humans[sid] = name
            return True
        return False
    
    def remove_human_player(self, sid):
        if sid in self.connected_humans:
            del self.connected_humans[sid]
    
    def initialize_players(self):
        # Create bot names
        bot_names = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank']
        random.shuffle(bot_names)
        
        # Add human players
        human_names = list(self.connected_humans.values())
        for name in human_names:
            self.players.append(Player(name, True, [], False, "", self.chips_per_player, 0, False))
        
        # Add bots
        for i in range(self.player_count - self.human_count):
            name = bot_names.pop()
            self.players.append(Player(name, False, [], False, "", self.chips_per_player, 0, False))
        
        self.dealer_index = random.randint(0, len(self.players) - 1)
    
    def get_game_state_dict(self):
        return {
            'game_id': self.game_id,
            'rounds': self.rounds,
            'table_chips': self.table_chips,
            'highest_bid': self.highest_bid,
            'cards_on_table': [{'value': card.value, 'color': card.color} for card in self.cards_on_table],
            'lap': self.lap,
            'players': [{
                'name': p.name,
                'human': p.human,
                'chips': p.chips,
                'chips_added_to_table': p.chips_added_to_table,
                'folded': p.folded,
                'cards': [{'value': card.value, 'color': card.color} for card in p.cards] if p.human else []
            } for p in self.players],
            'waiting_for_action': self.waiting_for_action,
            'current_player': self.players[self.action_index].name if self.players else None
        }

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    emit('connected', {'sid': request.sid})

@socketio.on('create_game')
def handle_create_game(data):
    game_id = str(uuid.uuid4())[:8]
    game = WebGame(
        game_id=game_id,
        player_count=int(data['player_count']),
        human_count=int(data['human_count']),
        chips_per_player=int(data['chips_per_player']),
        bet_limit=int(data['bet_limit']),
        full_deck=data.get('full_deck', False)
    )
    games[game_id] = game
    
    join_room(game_id)
    game.add_human_player(request.sid, data['player_name'])
    
    emit('game_created', {
        'game_id': game_id,
        'message': f'Game {game_id} created! Share this code with other players.'
    })

@socketio.on('join_game')
def handle_join_game(data):
    game_id = data['game_id']
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game = games[game_id]
    if game.game_started:
        emit('error', {'message': 'Game already started'})
        return
    
    if game.add_human_player(request.sid, data['player_name']):
        join_room(game_id)
        emit('joined_game', {
            'game_id': game_id,
            'message': f'Joined game {game_id}',
            'players_joined': len(game.connected_humans),
            'players_needed': game.human_count
        }, room=game_id)
    else:
        emit('error', {'message': 'Game is full'})

@socketio.on('start_game')
def handle_start_game(data):
    game_id = data['game_id']
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game = games[game_id]
    if len(game.connected_humans) != game.human_count:
        emit('error', {'message': f'Waiting for {game.human_count - len(game.connected_humans)} more players'})
        return
    
    game.initialize_players()
    game.game_started = True
    start_round(game_id)

def start_round(game_id):
    game = games[game_id]
    game.rounds += 1
    
    # Create and shuffle deck
    game.deck = create_deck(game.full_deck)
    game.deck = shuffle_deck(game.deck, 10)
    
    # Reset players
    for player in game.players:
        player.cards = []
        player.folded = False
        player.chips_added_to_table = 0
        player.action_taken = False
    
    # Deal cards
    for _ in range(game.cards_per_hand):
        for player in game.players:
            if not player.folded:
                card = game.deck.pop()
                player.cards.append(card)
    
    game.cards_on_table = []
    game.burned_cards = []
    game.table_chips = 0
    game.highest_bid = 0
    game.lap = 0
    
    # Set blinds
    small_blind_index = get_proper_array_index(game.dealer_index, game.players, 1)
    big_blind_index = get_proper_array_index(game.dealer_index, game.players, 2)
    
    game.players[small_blind_index].role = "Small Blind"
    game.players[big_blind_index].role = "Big Blind"
    
    # Take blinds
    small_blind = min(game.bet_limit // 2, game.players[small_blind_index].chips)
    game.players[small_blind_index].chips -= small_blind
    game.players[small_blind_index].chips_added_to_table = small_blind
    game.table_chips += small_blind
    game.highest_bid = small_blind
    
    big_blind = min(game.bet_limit, game.players[big_blind_index].chips)
    game.players[big_blind_index].chips -= big_blind
    game.players[big_blind_index].chips_added_to_table = big_blind
    game.table_chips += big_blind
    game.highest_bid = max(game.highest_bid, big_blind)
    
    # Set action to start after big blind
    game.action_index = get_proper_array_index(game.dealer_index, game.players, 3)
    
    emit('round_started', game.get_game_state_dict(), room=game_id)
    request_next_action(game_id)

def request_next_action(game_id):
    game = games[game_id]
    
    # Check if round is over
    if check_if_all_players_taken_action(game.players, game.highest_bid):
        advance_lap(game_id)
        return
    
    # Skip folded players
    while game.players[game.action_index].folded:
        game.action_index = get_proper_array_index(game.action_index, game.players, 1)
    
    current_player = game.players[game.action_index]
    game.waiting_for_action = True
    
    if current_player.human:
        # Request action from human
        emit('request_action', {
            'player_name': current_player.name,
            'available_actions': get_available_actions_web(game, game.action_index)
        }, room=game_id)
    else:
        # Bot takes action
        handle_bot_action(game_id)

def get_available_actions_web(game, player_index):
    game_state = GameState(
        players=game.players,
        my_index=player_index,
        cards_on_table=game.cards_on_table,
        highest_bid=game.highest_bid,
        deck=game.deck,
        lap=game.lap,
        fake_state=False
    )
    return get_available_actions(game_state)

def handle_bot_action(game_id):
    game = games[game_id]
    player_index = game.action_index
    
    game_state = GameState(
        players=game.players,
        my_index=player_index,
        cards_on_table=game.cards_on_table,
        highest_bid=game.highest_bid,
        deck=deepcopy(game.deck),
        lap=game.lap,
        fake_state=False
    )
    
    # Simple bot logic for now
    available_actions = get_available_actions(game_state)
    action = random.choice(available_actions)
    
    process_action(game_id, action)

@socketio.on('player_action')
def handle_player_action(data):
    game_id = data['game_id']
    action = data['action']
    
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game = games[game_id]
    current_player = game.players[game.action_index]
    
    if not current_player.human:
        emit('error', {'message': 'Not your turn'})
        return
    
    process_action(game_id, action, data.get('chips', 0))

def process_action(game_id, action, chips_to_give=0):
    game = games[game_id]
    player = game.players[game.action_index]
    
    if action == 'FOLD':
        player.folded = True
        emit('action_taken', {
            'player': player.name,
            'action': 'folded'
        }, room=game_id)
    
    elif action == 'CALL':
        chips_needed = game.highest_bid - player.chips_added_to_table
        chips_to_give = min(chips_needed, player.chips)
        player.chips -= chips_to_give
        player.chips_added_to_table += chips_to_give
        game.table_chips += chips_to_give
        player.action_taken = True
        
        emit('action_taken', {
            'player': player.name,
            'action': 'called',
            'chips': chips_to_give
        }, room=game_id)
    
    else:  # RAISE
        if 'RAISE' in action:
            raise_amount = int(action.replace('RAISE', ''))
            chips_to_give = game.highest_bid - player.chips_added_to_table + raise_amount
        
        player.chips -= chips_to_give
        player.chips_added_to_table += chips_to_give
        game.table_chips += chips_to_give
        game.highest_bid = player.chips_added_to_table
        player.action_taken = True
        
        # Reset other players' action_taken
        for p in game.players:
            if p != player and not p.folded:
                p.action_taken = False
        
        emit('action_taken', {
            'player': player.name,
            'action': 'raised',
            'chips': chips_to_give,
            'new_highest_bid': game.highest_bid
        }, room=game_id)
    
    game.waiting_for_action = False
    game.action_index = get_proper_array_index(game.action_index, game.players, 1)
    
    emit('game_state', game.get_game_state_dict(), room=game_id)
    
    # Check if only one player left
    active_players = [p for p in game.players if not p.folded]
    if len(active_players) == 1:
        end_round(game_id, active_players[0])
    else:
        request_next_action(game_id)

def advance_lap(game_id):
    game = games[game_id]
    game.lap += 1
    
    # Reset action_taken for all players
    for player in game.players:
        player.action_taken = False
    
    if game.lap == 1:
        # Flop - deal 3 cards
        game.burned_cards.append(game.deck.pop())
        for _ in range(3):
            game.cards_on_table.append(game.deck.pop())
        emit('cards_dealt', {
            'message': 'Flop dealt',
            'cards': [{'value': c.value, 'color': c.color} for c in game.cards_on_table]
        }, room=game_id)
    
    elif game.lap == 2:
        # Turn - deal 1 card
        game.burned_cards.append(game.deck.pop())
        game.cards_on_table.append(game.deck.pop())
        emit('cards_dealt', {
            'message': 'Turn dealt',
            'cards': [{'value': c.value, 'color': c.color} for c in game.cards_on_table]
        }, room=game_id)
    
    elif game.lap == 3:
        # River - deal 1 card
        game.burned_cards.append(game.deck.pop())
        game.cards_on_table.append(game.deck.pop())
        emit('cards_dealt', {
            'message': 'River dealt',
            'cards': [{'value': c.value, 'color': c.color} for c in game.cards_on_table]
        }, room=game_id)
    
    elif game.lap == 4:
        # Showdown
        winner = check_winner(game.players, game.cards_on_table)
        end_round(game_id, winner)
        return
    
    game.action_index = get_proper_array_index(game.dealer_index, game.players, 1)
    while game.players[game.action_index].folded:
        game.action_index = get_proper_array_index(game.action_index, game.players, 1)
    
    emit('game_state', game.get_game_state_dict(), room=game_id)
    request_next_action(game_id)

def end_round(game_id, winner):
    game = games[game_id]
    winner.chips += game.table_chips
    
    emit('round_ended', {
        'winner': winner.name,
        'chips_won': game.table_chips,
        'game_state': game.get_game_state_dict()
    }, room=game_id)
    
    # Remove players with 0 chips
    game.players = [p for p in game.players if p.chips > 0]
    
    if len(game.players) > 1:
        game.dealer_index = get_proper_array_index(game.dealer_index, game.players, 1)
        emit('next_round_prompt', {}, room=game_id)
    else:
        emit('game_over', {
            'winner': game.players[0].name if game.players else 'No one'
        }, room=game_id)
        del games[game_id]

@socketio.on('next_round')
def handle_next_round(data):
    game_id = data['game_id']
    if game_id in games:
        start_round(game_id)

@socketio.on('disconnect')
def handle_disconnect():
    # Find and clean up game if player disconnects
    for game_id, game in list(games.items()):
        if request.sid in game.connected_humans:
            game.remove_human_player(request.sid)
            if len(game.connected_humans) == 0:
                del games[game_id]
            break

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
