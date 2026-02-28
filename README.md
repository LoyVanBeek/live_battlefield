# Live Battlefield

Battleship game played via Telegram with real-life location quests.

## Quick Start

1. Copy `.env.example` to `.env` and add your Telegram Bot Token:
   ```bash
   cp .env.example .env
   # Edit .env and add TELEGRAM_BOT_TOKEN=your_token_here
   ```

2. Start the application with Docker Compose:
   ```bash
   docker compose up --build
   ```

3. The bot will be running and the web API at `http://localhost:8000`

## Commands

### For Players
- `/join <team_name>` - Join the game as a team
- `/leave` - Leave the game (before it starts)
- `/place <ship_type> <coordinate> <direction>` - Place a ship
  - Ship types: `airplane_carrier`, `battleship`, `torpedo_hunter`, `patrol_boat`
  - Coordinates: A1-J10 (e.g., B2)
  - Directions: `horizontal` or `vertical`
- `/bomb <team_color> <coordinate>` - Throw a bomb at another team
- `/code <location_number> <code>` - Redeem a code from a location
- `/overview` - View your private board and all public boards
- `/locations` - View all quest locations

### For Game Masters
- `/registergm` - Register as a game master
- Send a location message to add a new quest location

## Web API

- `GET /` - API info
- `GET /game-state.png` - Current game state as image
- `GET /teams` - List all teams and their status

## Database Management

### pgAdmin (Database Viewer)

A pgAdmin instance is included for database management.

1. Open http://localhost:5050
2. Login with:
   - Email: admin@example.com
   - Password: admin

3. Add a new server:
   - Name: battleship
   - Host: postgres
   - Port: 5432
   - Username: postgres
   - Password: postgres
   - Database: battleship

## Development

### Running Tests
```bash
python3 -m pytest tests/ -v
```

### Running Locally (without Docker)
```bash
# Install dependencies
uv pip install --system -r pyproject.toml

# Run migrations
alembic upgrade head

# Run the bot and server
python3 -m app.main
```

## Ship Types
- 1x airplane carrier (6 squares)
- 2x battleship (4 squares each)
- 3x torpedo hunter (3 squares each)
- 4x patrol boat (2 squares each)
