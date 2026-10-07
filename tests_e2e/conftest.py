import os
import socket
import socketserver
import sys
import threading
from typing import cast
from urllib.parse import urlparse

import pytest
from tests_e2e.config import IS_CI, HTTPX_TIMEOUT, PLAYWRIGHT_TIMEOUT


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "teardown":
        output_dir = item.config.getoption("--output", "test-results")
        for entry in os.listdir(output_dir):
            subdir = os.path.join(output_dir, entry)
            video_file = os.path.join(subdir, "video.webm")
            if os.path.isfile(video_file):
                os.rename(video_file, os.path.join(subdir, f"{entry}.webm"))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

APP_URL = os.environ.get("APP_URL", "http://localhost:8000")
APP_UPSTREAM = os.environ.get("APP_UPSTREAM", "test-app:8000")
ADMIN_TOKEN = "e2e-test-admin"


def _pump(src: socket.socket, dst: socket.socket) -> None:
    """Relay bytes until one side closes, then tear down both directions."""
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for sock in (src, dst):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


class _RelayHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        # Nagle + delayed-ACK on a forwarding socket stalls small segments for
        # ~40ms — enough to turn every API round trip into a visible wait.
        self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # socketserver types .server as BaseServer; only _Relay builds this handler.
        server = cast(_Relay, self.server)
        host, port = server.upstream
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError as exc:
            print(f"e2e relay: cannot reach {host}:{port}: {exc}", file=sys.stderr)
            return
        upstream.settimeout(None)  # SSE connections idle longer than connect-timeout
        upstream.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        reverse = threading.Thread(target=_pump, args=(upstream, self.request), daemon=True)
        reverse.start()
        _pump(self.request, upstream)
        reverse.join(timeout=5)


class _Relay(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr, upstream, family=socket.AF_INET):
        self.upstream = upstream
        self.address_family = family
        super().__init__(addr, _RelayHandler)


@pytest.fixture(scope="session", autouse=True)
def _loopback_relay():
    """Expose the test app on APP_URL's loopback address.

    The app runs at http://test-app:8000 — not a potentially-trustworthy origin,
    so `window.isSecureContext` is false and the Geolocation API is unavailable
    (a real phone gets a secure context through ngrok's https). Browsers treat
    loopback as secure without TLS, so relaying APP_URL to the app gives tests a
    genuine secure context with no Chromium flags or certificates.

    If the port is already served locally (app run outside docker), nothing is
    started and the existing listener answers directly.
    """
    parsed = urlparse(APP_URL)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    host, _, up_port = APP_UPSTREAM.rpartition(":")
    upstream = (host, int(up_port))

    servers = []
    for family, bind in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            servers.append(_Relay((bind, port), upstream, family))
        except OSError:
            continue  # IPv6 unavailable (or port already in use locally)

    threads = [
        threading.Thread(target=server.serve_forever, daemon=True) for server in servers
    ]
    for thread in threads:
        thread.start()

    yield

    for server in servers:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def _page_timeout(page):
    page.set_default_timeout(PLAYWRIGHT_TIMEOUT)


@pytest.fixture(scope="session")
def app_url() -> str:
    return APP_URL


@pytest.fixture(scope="session")
def admin_token() -> str:
    return ADMIN_TOKEN


@pytest.fixture(scope="function")
def seeded_game(app_url: str, admin_token: str) -> dict:
    """Create a fresh game via API and return its GM token."""
    import httpx

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/admin/create-game",
            params={"token": admin_token},
        )
        data = resp.json()
        gm_token = data["token"]

        resp = client.get(
            "/api/state",
            params={"gm_token": gm_token},
        )
        data = resp.json()

        return {
            "gm_token": gm_token,
            "available_colors": data.get("available_colors", []),
        }


@pytest.fixture(scope="function")
def seeded_game_with_locations(app_url: str, admin_token: str) -> dict:
    """Create a fresh game with locations already placed."""
    import httpx

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/admin/create-game",
            params={"token": admin_token},
        )
        data = resp.json()
        gm_token = data["token"]

        resp = client.get(
            "/api/state",
            params={"gm_token": gm_token},
        )
        data = resp.json()

        locations_created = []
        coords = [
            (51.59, 5.33),
            (51.58, 5.34),
            (51.57, 5.35),
            (51.59, 5.36),
            (51.58, 5.37),
        ]
        for lat, lon in coords:
            resp = client.post(
                "/api/quick/create_locations",
                params={"gm_token": gm_token},
                json={"latitude": lat, "longitude": lon, "count": 1, "radius_km": 0},
            )
            loc_data = resp.json()
            if loc_data.get("success"):
                locations_created.extend(loc_data.get("locations", []))

        return {
            "gm_token": gm_token,
            "available_colors": data.get("available_colors", []),
            "locations": locations_created,
        }


@pytest.fixture(scope="function")
def seeded_game_with_teams(app_url: str, admin_token: str) -> dict:
    """Create a fresh game with 2 teams joined and ships placed."""
    import httpx

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/admin/create-game",
            params={"token": admin_token},
        )
        data = resp.json()
        gm_token = data["token"]

        colors = ["red", "blue"]
        teams = {}
        for color in colors:
            resp = client.post(
                "/api/execute",
                params={"gm_token": gm_token},
                json={
                    "team_color": color,
                    "command": "join",
                    "args": {"name": f"{color.capitalize()} Team"},
                },
            )
            
        # Fetch team data (tokens, names) from game state
        resp = client.get(
            "/api/state",
            params={"gm_token": gm_token},
        )
        state_data = resp.json()
        for team in state_data.get("teams", []):
            teams[team["color"]] = {
                "name": team["name"],
                "token": team.get("token", ""),
            }

        # Place all ships with retry until both teams have all 10
        tokens = {c: teams[c]["token"] for c in colors}
        for _ in range(20):
            for color in colors:
                client.post(
                    "/api/quick/place_all_ships",
                    params={"team_token": tokens[color]},
                    json={"team_color": color},
                )
            resp = client.get(
                "/api/game-status",
                params={"gm_token": gm_token},
            )
            status = resp.json()
            if status.get("teams_with_all_ships") == len(colors):
                break

        coords = [(51.59, 5.33), (51.58, 5.34)]
        for lat, lon in coords:
            client.post(
                "/api/quick/create_locations",
                params={"gm_token": gm_token},
                json={"latitude": lat, "longitude": lon, "count": 1, "radius_km": 0},
            )

        return {
            "gm_token": gm_token,
            "teams": teams,
            "team_urls": {c: f"/team/{teams[c]['token']}" for c in colors},
        }
