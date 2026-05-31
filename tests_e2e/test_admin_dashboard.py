import httpx
import pytest
from tests_e2e.config import HTTPX_TIMEOUT
from tests_e2e.pages.admin_dashboard import AdminDashboardPage


@pytest.fixture
def admin_page(page, app_url, admin_token):
    return AdminDashboardPage(page, admin_token, app_url)


def _create_game(app_url, admin_token):
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/admin/games",
            params={"token": admin_token},
            json={"name": None},
        )
        return resp.json()


def test_checkboxes_render(page, app_url, admin_token, admin_page):
    _create_game(app_url, admin_token)
    _create_game(app_url, admin_token)

    admin_page.goto()

    checkboxes = page.locator("input.game-checkbox")
    count = checkboxes.count()
    assert count >= 2, f"Expected at least 2 checkboxes, got {count}"
    for i in range(count):
        assert checkboxes.nth(i).is_visible()


def test_select_all_toggles_all(page, app_url, admin_token, admin_page):
    _create_game(app_url, admin_token)
    _create_game(app_url, admin_token)

    admin_page.goto()

    game_count = admin_page.game_rows().count()
    assert game_count >= 2

    admin_page.select_all_checkbox().check()
    page.wait_for_timeout(200)

    checked = page.locator("input.game-checkbox:checked:not(#select-all)")
    assert checked.count() == game_count

    admin_page.select_all_checkbox().uncheck()
    page.wait_for_timeout(200)

    checked = page.locator("input.game-checkbox:checked:not(#select-all)")
    assert checked.count() == 0


def test_delete_button_disabled_when_none_checked(page, app_url, admin_token, admin_page):
    _create_game(app_url, admin_token)

    admin_page.goto()
    assert admin_page.delete_selected_button().is_disabled()


def test_delete_single_game(page, app_url, admin_token, admin_page):
    game = _create_game(app_url, admin_token)
    game_id = game["id"]

    admin_page.goto()
    assert admin_page.game_checkbox(game_id).is_visible()

    admin_page.game_checkbox(game_id).check()

    assert admin_page.selected_count().text_content() == "1"
    assert not admin_page.delete_selected_button().is_disabled()

    admin_page.delete_selected_games(accept=True)

    admin_page.goto()
    assert admin_page.game_checkbox(game_id).is_hidden()


def test_delete_multiple_games(page, app_url, admin_token, admin_page):
    game1 = _create_game(app_url, admin_token)
    game2 = _create_game(app_url, admin_token)
    game_id_1 = game1["id"]
    game_id_2 = game2["id"]

    admin_page.goto()
    admin_page.game_checkbox(game_id_1).check()
    admin_page.game_checkbox(game_id_2).check()

    assert admin_page.selected_count().text_content() == "2"

    admin_page.delete_selected_games(accept=True)

    admin_page.goto()
    assert admin_page.game_checkbox(game_id_1).is_hidden()
    assert admin_page.game_checkbox(game_id_2).is_hidden()


def test_delete_cancel_dialog(page, app_url, admin_token, admin_page):
    game = _create_game(app_url, admin_token)
    game_id = game["id"]

    admin_page.goto()
    admin_page.game_checkbox(game_id).check()

    admin_page.delete_selected_games(accept=False)

    assert admin_page.game_checkbox(game_id).is_visible()
