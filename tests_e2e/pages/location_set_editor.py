class LocationSetEditorPage:
    """Page Object for the full-page Location Set editor (/admin/<token>/location-sets)."""

    def __init__(self, page, admin_token: str, app_url: str = "http://localhost:8000"):
        self.page = page
        self.admin_token = admin_token
        self.app_url = app_url
        self.base_url = f"{app_url}/admin/{admin_token}/location-sets"

    def goto(self, set_id=None):
        url = self.base_url + (f"?id={set_id}" if set_id is not None else "")
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")

    def back_link(self):
        return self.page.locator("#back-link")

    def set_name_input(self):
        return self.page.locator("#set-name")

    def save_button(self):
        return self.page.locator("#set-save-btn")

    def delete_button(self):
        return self.page.locator("#set-delete-btn")

    def status_text(self):
        return self.page.locator("#set-status")

    def save(self):
        self.save_button().click()
        self.page.wait_for_timeout(600)

    def delete(self, accept: bool = True):
        def handle_dialog(dialog):
            if accept:
                dialog.accept()
            else:
                dialog.dismiss()

        self.page.once("dialog", handle_dialog)
        self.delete_button().click()
        self.page.wait_for_timeout(800)

    # --- Add form ---
    def lat_input(self):
        return self.page.locator("#loc-lat")

    def lon_input(self):
        return self.page.locator("#loc-lon")

    def my_location_button(self):
        return self.page.locator("#btn-my-location")

    def add_button(self):
        return self.page.locator(".location-form button", has_text="Add").first

    def add_location(self, lat: str, lon: str):
        self.lat_input().fill(lat)
        self.lon_input().fill(lon)
        self.add_button().click()
        self.page.wait_for_timeout(400)

    def map_element(self):
        return self.page.locator("#map")

    def map_hint(self):
        return self.page.locator("#map-hint")

    def pins(self):
        return self.page.locator(".location-pin")

    # --- Table ---
    def locations_table(self):
        return self.page.locator("#locations-body")

    def location_rows(self):
        return self.locations_table().locator("tr")

    def no_locations_message(self):
        return self.locations_table().locator("td", has_text="No locations found")

    def get_location_count(self):
        if self.no_locations_message().count() > 0:
            return 0
        return self.location_rows().count()

    def code_cell(self, number: int):
        return self.page.locator(f"#cell-code-{number}")

    def bombs_cell(self, number: int):
        return self.page.locator(f"#cell-bombs-{number}")

    def coords_cell(self, number: int):
        return self.page.locator(f"#cell-coords-{number}")

    def remove_button(self, number: int):
        return self.page.locator(f"#locations-body [data-remove='{number}']")

    def remove_location(self, number: int, accept: bool = True):
        def handle_dialog(dialog):
            if accept:
                dialog.accept()
            else:
                dialog.dismiss()

        self.page.once("dialog", handle_dialog)
        self.remove_button(number).click()
        self.page.wait_for_timeout(400)

    def toast(self):
        return self.page.locator("#toast")

    # --- Inline cell editing ---
    def edit_input(self):
        return self.page.locator("#cell-edit-input")

    def save_cell_button(self):
        return self.page.locator("button.btn-save-cell")

    def cancel_cell_button(self):
        return self.page.locator("button.btn-cancel-cell")

    def start_cell_edit(self, field: str, number: int):
        cell = {
            "code": self.code_cell(number),
            "bombs": self.bombs_cell(number),
            "coords": self.coords_cell(number),
        }[field]
        cell.click()
        self.edit_input().wait_for(state="visible")

    def save_cell_edit(self, expect="success"):
        before = self.toast().text_content() or ""
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
                "() => !document.getElementById('cell-edit-input')"
            )
            self.page.wait_for_load_state("networkidle")

    def edit_cell(self, field: str, number: int, value: str, expect="success"):
        self.start_cell_edit(field, number)
        self.edit_input().fill(value)
        self.save_cell_edit(expect=expect)

    # --- Per-location quiz modal ---
    def quiz_cell(self, number: int):
        return self.page.locator(f"#cell-quiz-{number}")

    def quiz_modal(self):
        return self.page.locator("#lq-modal")

    def open_quiz_modal(self, number: int):
        self.quiz_cell(number).click()
        self.quiz_modal().wait_for(state="visible")

    def quiz_mode_select(self):
        return self.page.locator("#lq-mode")

    def set_quiz_mode(self, mode: str):
        self.quiz_mode_select().select_option(mode)

    def add_quiz_question(self):
        self.page.locator("#lq-modal button", has_text="Add Question").click()
        self.page.wait_for_timeout(200)

    def set_quiz_question_text(self, qi: int, text: str):
        self.page.locator(
            f"#lq-questions-list input[data-role='question-text'][data-qi='{qi}']"
        ).fill(text)

    def set_quiz_answer_text(self, qi: int, ai: int, text: str):
        self.page.locator(
            f"#lq-questions-list input[data-role='answer-text'][data-qi='{qi}'][data-ai='{ai}']"
        ).fill(text)

    def set_quiz_answer_bombs(self, qi: int, ai: int, value: int):
        self.page.locator(
            f"#lq-questions-list input[data-role='answer-bombs'][data-qi='{qi}'][data-ai='{ai}']"
        ).fill(str(value))

    def save_quiz(self):
        self.page.locator("#lq-modal button", has_text="Save Quiz").click()
        self.page.wait_for_function(
            "() => document.getElementById('lq-modal').style.display === 'none'"
        )
