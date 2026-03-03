/**
 * Game Replay Engine
 * Handles replaying game events with playback controls
 */

class GameReplay {
    constructor(container, boardContainer) {
        this.container = container;
        this.boardContainer = boardContainer;
        this.events = [];
        this.currentIndex = 0;
        this.playing = false;
        this.speed = 5;  // Default 5x speed
        this.state = this.createInitialState();
        this.timerId = null;
    }

    createInitialState() {
        return {
            teams: {},
            locationCodes: {},
            status: 'waiting',
            currentEvent: null,
            winner: null
        };
    }

    async load() {
        const response = await fetch('/api/game/replay');
        const data = await response.json();
        this.events = data.events;
        this.gameStatus = data.game_status;
        this.renderTimeline();
        return data;
    }

    play() {
        if (this.currentIndex >= this.events.length) {
            this.currentIndex = 0;
            this.state = this.createInitialState();
        }
        this.playing = true;
        this.updatePlayPauseButtons();
        this.tick();
    }

    pause() {
        this.playing = false;
        this.updatePlayPauseButtons();
        if (this.timerId) {
            clearTimeout(this.timerId);
            this.timerId = null;
        }
    }

    tick() {
        if (!this.playing || this.currentIndex >= this.events.length) {
            if (this.currentIndex >= this.events.length) {
                this.playing = false;
                this.updatePlayPauseButtons();
                
                // Trigger end animation if game ended
                if (this.state.status === 'ended') {
                    this.showWinnerAnimation();
                }
            }
            return;
        }

        const event = this.events[this.currentIndex];
        this.applyEvent(event);
        this.render();
        
        // Calculate delay based on speed (base 200ms / speed for snappy feel)
        const delay = Math.max(50, 200 / this.speed);
        
        this.timerId = setTimeout(() => {
            this.currentIndex++;
            this.tick();
        }, delay);
    }

    applyEvent(event) {
        this.state.currentEvent = event;
        
        switch (event.type) {
            case 'team_joined':
                this.state.teams[event.payload.color] = {
                    name: event.payload.name,
                    color: event.payload.color,
                    ships: [],
                    bombs: event.payload.bombs,
                    privateBoard: this.createEmptyBoard(),
                    publicBoard: this.createEmptyBoard()
                };
                break;
                
            case 'ship_placed':
                if (this.state.teams[event.payload.color]) {
                    const team = this.state.teams[event.payload.color];
                    const shipCells = this.getShipCells(
                        event.payload.row,
                        event.payload.col,
                        event.payload.ship_type,
                        event.payload.direction
                    );
                    
                    // Add ship to private board (own view)
                    shipCells.forEach(([row, col]) => {
                        team.privateBoard[row][col] = { ship: event.payload.ship_type, isNew: true };
                    });
                    
                    // Track ships for animation
                    team.ships.push({
                        type: event.payload.ship_type,
                        cells: shipCells,
                        isNew: true
                    });
                }
                break;
                
            case 'bomb_thrown':
                const attacker = event.payload.attacker_color;
                const target = event.payload.target_color;
                const row = event.payload.row;
                const col = event.payload.col;
                const result = event.payload.result;
                
                // Update target's public board (shows attacks from others)
                if (this.state.teams[target]) {
                    const isHit = result === 'hit';
                    this.state.teams[target].publicBoard[row][col] = { 
                        attacker: attacker, 
                        isHit: isHit,
                        isNew: true 
                    };
                }
                break;
                
            case 'code_redeemed':
                if (event.payload.success && this.state.teams[event.payload.color]) {
                    this.state.teams[event.payload.color].bombs += event.payload.bombs_earned;
                }
                break;
                
            case 'game_started':
                this.state.status = 'started';
                break;
                
            case 'game_ended':
                this.state.status = 'ended';
                this.state.winner = event.payload.winner;
                break;
        }
    }

    createEmptyBoard() {
        return Array(10).fill(null).map(() => Array(10).fill(null));
    }

    getShipCells(row, col, shipType, direction) {
        const sizes = {
            'airplane_carrier': 6,
            'battleship': 4,
            'torpedo_hunter': 3,
            'patrol_boat': 2
        };
        const size = sizes[shipType] || 4;
        const cells = [];
        
        for (let i = 0; i < size; i++) {
            if (direction === 'horizontal') {
                cells.push([row, col + i]);
            } else {
                cells.push([row + i, col]);
            }
        }
        return cells;
    }

