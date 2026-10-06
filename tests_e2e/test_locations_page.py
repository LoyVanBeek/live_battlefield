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


def test_map_pins_show_location_number(page, app_url, seeded_game_with_locations):
    seed = seeded_game_with_locations
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    pins = lp.pins()
    pins.first.wait_for(state="visible")

    # fixture creates locations 1..5 — every pin carries its location number
    assert pins.count() == lp.get_location_count()
    numbers = {pins.nth(i).inner_text().strip() for i in range(pins.count())}
    assert {str(n) for n in range(1, 6)} <= numbers


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


def test_edit_coords_inline(page, app_url, seeded_game_with_locations):
    seed = seeded_game_with_locations
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    number = 1
    lp.edit_cell("coords", number, "52.5200, 13.4050")

    assert "moved to" in lp.toast().text_content()
    assert lp.coords_cell(number).inner_text().strip() == "52.5200, 13.4050"

    # marker followed the new position (old pos was 51.59, 5.33)
    lp.page.reload()
    lp.page.wait_for_load_state("networkidle")
    assert lp.coords_cell(number).inner_text().strip() == "52.5200, 13.4050"


def test_edit_coords_via_map_click(page, app_url, seeded_game_with_locations):
    seed = seeded_game_with_locations
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    number = 1
    lp.start_cell_edit("coords", number)
    lp.edit_input().fill("0, 0")

    # hint switches to picking mode, then a map click fills the input
    assert "drag marker" in lp.map_hint().inner_text()
    lp.map_element().click(position={"x": 300, "y": 200})
    lp.page.wait_for_function(
        "() => document.getElementById('cell-edit-input').value !== '0, 0'"
    )
    picked = lp.edit_input().input_value()
    lat, lon = (float(p.strip()) for p in picked.split(","))
    assert -90 <= lat <= 90 and -180 <= lon <= 180

    lp.save_cell_edit()
    assert "moved to" in lp.toast().text_content()

    # map click with no editor open still creates a location (unchanged)
    assert lp.map_hint().inner_text().strip().endswith("add location")


def test_edit_coords_rejects_invalid(page, app_url, seeded_game_with_locations):
    seed = seeded_game_with_locations
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    number = 1
    original = lp.coords_cell(number).inner_text().strip()

    lp.edit_cell("coords", number, "not a coordinate", expect="error")
    assert 'latitude, longitude' in lp.toast().text_content()

    # editor is still open after the rejected save — retry in place
    lp.edit_input().fill("120, 5.33")
    lp.save_cell_edit(expect="error")
    assert "Latitude must be between -90 and 90" in lp.toast().text_content()

    # neither attempt moved the location
    lp.cancel_cell_edit()
    assert lp.coords_cell(number).inner_text().strip() == original


def test_edit_coords_via_marker_drag(page, app_url, seeded_game_with_locations):
    seed = seeded_game_with_locations
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    number = 1
    lp.start_cell_edit("coords", number)
    lp.edit_input().fill("0, 0")

    marker = lp.page.locator(".leaflet-marker-icon").first
    box = marker.bounding_box()
    assert box is not None

    # drag the marker; dragend should fill the input with the new position
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + 80, box["y"] + 60, steps=10)
    page.mouse.up()
    page.wait_for_function(
        "() => document.getElementById('cell-edit-input').value !== '0, 0'"
    )

    picked = lp.edit_input().input_value()
    lat, lon = (float(p.strip()) for p in picked.split(","))
    assert (lat, lon) != (0.0, 0.0)
    assert -90 <= lat <= 90 and -180 <= lon <= 180

    lp.save_cell_edit()
    assert "moved to" in lp.toast().text_content()
    # cell displays toFixed(4); the input keeps full precision
    lat4, lon4 = (float(p.strip()) for p in lp.coords_cell(number).inner_text().split(","))
    assert lat4 == round(lat, 4)
    assert lon4 == round(lon, 4)


def test_map_click_still_creates_location_when_not_editing(page, app_url, seeded_game):
    """Regression: map click creates a location unless the coords editor is open."""
    seed = seeded_game
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    assert lp.get_location_count() == 0
    assert "add location" in lp.map_hint().inner_text()

    lp.map_element().click(position={"x": 80, "y": 260})
    lp.page.wait_for_function(
        "() => !document.querySelector('#locations-body td[colspan=\"7\"]')"
    )

    assert lp.get_location_count() == 1
    assert "add location" in lp.map_hint().inner_text()


def test_insert_location_via_gps(page, app_url, seeded_game):
    """📍 button drops one location at the exact GPS fix (radius_km=0)."""
    seed = seeded_game
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)

    page.context.grant_permissions(["geolocation"])
    page.context.set_geolocation({"latitude": 52.52, "longitude": 13.405, "accuracy": 12})

    lp.goto()
    assert lp.get_location_count() == 0

    lp.my_location_button().click()
    page.wait_for_function(
        "() => document.getElementById('toast').classList.contains('success')"
    )
    assert "±12m" in lp.toast().text_content()

    page.wait_for_function(
        "() => !document.querySelector('#locations-body td[colspan=\"7\"]')"
    )
    assert lp.get_location_count() == 1
    # exact position — the default 2km radius would have offset it
    assert lp.coords_cell(1).inner_text().strip() == "52.5200, 13.4050"
    assert lp.my_location_button().is_enabled()


def test_insert_location_via_gps_denied(page, app_url, seeded_game):
    """Without geolocation permission the button errors and creates nothing."""
    seed = seeded_game
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    lp.my_location_button().click()
    page.wait_for_function(
        "() => document.getElementById('toast').classList.contains('error')"
    )
    assert "permission denied" in lp.toast().text_content().lower()

    assert lp.get_location_count() == 0
    assert lp.my_location_button().is_enabled()


def test_insert_location_via_gps_requires_secure_context(page, app_url, seeded_game):
    """Plain-HTTP origins get no Geolocation API — the button must say so (HTTPS)."""
    seed = seeded_game
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)

    # simulate an insecure origin: navigator.geolocation is undefined in browsers
    page.add_init_script(
        "Object.defineProperty(Navigator.prototype, 'geolocation',"
        " { get: function () { return undefined; } });"
    )
    lp.goto()

    lp.my_location_button().click()
    page.wait_for_function(
        "() => document.getElementById('toast').classList.contains('error')"
    )
    assert "HTTPS" in lp.toast().text_content()

    assert lp.get_location_count() == 0
