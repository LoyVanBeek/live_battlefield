class LocationsPage:
    def __init__(self, page, token: str, prefix: str = "game-master", app_url: str = "http://localhost:8000"):
        self.page = page
        self.token = token
        self.app_url = app_url
        self.url = f"{app_url}/{prefix}/{token}/locations-secret"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def locations_table(self):
        return self.page.locator("#locations-body")

    def location_rows(self):
        return self.locations_table().locator("tr")

    def no_locations_message(self):
        return self.locations_table().locator("td", has_text="No locations found")

    def error_message(self):
        return self.locations_table().locator("td", has_text="Error loading locations")

    def get_location_count(self):
        if self.no_locations_message().count() > 0:
            return 0
        if self.error_message().count() > 0:
            return -1
        return self.location_rows().count()

    def lat_input(self):
        return self.page.locator("#loc-lat")

    def lon_input(self):
        return self.page.locator("#loc-lon")

    def count_input(self):
        return self.page.locator("#loc-count")

    def radius_input(self):
        return self.page.locator("#loc-radius")

    def add_button(self):
        return self.page.locator("button.btn-add", has_text="Add")

    def add_location(self, lat: float, lon: float, count: int = 1, radius: float = 0):
        self.lat_input().fill(str(lat))
        self.lon_input().fill(str(lon))
        self.count_input().fill(str(count))
        self.radius_input().fill(str(radius))
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.add_button().click()
        self.page.wait_for_timeout(1000)

    def map_element(self):
        return self.page.locator("#map")

    def back_link(self):
        return self.page.locator("#back-link")

    def code_cell(self, number: int):
        return self.page.locator(f"#cell-code-{number}")

    def bombs_cell(self, number: int):
        return self.page.locator(f"#cell-bombs-{number}")

    def coords_cell(self, number: int):
        return self.page.locator(f"#cell-coords-{number}")

    def map_hint(self):
        return self.page.locator("#map-hint")

    def marker_count(self):
        return self.page.locator(".leaflet-marker-icon").count()

    def edit_input(self):
        return self.page.locator("#cell-edit-input")

    def save_cell_button(self):
        return self.page.locator("button.btn-save-cell")

    def cancel_cell_button(self):
        return self.page.locator("button.btn-cancel-cell")

    def toast(self):
        return self.page.locator("#toast")

    def default_bombs_value(self):
        return self.page.locator("#default-bombs-value")

    def default_bombs_cell(self):
        return self.page.locator("#default-bombs-cell")

    def default_bombs_input(self):
        return self.page.locator("#default-bombs-input")

    def edit_default_bombs(self, value: str, expect="success"):
        """Click the header default, set a new value, and save."""
        before = self.toast().text_content() or ""
        self.default_bombs_cell().click()
        self.default_bombs_input().wait_for(state="visible")
        self.default_bombs_input().fill(value)
        self.save_cell_button().click()
        self.page.wait_for_function(
            """([before]) => {
                const toast = document.getElementById('toast');
                return toast && toast.textContent !== before;
            }""",
            arg=[before],
        )
        if expect == "success":
            self.page.wait_for_function(
                "() => !document.getElementById('default-bombs-input')"
            )
        self.page.wait_for_load_state("networkidle")

    def start_cell_edit(self, field: str, number: int):
        """Click a Code/Bombs/Coords cell to open the inline editor."""
        cell = self.code_cell(number) if field == "code" else (
            self.coords_cell(number) if field == "coords" else self.bombs_cell(number)
        )
        cell.click()
        self.edit_input().wait_for(state="visible")

    def save_cell_edit(self, expect="success"):
        before = self.toast().text_content() or ""
        self.save_cell_button().click()
        # networkidle is already latched by goto(), so wait on the actual
        # signal instead: the toast changes when the response is processed.
        self.page.wait_for_function(
            """([before]) => {
                const toast = document.getElementById('toast');
                return toast && toast.textContent !== before;
            }""",
            arg=[before],
        )
        if expect == "success":
            # success also re-renders the table, closing the inline editor
            self.page.wait_for_function(
                "() => !document.getElementById('cell-edit-input')"
            )
            self.page.wait_for_load_state("networkidle")

    def cancel_cell_edit(self):
        self.cancel_cell_button().click()

    def edit_cell(self, field: str, number: int, value: str, expect="success"):
        self.start_cell_edit(field, number)
        self.edit_input().fill(value)
        self.save_cell_edit(expect=expect)
