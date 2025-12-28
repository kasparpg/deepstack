const socket = io();
let currentGameId = null;
let playerName = null;

// Connect to server
socket.on('connect', () => {
    console.log('Connected to server');
    addLog('Connected to server');
});

socket.on('connected', (data) => {
    console.log('Session ID:', data.sid);
});

// Tab switching
function showTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    if (tabName === 'create') {
        document.querySelector('.tab-btn:first-child').classList.add('active');
        document.getElementById('create-tab').classList.add('active');
    } else {
        document.querySelector('.tab-btn:last-child').classList.add('active');
        document.getElementById('join-tab').classList.add('active');
    }
}

// Create game
function createGame() {
    playerName = document.getElementById('player-name-create').value.trim();
    const playerCount = parseInt(document.getElementById('player-count').value);
    const humanCount = parseInt(document.getElementById('human-count').value);
    const chipsPerPlayer = parseInt(document.getElementById('chips-per-player').value);
    const betLimit = parseInt(document.getElementById('bet-limit').value);
    
    if (!playerName) {
        alert('Please enter your name');
        return;
    }
    
    if (humanCount > playerCount) {
        alert('Human players cannot exceed total players');
        return;
    }
    
    socket.emit('create_game', {
        player_name: playerName,
        player_count: playerCount,
        human_count: humanCount,
        chips_per_player: chipsPerPlayer,
        bet_limit: betLimit
    });
}

// Join game
function joinGame() {
    playerName = document.getElementById('player-name-join').value.trim();
    const gameCode = document.getElementById('game-code').value.trim().toUpperCase();
    
    if (!playerName || !gameCode) {
        alert('Please enter your name and game code');
        return;
    }
    
    socket.emit('join_game', {
        game_id: gameCode,
        player_name: playerName
    });
}

// Start game
function startGame() {
    if (currentGameId) {
        socket.emit('start_game', { game_id: currentGameId });
    }
}

// Socket event handlers
socket.on('game_created', (data) => {
    currentGameId = data.game_id;
    showScreen('waiting');
    document.getElementById('game-code-display').textContent = data.game_id;
    addLog(data.message);
});

socket.on('joined_game', (data) => {
    currentGameId = data.game_id;
    showScreen('waiting');
    document.getElementById('game-code-display').textContent = data.game_id;
    document.getElementById('waiting-message').textContent = 
        `${data.players_joined} / ${data.players_needed} players ready`;
    addLog(data.message);
});

socket.on('round_started', (gameState) => {
    showScreen('game');
    updateGameState(gameState);
    addLog(`Round ${gameState.rounds} started!`);
});

socket.on('game_state', (gameState) => {
    updateGameState(gameState);
});

socket.on('request_action', (data) => {
    if (data.player_name === playerName) {
        showActionPanel(data.available_actions);
        addLog(`Your turn! Available actions: ${data.available_actions.join(', ')}`);
    } else {
        hideActionPanel();
        addLog(`Waiting for ${data.player_name}...`);
    }
});

socket.on('action_taken', (data) => {
    let message = `${data.player} ${data.action}`;
    if (data.chips) {
        message += ` (${data.chips} chips)`;
    }
    addLog(message);
});

socket.on('cards_dealt', (data) => {
    addLog(data.message);
    updateCommunityCards(data.cards);
});

socket.on('round_ended', (data) => {
    addLog(`${data.winner} won ${data.chips_won} chips!`);
    updateGameState(data.game_state);
    hideActionPanel();
    
    setTimeout(() => {
        if (confirm('Start next round?')) {
            socket.emit('next_round', { game_id: currentGameId });
        }
    }, 2000);
});

socket.on('game_over', (data) => {
    addLog(`Game Over! ${data.winner} wins!`);
    alert(`Game Over! ${data.winner} wins!`);
    setTimeout(() => {
        location.reload();
    }, 3000);
});

socket.on('error', (data) => {
    alert(data.message);
    addLog('Error: ' + data.message);
});

// UI Functions
function showScreen(screenName) {
    document.querySelectorAll('.screen').forEach(screen => screen.classList.remove('active'));
    document.getElementById(`${screenName}-screen`).classList.add('active');
}

