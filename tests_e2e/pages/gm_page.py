class GameMasterPage:
    def __init__(self, page, gm_token: str, app_url: str = "http://localhost:8000"):
        self.page = page
        self.gm_token = gm_token
        self.app_url = app_url
        self.url = f"{app_url}/game-master/{gm_token}"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def join_color_select(self):
        return self.page.locator("#join-color")

    def join_name_input(self):
        return self.page.locator("#join-name")

    def join_button(self):
        return self.page.locator("button.btn-success", has_text="Join")

    def join_team(self, color: str, name: str):
        self.join_color_select().select_option(color)
        self.join_name_input().fill(name)
        self.join_button().click()
        self.page.wait_for_timeout(500)

    def team_card(self, color: str):
        return self.page.locator(f"#team-card-{color}")

    def team_card_name(self, color: str):
        return self.team_card(color).locator(".team-name-text")

    def start_button(self):
        return self.page.locator("#btn-start")

    def end_button(self):
        return self.page.locator("#btn-end")

    def new_game_button(self):
        return self.page.locator("#btn-new")

    def game_status_element(self):
        return self.page.locator("#game-status")

    def get_game_status(self):
        return self.game_status_element().text_content()

    def ai_color_select(self):
        return self.page.locator("#ai-color")

    def ai_name_input(self):
        return self.page.locator("#ai-name")

    def add_ai_button(self):
        return self.page.locator("button.btn-primary", has_text="Add AI")

    def add_ai(self, color: str, name: str | None = None):
        self.ai_color_select().select_option(color)
        if name:
            self.ai_name_input().fill(name)
        self.add_ai_button().click()
        self.page.wait_for_timeout(500)

    def ai_badge(self, color: str):
        return self.team_card(color).locator(".ai-badge")

    def start_game(self):
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.start_button().click()
        self.page.wait_for_timeout(2000)

    def end_game(self):
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.end_button().click()
        self.page.wait_for_timeout(2000)

    def teams_grid(self):
        return self.page.locator("#teams-grid")

    def location_progress(self):
        return self.page.locator("#location-progress")

    def nav_events_link(self):
        return self.page.locator("a[href*='/events']")

    def nav_locations_link(self):
        return self.page.locator("a[href*='/locations-secret']")
