class JoinPage:
    def __init__(self, page, invite_token: str, app_url: str = "http://localhost:8000"):
        self.page = page
        self.invite_token = invite_token
        self.app_url = app_url
        self.url = f"{app_url}/join/{invite_token}"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("load")

    def color_select(self):
        return self.page.locator("#team-color")

    def name_input(self):
        return self.page.locator("#team-name")

    def join_button(self):
        return self.page.locator("#btn-join")

    def message_element(self):
        return self.page.locator("#message")

    def get_message_text(self):
        return self.message_element().text_content()

    def join_game(self, color: str, name: str = ""):
        self.color_select().select_option(color)
        if name:
            self.name_input().fill(name)
        self.join_button().click()
        self.page.wait_for_timeout(1000)

    def game_name_element(self):
        return self.page.locator("#game-name")

    def game_status_element(self):
        return self.page.locator("#game-status")
