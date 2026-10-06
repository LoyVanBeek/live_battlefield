import pytest
from tests_e2e.pages.locations_page import LocationsPage
from tests_e2e.pages.gm_page import GameMasterPage


def test_locations_page_loads(page, app_url, seeded_game_with_locations):
    seed = seeded_game_with_locations
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    count = lp.get_location_count()
    assert count > 0

    map_el = lp.map_element()
    assert map_el.is_visible()

    back_link = lp.back_link()
    href = back_link.get_attribute("href")
    assert "game-master" in href


def test_add_location_via_form(page, app_url, seeded_game):
    seed = seeded_game
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    lp.add_location(51.59, 5.33, count=1, radius=0)
    lp.page.wait_for_timeout(1000)

    count = lp.get_location_count()
    assert count >= 1


def test_edit_bomb_count_inline(page, app_url, seeded_game_with_locations):
    seed = seeded_game_with_locations
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    number = 1
    lp.edit_cell("bombs", number, "7")

    # toast confirms, cell re-renders with new value
    assert "7" in lp.toast().text_content()
    assert "7" in lp.bombs_cell(number).inner_text()

    # persists after reload
    lp.goto()
    assert "7" in lp.bombs_cell(number).inner_text()


def test_edit_code_inline(page, app_url, seeded_game_with_locations):
    seed = seeded_game_with_locations
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    number = 1
    lp.edit_cell("code", number, "NEW123")

    assert "NEW123" in lp.toast().text_content()
    assert lp.code_cell(number).inner_text().strip() == "NEW123"

    # persists after reload
    lp.goto()
    assert lp.code_cell(number).inner_text().strip() == "NEW123"


def test_edit_code_rejects_invalid(page, app_url, seeded_game_with_locations):
    seed = seeded_game_with_locations
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    number = 1
    original = lp.code_cell(number).inner_text().strip()

    # empty code blocked client-side, editor stays open
    lp.start_cell_edit("code", number)
    lp.edit_input().fill("")
    lp.save_cell_button().click()
    assert lp.edit_input().is_visible()
    assert "empty" in lp.toast().text_content()

    lp.cancel_cell_edit()
    assert lp.code_cell(number).inner_text().strip() == original

    # non-alphanumeric rejected (client-side validation, same message as server)
    lp.edit_cell("code", number, "BAD CODE!", expect="error")
    assert "letters and digits" in lp.toast().text_content()


def test_edit_cancel_leaves_value_unchanged(page, app_url, seeded_game_with_locations):
    seed = seeded_game_with_locations
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    number = 1
    original = lp.bombs_cell(number).inner_text()

    lp.start_cell_edit("bombs", number)
    lp.edit_input().fill("99")
    lp.cancel_cell_edit()

    assert lp.bombs_cell(number).inner_text() == original


def test_default_bombs_shown_as_10(page, app_url, seeded_game):
    """A fresh game defaults to 10 bombs per new location."""
    seed = seeded_game
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    assert lp.default_bombs_value().inner_text().strip() == "10"


def test_edit_default_bombs_affects_new_locations(page, app_url, seeded_game):
    seed = seeded_game
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    lp.edit_default_bombs("25")
    assert lp.default_bombs_value().inner_text().strip() == "25"
    assert "25 bombs" in lp.toast().text_content()

    # a location created afterwards gets the new default
    lp.add_location(51.59, 5.33, count=1, radius=0)
    lp.page.wait_for_function(
        "() => document.querySelectorAll('#locations-body tr').length > 0"
    )
    assert lp.bombs_cell(1).inner_text().strip() == "💣 25"


def test_edit_default_bombs_rejects_zero(page, app_url, seeded_game):
    seed = seeded_game
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    lp.edit_default_bombs("0", expect="error")
    assert "at least 1" in lp.toast().text_content()
    # editor stays open, value unchanged
    assert lp.default_bombs_input().is_visible()
    assert lp.default_bombs_value().count() == 0