function updateGameState(gameState) {
    // Update info
    document.getElementById('round-number').textContent = gameState.rounds;
    document.getElementById('pot-size').textContent = gameState.table_chips;
    document.getElementById('highest-bid').textContent = gameState.highest_bid;
    
    // Update community cards
    updateCommunityCards(gameState.cards_on_table);
    
    // Update players
    updatePlayers(gameState.players, gameState.current_player);
    
    // Update your hand
    const myPlayer = gameState.players.find(p => p.name === playerName);
    if (myPlayer && myPlayer.cards.length > 0) {
        updateYourCards(myPlayer.cards);
    }
}

function updateCommunityCards(cards) {
    const container = document.getElementById('community-cards');
    container.innerHTML = '';
    
    for (let i = 0; i < 5; i++) {
        const cardDiv = document.createElement('div');
        cardDiv.className = 'card';
        
        if (i < cards.length) {
            const card = cards[i];
            cardDiv.className += ` ${card.color}`;
            cardDiv.textContent = formatCard(card);
        } else {
            cardDiv.className += ' card-back';
            cardDiv.textContent = '?';
        }
        
        container.appendChild(cardDiv);
    }
}

function updateYourCards(cards) {
    const container = document.getElementById('your-cards');
    container.innerHTML = '';
    
    cards.forEach(card => {
        const cardDiv = document.createElement('div');
        cardDiv.className = `card ${card.color}`;
        cardDiv.textContent = formatCard(card);
        container.appendChild(cardDiv);
    });
}

function updatePlayers(players, currentPlayerName) {
    const container = document.getElementById('players-container');
    container.innerHTML = '';
    
    players.forEach(player => {
        const playerDiv = document.createElement('div');
        playerDiv.className = 'player-box';
        
        if (player.name === currentPlayerName) {
            playerDiv.classList.add('active');
        }
        
        if (player.folded) {
            playerDiv.classList.add('folded');
        }
        
        playerDiv.innerHTML = `
            <div class="player-name">${player.name} ${player.human ? '👤' : '🤖'}</div>
            <div class="player-chips">💰 ${player.chips} chips</div>
            <div class="player-chips">📍 ${player.chips_added_to_table} on table</div>
            ${player.folded ? '<div style="color: #f44336;">FOLDED</div>' : ''}
        `;
        
        container.appendChild(playerDiv);
    });
}

function showActionPanel(availableActions) {
    const panel = document.getElementById('action-panel');
    const buttonsContainer = document.getElementById('action-buttons');
    const raiseInput = document.getElementById('raise-input');
    
    panel.style.display = 'block';
    buttonsContainer.innerHTML = '';
    raiseInput.style.display = 'none';
    
    availableActions.forEach(action => {
        const btn = document.createElement('button');
        btn.className = 'btn';
        
        if (action === 'FOLD') {
            btn.className += ' btn-fold';
            btn.textContent = 'Fold';
            btn.onclick = () => takeAction('FOLD');
        } else if (action === 'CALL') {
            btn.className += ' btn-call';
            btn.textContent = 'Call';
            btn.onclick = () => takeAction('CALL');
        } else if (action.startsWith('RAISE')) {
            btn.className += ' btn-raise';
            const amount = action.replace('RAISE', '');
            btn.textContent = `Raise ${amount}`;
            btn.onclick = () => takeAction(action);
        }
        
        buttonsContainer.appendChild(btn);
    });
}

function hideActionPanel() {
    document.getElementById('action-panel').style.display = 'none';
}

function takeAction(action) {
    socket.emit('player_action', {
        game_id: currentGameId,
        action: action
    });
    hideActionPanel();
}

function formatCard(card) {
    const suits = {
        'heart': '♥',
        'diamonds': '♦',
        'spades': '♠',
        'clubs': '♣'
    };
    
    const values = {
        11: 'J',
        12: 'Q',
        13: 'K',
        14: 'A'
    };
    
    const value = values[card.value] || card.value;
    const suit = suits[card.color] || card.color;
    
    return `${value}${suit}`;
}

function addLog(message) {
    const logMessages = document.getElementById('log-messages');
    const p = document.createElement('p');
    p.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    logMessages.appendChild(p);
    logMessages.scrollTop = logMessages.scrollHeight;
}
