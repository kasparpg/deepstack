# DeepStack2 - Texas Hold'em Poker with AI

A Python implementation of Texas Hold'em poker featuring AI opponents powered by neural networks and game theory optimal (GTO) strategies.

## Features

- **Interactive Console Game**: Play Texas Hold'em poker directly in your terminal
- **AI Opponents**: Bot players that use neural networks and counterfactual regret minimization (CFR)
- **2-Player Resolver**: Advanced AI decision-making for heads-up play using subtree solving
- **Flexible Configuration**: Customizable player count, human players, chips, and bet limits
- **Multiple Game Phases**: Pre-flop, flop, turn, and river betting rounds
- **Neural Network Models**: Pre-trained models for different game states (3, 4, and 5 community cards)

## Requirements

- Python 3.10+
- TensorFlow
- Keras
- NumPy
- Pandas
- art (for ASCII text display)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd deepstack2
```

2. Create a virtual environment (recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the game:
```bash
python game_manager.py
```

Follow the prompts to configure your game:
1. Enter the number of players (2-6)
2. Enter the number of human players (0-N)
3. Set starting chips per player
4. Set the bet limit
5. Choose number of deck shuffles

### In-Game Actions

When it's your turn, you can:
1. **Add chips to table** - Call or raise
2. **Fold** - Give up your hand
3. **Show your cards** - View your hole cards
4. **Show cards on table** - View the community cards
5. **Show player chips** - View the leaderboard

## Project Structure

```
deepstack2/
├── game_manager.py           # Main game loop and player interaction
├── resolver.py               # Action resolution and AI decision logic
├── resolver_subtree.py       # Subtree building and CFR algorithm
├── resolver_neural_network.py # Neural network training utilities
├── oracle.py                 # Deck management, hand evaluation, utilities
├── state_manager.py          # Game state tracking
├── helper_functions.py       # Utility functions
├── models/                   # Pre-trained neural network models
│   ├── model24_3cards_*      # Flop models (3 community cards)
│   ├── model24_4cards_*      # Turn models (4 community cards)
│   └── model24_5cards_*      # River models (5 community cards)
└── requirements.txt          # Python dependencies
```

## How It Works

### AI Strategy

The bot players use two main strategies:

1. **Neural Network Evaluation**: Pre-trained models estimate hand values based on:
   - Player hand ranges
   - Community cards
   - Current pot size
   - Betting round (flop/turn/river)

2. **Counterfactual Regret Minimization (CFR)**: 
   - In 2-player games, builds a game subtree
   - Runs rollouts to compute optimal strategies
   - Minimizes regret to find Nash equilibrium strategies

### Game Flow

1. Players are dealt hole cards
2. Pre-flop betting round
3. Flop (3 community cards) + betting
4. Turn (4th community card) + betting
5. River (5th community card) + betting
6. Showdown - best hand wins

## Models

The `models/` directory contains neural networks trained on different scenarios:
- `*_5rollouts_*`: Fast models with minimal training
- `*_100rollouts_*`: Balanced performance
- `*_10000rollouts_*`: High-quality strategic models

Models are automatically loaded based on the current game state.

## Configuration

Edit the bottom of `game_manager.py` to change defaults:
```python
full_deck = False  # True for 52 cards, False for 24 cards
cards_per_hand = 2  # Standard Texas Hold'em
```

## Known Limitations

- Currently supports up to 6 players
- Full deck (52 cards) support is experimental
- Side pot logic needs implementation for all-in scenarios
- Neural network models are pre-trained and not updated during gameplay

## Future Enhancements

- [ ] Web interface for browser-based play
- [ ] Multiplayer online support
- [ ] Real-time neural network training
- [ ] Tournament mode
- [ ] Statistics tracking and analysis
- [ ] Full side pot implementation
- [ ] Additional betting structures (no-limit, pot-limit)

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

[Add your license here]

## Acknowledgments

Inspired by DeepStack, the first AI to beat professional poker players in heads-up no-limit Texas Hold'em.
