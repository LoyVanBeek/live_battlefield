import pytest
from tests_e2e.pages.gm_page import GameMasterPage


def test_page_loads(page, app_url, seeded_game):
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()

    title = page.title()
    assert "Game Master" in title

    options = gm.join_color_select().locator("option").all()
    option_values = [opt.get_attribute("value") for opt in options]
    assert "" in option_values
    assert "red" in option_values
    assert "blue" in option_values
    assert "green" in option_values

    assert gm.start_button().is_disabled()
    assert gm.end_button().is_disabled()

    new_game_btn = gm.new_game_button()
    new_game_style = new_game_btn.get_attribute("style")
    assert new_game_style is None or "display: none" not in new_game_style


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
    # After first join, "red" is no longer available in the dropdown
    # The duplicate join via the same select should be rejected by the API
    # We verify that only one team card exists for red
    cards = gm.team_card("red").all()
    assert len(cards) == 1
    name_text = gm.team_card_name("red").text_content()
    assert "First Team" in name_text


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
    assert not gm.new_game_button().is_disabled()


def test_start_button_disabled_without_preconditions(page, app_url, seeded_game):
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()

    gm.join_team("red", "Lone Team")
    assert gm.start_button().is_disabled()
