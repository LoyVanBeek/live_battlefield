import random
import httpx
import pytest
from tests_e2e.pages.gm_page import GameMasterPage
from tests_e2e.pages.team_page import TeamPage


def _find_unhit_ship_cell(grid):
    for ri, row in enumerate(grid):
        for ci, cell in enumerate(row):
            if cell.get("has_ship") and cell.get("status") == "clear":
                return ri, ci
    return None


def _find_unbombed_empty_cell(grid):
    for ri, row in enumerate(grid):
        for ci, cell in enumerate(row):
            if not cell.get("has_ship") and cell.get("status") == "clear":
                return ri, ci
    return None


def test_play_full_game(page, app_url, admin_token):
    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.post(
            "/api/admin/create-game",
            params={"token": admin_token},
        )
        data = resp.json()
        gm_token = data["token"]

        client.post(
            "/api/quick/create_locations",
            params={"gm_token": gm_token},
            json={"latitude": 51.590, "longitude": 5.330, "count": 1, "radius_km": 0},
        )

        for color in ["red", "blue"]:
            client.post(
                "/api/execute",
                params={"gm_token": gm_token},
                json={
                    "team_color": color,
                    "command": "join",
                    "args": {"name": f"{color.title()} Team"},
                },
            )

        resp = client.get("/api/state", params={"gm_token": gm_token})
        state = resp.json()
        red_token = next(t["token"] for t in state["teams"] if t["color"] == "red")
        blue_token = next(t["token"] for t in state["teams"] if t["color"] == "blue")

        client.post(
            "/api/quick/place_all_ships",
            params={"team_token": red_token},
            json={"team_color": "red"},
        )
        client.post(
            "/api/quick/place_all_ships",
            params={"team_token": blue_token},
            json={"team_color": "blue"},
        )

    gm = GameMasterPage(page, gm_token, app_url)
    gm.goto()
    page.wait_for_timeout(2000)
    gm.start_game()

    status_text = gm.get_game_status()
    assert "STARTED" in status_text

    tp = TeamPage(page, f"/team/{red_token}", app_url)
    tp.goto()

    page.wait_for_function(
        "document.getElementById('ship-count') !== null",
        timeout=10000,
    )

    max_turns = 64
    winner = None

    for turn in range(max_turns):
        with httpx.Client(base_url=app_url, timeout=30) as client:
            resp = client.get("/api/state", params={"gm_token": gm_token})
            state = resp.json()
            winner = state.get("winner")
            if winner:
                break

            # API opponent (blue) bombs a random cell — produces hits AND misses
            resp = client.get(
                "/api/board/red/private.json",
                params={"gm_token": gm_token},
            )
            red_grid = resp.json()["grid"]
            candidates = [
                (ri, ci)
                for ri in range(10)
                for ci in range(10)
                if red_grid[ri][ci].get("status") == "clear"
            ]
            if candidates:
                r, c = random.choice(candidates)
                coord = f"{chr(c + 65)}{r + 1}"
                client.post(
                    "/api/execute",
                    params={"team_token": blue_token},
                    json={
                        "team_color": "blue",
                        "command": "bomb",
                        "args": {"target": "red", "coordinate": coord},
                    },
                )

            resp = client.get("/api/state", params={"gm_token": gm_token})
            state = resp.json()
            winner = state.get("winner")
            if winner:
                break

            red_team = next(t for t in state["teams"] if t["color"] == "red")
            if red_team["bombs"] < 3:
                client.post(
                    "/api/quick/add_bombs",
                    params={"gm_token": gm_token},
                    json={"team_color": "red", "count": 5},
                )

            resp = client.get(
                "/api/board/blue/private.json",
                params={"gm_token": gm_token},
            )
            blue_grid = resp.json()["grid"]

            # UI player (red): mostly hits, every 3rd turn = deliberate miss
            next_target = None
            if turn % 3 == 0 and turn > 0:
                next_target = _find_unbombed_empty_cell(blue_grid)
            if next_target is None:
                next_target = _find_unhit_ship_cell(blue_grid)

        if next_target is None:
            break

        tp.bomb_cell_on_board("blue", next_target[0], next_target[1])

    assert winner is not None, "Game should have a winner"

    gm.goto()
    status_text = gm.get_game_status()
    assert "ENDED" in status_text or "STARTED" not in status_text

    print(f"Game winner: {winner['name']} ({winner['color']}) after {turn + 1} turns")