    render() {
        this.renderBoard();
        this.updateTimelinePosition();
        this.updateEventInfo();
    }

    renderBoard() {
        const teams = Object.values(this.state.teams);
        if (teams.length === 0) {
            this.boardContainer.innerHTML = '<p style="color: #888; text-align: center;">No teams yet</p>';
            return;
        }

        let html = '';
        
        // Get column labels
        const colLabels = 'ABCDEFGHIJ';
        
        teams.forEach(team => {
            html += `<div class="replay-team-board" data-color="${team.color}">`;
            html += `<h4 style="color: ${this.getTeamColorHex(team.color)}; margin: 10px 0 5px;">${team.name} (${team.color}) - Bombs: ${team.bombs}</h4>`;
            
            // Private board (shows own ships)
            html += '<div class="board-grid">';
            html += '<div class="board-label" style="grid-column: 1;">Own Ships</div>';
            html += '<div class="col-labels">';
            for (let c = 0; c < 10; c++) html += `<span>${colLabels[c]}</span>`;
            html += '</div>';
            
            for (let r = 0; r < 10; r++) {
                html += `<span class="row-label">${r + 1}</span>`;
                for (let c = 0; c < 10; c++) {
                    const cell = team.privateBoard[r][c];
                    let cellClass = 'cell';
                    let cellContent = '';
                    
                    if (cell) {
                        if (cell.ship) {
                            cellClass += ' ship';
                            cellContent = '■';
                            if (cell.isNew) cellClass += ' ship-new';
                        }
                    }
                    html += `<div class="${cellClass}">${cellContent}</div>`;
                }
            }
            html += '</div>';
            
            // Public board (shows attacks from others)
            html += '<div class="board-grid">';
            html += '<div class="board-label" style="grid-column: 1;">Attacks</div>';
            html += '<div class="col-labels">';
            for (let c = 0; c < 10; c++) html += `<span>${colLabels[c]}</span>`;
            html += '</div>';
            
            for (let r = 0; r < 10; r++) {
                html += `<span class="row-label">${r + 1}</span>`;
                for (let c = 0; c < 10; c++) {
                    const cell = team.publicBoard[r][c];
                    let cellClass = 'cell';
                    let cellContent = '';
                    
                    if (cell) {
                        if (cell.isHit) {
                            cellClass += ' hit';
                            cellContent = '✕';
                            if (cell.isNew) cellClass += ' hit-new';
                        } else {
                            cellClass += ' miss';
                            cellContent = '○';
                            if (cell.isNew) cellClass += ' miss-new';
                        }
                    }
                    html += `<div class="${cellClass}">${cellContent}</div>`;
                }
            }
            html += '</div>';
            
            html += '</div>';
        });
        
        // Show game status overlay
        if (this.state.status === 'started') {
            html += '<div class="replay-overlay">GAME STARTED</div>';
        }
        
        this.boardContainer.innerHTML = html;
    }

    updateTimelinePosition() {
        const progress = document.getElementById('replay-progress');
        const position = document.getElementById('replay-position');
        
        if (progress && this.events.length > 0) {
            const percent = ((this.currentIndex + 1) / this.events.length) * 100;
            progress.style.width = percent + '%';
        }
        
        if (position) {
            position.textContent = `${this.currentIndex + 1} / ${this.events.length}`;
        }
    }

    updateEventInfo() {
        const eventInfo = document.getElementById('replay-event-info');
        if (!eventInfo) return;
        
        const event = this.state.currentEvent;
        if (!event) {
            eventInfo.textContent = 'Click play to start replay';
            return;
        }
        
        let text = '';
        switch (event.type) {
            case 'team_joined':
                text = `${event.payload.name} joined as ${event.payload.color}`;
                break;
            case 'ship_placed':
                text = `${event.payload.color} placed ${event.payload.ship_type}`;
                break;
            case 'bomb_thrown':
                const result = event.payload.result === 'hit' ? 'HIT!' : 'Miss';
                text = `${event.payload.attacker_color} bombed ${event.payload.target_color} - ${result}`;
                break;
            case 'code_redeemed':
                text = `${event.payload.color} redeemed code for ${event.payload.bombs_earned} bomb(s)`;
                break;
            case 'game_started':
                text = '🎮 Game Started!';
                break;
            case 'game_ended':
                text = `🏆 Game Over! Winner: ${event.payload.winner || 'Unknown'}`;
                break;
            default:
                text = event.type;
        }
        
        eventInfo.textContent = text;
    }

