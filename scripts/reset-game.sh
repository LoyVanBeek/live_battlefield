#!/bin/bash
# Reset the game and create initial state

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "=== Resetting Game ==="

echo ""
echo "1. Clearing database..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/quick/clear-database")
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "2. Creating 10 locations around Berlin..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/quick/create_locations" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 52.52,
    "longitude": 13.405,
    "count": 10,
    "radius_km": 2.0
  }')
echo "$RESPONSE" | jq -r '.message // .'

echo ""
echo "3. Locations created:"
echo "$RESPONSE" | jq -r '.locations[]? | "  Location \(.number): \(.code) (\(.lat | floor(4)), \(.lon | floor(4)))"' 2>/dev/null

echo ""
echo "=== Current Game Status ==="
curl -s "$BASE_URL/api/game-status" | jq '.'

echo ""
echo "=== Public State ==="
curl -s "$BASE_URL/api/public-state" | jq '.'
