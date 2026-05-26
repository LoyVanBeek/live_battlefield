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
