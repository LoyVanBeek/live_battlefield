import pytest
from tests_e2e.pages.gm_page import GameMasterPage


def test_page_loads(page, app_url, seeded_game):
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()

    title = page.title()
    assert "Game Master" in title

    for color in ["red", "blue", "green"]:
        assert gm.available_team_card(color).count() == 1

    assert gm.start_button().is_disabled()
    assert gm.end_button().is_disabled()


def test_create_team(page, app_url, seeded_game):
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()

    gm.join_team("red", "Red Team")
    card = gm.team_card("red")
    card.wait_for(state="visible")

    name_text = gm.team_card_name("red").text_content()
    assert "Red Team" in name_text


def test_create_team_duplicate_color(page, app_url, seeded_game):
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()

    gm.join_team("red", "First Team")
    # Only one team card may exist for red after a single join
    cards = gm.team_card("red").all()
    assert len(cards) == 1
    name_text = gm.team_card_name("red").text_content()
    assert "First Team" in name_text
    # The red available card disappears once the color is taken
    assert gm.available_team_card("red").count() == 0


def test_create_multiple_teams(page, app_url, seeded_game):
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()

    gm.join_team("red", "Team Alpha")
    gm.join_team("blue", "Team Beta")

    for color in ["red", "blue"]:
        card = gm.team_card(color)
        card.wait_for(state="visible")


def test_add_ai_player(page, app_url, seeded_game):
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()

    gm.add_ai("purple", "AI Bot")
    card = gm.team_card("purple")
    card.wait_for(state="visible")

    badge = gm.ai_badge("purple")
    badge.wait_for(state="visible")
    badge_text = badge.text_content()
    assert "AI" in badge_text





def test_start_game_with_preconditions(page, app_url, seeded_game_with_teams):
    seed = seeded_game_with_teams
    gm = GameMasterPage(page, seed["gm_token"], app_url)
    gm.goto()

    assert not gm.start_button().is_disabled()

    gm.start_game()
    status = gm.get_game_status()
    assert "STARTED" in status


def test_end_game(page, app_url, seeded_game_with_teams):
    seed = seeded_game_with_teams
    gm = GameMasterPage(page, seed["gm_token"], app_url)
    gm.goto()

    gm.start_game()
    gm.end_game()

    status = gm.get_game_status()
    assert "ENDED" in status

    assert gm.start_button().is_disabled()
    assert gm.end_button().is_disabled()


def test_start_button_disabled_without_preconditions(page, app_url, seeded_game):
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()

    gm.join_team("red", "Lone Team")
    assert gm.start_button().is_disabled()


def test_ready_badge_shown_when_all_ships_placed(page, app_url, seeded_game_with_teams):
    """Teams that placed all ships get a ✓ Ready badge while preparing."""
    seed = seeded_game_with_teams
    gm = GameMasterPage(page, seed["gm_token"], app_url)
    gm.goto()

    for color in ["red", "blue"]:
        badge = gm.ready_badge(color)
        badge.wait_for(state="visible", timeout=5000)
        assert "Ready" in badge.text_content()


def test_ready_badge_absent_before_ships_placed(page, app_url, seeded_game):
    """A fresh team with no ships placed has no ready badge."""
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()
    gm.join_team("red", "Red Team")

    assert gm.ready_badge("red").count() == 0


def test_auto_start_on_ready_starts_game(page, app_url, seeded_game_with_teams):
    """Enabling auto-start on a ready game starts it immediately."""
    seed = seeded_game_with_teams
    gm = GameMasterPage(page, seed["gm_token"], app_url)
    gm.goto()

    toggle = gm.auto_start_toggle()
    toggle.wait_for(state="visible")
    toggle.check()
    page.wait_for_timeout(1500)

    status = gm.get_game_status()
    assert "STARTED" in status


def test_auto_start_waiting_when_ships_missing(page, app_url, seeded_game):
    """Enabling auto-start before all ships are placed keeps the game waiting."""
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()
    gm.join_team("red", "Red Team")
    gm.join_team("blue", "Blue Team")

    toggle = gm.auto_start_toggle()
    toggle.check()
    page.wait_for_timeout(1000)

    status = gm.get_game_status()
    assert "WAITING" in status


