class AdminDashboardPage:
    def __init__(self, page, admin_token: str, app_url: str = "http://localhost:8000"):
        self.page = page
        self.admin_token = admin_token
        self.app_url = app_url
        self.url = f"{app_url}/admin/{admin_token}"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def game_checkbox(self, game_id: str):
        return self.page.locator(f'input.game-checkbox[value="{game_id}"]')

    def select_all_checkbox(self):
        return self.page.locator("#select-all")

    def delete_selected_button(self):
        return self.page.locator("#delete-selected-btn")

    def selected_count(self):
        return self.page.locator("#selected-count")

    def game_rows(self):
        return self.page.locator(".game-row")

    def games_list(self):
        return self.page.locator("#games-list")

    def toast(self):
        return self.page.locator("#toast")

    def create_game_name_input(self):
        return self.page.locator("#game-name")

    def create_game_button(self):
        return self.page.locator("button.btn-success", has_text="Create Game")

    def create_game(self, name: str = ""):
        if name:
            self.create_game_name_input().fill(name)
        self.create_game_button().click()
        self.page.wait_for_timeout(1000)

    def delete_selected_games(self, accept: bool = True):
        def handle_dialog(dialog):
            if accept:
                dialog.accept()
            else:
                dialog.dismiss()
        self.page.once("dialog", handle_dialog)
        self.delete_selected_button().click()
        self.page.wait_for_timeout(2000)

    def get_toast_text(self):
        t = self.toast()
        if t.is_hidden():
            return ""
        return t.text_content() or ""

    def wait_for_toast(self):
        self.toast().wait_for(state="visible", timeout=5000)
