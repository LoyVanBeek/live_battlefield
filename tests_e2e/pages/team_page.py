class TeamPage:
    def __init__(self, page, team_url: str, app_url: str = "http://localhost:8000"):
        self.page = page
        self.team_url = team_url
        self.app_url = app_url
        self.url = f"{app_url}{team_url}" if team_url.startswith("/") else team_url

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("load")

    def map_link(self):
        """Header 🗺️ button linking to the Quest Locations Map."""
        return self.page.locator('.team-actions a[href*="/map?game_id="]')

    def redeem_map_link(self):
        """Map link inside the Redeem Code form (rendered once the game started)."""
        return self.page.locator('#actions a[href*="/map?game_id="]')

    def board_cells(self):
        return self.page.locator("table.board-table td.cell")

    def board_cell(self, row: int, col: int):
        return self.page.locator(f"table.board-table tr:nth-child({row + 2}) td:nth-child({col + 2})")

    def auto_place_button(self):
        return self.page.locator("button", has_text="Place All Ships")

    def auto_place_ships(self):
        self.auto_place_button().click()
        self.page.wait_for_timeout(1000)

    def team_color_display(self):
        return self.page.locator(".team-color-dot")

    def ships_placed_text(self):
        return self.page.locator("#ship-count")

    def location_bomb_buttons(self):
        return self.page.locator("button", has_text="Bomb")

    def bomb_location(self, index: int = 0):
        buttons = self.location_bomb_buttons().all()
        if buttons:
            buttons[index].click()
            self.page.wait_for_timeout(1000)

    def attack_cells(self):
        return self.page.locator("td.cell.attackable")

    def attack_cell(self, row: int, col: int):
        cell = self.page.locator(
            f"table.board-table tr:nth-child({row + 2}) td:nth-child({col + 2}).attackable"
        )
        if cell.count() > 0:
            cell.click()
            self.page.wait_for_timeout(500)

    def public_board(self, color: str):
        return self.page.locator(f"#public-board-{color}")

    def public_board_cell(self, color: str, row: int, col: int):
        return self.public_board(color).locator(
            f".board-cell[data-row='{row}'][data-col='{col}']"
        )

    def bomb_cell_on_board(self, color: str, row: int, col: int):
        self.public_board_cell(color, row, col).click()
        self.page.locator("#bomb-confirm.active").wait_for(timeout=5000)
        self.page.locator("#bomb-confirm .btn-primary").click()
        self.page.wait_for_timeout(1500)

    def bomb_count(self):
        return self.page.locator("#bomb-count")

    def get_bomb_count(self):
        return int(self.bomb_count().text_content())

    def quiz_content(self):
        return self.page.locator("#quiz-content")

    def get_quiz_text(self):
        return self.quiz_content().text_content()

    def answer_quiz(self, answer_index: int):
        """Click the nth answer button in the quiz section."""
        buttons = self.quiz_content().locator("button")
        buttons.nth(answer_index).click()
        self.page.wait_for_timeout(500)

    def quiz_verdict(self):
        return self.page.locator("#quiz-verdict")

    def quiz_correct_answer(self):
        return self.page.locator("#quiz-correct-answer")

    def quiz_source_link(self):
        return self.page.locator("#quiz-source-link")

    def quiz_next_button(self):
        return self.page.locator("#quiz-next")

    def next_quiz_question(self):
        self.quiz_next_button().click()
        self.page.wait_for_timeout(500)

    def is_quiz_done(self):
        return self.quiz_content().text_content().lower().includes("answered")

    # --- Location quiz ---

    def location_quiz_section(self):
        return self.page.locator("#location-quiz-section")

    def location_quiz_content(self):
        return self.page.locator("#location-quiz-content")

    def location_quiz_select(self):
        return self.page.locator("#location-quiz-select")

    def select_location_quiz(self, value: str):
        self.location_quiz_select().select_option(value)
        self.page.wait_for_timeout(300)

    def location_quiz_answer_buttons(self):
        return self.location_quiz_content().locator("button.btn-primary")

    def answer_location_quiz(self, answer_index: int = 0):
        self.location_quiz_answer_buttons().nth(answer_index).click()
        self.page.wait_for_timeout(500)

    def location_quiz_verdict(self):
        return self.page.locator("#location-quiz-verdict")

    def location_quiz_correct_answer(self):
        return self.page.locator("#location-quiz-correct-answer")

    def location_quiz_source_link(self):
        return self.page.locator("#location-quiz-source-link")

    def location_quiz_next_button(self):
        return self.page.locator("#location-quiz-next")

    def next_location_quiz_question(self):
        self.location_quiz_next_button().click()
        self.page.wait_for_timeout(500)

    # --- Ship Editor ---

    def private_board_cell(self, row: int, col: int):
        return self.page.locator("#private-board .board-cell").nth(row * 10 + col + 12)

    def ship_inventory(self):
        return self.page.locator(".ship-inv-item")

    def ship_inventory_count(self):
        return self.ship_inventory().count()

    def select_ship_in_inventory(self, index: int = 0):
        self.ship_inventory().nth(index).click()
        self.page.wait_for_timeout(300)

    def place_ship_on_board(self, row: int, col: int):
        self.private_board_cell(row, col).click()
        self.page.wait_for_timeout(500)

    def clear_all_ships_btn(self):
        return self.page.locator("button", has_text="Clear All")

    def clear_all_ships(self):
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.clear_all_ships_btn().click()
        self.page.wait_for_timeout(1000)

    def rotate_btn(self):
        return self.page.locator("#ship-hint a", has_text="horizontal").or_(
            self.page.locator("#ship-hint a", has_text="vertical")
        )

    def click_rotate(self):
        self.rotate_btn().click()
        self.page.wait_for_timeout(300)

    def get_ship_hint_text(self):
        return self.page.locator("#ship-hint").text_content()

    def get_ship_placed_count(self):
        text = self.page.locator("#ship-count").text_content()
        return int(text) if text and text != "-" else 0

    # --- Game-state indicators ---

    def self_eliminated_badge(self):
        """Header badge shown when this team has lost all its ships."""
        return self.page.locator("#eliminated-badge")

    def private_board(self):
        return self.page.locator("#private-board")

    def public_board_item(self, color: str):
        return self.page.locator(f"#public-board-item-{color}")

    def public_board_eliminated_badge(self, color: str):
        return self.public_board_item(color).locator(".eliminated-badge")

    def target_team_option(self, color: str):
        return self.page.locator(f"#target-team option[value='{color}']")
