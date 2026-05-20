import json
import os


_translations: dict[str, dict] = {}
SUPPORTED_LANGS = {"en", "nl"}


def _load(lang: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), f"{lang}.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_translations(lang: str) -> dict:
    if lang not in _translations:
        _translations[lang] = _load(lang)
    if not _translations[lang] and lang != "en":
        return get_translations("en")
    return _translations[lang]


def detect_language(accept_language: str) -> str:
    for part in accept_language.split(","):
        code = part.split(";")[0].strip().split("-")[0].lower()
        if code in SUPPORTED_LANGS:
            return code
    return "en"