    updatePlayPauseButtons() {
        const playBtn = document.getElementById('replay-btn-play');
        const pauseBtn = document.getElementById('replay-btn-pause');
        
        if (playBtn && pauseBtn) {
            if (this.playing) {
                playBtn.classList.add('hidden');
                pauseBtn.classList.remove('hidden');
            } else {
                playBtn.classList.remove('hidden');
                pauseBtn.classList.add('hidden');
            }
        }
    }

    setSpeed(speed) {
        this.speed = speed;
        
        // Update button states
        document.querySelectorAll('.speed-btn').forEach(btn => {
            btn.classList.toggle('active', parseInt(btn.dataset.speed) === speed);
        });
    }

    seekTo(index) {
        // Rebuild state up to this index
        this.currentIndex = Math.max(0, Math.min(index, this.events.length - 1));
        this.state = this.createInitialState();
        
        for (let i = 0; i <= this.currentIndex; i++) {
            this.applyEvent(this.events[i]);
        }
        
        this.render();
    }

    reset() {
        this.pause();
        this.seekTo(0);
    }

    goToEnd() {
        this.seekTo(this.events.length - 1);
    }

    renderTimeline() {
        const timeline = document.getElementById('replay-timeline');
        if (!timeline || this.events.length === 0) return;
        
        // Clear existing markers
        timeline.querySelectorAll('.timeline-marker').forEach(m => m.remove());
        
        // Add event markers
        this.events.forEach((event, index) => {
            const marker = document.createElement('div');
            marker.className = 'timeline-marker';
            marker.dataset.index = index;
            marker.style.left = ((index + 1) / this.events.length * 100) + '%';
            
            // Color based on event type
            const colors = {
                'team_joined': '#51cf66',
                'ship_placed': '#4dabf7',
                'bomb_thrown': '#e03131',
                'code_redeemed': '#fcc419',
                'game_started': '#9775fa',
                'game_ended': '#ffd43b'
            };
            marker.style.background = colors[event.type] || '#666';
            
            marker.addEventListener('click', () => this.seekTo(index));
            timeline.appendChild(marker);
        });
    }

    showWinnerAnimation() {
        if (this.state.winner) {
            // Could trigger confetti here
            console.log('Winner:', this.state.winner);
        }
    }

    getTeamColorHex(color) {
        const colors = {
            'red': '#e03131',
            'blue': '#4dabf7',
            'green': '#51cf66',
            'purple': '#9775fa',
            'orange': '#fd7e14',
            'yellow': '#fcc419'
        };
        return colors[color] || '#fff';
    }
}

// Global replay instance
let gameReplay = null;

function initReplay() {
    const container = document.getElementById('replay-modal');
    const boardContainer = document.getElementById('replay-board');
    
    if (!container || !boardContainer) {
        console.error('Replay elements not found');
        return null;
    }
    
    gameReplay = new GameReplay(container, boardContainer);
    
    // Attach control event listeners
    document.getElementById('replay-btn-play')?.addEventListener('click', () => gameReplay.play());
    document.getElementById('replay-btn-pause')?.addEventListener('click', () => gameReplay.pause());
    document.getElementById('replay-btn-reset')?.addEventListener('click', () => gameReplay.reset());
    document.getElementById('replay-btn-end')?.addEventListener('click', () => gameReplay.goToEnd());
    
    // Speed buttons
    document.querySelectorAll('.speed-btn').forEach(btn => {
        btn.addEventListener('click', () => gameReplay.setSpeed(parseInt(btn.dataset.speed)));
    });
    
    // Timeline click to seek
    const timeline = document.getElementById('replay-timeline');
    timeline?.addEventListener('click', (e) => {
        if (e.target === timeline) {
            const rect = timeline.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            const index = Math.floor(percent * gameReplay.events.length);
            gameReplay.seekTo(index);
        }
    });
    
    return gameReplay;
}

async function showReplayModal() {
    const modal = document.getElementById('replay-modal');
    if (!modal) return;
    
    modal.classList.add('active');
    
    // Initialize or reload replay
    if (!gameReplay) {
        gameReplay = initReplay();
    }
    
    if (gameReplay) {
        await gameReplay.load();
        gameReplay.render();
    }
}

function closeReplayModal() {
    const modal = document.getElementById('replay-modal');
    if (modal) {
        modal.classList.remove('active');
    }
    if (gameReplay) {
        gameReplay.pause();
    }
}

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeReplayModal();
    }
});
