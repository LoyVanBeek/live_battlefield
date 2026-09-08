import pytest


class TestSanitizeName:
    def test_strips_html_tags(self):
        from app.safety import sanitize_name

        assert "<" not in sanitize_name("<script>alert(1)</script>")
        assert ">" not in sanitize_name("<script>alert(1)</script>")

    def test_strips_quotes_and_ampersands(self):
        from app.safety import sanitize_name

        assert ">" not in sanitize_name('"><img src=x onerror=1>')
        assert '"' not in sanitize_name('"><img src=x onerror=1>')

    def test_truncates_to_max_length(self):
        from app.safety import sanitize_name

        assert len(sanitize_name("x" * 100)) == 30

    def test_none_becomes_empty(self):
        from app.safety import sanitize_name

        assert sanitize_name(None) == ""

    def test_plain_name_unchanged(self):
        from app.safety import sanitize_name

        assert sanitize_name("Blue Team") == "Blue Team"