def test_eliminated_badge_on_destroyed_team(page, app_url, seeded_game_with_teams):
    """Sinking all of a team's ships shows the 💀 Eliminated badge on its card."""
    import httpx

    from tests_e2e.config import HTTPX_TIMEOUT

    seed = seeded_game_with_teams
    gm = GameMasterPage(page, seed["gm_token"], app_url)
    gm.goto()

    # Start the game so bombing is allowed.
    gm.start_game()

    # Sink every blue-team ship by bombing each cell of its private board that
    # holds a ship.
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.get(
            "/api/board/blue/private.json",
            params={"gm_token": seed["gm_token"]},
        )
        grid = resp.json()["grid"]
        ship_cells = [
            (ri, ci)
            for ri in range(10)
            for ci in range(10)
            if grid[ri][ci].get("has_ship")
        ]
        # Give red enough bombs to sink everything, then sweep the ship cells.
        resp = client.get(
            "/api/state",
            params={"gm_token": seed["gm_token"]},
        )
        red_team = next(t for t in resp.json()["teams"] if t["color"] == "red")
        if red_team["bombs"] < len(ship_cells):
            client.post(
                "/api/quick/add_bombs",
                params={"gm_token": seed["gm_token"]},
                json={"team_color": "red", "count": len(ship_cells) + 5},
            )
        for ri, ci in ship_cells:
            coord = f"{chr(ci + 65)}{ri + 1}"
            resp = client.post(
                "/api/execute",
                params={"team_token": red_team["token"]},
                json={
                    "team_color": "red",
                    "command": "bomb",
                    "args": {"target": "blue", "coordinate": coord},
                },
            )

    # The GM page reflects the destroyed state on the blue team card.
    badge = gm.destroyed_badge("blue")
    badge.wait_for(state="visible", timeout=5000)
    assert "Eliminated" in badge.text_content()


def test_pending_badge_on_team_without_ships(page, app_url, seeded_game):
    """A team that has joined but placed zero ships shows the ⏳ Waiting badge."""
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()
    gm.join_team("red", "No Ships Yet")

    badge = gm.pending_badge("red")
    badge.wait_for(state="visible", timeout=5000)
    assert "Waiting" in badge.text_content()

    # After placing all ships the pending badge disappears and ready appears.
    gm.auto_place_all_ships()
    page.wait_for_timeout(1000)

    assert gm.pending_badge("red").count() == 0
    ready = gm.ready_badge("red")
    ready.wait_for(state="visible", timeout=5000)
    assert "Ready" in ready.text_content()


def test_ai_auto_move_controls_visible(page, app_url, seeded_game_with_teams):
    """AI players have the auto-move toggle and interval input visible."""
    import httpx
    from tests_e2e.config import HTTPX_TIMEOUT

    seed = seeded_game_with_teams
    gm = GameMasterPage(page, seed["gm_token"], app_url)
    gm.goto()

    # No AI yet — controls should not exist.
    assert gm.ai_auto_toggle("purple").count() == 0

    # Add an AI player.
    gm.add_ai("purple", "AutoBot")
    toggle = gm.ai_auto_toggle("purple")
    toggle.wait_for(state="visible", timeout=5000)
    assert toggle.is_visible()

    interval = gm.ai_auto_interval("purple")
    assert interval.is_visible()
    # Default interval is 60 s.
    assert interval.input_value() == "60"

    # Toggle on, then check the state persists.
    toggle.check()
    page.wait_for_timeout(500)
    assert toggle.is_checked()

    # Toggle off.
    toggle.uncheck()
    page.wait_for_timeout(500)
    assert not toggle.is_checked()


def test_ai_auto_move_waits_for_interval(page, app_url, seeded_game_with_teams):
    """Auto-move must not fire before the configured interval elapses.

    Regression: the 2 s /api/state poll used to clear the timer flag while
    the timer was running, so the loop restarted on the next poll and fired
    a move almost immediately (and then every poll).  With a long interval
    there must be no trigger-ai-move request during several poll cycles.
    """
    seed = seeded_game_with_teams
    gm = GameMasterPage(page, seed["gm_token"], app_url)
    gm.goto()

    moves: list[str] = []

    def _record(request):
        if "/api/quick/trigger-ai-move" in request.url:
            moves.append(request.url)

    page.on("request", _record)

    # Add an AI and enable auto-move with a long interval.
    gm.add_ai("purple", "AutoBot")
    toggle = gm.ai_auto_toggle("purple")
    toggle.wait_for(state="visible", timeout=5000)
    gm.ai_auto_interval("purple").fill("300")
    toggle.check()

    # Observe across several 2 s poll cycles.
    page.wait_for_timeout(6000)

    assert moves == [], f"auto-move fired before the interval elapsed: {moves}"
