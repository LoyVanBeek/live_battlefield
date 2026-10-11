class GameSettingsPage:
    def __init__(self, page, gm_token: str, app_url: str = "http://localhost:8000"):
        self.page = page
        self.gm_token = gm_token
        self.app_url = app_url
        self.url = f"{app_url}/game-master/{gm_token}/game-settings"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def quiz_enabled_checkbox(self):
        return self.page.locator("#quiz-enabled")

    def quiz_total_input(self):
        return self.page.locator("#quiz-total")

    def add_question_button(self):
        return self.page.locator("button", has_text="Add Question")

    def save_quiz_button(self):
        return self.page.locator("button", has_text="Save Quiz Settings")

    def enable_quiz(self, total_bombs: int = 50):
        self.quiz_enabled_checkbox().check()
        self.page.wait_for_timeout(300)
        self.quiz_total_input().fill(str(total_bombs))

    def add_question(self, question_text: str, answers: list):
        """Add a question with answers. Each answer: {"text": ..., "correct": bool}."""
        self.add_question_button().click()
        self.page.wait_for_timeout(300)

        question_blocks = self.page.locator("#quiz-questions-list > div")
        q_count = question_blocks.count()
        q_block = question_blocks.nth(q_count - 1)

        text_inputs = q_block.locator("input[type='text']")
        if text_inputs.count() > 0:
            text_inputs.first.fill(question_text)

        answer_radios = q_block.locator("input[type='radio']")

        for i, a in enumerate(answers):
            if i > 0:
                q_block.locator("button", has_text="Add Answer").click()
                self.page.wait_for_timeout(200)

            text_inputs = q_block.locator("input[type='text']")
            answer_radios = q_block.locator("input[type='radio']")
            # answer text is after question text at index i+1 in current structure? keep simple
            text_inputs.nth(i+1 if text_inputs.count() > i+1 else i).fill(a["text"]) if False else None
            # safer: fill answer text inputs in order (skip first = question)
            all_text = q_block.locator("input[type='text']")
            if all_text.count() > 1 + i:
                all_text.nth(1 + i).fill(a["text"])
            elif all_text.count() > i:
                all_text.nth(i).fill(a["text"])

            if a.get("correct"):
                answer_radios.nth(i).check()

    def rebalance_bombs(self):
        self.page.get_by_role("button", name="Rebalance").click()
        self.page.wait_for_timeout(200)

    def set_answer_bombs(self, qi: int, ai: int, value: int):
        """Edit the bomb value of answer ai of question qi."""
        locator = self.page.locator(f"#ans-bombs-{qi}-{ai}")
        locator.fill(str(value))
        # Numeric inputs fire `change` on blur/Enter; the handler re-renders the list.
        locator.press("Enter")
        self.page.wait_for_timeout(200)

    def import_quiz(self, file_path: str):
        """Import a quiz JSON file like a human via the file input."""
        self.page.locator("#quiz-import-input").set_input_files(file_path)
        self.page.wait_for_timeout(500)

    def library_select(self):
        return self.page.locator("#quiz-library-select")

    def load_library_quiz(self, name: str):
        """Pick a saved library quiz by name and click Load."""
        self.page.wait_for_function(
            "() => document.getElementById('quiz-library-select').options.length > 1",
            timeout=5000,
        )
        value = self.page.evaluate(
            """(name) => {
                const sel = document.getElementById('quiz-library-select');
                const opt = Array.from(sel.options).find(o => o.textContent.includes(name));
                return opt ? opt.value : '';
            }""",
            name,
        )
        assert value, f"library quiz {name!r} not offered in the settings dropdown"
        self.library_select().select_option(value)
        self.page.get_by_role("button", name="Load").click()
        self.page.wait_for_timeout(500)

    def save_as_library_quiz(self, name: str):
        """Save the current editor contents to the library under `name`."""
        self.page.once("dialog", lambda d: d.accept(name))
        self.page.locator("#quiz-questions-area button", has_text="Save as").click()
        self.page.wait_for_timeout(800)

    def question_blocks(self):
        return self.page.locator("#quiz-questions-list > div")

    def save_quiz(self):
        self.save_quiz_button().click()
        self.page.wait_for_timeout(1000)

    def quiz_warning_banner(self):
        return self.page.locator("#quiz-warning-banner")