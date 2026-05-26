class EventsPage:
    def __init__(self, page, token: str, prefix: str = "game-master", app_url: str = "http://localhost:8000"):
        self.page = page
        self.token = token
        self.app_url = app_url
        self.url = f"{app_url}/{prefix}/{token}/events"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("load")

    def event_list(self):
        return self.page.locator("#event-list")

    def event_items(self):
        return self.event_list().locator(".event-item")

    def get_event_count(self):
        return self.event_items().count()

    def no_events_message(self):
        return self.event_list().locator(".empty-state")

    def boards_section(self):
        return self.page.locator("#boards-section")

    def board_images(self):
        return self.boards_section().locator("img")

    def select_event(self, index: int):
        items = self.event_items().all()
        if items and index < len(items):
            items[index].click()
            self.page.wait_for_timeout(500)

    def first_button(self):
        return self.page.locator("#btn-first")

    def prev_button(self):
        return self.page.locator("#btn-prev")

    def next_button(self):
        return self.page.locator("#btn-next")

    def last_button(self):
        return self.page.locator("#btn-last")

    def event_counter(self):
        return self.page.locator("#event-counter")
