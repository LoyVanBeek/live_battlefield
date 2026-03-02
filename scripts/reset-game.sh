#!/bin/bash
# Reset the game and create initial state

BASE_URL="${BASE_URL:-http://localhost:8000}"

WAIT_TIME=0
WAIT_KEY=no

usage() {
    echo "Usage: $0 [-w] [-t seconds]"
    echo "  -w, --wait-key      Wait for key press between steps"
    echo "  -t, --wait-time N   Wait N seconds between steps"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -w|--wait-key)
            WAIT_KEY=yes
            shift
            ;;
        -t|--wait-time)
            WAIT_TIME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

wait_between_steps() {
    if [ "$WAIT_TIME" -gt 0 ] 2>/dev/null; then
        echo "  (waiting ${WAIT_TIME}s...)"
        sleep "$WAIT_TIME"
    fi
    if [ "$WAIT_KEY" = "yes" ]; then
        echo ""
        read -p "Press Enter to continue..."
    fi
}

echo "=== Resetting Game ==="

echo ""
echo "1. Clearing database..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/quick/clear-database")
echo "$RESPONSE" | jq -r '.message // .'

wait_between_steps

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

wait_between_steps

echo ""
echo "=== Current Game Status ==="
curl -s "$BASE_URL/api/game-status" | jq '.'

echo ""
echo "=== Public State ==="
curl -s "$BASE_URL/api/public-state" | jq '.'
