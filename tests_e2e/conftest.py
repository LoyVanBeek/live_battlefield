import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

APP_URL = os.environ.get("APP_URL", "http://localhost:8000")
ADMIN_TOKEN = "e2e-test-admin"


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

    with httpx.Client(base_url=app_url, timeout=30) as client:
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

    with httpx.Client(base_url=app_url, timeout=30) as client:
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

    with httpx.Client(base_url=app_url, timeout=30) as client:
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
            join_data = resp.json()

            resp = client.post(
                "/api/quick/place_all_ships",
                params={"gm_token": gm_token},
                json={"team_color": color},
            )

            resp = client.get(
                "/api/state",
                params={"gm_token": gm_token},
            )
            state_data = resp.json()
            for team in state_data.get("teams", []):
                if team["color"] == color:
                    teams[color] = {
                        "name": team["name"],
                        "token": team.get("token", ""),
                    }

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
