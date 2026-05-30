class TeamPage:
    def __init__(self, page, team_url: str, app_url: str = "http://localhost:8000"):
        self.page = page
        self.team_url = team_url
        self.app_url = app_url
        self.url = f"{app_url}{team_url}" if team_url.startswith("/") else team_url

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

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
