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
        """Add a question with answers. Each answer: {"text": ..., "bombs": ..., "correct": bool}"""
        self.add_question_button().click()
        self.page.wait_for_timeout(300)

        # The last question block is the one we just added
        question_blocks = self.page.locator("#quiz-questions-list > div")
        q_count = question_blocks.count()
        q_block = question_blocks.nth(q_count - 1)

        # Fill question text
        text_inputs = q_block.locator("input[type='text']")
        text_inputs.first.fill(question_text)

        # First answer is auto-created, update it
        answer_radios = q_block.locator("input[type='radio']")
        bomb_inputs = q_block.locator("input[type='number']")

        for i, a in enumerate(answers):
            if i > 0:
                q_block.locator("button", has_text="Add Answer").click()
                self.page.wait_for_timeout(200)

            # Re-query after adding new answer
            text_inputs = q_block.locator("input[type='text']")
            answer_radios = q_block.locator("input[type='radio']")
            bomb_inputs = q_block.locator("input[type='number']")

            text_inputs.nth(i).fill(a["text"])
            bomb_inputs.nth(i).fill(str(a["bombs"]))
            if a["correct"]:
                answer_radios.nth(i).check()

    def save_quiz(self):
        self.save_quiz_button().click()
        self.page.wait_for_timeout(1000)