#!/usr/bin/env bash
set -euo pipefail

exec docker compose exec app python3 -c "
import urllib.request, json
data = json.loads(urllib.request.urlopen('http://ngrok:4040/api/tunnels').read())
print(data['tunnels'][0]['public_url'])
"
