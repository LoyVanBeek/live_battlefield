#!/bin/bash
# Prepare the game - join teams and place ships

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "=== Preparing Game (Join Teams & Place Ships) ==="

echo ""
echo "1. Joining team RED..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "team_color": "red",
    "command": "join",
    "args": {"name": "Red Team"}
  }')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "2. Joining team BLUE..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "team_color": "blue",
    "command": "join",
    "args": {"name": "Blue Team"}
  }')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "3. Joining team GREEN..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "team_color": "green",
    "command": "join",
    "args": {"name": "Green Team"}
  }')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "=== Adding bombs to teams (must be before starting game) ==="
echo ""
echo "4. Adding bombs to RED..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/quick/add_bombs" \
  -H "Content-Type: application/json" \
  -d '{"team_color": "red", "count": 5}')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "5. Adding bombs to BLUE..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/quick/add_bombs" \
  -H "Content-Type: application/json" \
  -d '{"team_color": "blue", "count": 5}')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "6. Adding bombs to GREEN..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/quick/add_bombs" \
  -H "Content-Type: application/json" \
  -d '{"team_color": "green", "count": 5}')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "=== Placing Ships ==="
echo ""
echo "7. Placing all ships for RED..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/quick/place_all_ships" \
  -H "Content-Type: application/json" \
  -d '{"team_color": "red"}')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "8. Placing all ships for BLUE..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/quick/place_all_ships" \
  -H "Content-Type: application/json" \
  -d '{"team_color": "blue"}')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "9. Placing all ships for GREEN..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/quick/place_all_ships" \
  -H "Content-Type: application/json" \
  -d '{"team_color": "green"}')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "=== Starting Game ==="
echo ""
echo "10. Starting the game..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/quick/start-game")
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "=== Final Game Status ==="
curl -s "$BASE_URL/api/game-status" | jq '.'

echo ""
echo "=== Game State (Teams) ==="
curl -s "$BASE_URL/api/state" | jq '{teams: .teams, winner: .winner, locations: .locations}'
