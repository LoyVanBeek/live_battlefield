import json


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
        # Scope to the games list: the shared ".game-row" class is also used by
        # the quiz/location libraries, whose cards must not count as games.
        return self.page.locator("#games-list .game-row")

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

    # --- Quiz Library ---
    def library_quiz_list(self):
        return self.page.locator("#library-quiz-list")

    def library_name_input(self):
        return self.page.locator("#library-quiz-name")

    def open_new_library_quiz(self, name: str):
        self.page.locator("#library-new-btn").click()
        self.page.wait_for_timeout(200)
        self.library_name_input().fill(name)

    def import_library_quiz(self, questions: list):
        """Import a questions array through the editor's file input (in-memory file)."""
        self.page.set_input_files(
            "#library-quiz-import-input",
            {
                "name": "quiz.json",
                "mimeType": "application/json",
                "buffer": json.dumps(questions).encode(),
            },
        )
        self.page.wait_for_timeout(600)

    def library_question_inputs(self):
        return self.page.locator('#library-quiz-questions-list input[data-role="question-text"]')

    def library_answer_inputs(self):
        return self.page.locator('#library-quiz-questions-list input[data-role="answer-text"]')

    def library_answer_texts(self):
        return self.library_answer_inputs().evaluate_all("els => els.map(e => e.value)")

    def library_answer_widths(self):
        return self.library_answer_inputs().evaluate_all(
            "els => els.map(e => e.getBoundingClientRect().width)"
        )

    def add_library_question(self, question_text: str, answers: list, source_url: str = ""):
        """Add a question to the library editor. Each answer: {"text", "correct"}."""
        self.page.locator("#library-editor button", has_text="Add Question").click()
        self.page.wait_for_timeout(200)
        blocks = self.page.locator("#library-quiz-questions-list > div")
        q = blocks.nth(blocks.count() - 1)
        q.locator("input[data-role='question-text']").fill(question_text)
        if source_url:
            q.locator("input[data-role='source-url']").fill(source_url)
        for i, a in enumerate(answers):
            if i > 0:
                q.locator("button", has_text="Add Answer").click()
                self.page.wait_for_timeout(150)
            q.locator("input[data-role='answer-text']").nth(i).fill(a["text"])
            if a.get("correct"):
                q.locator("input[data-role='correct']").nth(i).check()

    def set_library_total(self, value: int):
        self.page.locator("#library-quiz-total").fill(str(value))

    def rebalance_library(self):
        self.page.locator("#library-editor button", has_text="Rebalance").click()
        self.page.wait_for_timeout(200)

    def save_library_quiz(self):
        self.page.locator("#library-editor button", has_text="Save Quiz").click()
        self.page.wait_for_timeout(800)

    def library_card(self, name: str):
        """The quiz card in the admin library list whose name contains `name`."""
        return self.page.locator("#library-quiz-list .game-row", has_text=name)

    def edit_library_quiz(self, name: str):
        """Open the library editor for the quiz card named `name`."""
        self.library_card(name).locator("button", has_text="✏️ Edit").click()
        self.page.wait_for_timeout(500)

    def delete_library_quiz(self, name: str, accept: bool = True):
        """Delete the quiz card named `name`, answering the confirm dialog."""
        def handle_dialog(dialog):
            if accept:
                dialog.accept()
            else:
                dialog.dismiss()
        self.page.once("dialog", handle_dialog)
        self.library_card(name).locator("button", has_text="🗑️ Delete").click()
        self.page.wait_for_timeout(800)

    # --- Location Set editor ---
    def new_set_button(self):
        return self.page.locator("#location-sets-new-btn")

    def set_name_input(self):
        return self.page.locator("#location-set-name")

    def set_location_rows(self):
        return self.page.locator("#location-set-rows .set-location-row")

    def set_row_field(self, i: int, role: str):
        return self.page.locator(f"#location-set-rows [data-role='{role}'][data-i='{i}']")

    def add_set_location(self):
        self.page.locator("#location-set-editor button", has_text="Add Location").click()
        self.page.wait_for_timeout(150)

    def save_set(self):
        self.page.locator("#location-set-editor button", has_text="Save Set").click()
        self.page.wait_for_timeout(800)

    def open_set_quiz(self, i: int):
        self.page.locator("#location-set-rows button", has_text="Quiz").nth(i).click()
        self.page.locator("#set-quiz-modal").wait_for(state="visible")

    def set_quiz_add_question(self):
        self.page.locator("#set-quiz-modal button", has_text="Add Question").click()
        self.page.wait_for_timeout(200)

    def set_quiz_question_text_input(self, qi: int):
        return self.page.locator(
            f"#set-quiz-questions-list input[data-role='question-text'][data-qi='{qi}']"
        )

    def set_quiz_answer_text(self, qi: int, ai: int, text: str):
        self.page.locator(
            f"#set-quiz-questions-list input[data-role='answer-text'][data-qi='{qi}'][data-ai='{ai}']"
        ).fill(text)

    def set_quiz_answer_bombs(self, qi: int, ai: int, value: int):
        self.page.locator(
            f"#set-quiz-questions-list input[data-role='answer-bombs'][data-qi='{qi}'][data-ai='{ai}']"
        ).fill(str(value))

    def set_quiz_apply(self):
        self.page.locator("#set-quiz-modal button", has_text="Apply Quiz").click()
        self.page.wait_for_function(
            "() => document.getElementById('set-quiz-modal').style.display === 'none'"
        )

    def set_card(self, name: str):
        """The set card in the admin list whose name contains `name`."""
        return self.page.locator("#location-sets-list .library-row", has_text=name)

    def edit_set(self, name: str):
        self.set_card(name).locator("button", has_text="✏️ Edit").click()
        self.page.wait_for_timeout(500)

    def delete_set(self, name: str, accept: bool = True):
        def handle_dialog(dialog):
            if accept:
                dialog.accept()
            else:
                dialog.dismiss()
        self.page.once("dialog", handle_dialog)
        self.set_card(name).locator("button", has_text="🗑️ Delete").click()
        self.page.wait_for_timeout(800)
