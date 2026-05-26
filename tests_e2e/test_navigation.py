import pytest
from tests_e2e.pages.gm_page import GameMasterPage
from tests_e2e.pages.locations_page import LocationsPage
from tests_e2e.pages.events_page import EventsPage


def test_navigate_to_locations_from_gm(page, app_url, seeded_game):
    seed = seeded_game
    gm = GameMasterPage(page, seed["gm_token"], app_url)
    gm.goto()

    gm.nav_locations_link().click()
    page.wait_for_load_state("load")

    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    count = lp.get_location_count()
    assert count >= 0

    current_url = page.url
    assert "locations-secret" in current_url


def test_navigate_to_events_from_gm(page, app_url, seeded_game):
    seed = seeded_game
    gm = GameMasterPage(page, seed["gm_token"], app_url)
    gm.goto()

    gm.nav_events_link().click()
    page.wait_for_load_state("load")

    ep = EventsPage(page, seed["gm_token"], app_url=app_url)
    count = ep.get_event_count()
    assert count >= 0

    current_url = page.url
    assert "/events" in current_url
