#!/bin/bash
# Battle phase - bomb enemies and redeem codes

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "=== Battle Phase ==="

echo ""
echo "1. RED bombs BLUE at A1..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "team_color": "red",
    "command": "bomb",
    "args": {"target": "blue", "coordinate": "A1"}
  }')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "2. BLUE bombs GREEN at B2..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "team_color": "blue",
    "command": "bomb",
    "args": {"target": "green", "coordinate": "B2"}
  }')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "3. GREEN bombs RED at C3..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "team_color": "green",
    "command": "bomb",
    "args": {"target": "red", "coordinate": "C3"}
  }')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "=== Getting Location Codes ==="
LOCATIONS=$(curl -s "$BASE_URL/api/admin/locations")
echo "$LOCATIONS" | jq -r '.locations[] | "Location \(.number): \(.code)"'

echo ""
echo "4. RED redeems code at location 1..."
CODE=$(echo "$LOCATIONS" | jq -r '.locations[0].code')
RESPONSE=$(curl -s -X POST "$BASE_URL/api/execute" \
  -H "Content-Type: application/json" \
  -d "{
    \"team_color\": \"red\",
    \"command\": \"code\",
    \"args\": {\"location_number\": 1, \"code\": \"$CODE\"}
  }")
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "5. BLUE redeems code at location 2..."
CODE=$(echo "$LOCATIONS" | jq -r '.locations[1].code')
RESPONSE=$(curl -s -X POST "$BASE_URL/api/execute" \
  -H "Content-Type: application/json" \
  -d "{
    \"team_color\": \"blue\",
    \"command\": \"code\",
    \"args\": {\"location_number\": 2, \"code\": \"$CODE\"}
  }")
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "6. GREEN redeems code at location 3..."
CODE=$(echo "$LOCATIONS" | jq -r '.locations[2].code')
RESPONSE=$(curl -s -X POST "$BASE_URL/api/execute" \
  -H "Content-Type: application/json" \
  -d "{
    \"team_color\": \"green\",
    \"command\": \"code\",
    \"args\": {\"location_number\": 3, \"code\": \"$CODE\"}
  }")
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "7. RED bombs BLUE at D4..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "team_color": "red",
    "command": "bomb",
    "args": {"target": "blue", "coordinate": "D4"}
  }')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "8. BLUE bombs GREEN at E5..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "team_color": "blue",
    "command": "bomb",
    "args": {"target": "green", "coordinate": "E5"}
  }')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "=== Current Game State ==="
curl -s "$BASE_URL/api/state" | jq '.'

echo ""
echo "=== Public State ==="
curl -s "$BASE_URL/api/public-state" | jq '.'

echo ""
echo "=== Game Status ==="
curl -s "$BASE_URL/api/game-status" | jq '.'
